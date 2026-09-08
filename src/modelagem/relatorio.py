"""Relatório e gráficos do treino de modelos (RF-05/RF-06) — as "entregas"
que a disciplina pede explicitamente: matriz de comparação de modelos,
curvas ROC, matrizes de confusão, feature importance, relatório de texto.

Mantido separado de `treino.py` (que só faz a matemática) pelo mesmo motivo
que `src/analise/relatorios.py` está separado de `src/analise/analise.py`:
uma coisa é calcular, outra é apresentar.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance
from sklearn.metrics import confusion_matrix, roc_curve

from src.modelagem.treino import ModeloTreinado

matplotlib.use("Agg")  # sem display interativo — roda de script/pipeline, não notebook


def matriz_comparacao_modelos(metricas_por_modelo: dict[str, dict], tempos: dict[str, float]) -> pd.DataFrame:
    """Tabela Modelo | Accuracy | Precision | Recall | F1 | AUC-ROC | Tempo(s)
    — entrega #4 pedida pela disciplina ("matriz de comparação de modelos")."""
    linhas = []
    for nome, metricas in metricas_por_modelo.items():
        linhas.append({
            "Modelo": nome,
            "Accuracy": round(metricas["accuracy"], 4),
            "Precision": round(metricas["precision"], 4),
            "Recall": round(metricas["recall"], 4),
            "F1": round(metricas["f1"], 4),
            "AUC-ROC": round(metricas["auc_roc"], 4),
            "Tempo treino (s)": round(tempos.get(nome, 0.0), 2),
        })
    return pd.DataFrame(linhas).sort_values("AUC-ROC", ascending=False).reset_index(drop=True)


