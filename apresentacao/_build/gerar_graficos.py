"""Gera os graficos da apresentacao (estilo Mackenzie: fundo branco, vermelho
#EB0029 de destaque, sem preto solido) a partir dos artefatos ja oficiais da
modelagem (dados/modelos/, rodada base completa) e dos numeros documentados
em docs/05-plano-de-modelagem.md (forca de associacao da EDA).

Nao retreina nada — so recarrega os 3 modelos/preprocessadores salvos e o
parquet da Gold pra recalcular a curva ROC no mesmo split temporal oficial.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.metrics import roc_curve

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from src.modelagem import treino  # noqa: E402

SAIDA = Path(__file__).resolve().parent.parent / "_assets_graficos"
SAIDA.mkdir(parents=True, exist_ok=True)

VERMELHO = "#EB0029"
PRETO = "#1A1A1A"
CINZA = "#8C8C8C"
CINZA_CLARO = "#E7E7E7"
BRANCO_TXT = "#FFFFFF"

plt.rcParams.update(
    {
        "font.family": "Arial",
        "text.color": PRETO,
        "axes.edgecolor": CINZA_CLARO,
        "axes.labelcolor": PRETO,
        "xtick.color": PRETO,
        "ytick.color": PRETO,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
    }
)


def salvar(fig, nome: str) -> None:
    caminho = SAIDA / nome
    fig.savefig(caminho, dpi=220, bbox_inches="tight", transparent=False)
    plt.close(fig)
    print(f"[ok] {caminho}")


def grafico_barh(labels, valores, titulo_arquivo, cor_destaque_idx=None, fmt="{:.3f}", figsize=(7.4, 3.6)):
    labels = labels[::-1]
    valores = valores[::-1]
    fig, ax = plt.subplots(figsize=figsize)
    cores = [VERMELHO] * len(valores)
    barras = ax.barh(labels, valores, color=cores, height=0.6, zorder=3)
    ax.set_xlim(0, max(valores) * 1.22)
    for spine in ("top", "right", "bottom", "left"):
        ax.spines[spine].set_visible(False)
    ax.set_xticks([])
    ax.tick_params(axis="y", length=0, labelsize=13.5)
    for barra, valor in zip(barras, valores):
        ax.text(
            barra.get_width() + max(valores) * 0.02,
            barra.get_y() + barra.get_height() / 2,
            fmt.format(valor),
            va="center",
            ha="left",
            fontsize=13,
            fontweight="bold",
            color=PRETO,
        )
    fig.tight_layout()
    salvar(fig, titulo_arquivo)


def grafico_eda_top_features():
    # V de Cramer / ponto-bisserial — docs/05-plano-de-modelagem.md secao 5
    dados = [
        ("Tamanho do negócio", 0.570),
        ("É temporário?", 0.460),
        ("Setor de atividade", 0.404),
        ("Grupamento ocupacional", 0.373),
        ("Nível de instrução", 0.325),
        ("Horas semanais", 0.272),
    ]
    labels = [d[0] for d in dados]
    valores = [d[1] for d in dados]
    grafico_barh(labels, valores, "fig_eda_top_features.png")


def grafico_shap_campeao():
    # SHAP (|valor| medio) do HistGradientBoosting — dashboard/modelagem_informalidade.html
    dados = [
        ("É temporário?", 1.224),
        ("Tamanho do negócio", 0.997),
        ("Horas semanais", 0.527),
        ("Grupamento ocupacional", 0.196),
        ("Nível de instrução", 0.157),
        ("Setor de atividade", 0.132),
    ]
    labels = [d[0] for d in dados]
    valores = [d[1] for d in dados]
    grafico_barh(labels, valores, "fig_shap_top_features.png", fmt="{:.2f}")


def _carregar_predicoes_teste():
    """Carrega os 3 modelos oficiais e retorna predicoes no teste (2025) —
    usado por grafico_roc() e grafico_confusao() para nao duplicar a leitura
    da Gold (2,5M linhas) duas vezes."""
    caminho_modelos = RAIZ / "dados" / "modelos"
    gold = pd.read_parquet(RAIZ / "dados" / "gold" / "dados_gold.parquet")
    _, x_teste, _, y_teste = treino.split_temporal(gold)

    resultado = {}
    for nome, arquivo in [
        ("HistGradientBoosting", "histgradientboosting"),
        ("Random Forest", "randomforest"),
        ("Regressão Logística", "logisticregression"),
    ]:
        modelo = joblib.load(caminho_modelos / f"{arquivo}.joblib")
        caminho_preproc = caminho_modelos / f"{arquivo}_preprocessador.joblib"
        if caminho_preproc.exists():
            x_proc = joblib.load(caminho_preproc).transform(x_teste)
        else:
            x_proc = treino.preparar_x_categorica(x_teste)
        proba = modelo.predict_proba(x_proc)[:, 1]
        pred = modelo.predict(x_proc)
        resultado[nome] = {"proba": proba, "pred": pred}
    return y_teste, resultado


def grafico_roc(y_teste, predicoes):
    from sklearn.metrics import auc as auc_fn

    estilos = {
        "HistGradientBoosting": (VERMELHO, "-", 3.4),
        "Random Forest": (PRETO, "--", 2.2),
        "Regressão Logística": (CINZA, ":", 2.2),
    }

    fig, ax = plt.subplots(figsize=(6.6, 6.0))
    ax.plot([0, 1], [0, 1], color=CINZA_CLARO, linewidth=1.6, zorder=1)

    for nome, (cor, estilo, largura) in estilos.items():
        fpr, tpr, _ = roc_curve(y_teste, predicoes[nome]["proba"])
        auc_valor = auc_fn(fpr, tpr)
        ax.plot(
            fpr, tpr, color=cor, linestyle=estilo, linewidth=largura,
            label=f"{nome}  (AUC {auc_valor:.3f})", zorder=3,
        )

    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("Taxa de falsos positivos", fontsize=12)
    ax.set_ylabel("Taxa de verdadeiros positivos", fontsize=12)
    ax.tick_params(labelsize=11)
    ax.legend(loc="lower right", fontsize=11.5, frameon=False)
    fig.tight_layout()
    salvar(fig, "fig_roc.png")


def grafico_confusao(y_teste, predicoes):
    from sklearn.metrics import confusion_matrix

    ordem = ["HistGradientBoosting", "Random Forest", "Regressão Logística"]
    fig, eixos = plt.subplots(1, 3, figsize=(11.5, 3.7))
    for ax, nome in zip(eixos, ordem):
        cm = confusion_matrix(y_teste, predicoes[nome]["pred"])
        total = cm.sum()
        ax.imshow(cm, cmap="Reds", vmin=0, vmax=cm.max() * 1.15)
        for i in range(2):
            for j in range(2):
                valor = cm[i, j]
                cor_texto = BRANCO_TXT if valor > cm.max() * 0.6 else PRETO
                ax.text(j, i, f"{valor:,}".replace(",", "."), ha="center", va="center",
                        fontsize=13, fontweight="bold", color=cor_texto)
        ax.set_xticks([0, 1])
        ax.set_yticks([0, 1])
        ax.set_xticklabels(["Formal", "Informal"], fontsize=10.5)
        ax.set_yticklabels(["Formal", "Informal"], fontsize=10.5)
        ax.set_xlabel("Previsto", fontsize=10.5, color=CINZA)
        if nome == ordem[0]:
            ax.set_ylabel("Real", fontsize=10.5, color=CINZA)
        ax.set_title(nome, fontsize=12.5, fontweight="bold", color=PRETO, pad=8)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.tick_params(length=0)
    fig.tight_layout()
    salvar(fig, "fig_confusao.png")


def grafico_indice_concentracao():
    """Indice de concentracao (razao informal/formal) combinando escolaridade
    e setor de atividade num unico ranking, escala log2 (simetrica em torno
    de 1x = mesma proporcao). So as 3 categorias mais extremas ganham cor —
    as outras 10 ficam cinza, sem competir por atencao — tecnica de
    "highlight + grey out" (Knaflic, Storytelling with Data: preattentive
    attributes) combinada com titulo de acao (McKinsey: takeaway title, nao
    rotulo descritivo). Dados de dashboard/censo_informalidade.html, sec. 02."""
    dados = [
        ("Sem instrução", 5, 1),
        ("Agropecuária, pesca e aquicultura", 24, 6),
        ("Serviços domésticos", 10, 3),
        ("Fundamental incompleto", 32, 12),
        ("Construção", 10, 4),
        ("Médio incompleto", 8, 5),
        ("Fundamental completo", 9, 6),
        ("Médio completo", 30, 38),
        ("Superior incompleto", 5, 7),
        ("Comércio e reparação de veículos", 14, 21),
        ("Educação, saúde e serviços sociais", 8, 17),
        ("Indústria geral", 7, 15),
        ("Superior completo", 12, 30),
    ]
    itens = sorted(((nome, informal / formal) for nome, informal, formal in dados), key=lambda t: -t[1])
    categorias = [n for n, _ in itens]
    razoes = [r for _, r in itens]
    logs = [math.log2(r) for r in razoes]

    CINZA_BARRA = "#D3D3D3"
    CINZA_TXT = "#9E9E9E"
    n = len(categorias)
    destaque_topo = {0, 1}
    destaque_base = {n - 1}

    fig, ax = plt.subplots(figsize=(7.8, 5.5))
    y_pos = list(range(n))
    cores = [
        VERMELHO if i in destaque_topo else (PRETO if i in destaque_base else CINZA_BARRA)
        for i in range(n)
    ]
    ax.barh(y_pos, logs, color=cores, height=0.64, zorder=3)
    ax.axvline(0, color=CINZA, linewidth=1.3, zorder=2)

    max_abs = max(abs(v) for v in logs)
    ax.set_xlim(-max_abs * 1.55, max_abs * 1.55)

    for i, (r, lv) in enumerate(zip(razoes, logs)):
        rotulo = f"{r:.1f}x".replace(".", ",")
        destaque = i in destaque_topo or i in destaque_base
        cor_txt = VERMELHO if i in destaque_topo else (PRETO if i in destaque_base else CINZA_TXT)
        peso = "bold" if destaque else "normal"
        tam = 13.5 if destaque else 11
        if lv >= 0:
            ax.text(lv + max_abs * 0.05, i, rotulo, va="center", ha="left",
                     fontsize=tam, fontweight=peso, color=cor_txt)
        else:
            ax.text(lv - max_abs * 0.05, i, rotulo, va="center", ha="right",
                     fontsize=tam, fontweight=peso, color=cor_txt)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(categorias, fontsize=12)
    for i, label in enumerate(ax.get_yticklabels()):
        if i in destaque_topo:
            label.set_color(VERMELHO)
            label.set_fontweight("bold")
        elif i in destaque_base:
            label.set_color(PRETO)
            label.set_fontweight("bold")
        else:
            label.set_color(CINZA_TXT)
    ax.invert_yaxis()
    ax.set_xticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(length=0)

    ax.text(0.0, 1.03, "← mais comum entre formais", transform=ax.transAxes, fontsize=11.5,
             color=PRETO, fontweight="bold", ha="left", va="bottom")
    ax.text(1.0, 1.03, "mais comum entre informais →", transform=ax.transAxes, fontsize=11.5,
             color=VERMELHO, fontweight="bold", ha="right", va="bottom")

    fig.tight_layout()
    salvar(fig, "fig_eda_indice.png")


def grafico_eda_renda():
    # Renda mediana formal x informal — dashboard/censo_informalidade.html
    grupos = ["Formal", "Informal"]
    valores = [2400, 1400]
    cores = [PRETO, VERMELHO]
    fig, ax = plt.subplots(figsize=(4.6, 1.35))
    barras = ax.barh(grupos, valores, color=cores, height=0.55, zorder=3)
    ax.invert_yaxis()
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_xticks([])
    ax.tick_params(axis="y", length=0, labelsize=13)
    max_val = max(valores)
    ax.set_xlim(0, max_val * 1.5)
    for barra, valor in zip(barras, valores):
        ax.text(barra.get_width() + max_val * 0.03, barra.get_y() + barra.get_height() / 2,
                 f"R$ {valor:,.0f}".replace(",", "."), va="center", ha="left",
                 fontsize=13, fontweight="bold", color=PRETO)
    fig.tight_layout()
    salvar(fig, "fig_eda_renda.png")


def grafico_equidade():
    # recall por grupo — Amarelos vs. geral (evidencia do diagnostico oficial)
    grupos = ["Geral", "Amarelos"]
    valores = [0.836, 0.718]
    fig, ax = plt.subplots(figsize=(3.6, 3.9))
    cores = [PRETO, VERMELHO]
    barras = ax.bar(grupos, valores, color=cores, width=0.55, zorder=3)
    ax.set_ylim(0, 1)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(CINZA_CLARO)
    ax.set_yticks([])
    ax.tick_params(axis="x", labelsize=13)
    for barra, valor in zip(barras, valores):
        ax.text(
            barra.get_x() + barra.get_width() / 2,
            barra.get_height() + 0.03,
            f"{valor:.0%}",
            ha="center", va="bottom", fontsize=14, fontweight="bold", color=PRETO,
        )
    ax.set_title("Recall: HistGradientBoosting", fontsize=11.5, color=CINZA, pad=10)
    fig.tight_layout()
    salvar(fig, "fig_equidade.png")


if __name__ == "__main__":
    grafico_eda_top_features()
    grafico_shap_campeao()
    grafico_equidade()
    grafico_indice_concentracao()
    grafico_eda_renda()
    y_teste, predicoes = _carregar_predicoes_teste()
    grafico_roc(y_teste, predicoes)
    grafico_confusao(y_teste, predicoes)
    print("Todos os graficos gerados em", SAIDA)
