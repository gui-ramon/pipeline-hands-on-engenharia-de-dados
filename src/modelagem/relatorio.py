"""Relatório e gráficos do treino de modelos (RF-05/RF-06).

Três camadas de saída, todas a partir dos mesmos números que `treino.py`
produz — nenhuma matemática de treino aqui:

1. **Entregas da disciplina** (`gerar_graficos` + `gerar_relatorio_txt`):
   matriz de comparação, ROC/confusão/feature importance em PNG, relatório
   `.txt`. Mantidas como estavam.
2. **Boletim de apresentação** (`gerar_boletim_html`):
   `dashboard/modelagem_informalidade.html`, mesma linguagem visual do
   boletim de EDA (`src/relatorio_visual.py`), com takeaway no topo de cada
   seção, micro-legendas e Model Card de equidade.
3. **Diagnóstico** (`gerar_diagnostico`): JSON + resumo `.txt` com flags
   automáticas, config da rodada e comparação com a rodada anterior — para
   retomar/ajustar o modelo depois.

Mantido separado de `treino.py` pelo mesmo motivo que
`src/analise/relatorios.py` está separado de `src/analise/analise.py`.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance
from sklearn.metrics import confusion_matrix, roc_curve

from src.modelagem.treino import ModeloTreinado
from src.relatorio_visual import cards, glossario, montar_pagina, secao, selo, takeaway

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


# =====================================================================
# Boletim de apresentação (dashboard/modelagem_informalidade.html) e
# diagnóstico (JSON + resumo .txt). Tudo derivado dos números que
# `treino.py`/`modelagem.py` já produzem — nenhuma matemática de treino.
# =====================================================================

LABELS_FEATURES = {
    "V4018": "Tamanho do negócio", "V4025": "É temporário?", "VD4010": "Setor de atividade",
    "VD4011": "Grupamento ocupacional", "VD3004": "Nível de instrução", "V1022": "Urbano/rural",
    "UF": "UF (estado)", "V4040": "Tempo no emprego", "V1023": "Tipo de área", "V2010": "Cor/raça",
    "VD2002": "Posição no domicílio", "V2007": "Sexo", "VD4031": "Horas semanais",
    "V2009": "Idade", "VD2003": "Pessoas no domicílio",
}
NOME_MODELO = {
    "LogisticRegression": "Regressão Logística",
    "RandomForest": "Random Forest",
    "HistGradientBoosting": "HistGradientBoosting",
}
# Da mais simples/explicável para a mais complexa — usado pra flag de "ganho marginal".
ORDEM_SIMPLICIDADE = ["LogisticRegression", "RandomForest", "HistGradientBoosting"]
GRUPO_LABEL = {
    "V2007": {1: "Homens", 2: "Mulheres"},
    "V2010": {1: "Brancos", 2: "Pretos", 3: "Amarelos", 4: "Pardos", 5: "Indígenas", 9: "Ignorado"},
}
N_MIN_GRUPO_EQUIDADE = 30  # abaixo disso a métrica do subgrupo é instável demais pra levantar flag


def _feat_base(nome: str) -> str:
    """'cat__V4018_1.0' / 'num__VD4031' / 'V4025' -> nome da feature base."""
    nome = re.sub(r"^(?:cat|num)__", "", nome)
    return re.sub(r"_-?\d+(?:\.\d+)?$", "", nome)


def _feat_label(nome: str) -> str:
    base = _feat_base(nome)
    return LABELS_FEATURES.get(base, base)


def _fmt_tempo(s: float) -> str:
    """Tempo de treino legível: '0,3s' abaixo de 10s, 's' inteiros acima,
    'min' quando passa de 90s (relevante na base cheia)."""
    if s < 10:
        return f"{s:.1f}s".replace(".", ",")
    if s < 90:
        return f"{s:.0f}s"
    return f"{s / 60:.1f} min".replace(".", ",")


def _nome_grupo(coluna: str, valor) -> str:
    try:
        return GRUPO_LABEL.get(coluna, {}).get(int(valor), f"{coluna}={valor}")
    except (TypeError, ValueError):
        return f"{coluna}={valor}"


def _agg_importancia(pares: list[tuple[str, float]]) -> dict[str, float]:
    """Soma |valor| por feature base (colapsa o one-hot: cat__V4018_1.0 +
    cat__V4018_4.0 -> V4018) e ordena decrescente."""
    out: dict[str, float] = {}
    for nome, valor in pares:
        out[_feat_base(nome)] = out.get(_feat_base(nome), 0.0) + abs(float(valor))
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def _downsample(xs, ys, n: int = 140):
    if len(xs) <= n:
        return [round(float(v), 4) for v in xs], [round(float(v), 4) for v in ys]
    idx = np.linspace(0, len(xs) - 1, n).round().astype(int)
    return [round(float(xs[i]), 4) for i in idx], [round(float(ys[i]), 4) for i in idx]


def _varrer_threshold(proba: np.ndarray, y: np.ndarray) -> list[dict]:
    """precision/recall/F1 + matriz de confusão para uma grade de limiares
    — base do slider interativo (dado pequeno, embutido no HTML)."""
    y = np.asarray(y)
    linhas = []
    for t in np.round(np.arange(0.05, 0.96, 0.02), 2):
        pred = (proba >= t).astype(int)
        tp = int(((pred == 1) & (y == 1)).sum())
        fp = int(((pred == 1) & (y == 0)).sum())
        fn = int(((pred == 0) & (y == 1)).sum())
        tn = int(((pred == 0) & (y == 0)).sum())
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        linhas.append({
            "t": float(t), "precision": round(prec, 4), "recall": round(rec, 4),
            "f1": round(f1, 4), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        })
    return linhas


def preparar_dados_boletim(
    modelos: dict[str, ModeloTreinado],
    x_teste: pd.DataFrame,
    y_teste: pd.Series,
    shap_importancia: dict[str, list[dict]],
) -> dict:
    """Calcula, uma vez só, tudo que o boletim e o diagnóstico precisam e
    que não vem pronto de `treino.py`: pontos da curva ROC, matriz de
    confusão geral, taxa de positivos prevista, varredura de threshold e
    importância agregada por feature (SHAP para RF/HGB, |coeficiente| para
    a Regressão Logística). Só `predict`/`predict_proba` no teste.
    """
    y = np.asarray(y_teste).astype(int)
    por_modelo: dict[str, dict] = {}
    for nome, info in modelos.items():
        xp = info.transformar(x_teste)
        proba = info.modelo.predict_proba(xp)[:, 1]
        pred = info.modelo.predict(xp)
        fpr, tpr, _ = roc_curve(y, proba)
        fx, tx = _downsample(fpr, tpr)
        cm = confusion_matrix(y, pred, labels=[0, 1])

        if nome == "LogisticRegression":
            nomes = list(info.preprocessador.get_feature_names_out())
            imp = _agg_importancia(list(zip(nomes, info.modelo.coef_[0])))
            fonte_imp = "|coeficiente|"
        elif nome in shap_importancia:
            imp = _agg_importancia([(r["feature"], r["shap_medio_abs"]) for r in shap_importancia[nome]])
            fonte_imp = "SHAP (|valor| médio)"
        else:
            imp, fonte_imp = {}, "—"

        por_modelo[nome] = {
            "roc": {"fpr": fx, "tpr": tx},
            "confusao": {"tn": int(cm[0, 0]), "fp": int(cm[0, 1]), "fn": int(cm[1, 0]), "tp": int(cm[1, 1])},
            "taxa_positivos_prevista": float(pred.mean()),
            "sweep": _varrer_threshold(proba, y),
            "importancia": {k: round(v, 5) for k, v in imp.items()},
            "fonte_importancia": fonte_imp,
        }
    return {"n_teste": int(len(y)), "taxa_base": float(y.mean()), "por_modelo": por_modelo}


# ---------------------------------------------------------------------
# SVG / HTML — gráficos nativos (mesma linguagem visual do boletim de EDA)
# ---------------------------------------------------------------------

def _svg_roc(dados_boletim: dict) -> str:
    w, h, pad = 420, 320, 44
    pw, ph = w - pad - 12, h - pad - 28
    cores = ["var(--accent)", "var(--roxo)", "var(--aqua)"]

    def x(v): return pad + v * pw
    def y(v): return pad - 16 + (1 - v) * ph

    linhas = [f'<line class="grid-line" x1="{x(0)}" y1="{y(0)}" x2="{x(1)}" y2="{y(0)}"/>',
              f'<line class="grid-line" x1="{x(0)}" y1="{y(0)}" x2="{x(0)}" y2="{y(1)}"/>',
              f'<line class="roc-diag" x1="{x(0)}" y1="{y(0)}" x2="{x(1)}" y2="{y(1)}"/>']
    legenda = []
    for i, (nome, d) in enumerate(dados_boletim["por_modelo"].items()):
        pts = " ".join(f"{x(fx):.1f},{y(tx):.1f}" for fx, tx in zip(d["roc"]["fpr"], d["roc"]["tpr"]))
        linhas.append(f'<polyline points="{pts}" fill="none" stroke="{cores[i % 3]}" stroke-width="2.2"/>')
        legenda.append(f'<span class="roc-leg"><i style="background:{cores[i % 3]}"></i>{NOME_MODELO.get(nome, nome)}</span>')
    for v in (0, 0.5, 1):
        linhas.append(f'<text class="axis-x" x="{x(v):.0f}" y="{h - 8}">{v}</text>')
        linhas.append(f'<text class="axis-y-label" x="{pad - 8}" y="{y(v) + 4:.0f}" text-anchor="end">{v}</text>')
    linhas.append(f'<text class="axis-x" x="{x(0.5):.0f}" y="{h + 6}"></text>')
    svg = (f'<svg viewBox="0 0 {w} {h}" class="chart-svg" role="img" aria-label="Curvas ROC">'
           + "".join(linhas)
           + f'<text class="axis-cap" x="{x(0.5):.0f}" y="{h - 2}" text-anchor="middle">Taxa de falsos positivos →</text>'
           + f'<text class="axis-cap" x="14" y="{y(0.5):.0f}" text-anchor="middle" transform="rotate(-90 14 {y(0.5):.0f})">Taxa de verdadeiros positivos →</text>'
           + "</svg>")
    return f'<div class="chart-wrap">{svg}<div class="roc-legenda">{"".join(legenda)}</div></div>'


def _svg_confusao(cm: dict, ident: str = "") -> str:
    total = cm["tn"] + cm["fp"] + cm["fn"] + cm["tp"] or 1
    celulas = [
        ("tn", "Formal previsto certo", cm["tn"], False),
        ("fp", "Formal virou informal", cm["fp"], True),
        ("fn", "Informal virou formal", cm["fn"], True),
        ("tp", "Informal previsto certo", cm["tp"], False),
    ]
    divs = []
    for chave, titulo, valor, erro in celulas:
        alpha = 0.10 + 0.6 * (valor / total)
        cor = f"rgba(200,73,72,{alpha:.2f})" if erro else f"rgba(42,120,214,{alpha:.2f})"
        idattr = f' id="{ident}-{chave}"' if ident else ""
        divs.append(f'<div class="cm-cell" style="background:{cor}"{idattr}>'
                    f'<span class="cm-n">{valor:,}</span><span class="cm-t">{titulo}</span></div>'.replace(",", "."))
    return (f'<div class="cm-grid">'
            f'<div class="cm-axis cm-axis-x">previsto →</div>'
            f'<div class="cm-axis cm-axis-y">real ↓</div>'
            f'<div class="cm-head">Formal</div><div class="cm-head">Informal</div>'
            f'<div class="cm-rowhead">Formal</div>{divs[0]}{divs[1]}'
            f'<div class="cm-rowhead">Informal</div>{divs[2]}{divs[3]}</div>')


def _svg_scatter_tempo_auc(matriz: pd.DataFrame) -> str:
    w, h, pad = 430, 300, 46
    pw, ph = w - pad - 90, h - pad - 26
    regs = matriz.to_dict("records")
    tempos = [r["Tempo treino (s)"] for r in regs]
    aucs = [r["AUC-ROC"] for r in regs]
    tmin, tmax = 0, max(tempos) * 1.15 or 1
    amin, amax = min(aucs) - 0.01, max(aucs) + 0.01

    def x(v): return pad + (v - tmin) / (tmax - tmin) * pw
    def y(v): return pad - 12 + (1 - (v - amin) / (amax - amin)) * ph

    linhas = [f'<line class="grid-line" x1="{x(tmin)}" y1="{y(amin)}" x2="{x(tmax)}" y2="{y(amin)}"/>',
              f'<line class="grid-line" x1="{x(tmin)}" y1="{y(amin)}" x2="{x(tmin)}" y2="{y(amax)}"/>']
    for r in regs:
        cx, cy = x(r["Tempo treino (s)"]), y(r["AUC-ROC"])
        linhas.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="6" fill="var(--accent)"/>')
        linhas.append(f'<text class="scatter-lbl" x="{cx + 10:.1f}" y="{cy + 4:.1f}">{NOME_MODELO.get(r["Modelo"], r["Modelo"])}</text>')
        linhas.append(f'<text class="scatter-sub" x="{cx + 10:.1f}" y="{cy + 17:.1f}">AUC {r["AUC-ROC"]:.3f} · {r["Tempo treino (s)"]:.1f}s</text>')
    for frac in (0, 0.5, 1):
        tv = tmin + frac * (tmax - tmin)
        linhas.append(f'<text class="axis-x" x="{x(tv):.0f}" y="{h - 6}">{_fmt_tempo(tv)}</text>')
    svg = (f'<svg viewBox="0 0 {w} {h}" class="chart-svg" role="img" aria-label="Tempo de treino versus AUC">'
           + "".join(linhas)
           + f'<text class="axis-cap" x="{x((tmin + tmax) / 2):.0f}" y="{h + 4}" text-anchor="middle">Tempo de treino →</text>'
           + f'<text class="axis-cap" x="12" y="{y((amin + amax) / 2):.0f}" text-anchor="middle" transform="rotate(-90 12 {y((amin + amax) / 2):.0f})">AUC no teste →</text>'
           + "</svg>")
    return f'<div class="chart-wrap">{svg}</div>'


def _matriz_comparacao_html(matriz: pd.DataFrame) -> str:
    regs = matriz.to_dict("records")
    cols_maior = ["Accuracy", "Precision", "Recall", "F1", "AUC-ROC"]
    melhores = {c: max(r[c] for r in regs) for c in cols_maior}
    melhor_tempo = min(r["Tempo treino (s)"] for r in regs)
    head = "".join(f"<th>{c}</th>" for c in ["Modelo", *cols_maior, "Tempo (s)"])
    linhas = []
    for r in regs:
        tds = [f'<td><b>{NOME_MODELO.get(r["Modelo"], r["Modelo"])}</b></td>']
        for c in cols_maior:
            cls = ' class="melhor"' if abs(r[c] - melhores[c]) < 1e-9 else ""
            tds.append(f"<td{cls}>{r[c]:.4f}</td>")
        cls_t = ' class="melhor"' if abs(r["Tempo treino (s)"] - melhor_tempo) < 1e-9 else ""
        tds.append(f'<td{cls_t}>{r["Tempo treino (s)"]:.2f}</td>')
        linhas.append(f"<tr>{''.join(tds)}</tr>")
    return f'<table class="data"><thead><tr>{head}</tr></thead><tbody>{"".join(linhas)}</tbody></table>'


def _barras_importancia(imp: dict[str, float], fonte: str) -> str:
    if not imp:
        return '<p class="painel-tk">Sem SHAP para este modelo — ver os coeficientes da Regressão Logística.</p>'
    itens = list(imp.items())[:8]
    maximo = max(v for _, v in itens) or 1
    linhas = []
    for nome, v in itens:
        larg = 100 * v / maximo
        linhas.append(f'<div class="mbar-row"><div class="mbar-label">{LABELS_FEATURES.get(nome, nome)}</div>'
                      f'<div class="mbar-track"><div class="mbar-fill" style="width:{larg:.1f}%"></div></div>'
                      f'<div class="mbar-val">{v:.3f}</div></div>')
    return f'<div class="mbar-rows">{"".join(linhas)}</div><p class="panel-caption">Importância = {fonte}, somada por variável.</p>'


def _barras_treino_teste(metricas_treino: dict, metricas_teste: dict) -> str:
    linhas = []
    for nome in metricas_teste:
        tr, te = metricas_treino[nome]["auc_roc"], metricas_teste[nome]["auc_roc"]
        gap = tr - te
        alerta = " tt-row--alerta" if gap > 0.05 else ""
        linhas.append(
            f'<div class="tt-row{alerta}"><div class="tt-label">{NOME_MODELO.get(nome, nome)}</div>'
            f'<div class="tt-bars">'
            f'<div class="tt-bar tt-bar--tr" style="width:{tr * 100:.1f}%"><span>treino {tr:.3f}</span></div>'
            f'<div class="tt-bar tt-bar--te" style="width:{te * 100:.1f}%"><span>teste {te:.3f}</span></div>'
            f'</div><div class="tt-gap">gap {gap:+.3f}</div></div>'
        )
    return f'<div class="tt-rows">{"".join(linhas)}</div>'


def _equidade_html(confusao_por_grupo: dict, metricas_teste: dict) -> str:
    blocos = []
    for nome, linhas_grupo in confusao_por_grupo.items():
        rec_geral = metricas_teste[nome]["recall"]
        rows = []
        for r in linhas_grupo:
            if r["recall"] is None:
                continue
            gap = r["recall"] - rec_geral
            disp = abs(gap) >= 0.10 and r["n"] >= N_MIN_GRUPO_EQUIDADE
            cls = " fair-row--disp" if disp else ""
            n_baixo = ' <span class="fair-nwarn">n baixo</span>' if r["n"] < N_MIN_GRUPO_EQUIDADE else ""
            fpr_txt = f'{r["fpr"] * 100:.0f}%' if r["fpr"] is not None else "—"
            rows.append(
                f'<tr class="{cls.strip()}"><td>{_nome_grupo(r["grupo"], r["valor"])}{n_baixo}</td>'
                f'<td>{r["n"]:,}</td><td>{r["recall"] * 100:.0f}%</td><td>{gap * 100:+.0f} p.p.</td>'
                f'<td>{fpr_txt}</td></tr>'.replace(",", ".")
            )
        blocos.append(
            f'<div class="panel"><div class="panel-head"><div class="panel-title">{NOME_MODELO.get(nome, nome)}</div>'
            f'<span class="panel-note">recall geral: {rec_geral * 100:.0f}%</span></div>'
            f'<table class="data"><thead><tr><th>Grupo</th><th>N</th><th>Recall</th>'
            f'<th>vs. geral</th><th>Falso positivo</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
        )
    return "".join(blocos)


def _shap_por_grupo_html(shap_por_grupo: dict) -> str:
    if not shap_por_grupo:
        return ""
    blocos = []
    for nome, por_grupo in shap_por_grupo.items():
        itens = []
        for chave, ranking in por_grupo.items():
            top = ", ".join(LABELS_FEATURES.get(_feat_base(r["feature"]), _feat_base(r["feature"])) for r in ranking[:3])
            col, _, val = chave.partition("=")
            itens.append(f"<li><b>{_nome_grupo(col, val)}</b>: {top}</li>")
        blocos.append(f'<div class="panel"><div class="panel-head"><div class="panel-title">{NOME_MODELO.get(nome, nome)} — o que mais pesa por grupo</div></div><ul class="lista-simples">{"".join(itens)}</ul></div>')
    return "".join(blocos)


def _recomendacao(matriz: pd.DataFrame, metricas_treino: dict, metricas_teste: dict, tempos: dict) -> tuple[str, list[str]]:
    regs = {r["Modelo"]: r for r in matriz.to_dict("records")}
    campeao = matriz.iloc[0]["Modelo"]
    auc_c = regs[campeao]["AUC-ROC"]
    t_c = tempos.get(campeao, 0.0)
    base = "LogisticRegression"
    gap_over = metricas_treino[campeao]["auc_roc"] - metricas_teste[campeao]["auc_roc"]

    if campeao == base:
        veredito = (f"A <b>Regressão Logística</b> — o baseline — teve o melhor AUC no teste "
                    f"(<b>{auc_c:.3f}</b>), treinando em {_fmt_tempo(t_c)}. Nenhum modelo mais complexo "
                    f"superou a baseline por margem que justifique perder a interpretabilidade.")
    else:
        auc_b = regs[base]["AUC-ROC"]
        delta = auc_c - auc_b
        mais_rapido = "mais rápida" if tempos.get(base, 0) < t_c else "mais lenta"
        veredito = (f"O <b>{NOME_MODELO[campeao]}</b> teve o melhor AUC no teste (<b>{auc_c:.3f}</b>), "
                    f"treinando em {_fmt_tempo(t_c)}. A Regressão Logística ficou {delta:.3f} atrás em AUC "
                    f"({auc_b:.3f}), mas é {mais_rapido} e explicável direto pelos coeficientes.")

    razoes = [
        f"<b>Melhor AUC de teste</b> ({auc_c:.3f}) — separa informal de formal melhor que os outros.",
        f"<b>Custo de treino</b>: {_fmt_tempo(t_c)} ({'o mais rápido' if t_c == min(tempos.values()) else 'aceitável'} para reexecutar e ajustar).",
    ]
    if gap_over > 0.05:
        razoes.append(f"<b>Atenção</b>: gap treino−teste de AUC = {gap_over:+.3f} — sinal de overfitting; "
                      f"ver Seção 05 antes de fechar a escolha.")
    else:
        razoes.append(f"<b>Generaliza bem</b>: gap treino−teste de AUC = {gap_over:+.3f}, pequeno.")
    return veredito, razoes


def _highlight_cards(matriz, metricas_teste, tempos, confusao_por_grupo, dados_boletim) -> str:
    regs = {r["Modelo"]: r for r in matriz.to_dict("records")}
    campeao = matriz.iloc[0]["Modelo"]
    auc = regs[campeao]["AUC-ROC"]
    intens = "forte" if auc >= 0.85 else ("razoável" if auc >= 0.75 else "fraco")
    mais_rapido = min(tempos, key=tempos.get)

    pior = None
    for nome, linhas in confusao_por_grupo.items():
        rg = metricas_teste[nome]["recall"]
        for r in linhas:
            if r["recall"] is None or r["n"] < N_MIN_GRUPO_EQUIDADE:
                continue
            d = abs(r["recall"] - rg)
            if pior is None or d > pior[0]:
                pior = (d, nome, r)
    if pior:
        _, nm, r = pior
        disp_card = {"label": "Maior disparidade entre grupos",
                     "value": f"{r['recall'] * 100:.0f}% vs {metricas_teste[nm]['recall'] * 100:.0f}%",
                     "sub": f"{NOME_MODELO.get(nm, nm)} · recall em {_nome_grupo(r['grupo'], r['valor'])} vs. geral",
                     "warn": pior[0] >= 0.10}
    else:
        disp_card = {"label": "Maior disparidade entre grupos", "value": "—", "sub": "grupos pequenos demais para medir"}

    return cards([
        {"label": "Melhor modelo (AUC de teste)", "value": NOME_MODELO.get(campeao, campeao), "sub": f"AUC {auc:.3f}"},
        {"label": "AUC no teste (2025)", "value": f"{auc:.3f}", "sub": f"poder de separação {intens}"},
        {"label": "Mais rápido de treinar", "value": _fmt_tempo(tempos[mais_rapido]), "sub": NOME_MODELO.get(mais_rapido, mais_rapido)},
        disp_card,
    ])


_GLOSSARIO_MOD = [
    ("AUC-ROC", "Chance de o modelo dar nota maior a um informal do que a um formal, sorteando um de cada. 0,5 = acaso, 1,0 = perfeito."),
    ("Acurácia", "De todas as previsões, a fração que o modelo acertou. Enganosa quando as classes são muito desbalanceadas."),
    ("Precisão", "Quando o modelo diz \"informal\", com que frequência acerta. Baixa = muitos alarmes falsos."),
    ("Recall (sensibilidade)", "Dos informais de verdade, quantos o modelo pega. Baixo = informal passando por formal, subestimando o problema."),
    ("F1", "Média harmônica de precisão e recall — resume os dois num número só."),
    ("Matriz de confusão", "Tabela 2×2: acertos e erros cruzando o que era real com o que o modelo previu."),
    ("Falso positivo / negativo", "Falso positivo = formal classificado como informal. Falso negativo = informal classificado como formal."),
    ("Overfitting", "O modelo decorou o treino em vez de aprender o padrão — vai bem no treino e mal em dados novos (gap grande entre os dois)."),
    ("SHAP", "Método que reparte a previsão do modelo entre as variáveis: quanto cada uma empurrou aquela previsão para \"informal\" ou \"formal\"."),
    ("Coeficiente (Regressão Logística)", "O peso que o modelo linear dá a cada variável. Sinal positivo empurra para informal, negativo para formal."),
    ("Split temporal", "Treinar com anos anteriores (2023–24) e testar no ano seguinte (2025) — evita vazar a mesma pessoa entre treino e teste na PNAD."),
    ("Threshold (ponto de corte)", "A probabilidade a partir da qual o modelo chama de \"informal\". Padrão 0,5; baixar aumenta recall, subir aumenta precisão."),
]


def _js_threshold_slider(dados_boletim: dict) -> str:
    sweep = {nome: d["sweep"] for nome, d in dados_boletim["por_modelo"].items()}
    dados_json = json.dumps(sweep, ensure_ascii=False).replace("</", "<\\/")
    nomes_json = json.dumps(NOME_MODELO, ensure_ascii=False)
    return f"""<script>
      const SWEEP = {dados_json};
      const NOMES_SW = {nomes_json};
      const MODELOS_SW = Object.keys(SWEEP);
      function _fmt(n) {{ return n.toLocaleString('pt-BR'); }}
      function atualizarThreshold() {{
        const modelo = document.getElementById('sw-modelo').value;
        const linhas = SWEEP[modelo];
        const i = +document.getElementById('sw-range').value;
        const r = linhas[i];
        document.getElementById('sw-t').textContent = r.t.toFixed(2);
        document.getElementById('sw-precision').textContent = (r.precision * 100).toFixed(0) + '%';
        document.getElementById('sw-recall').textContent = (r.recall * 100).toFixed(0) + '%';
        document.getElementById('sw-f1').textContent = r.f1.toFixed(3);
        const tot = r.tn + r.fp + r.fn + r.tp || 1;
        const set = (id, v, erro) => {{
          const el = document.getElementById(id);
          const a = (0.10 + 0.6 * v / tot).toFixed(2);
          el.style.background = (erro ? 'rgba(200,73,72,' : 'rgba(42,120,214,') + a + ')';
          el.querySelector('.cm-n').textContent = _fmt(v);
        }};
        set('sw-tn', r.tn, false); set('sw-fp', r.fp, true);
        set('sw-fn', r.fn, true); set('sw-tp', r.tp, false);
      }}
      document.addEventListener('DOMContentLoaded', function () {{
        const sel = document.getElementById('sw-modelo');
        MODELOS_SW.forEach(m => {{ const o = document.createElement('option'); o.value = m; o.textContent = NOMES_SW[m] || m; sel.appendChild(o); }});
        const rng = document.getElementById('sw-range');
        rng.max = SWEEP[MODELOS_SW[0]].length - 1;
        rng.value = SWEEP[MODELOS_SW[0]].findIndex(r => r.t >= 0.5);
        sel.addEventListener('change', atualizarThreshold);
        rng.addEventListener('input', atualizarThreshold);
        atualizarThreshold();
      }});
    </script>"""


_CSS_MOD = """
  .chart-wrap{overflow-x:auto;margin-top:16px}
  .chart-svg{width:100%;min-width:340px;height:auto;max-width:480px;display:block}
  .chart-svg .grid-line{stroke:var(--border-strong);stroke-width:1}
  .roc-diag{stroke:var(--ink-muted);stroke-dasharray:4 4;stroke-width:1}
  .axis-cap{font-family:"IBM Plex Mono",monospace;font-size:10px;fill:var(--ink-muted)}
  .chart-svg .axis-x,.chart-svg .axis-y-label{font-family:"IBM Plex Mono",monospace;font-size:10.5px;fill:var(--ink-muted)}
  .chart-svg .axis-x{text-anchor:middle}
  .scatter-lbl{font-size:11px;font-weight:600;fill:var(--ink)}.scatter-sub{font-size:9.5px;fill:var(--ink-muted);font-family:"IBM Plex Mono",monospace}
  .roc-legenda{display:flex;gap:16px;flex-wrap:wrap;margin-top:8px;font-size:.8rem;color:var(--ink-2)}
  .roc-leg{display:flex;align-items:center;gap:6px}.roc-leg i{width:14px;height:3px;border-radius:2px;display:inline-block}
  .cm-grid{display:grid;grid-template-columns:auto 1fr 1fr;grid-template-rows:auto auto auto;gap:4px;max-width:440px;margin-top:14px;position:relative}
  .cm-head{text-align:center;font-size:.75rem;font-weight:700;color:var(--ink-muted);padding-bottom:2px}
  .cm-rowhead{display:flex;align-items:center;font-size:.75rem;font-weight:700;color:var(--ink-muted);padding-right:6px}
  .cm-cell{border-radius:8px;padding:14px 10px;display:flex;flex-direction:column;gap:3px;align-items:center;justify-content:center;text-align:center;min-height:78px}
  .cm-n{font-family:"IBM Plex Mono",monospace;font-size:1.25rem;font-weight:700;color:var(--ink)}
  .cm-t{font-size:.72rem;color:var(--ink-2);line-height:1.25}
  .cm-axis{font-size:.68rem;color:var(--ink-muted);font-family:"IBM Plex Mono",monospace}
  .cm-axis-x{grid-column:2/4;text-align:center}.cm-axis-y{display:none}
  .mbar-rows,.tt-rows{display:grid;gap:10px;margin-top:14px}
  .mbar-row{display:grid;grid-template-columns:150px 1fr 60px;align-items:center;gap:12px}
  .mbar-label{font-size:.85rem;color:var(--ink-2)}
  .mbar-track{height:18px;background:var(--surface-2);border-radius:5px;overflow:hidden}
  .mbar-fill{height:100%;background:var(--roxo);border-radius:5px}
  .mbar-val{font-family:"IBM Plex Mono",monospace;font-size:.78rem;text-align:right;color:var(--ink)}
  .tt-row{display:grid;grid-template-columns:150px 1fr 92px;align-items:center;gap:12px}
  .tt-label{font-size:.85rem;color:var(--ink-2)}
  .tt-bars{display:grid;gap:4px}
  .tt-bar{height:16px;border-radius:4px;display:flex;align-items:center;min-width:2px}
  .tt-bar span{font-family:"IBM Plex Mono",monospace;font-size:.68rem;color:#fff;padding-left:7px;white-space:nowrap}
  .tt-bar--tr{background:var(--ink-muted)}.tt-bar--te{background:var(--accent)}
  .tt-gap{font-family:"IBM Plex Mono",monospace;font-size:.78rem;text-align:right;color:var(--ink-2)}
  .tt-row--alerta .tt-gap{color:var(--negative);font-weight:700}
  .lista-simples{margin:12px 0 0;padding-left:1.15em;display:grid;gap:6px}
  .lista-simples li{font-size:.9rem;line-height:1.5;color:var(--ink-2)}.lista-simples li b{color:var(--ink)}
  .fair-row--disp{background:rgba(200,48,47,.09)}
  .fair-row--disp td{color:var(--negative);font-weight:600}
  .fair-nwarn{font-family:"IBM Plex Mono",monospace;font-size:.66rem;color:var(--ink-muted);border:1px solid var(--border);border-radius:4px;padding:0 4px}
  .modelcard{border:1px solid var(--roxo);background:rgba(124,92,191,.07);border-radius:14px;padding:16px 20px;margin-top:16px}
  .modelcard b{color:var(--type-forca-strong)}
  .sw-box{margin-top:16px}
  .sw-controls{display:flex;gap:20px;flex-wrap:wrap;align-items:center;margin-bottom:14px}
  .sw-controls select{font:inherit;font-size:.86rem;color:var(--ink);background:var(--surface);border:1px solid var(--border-strong);border-radius:8px;padding:6px 10px}
  .sw-range{width:min(360px,60vw)}
  .sw-metricas{display:flex;gap:26px;flex-wrap:wrap;margin:6px 0 4px}
  .sw-metrica{font-size:.82rem;color:var(--ink-muted)}
  .sw-metrica b{display:block;font-family:"IBM Plex Mono",monospace;font-size:1.3rem;color:var(--accent-ink);margin-top:2px}
  .veredito{border:1px solid var(--accent);background:var(--accent-soft-2);border-radius:16px;padding:20px 24px;margin-top:20px}
  .veredito p{margin:0;font-size:1.08rem;line-height:1.55;color:var(--ink)}.veredito p b{color:var(--accent-ink)}
  .metrica-def{display:grid;gap:7px;margin-top:14px}
  .metrica-def div{font-size:.86rem;line-height:1.45;color:var(--ink-2)}
  .metrica-def b{color:var(--ink);font-family:"IBM Plex Mono",monospace;font-size:.8rem;text-transform:uppercase;letter-spacing:.03em}
  @media (max-width:760px){.mbar-row{grid-template-columns:110px 1fr 52px}.tt-row{grid-template-columns:110px 1fr 78px}}
"""


def gerar_boletim_html(
    metricas_treino: dict[str, dict],
    metricas_teste: dict[str, dict],
    matriz_comparacao: pd.DataFrame,
    confusao_por_grupo: dict[str, list[dict]],
    shap_por_grupo: dict[str, dict],
    dados_boletim: dict,
    tempos: dict[str, float],
    config: dict,
    caminho_arquivo: Path,
) -> str:
    """Boletim de apresentação — `dashboard/modelagem_informalidade.html`.
    Mesma linguagem visual do boletim de EDA. Tudo derivado dos números
    recebidos; nenhuma métrica nova de treino é calculada aqui.
    """
    campeao = matriz_comparacao.iloc[0]["Modelo"]
    veredito, razoes = _recomendacao(matriz_comparacao, metricas_treino, metricas_teste, tempos)
    base_txt = "amostra de teste" if config.get("n_amostra") else "base completa"

    metrica_frases = [
        ("Recall", "dos informais de verdade, quantos o modelo pega. Recall baixo = informal classificado como formal, o que <b>subestima</b> o tamanho da informalidade."),
        ("Precisão", "quando o modelo diz \"informal\", quantas vezes acerta. Precisão baixa = muitos alarmes falsos."),
        ("F1", "junta precisão e recall num número; útil quando os dois importam."),
        ("AUC-ROC", "capacidade de ordenar informal acima de formal, independente do ponto de corte. 0,5 = acaso."),
        ("Acurácia", "fração de acertos no total. Aqui informa, mas não decide sozinha — recall importa mais."),
        ("Tempo", "segundos para treinar. Importa para reexecutar, ajustar e comparar rodadas."),
    ]
    metrica_def = '<div class="metrica-def">' + "".join(
        f"<div><b>{k}</b> — {v}</div>" for k, v in metrica_frases) + "</div>"

    # --- highlights + como ler ---
    highlights = _highlight_cards(matriz_comparacao, metricas_teste, tempos, confusao_por_grupo, dados_boletim)
    como_ler = (
        '<div class="ler"><div class="ler-head">Como ler este boletim</div>'
        '<p class="ler-p">Cada painel tem um <b>selo</b> dizendo o que mostra. As métricas '
        'de modelo (AUC, recall, precisão) vão de 0 a 1 — mais alto é melhor, mas cada uma '
        'responde a uma pergunta diferente (abaixo).</p>'
        '<div class="ler-tipos">'
        f'<div class="ler-tipo">{selo("DESEMPENHO 0 a 1", 1)}<span>Quão bem o modelo acerta.</span></div>'
        f'<div class="ler-tipo">{selo("CUSTO", 5)}<span>Tempo de treino — o preço de usar o modelo.</span></div>'
        f'<div class="ler-tipo">{selo("CONFIABILIDADE", 3)}<span>Se o resultado do teste se sustenta (sem overfitting).</span></div>'
        f'<div class="ler-tipo">{selo("O QUE PESA", 4)}<span>Quais variáveis o modelo usa mais.</span></div>'
        f'<div class="ler-tipo">{selo("EQUIDADE / MODEL CARD", 6)}<span>Se o modelo trata os grupos de forma parecida.</span></div>'
        '</div>'
        '<p class="ler-nota">O modelo aprende <b>associação</b>, não causa. E foi treinado com '
        '2023–2024 e testado em 2025 (split temporal) — as 15 variáveis são as da EDA, sem renda '
        '(vazamento) e sem ponderação amostral.</p></div>'
    )

    cabecalho = f'''  <header class="top">
    <div class="eyebrow">Boletim de modelagem · PNAD Contínua · RF-05 / RF-06</div>
    <h1>Modelagem da <em>informalidade</em></h1>
    <p class="lede">Três modelos treinados para prever se um trabalhador ocupado é informal, a partir de 15 características — e a leitura de qual escolher, se é confiável e se é justo entre grupos. Roda sobre a {base_txt} ({dados_boletim["n_teste"]:,} pessoas no teste de 2025).</p>
    <div class="callout callout--metodo">
      <div class="callout-head">Antes dos números</div>
      <ul>
        <li><b>Split temporal</b>: treino = 2023–2024, teste = 2025. Nada de 2025 foi visto no treino.</li>
        <li><b>15 features da EDA</b> — renda fica de fora (vazamento circular); sem ponderação por <code>V1028</code>.</li>
        <li><b>As flags do diagnóstico levantam a mão</b> ("possível X, investigar") — os limiares (gap &gt; 0,05, etc.) são convenção, não lei.</li>
      </ul>
    </div>
    {highlights}
    {como_ler}
  </header>'''.replace(",", ".")

    # --- 01 recomendação ---
    razoes_html = "".join(f"<li>{r}</li>" for r in razoes)
    s01 = secao("01", "Qual modelo escolher, e por quê",
                "O veredito antes da tabela. A comparação completa vem na Seção 02.",
                f'<div class="veredito"><p>{veredito}</p></div>'
                f'<div class="panel"><div class="panel-head"><div class="panel-title">Por trás da recomendação</div>'
                f'{selo("DESEMPENHO 0 a 1", 1)}</div><ul class="lista-simples">{razoes_html}</ul></div>')

    # --- 02 comparação ---
    s02 = secao("02", "Comparação dos modelos",
                "Cada métrica responde a uma pergunta diferente. O melhor de cada coluna está destacado.",
                takeaway(f"O <b>{NOME_MODELO.get(campeao, campeao)}</b> lidera em AUC; os três ficam "
                         f"próximos em acurácia (~{matriz_comparacao.iloc[0]['Accuracy'] * 100:.0f}%). "
                         f"A diferença real está em <b>recall</b> (pegar informais) e <b>tempo</b>.")
                + f'<div class="panel"><div class="panel-head"><div class="panel-title">Métricas no teste (2025)</div>'
                  f'{selo("DESEMPENHO 0 a 1", 1)}</div>{_matriz_comparacao_html(matriz_comparacao)}{metrica_def}</div>'
                + f'<div class="panel"><div class="panel-head"><div class="panel-title">Curvas ROC</div>'
                  f'{selo("DESEMPENHO 0 a 1", 1)}</div>'
                  f'<p class="painel-tk">Cada curva sobe da esquerda para cima. Quanto mais "colada" no canto superior '
                  f'esquerdo, melhor o modelo separa informal de formal. A diagonal pontilhada é o acaso.</p>'
                  f'{_svg_roc(dados_boletim)}</div>')

    # --- 03 threshold slider ---
    s03 = secao("03", "Ajustando o ponto de corte",
                "O modelo dá uma probabilidade; o <i>threshold</i> decide a partir de quanto isso vira \"informal\". "
                "Mexa no controle e veja precisão, recall e a matriz de confusão mudarem.",
                takeaway("Baixar o corte <b>pega mais informais</b> (recall sobe) mas gera <b>mais alarmes falsos</b> "
                         "(precisão cai). Não existe corte \"certo\" — depende do que custa mais errar.")
                + f'''<div class="panel"><div class="panel-head"><div class="panel-title">Simulador de threshold</div>{selo("DESEMPENHO 0 a 1", 1)}</div>
      <div class="sw-box">
        <div class="sw-controls">
          <label>Modelo <select id="sw-modelo"></select></label>
          <label>Corte: <b id="sw-t">0.50</b> <input type="range" id="sw-range" class="sw-range" min="0" max="45" value="22"></label>
        </div>
        <div class="sw-metricas">
          <span class="sw-metrica">Precisão <b id="sw-precision">—</b></span>
          <span class="sw-metrica">Recall <b id="sw-recall">—</b></span>
          <span class="sw-metrica">F1 <b id="sw-f1">—</b></span>
        </div>
        {_svg_confusao(next(iter(dados_boletim["por_modelo"].values()))["confusao"], ident="sw")}
      </div></div>
      {_js_threshold_slider(dados_boletim)}''')

    # --- 04 velocidade x desempenho ---
    regs = {r["Modelo"]: r for r in matriz_comparacao.to_dict("records")}
    t_min_nome = min(tempos, key=tempos.get)
    t_max_nome = max(tempos, key=tempos.get)
    s04 = secao("04", "Velocidade × desempenho",
                "O que foi rápido, o que foi caro — e se o caro compensou.",
                takeaway(f"<b>{NOME_MODELO.get(t_min_nome, t_min_nome)}</b> treinou em {_fmt_tempo(tempos[t_min_nome])} "
                         f"(AUC {regs[t_min_nome]['AUC-ROC']:.3f}); <b>{NOME_MODELO.get(t_max_nome, t_max_nome)}</b> "
                         f"levou {_fmt_tempo(tempos[t_max_nome])} (AUC {regs[t_max_nome]['AUC-ROC']:.3f}). "
                         f"A diferença de AUC entre eles é de {abs(regs[t_min_nome]['AUC-ROC'] - regs[t_max_nome]['AUC-ROC']):.3f}.")
                + f'<div class="panel"><div class="panel-head"><div class="panel-title">Tempo de treino × AUC de teste</div>'
                  f'{selo("CUSTO", 5)}</div><p class="painel-tk">Ponto no alto e à esquerda = muito desempenho, pouco custo.</p>'
                  f'{_svg_scatter_tempo_auc(matriz_comparacao)}</div>')

    # --- 05 overfitting ---
    piores_over = [n for n in metricas_teste if metricas_treino[n]["auc_roc"] - metricas_teste[n]["auc_roc"] > 0.05]
    frase_over = (f"<b>{', '.join(NOME_MODELO.get(n, n) for n in piores_over)}</b> mostra gap treino−teste acima de "
                  f"0,05 — decorou parte do treino." if piores_over
                  else "Nenhum modelo tem gap treino−teste preocupante — todos generalizam bem.")
    s05 = secao("05", "O modelo é confiável?",
                "Se o modelo vai bem no treino mas mal no teste (gap grande), ele decorou em vez de aprender.",
                takeaway(frase_over)
                + f'<div class="panel"><div class="panel-head"><div class="panel-title">AUC treino vs. teste</div>'
                  f'{selo("CONFIABILIDADE", 3)}</div>'
                  f'<p class="painel-tk">Barra cinza = treino, azul = teste. Gap pequeno = generaliza; '
                  f'gap grande (destacado em vermelho) = overfitting.</p>{_barras_treino_teste(metricas_treino, metricas_teste)}</div>')

    # --- 06 interpretabilidade ---
    imp_paineis = ""
    for nome, d in dados_boletim["por_modelo"].items():
        imp_paineis += (f'<div class="panel"><div class="panel-head"><div class="panel-title">{NOME_MODELO.get(nome, nome)}</div>'
                        f'{selo("O QUE PESA", 4)}</div>{_barras_importancia(d["importancia"], d["fonte_importancia"])}</div>')
    top_geral = []
    for nome, d in dados_boletim["por_modelo"].items():
        if d["importancia"]:
            top_geral = [LABELS_FEATURES.get(k, k) for k in list(d["importancia"])[:4]]
            break
    s06 = secao("06", "O que o modelo aprendeu",
                "As variáveis que mais pesam na previsão — e o quanto batem com a força de associação medida na EDA.",
                takeaway(f"Os fatores de maior peso são <b>{', '.join(top_geral[:3])}</b>"
                         + (f" e <b>{top_geral[3]}</b>" if len(top_geral) > 3 else "")
                         + " — os mesmos que a EDA já apontava como mais associados à informalidade.")
                + '<p class="painel-tk" style="margin-left:calc(2ch + 18px)">A Regressão Logística não tem SHAP; '
                  'é lida pelo <b>coeficiente</b> de cada variável (peso no modelo linear). RF e HGB usam SHAP.</p>'
                + imp_paineis)

    # --- 07 equidade / Model Card ---
    modelcard = ('<div class="modelcard">Esta seção segue o padrão <b>Model Card</b> (Mitchell et al., '
                 '<i>FAT* 2019</i>): reportar métricas <b>separadas por subgrupo</b> — aqui recall e taxa de '
                 'falso positivo por sexo e por raça/cor — é a prática recomendada para tornar visível se o '
                 'modelo trata grupos de forma desigual, mesmo quando a métrica geral parece boa.</div>')
    s07 = secao("07", "É justo entre grupos?",
                "Um modelo pode ir bem na média e ainda errar mais para um grupo específico.",
                modelcard
                + takeaway("Procure linhas destacadas em vermelho: recall do grupo <b>10 pontos ou mais</b> abaixo "
                           "do recall geral significa que o modelo deixa passar mais informais desse grupo. "
                           "Grupos com \"n baixo\" têm poucos casos no teste — leia com cautela.")
                + '<p class="painel-tk" style="margin-left:calc(2ch + 18px)"><b>Por que importa:</b> classificar um '
                  'informal como formal (falso negativo) subestima o problema; se esse erro se concentra num grupo, '
                  'o modelo reproduz um viés. Recall alto e parelho entre grupos é o alvo.</p>'
                + _equidade_html(confusao_por_grupo, metricas_teste)
                + _shap_por_grupo_html(shap_por_grupo))

    corpo = (cabecalho + s01 + s02 + s03 + s04 + s05 + s06 + s07
             + glossario(_GLOSSARIO_MOD)
             + '''
  <footer>
    <div class="foot-col"><b style="color:var(--ink);">Fonte:</b> PNAD Contínua, IBGE — camada Gold. Split temporal treino 2023–2024 / teste 2025. Estimativas não ponderadas por <code>V1028</code>.</div>
    <div class="foot-col"><b style="color:var(--ink);">Gerado por:</b> <code>src/modelagem/relatorio.py</code> (RF-05/RF-06). Diagnóstico técnico em <code>dados/modelos/diagnostico_modelagem.json</code>. Ver também o <a href="censo_informalidade.html">boletim de EDA</a>.</div>
  </footer>''')

    html = montar_pagina("Modelagem da Informalidade", corpo, _CSS_MOD)
    caminho_arquivo.parent.mkdir(parents=True, exist_ok=True)
    caminho_arquivo.write_text(html, encoding="utf-8")
    return html


# ---------------------------------------------------------------------
# Diagnóstico — flags automáticas, config da rodada, comparação histórica
# ---------------------------------------------------------------------

_SEVERIDADE_ORDEM = {"alta": 0, "media": 1, "baixa": 2}


def _flag(cat, severidade, modelo, mensagem, evidencia, sugestao):
    return {"categoria": cat, "severidade": severidade, "modelo": modelo,
            "mensagem": mensagem, "evidencia": evidencia, "sugestao": sugestao}


def _calcular_flags(metricas_treino, metricas_teste, matriz_comparacao, confusao_por_grupo, dados_boletim):
    flags = []
    regs = {r["Modelo"]: r for r in matriz_comparacao.to_dict("records")}
    campeao = matriz_comparacao.iloc[0]["Modelo"]

    for nome in metricas_teste:
        gap = metricas_treino[nome]["auc_roc"] - metricas_teste[nome]["auc_roc"]
        if gap > 0.05:
            flags.append(_flag(
                "overfitting", "alta", nome,
                f"Possível overfitting em {NOME_MODELO.get(nome, nome)}: AUC de treino "
                f"{metricas_treino[nome]['auc_roc']:.3f} contra {metricas_teste[nome]['auc_roc']:.3f} no teste "
                f"(gap {gap:+.3f}, acima de 0,05).",
                {"auc_treino": round(metricas_treino[nome]["auc_roc"], 4),
                 "auc_teste": round(metricas_teste[nome]["auc_roc"], 4), "gap": round(gap, 4)},
                "Reduzir a capacidade do modelo (menos profundidade / mais regularização) ou treinar com mais "
                "dados; reavaliar o gap na próxima rodada.",
            ))

    for nome, linhas in confusao_por_grupo.items():
        rec_geral = metricas_teste[nome]["recall"]
        for r in linhas:
            if r["recall"] is None or r["n"] < N_MIN_GRUPO_EQUIDADE:
                continue
            if r["recall"] < rec_geral - 0.10:
                flags.append(_flag(
                    "equidade", "alta", nome,
                    f"Disparidade de equidade em {NOME_MODELO.get(nome, nome)}, grupo "
                    f"{_nome_grupo(r['grupo'], r['valor'])}: recall {r['recall']:.3f} contra {rec_geral:.3f} geral "
                    f"— o modelo deixa passar mais informais desse grupo.",
                    {"grupo": _nome_grupo(r["grupo"], r["valor"]), "n": r["n"],
                     "recall_grupo": round(r["recall"], 4), "recall_geral": round(rec_geral, 4)},
                    "Investigar representatividade e features do grupo; considerar reponderação no treino ou "
                    "threshold por grupo; registrar no Model Card.",
                ))

    auc_c = regs[campeao]["AUC-ROC"]
    for nome in ORDEM_SIMPLICIDADE:
        if nome == campeao:
            break
        if nome in regs and auc_c - regs[nome]["AUC-ROC"] < 0.01:
            flags.append(_flag(
                "ganho_marginal", "media", campeao,
                f"O campeão ({NOME_MODELO.get(campeao, campeao)}) supera {NOME_MODELO.get(nome, nome)} por apenas "
                f"{auc_c - regs[nome]['AUC-ROC']:+.4f} de AUC — ganho pequeno frente a um modelo mais simples e "
                f"explicável.",
                {"auc_campeao": round(auc_c, 4), "auc_alternativa": round(regs[nome]["AUC-ROC"], 4),
                 "modelo_alternativo": nome},
                f"Considerar adotar {NOME_MODELO.get(nome, nome)} em produção pela interpretabilidade, mantendo o "
                f"campeão como referência de teto de desempenho.",
            ))

    for nome, d in dados_boletim["por_modelo"].items():
        imp = d["importancia"]
        total = sum(imp.values())
        if total > 0:
            feat, val = next(iter(imp.items()))
            share = val / total
            if share > 0.5:
                flags.append(_flag(
                    "leakage", "media", nome,
                    f"Em {NOME_MODELO.get(nome, nome)}, '{LABELS_FEATURES.get(feat, feat)}' concentra "
                    f"{share * 100:.0f}% da importância — checar se não é vazamento (feature que só existe por "
                    f"causa do alvo).",
                    {"feature": LABELS_FEATURES.get(feat, feat), "share": round(share, 3)},
                    "Revisar a definição da feature; treinar sem ela e medir quanto de AUC se perde.",
                ))

    for nome, d in dados_boletim["por_modelo"].items():
        taxa = d["taxa_positivos_prevista"]
        if taxa < 0.10 or taxa > 0.90:
            flags.append(_flag(
                "colapso", "alta", nome,
                f"{NOME_MODELO.get(nome, nome)} prevê a classe 'informal' em {taxa * 100:.0f}% do teste "
                f"(base real ~{dados_boletim['taxa_base'] * 100:.0f}%) — pode estar colapsando numa classe só.",
                {"taxa_prevista": round(taxa, 3), "taxa_base": round(dados_boletim["taxa_base"], 3)},
                "Checar balanceamento do treino e o threshold; olhar a distribuição das probabilidades previstas.",
            ))

    for nome, mt in metricas_teste.items():
        if mt["auc_roc"] < 0.70:
            flags.append(_flag(
                "auc_baixa", "alta", nome,
                f"{NOME_MODELO.get(nome, nome)} tem AUC de teste {mt['auc_roc']:.3f} — pouco acima do acaso (0,5).",
                {"auc_teste": round(mt["auc_roc"], 4)},
                "Revisar features e pré-processamento; o sinal disponível pode ser insuficiente para o alvo.",
            ))
        if abs(mt["precision"] - mt["recall"]) > 0.15:
            flags.append(_flag(
                "threshold", "baixa", nome,
                f"Em {NOME_MODELO.get(nome, nome)}, precisão ({mt['precision']:.2f}) e recall ({mt['recall']:.2f}) "
                f"estão desbalanceados no corte padrão (0,5).",
                {"precision": round(mt["precision"], 4), "recall": round(mt["recall"], 4)},
                "Ajustar o threshold conforme o que custa mais: perder informal (subir recall) ou alarme falso "
                "(subir precisão). Ver a Seção 03 do boletim.",
            ))

    flags.sort(key=lambda f: (_SEVERIDADE_ORDEM[f["severidade"]], f["categoria"]))
    return flags


def _resumo_run(config, metricas_treino, metricas_teste, matriz_comparacao, flags):
    campeao = matriz_comparacao.iloc[0]["Modelo"]
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "config": config,
        "campeao": campeao,
        "auc_teste": {n: round(metricas_teste[n]["auc_roc"], 4) for n in metricas_teste},
        "gap_overfitting": {n: round(metricas_treino[n]["auc_roc"] - metricas_teste[n]["auc_roc"], 4)
                            for n in metricas_teste},
        "n_flags": len(flags),
        "flags_categorias": sorted({f["categoria"] for f in flags}),
    }


def _comparar_com_anterior(atual, anterior):
    if not anterior:
        return None
    campeao = atual["campeao"]
    d_auc = None
    if campeao in atual["auc_teste"] and campeao in anterior.get("auc_teste", {}):
        d_auc = round(atual["auc_teste"][campeao] - anterior["auc_teste"][campeao], 4)
    novas = sorted(set(atual["flags_categorias"]) - set(anterior.get("flags_categorias", [])))
    resolvidas = sorted(set(anterior.get("flags_categorias", [])) - set(atual["flags_categorias"]))
    return {
        "rodada_anterior": anterior.get("timestamp"),
        "hiperparametros_anteriores": anterior.get("config", {}).get("hiperparametros"),
        "delta_auc_campeao": d_auc,
        "delta_gap_overfitting": {
            n: round(atual["gap_overfitting"].get(n, 0) - anterior.get("gap_overfitting", {}).get(n, 0), 4)
            for n in atual["gap_overfitting"] if n in anterior.get("gap_overfitting", {})
        },
        "flags_novas": novas,
        "flags_resolvidas": resolvidas,
    }


def gerar_diagnostico(
    metricas_treino: dict[str, dict],
    metricas_teste: dict[str, dict],
    matriz_comparacao: pd.DataFrame,
    confusao_por_grupo: dict[str, list[dict]],
    dados_boletim: dict,
    config: dict,
    caminho_dir: Path,
) -> dict:
    """Relatório de diagnóstico (JSON + resumo .txt) para retomar/ajustar o
    modelo numa próxima rodada. Contém o julgamento (flags), não só os
    números — e as flags levantam a mão, não afirmam como lei.
    """
    flags = _calcular_flags(metricas_treino, metricas_teste, matriz_comparacao,
                            confusao_por_grupo, dados_boletim)
    resumo = _resumo_run(config, metricas_treino, metricas_teste, matriz_comparacao, flags)

    hist_dir = caminho_dir / "historico"
    hist_dir.mkdir(parents=True, exist_ok=True)
    anteriores = sorted(hist_dir.glob("run_*.json"))
    anterior = json.loads(anteriores[-1].read_text(encoding="utf-8")) if anteriores else None
    comparacao = _comparar_com_anterior(resumo, anterior)

    sugestoes = [{"prioridade": i + 1, "de_flag": f["categoria"], "severidade": f["severidade"],
                  "acao": f["sugestao"]} for i, f in enumerate(flags)]
    if not flags:
        sugestoes = [{"prioridade": 1, "de_flag": "—", "severidade": "info",
                      "acao": "Nenhuma flag disparou. Próximo passo natural: rodar na base completa (se ainda "
                              "não rodou) e/ou ampliar a busca de hiperparâmetros."}]

    diagnostico = {
        "gerado_em": resumo["timestamp"],
        "aviso": ("As flags abaixo LEVANTAM A MÃO ('possível X, investigar'), não afirmam como lei. "
                  "Os limiares (gap de AUC > 0,05; recall de subgrupo 0,10 abaixo do geral; etc.) são "
                  "convenção comum, não verdade absoluta — ajuste ao contexto."),
        "config": config,
        "campeao": resumo["campeao"],
        "metricas": {
            n: {"treino": {k: round(v, 4) for k, v in metricas_treino[n].items()},
                "teste": {k: round(v, 4) for k, v in metricas_teste[n].items()}}
            for n in metricas_teste
        },
        "flags": flags,
        "sugestoes_priorizadas": sugestoes,
        "comparacao_rodada_anterior": comparacao,
    }

    caminho_dir.mkdir(parents=True, exist_ok=True)
    (caminho_dir / "diagnostico_modelagem.json").write_text(
        json.dumps(diagnostico, indent=2, ensure_ascii=False), encoding="utf-8")
    (hist_dir / f"run_{resumo['timestamp'].replace(':', '').replace('-', '')}.json").write_text(
        json.dumps(resumo, indent=2, ensure_ascii=False), encoding="utf-8")

    _escrever_diagnostico_txt(diagnostico, caminho_dir / "diagnostico_modelagem.txt")
    return diagnostico


def _escrever_diagnostico_txt(diag: dict, caminho: Path) -> None:
    L = []
    L.append("=" * 78)
    L.append("DIAGNÓSTICO DE MODELAGEM — INFORMALIDADE (RF-05/RF-06)")
    L.append("=" * 78)
    L.append(f"Gerado em: {diag['gerado_em']}")
    cfg = diag["config"]
    base = f"amostra de {cfg['n_amostra']:,} linhas" if cfg.get("n_amostra") else "base completa"
    L.append(f"Rodada: {base} | seed={cfg.get('seed')} | tuning={cfg.get('ajustar_hiperparametros')} "
             f"| tempo total={cfg.get('tempo_total_s')}s")
    L.append(f"Treino: {cfg.get('n_treino'):,} | Teste: {cfg.get('n_teste'):,}")
    L.append(f"Campeão (AUC de teste): {NOME_MODELO.get(diag['campeao'], diag['campeao'])}")
    L.append("")
    L.append(diag["aviso"])
    L.append("")
    L.append("-" * 78)
    L.append(f"FLAGS ({len(diag['flags'])}):")
    L.append("-" * 78)
    if not diag["flags"]:
        L.append("  Nenhuma flag disparou nesta rodada.")
    for f in diag["flags"]:
        L.append(f"  [{f['severidade'].upper()}] {f['mensagem']}")
        L.append(f"         -> {f['sugestao']}")
    L.append("")
    L.append("-" * 78)
    L.append("SUGESTÕES PRIORIZADAS:")
    L.append("-" * 78)
    for s in diag["sugestoes_priorizadas"]:
        L.append(f"  {s['prioridade']}. ({s['severidade']}) {s['acao']}")
    L.append("")
    comp = diag["comparacao_rodada_anterior"]
    L.append("-" * 78)
    L.append("COMPARAÇÃO COM A RODADA ANTERIOR:")
    L.append("-" * 78)
    if not comp:
        L.append("  Primeira rodada registrada — sem histórico para comparar.")
    else:
        L.append(f"  Rodada anterior: {comp['rodada_anterior']}")
        L.append(f"  ΔAUC do campeão: {comp['delta_auc_campeao']}")
        L.append(f"  Δgap de overfitting: {comp['delta_gap_overfitting']}")
        L.append(f"  Flags novas: {comp['flags_novas'] or 'nenhuma'}")
        L.append(f"  Flags resolvidas: {comp['flags_resolvidas'] or 'nenhuma'}")
        L.append(f"  Hiperparâmetros da rodada anterior: {comp['hiperparametros_anteriores']}")
    L.append("")
    L.append("=" * 78)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text("\n".join(L), encoding="utf-8")