def gerar_graficos(
    modelos: dict[str, ModeloTreinado],
    x_teste: pd.DataFrame,
    y_teste: pd.Series,
    caminho_dir: Path,
) -> None:
    """Salva PNGs: curvas ROC (todos os modelos sobrepostos), matriz de
    confusão por modelo, feature importance nativa de RF/HGB e coeficientes
    da Regressão Logística — entrega #5 da disciplina.
    """
    caminho_dir.mkdir(parents=True, exist_ok=True)

    # --- Curvas ROC ---
    fig, ax = plt.subplots(figsize=(7, 6))
    for nome, info in modelos.items():
        x_proc = info.transformar(x_teste)
        y_proba = info.modelo.predict_proba(x_proc)[:, 1]
        fpr, tpr, _ = roc_curve(y_teste, y_proba)
        auc = np.trapezoid(tpr, fpr)
        ax.plot(fpr, tpr, label=f"{nome} (AUC={auc:.3f})", linewidth=2)
    ax.plot([0, 1], [0, 1], "k--", alpha=0.4)
    ax.set_xlabel("Taxa de falsos positivos")
    ax.set_ylabel("Taxa de verdadeiros positivos")
    ax.set_title("Curvas ROC — teste (2025)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(caminho_dir / "curvas_roc.png", dpi=150)
    plt.close(fig)

    # --- Matrizes de confusão ---
    fig, eixos = plt.subplots(1, len(modelos), figsize=(5 * len(modelos), 4.5))
    if len(modelos) == 1:
        eixos = [eixos]
    for ax, (nome, info) in zip(eixos, modelos.items()):
        x_proc = info.transformar(x_teste)
        y_pred = info.modelo.predict(x_proc)
        cm = confusion_matrix(y_teste, y_pred)
        ax.imshow(cm, cmap="Blues")
        for i in range(2):
            for j in range(2):
                ax.text(j, i, str(cm[i, j]), ha="center", va="center", fontsize=13)
        ax.set_xticks([0, 1], ["Formal", "Informal"])
        ax.set_yticks([0, 1], ["Formal", "Informal"])
        ax.set_xlabel("Predito")
        ax.set_ylabel("Real")
        ax.set_title(nome)
    fig.tight_layout()
    fig.savefig(caminho_dir / "matrizes_confusao.png", dpi=150)
    plt.close(fig)

    # --- Feature importance / coeficientes ---
    fig, eixos = plt.subplots(1, len(modelos), figsize=(6 * len(modelos), 6))
    if len(modelos) == 1:
        eixos = [eixos]
    for ax, (nome, info) in zip(eixos, modelos.items()):
        if nome == "LogisticRegression":
            nomes_feat = info.preprocessador.get_feature_names_out()
            valores = np.abs(info.modelo.coef_[0])
            titulo = "Regressão Logística — |coeficiente|"
        elif nome == "RandomForest":
            nomes_feat = info.preprocessador.get_feature_names_out()
            valores = info.modelo.feature_importances_
            titulo = "Random Forest — importância"
        else:
            # HistGradientBoostingClassifier não expõe feature_importances_ nativa
            # (isso é específico de bagging/árvores como RF) — usa permutation
            # importance numa subamostra do teste, custo controlado mesmo em 2,5M linhas.
            x_cat = info.transformar(x_teste)
            amostra_idx = x_cat.sample(n=min(3000, len(x_cat)), random_state=42).index
            resultado_perm = permutation_importance(
                info.modelo, x_cat.loc[amostra_idx], y_teste.loc[amostra_idx],
                n_repeats=5, random_state=42, scoring="roc_auc", n_jobs=-1,
            )
            nomes_feat = list(x_cat.columns)
            valores = resultado_perm.importances_mean
            titulo = "HistGradientBoosting — permutation importance"
        indices = np.argsort(valores)[::-1][:15]
        ax.barh(range(len(indices)), valores[indices][::-1])
        ax.set_yticks(range(len(indices)), [nomes_feat[i] for i in indices][::-1], fontsize=8)
        ax.set_title(titulo)
    fig.tight_layout()
    fig.savefig(caminho_dir / "feature_importance.png", dpi=150)
    plt.close(fig)


def gerar_relatorio_txt(
    metricas_treino: dict[str, dict],
    metricas_teste: dict[str, dict],
    matriz_comparacao: pd.DataFrame,
    confusao_por_grupo: dict[str, list[dict]],
    shap_importancia: dict[str, list[dict]],
    shap_por_grupo: dict[str, dict[str, list[dict]]],
    caminho_arquivo: Path,
) -> str:
    """Relatório de avaliação em texto — entrega #3 da disciplina (métricas,
    comparação, justificativa) + checagem de overfitting (treino vs. teste)
    + equidade por grupo (RNF-11)."""
    linhas = []
    linhas.append("=" * 78)
    linhas.append("RELATÓRIO DE MODELAGEM — INFORMALIDADE (RF-05/RF-06)")
    linhas.append("=" * 78)
    linhas.append(f"Gerado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    linhas.append("")
    linhas.append("MATRIZ DE COMPARAÇÃO DE MODELOS (teste, 2025):")
    linhas.append(matriz_comparacao.to_string(index=False))
    linhas.append("")

    melhor = matriz_comparacao.iloc[0]["Modelo"]
    linhas.append(f"Melhor modelo por AUC-ROC: {melhor}")
    linhas.append("")

    linhas.append("-" * 78)
    linhas.append("CHECAGEM DE OVERFITTING (accuracy/AUC treino vs. teste — gap grande é sinal de overfit):")
    linhas.append("-" * 78)
    for nome in metricas_teste:
        tr, te = metricas_treino[nome], metricas_teste[nome]
        linhas.append(
            f"{nome}: accuracy treino={tr['accuracy']:.4f} vs. teste={te['accuracy']:.4f} "
            f"(gap={tr['accuracy']-te['accuracy']:+.4f}) | "
            f"AUC treino={tr['auc_roc']:.4f} vs. teste={te['auc_roc']:.4f} "
            f"(gap={tr['auc_roc']-te['auc_roc']:+.4f})"
        )
    linhas.append("")

    linhas.append("-" * 78)
    linhas.append("EQUIDADE — matriz de confusão por sexo (V2007) e raça/cor (V2010), RNF-11:")
    linhas.append("-" * 78)
    for nome, linhas_grupo in confusao_por_grupo.items():
        linhas.append(f"\n{nome}:")
        for r in linhas_grupo:
            recall_txt = f"{r['recall']:.3f}" if r["recall"] is not None else "—"
            fpr_txt = f"{r['fpr']:.3f}" if r["fpr"] is not None else "—"
            linhas.append(
                f"  {r['grupo']}={r['valor']} (n={r['n']}): recall={recall_txt} | "
                f"taxa falso-positivo={fpr_txt} | TP={r['tp']} FP={r['fp']} FN={r['fn']} TN={r['tn']}"
            )
    linhas.append("")

    linhas.append("-" * 78)
    linhas.append("SHAP — importância global (RF-06):")
    linhas.append("-" * 78)
    for nome, ranking in shap_importancia.items():
        linhas.append(f"\n{nome} (top features por |SHAP| médio):")
        for r in ranking[:10]:
            linhas.append(f"  {r['feature']}: {r['shap_medio_abs']:.4f}")

    linhas.append("")
    linhas.append("-" * 78)
    linhas.append("SHAP — recortado por sexo e raça/cor (RNF-11):")
    linhas.append("-" * 78)
    for nome_modelo, por_grupo in shap_por_grupo.items():
        linhas.append(f"\n{nome_modelo}:")
        for valor_grupo, ranking in por_grupo.items():
            top3 = ", ".join(f"{r['feature']}={r['shap_medio_abs']:.3f}" for r in ranking[:3])
            linhas.append(f"  grupo={valor_grupo}: {top3}")

    linhas.append("")
    linhas.append("=" * 78)

    conteudo = "\n".join(linhas)
    caminho_arquivo.parent.mkdir(parents=True, exist_ok=True)
    caminho_arquivo.write_text(conteudo, encoding="utf-8")
    return conteudo
