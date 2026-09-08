"""Calcula métricas e renderiza o boletim HTML "Censo da Informalidade"
a partir da camada Gold (RF-04).

A Gold já chega filtrada para pessoas ocupadas e com a coluna-alvo
`informal` (ver `src/transformacao/transformacao.py`), então todas as
métricas aqui — idade, horas, renda, correlações — são calculadas sobre
essa população de trabalhadores, não sobre a base completa de
respondentes (diferença sutil em relação à primeira versão manual deste
relatório, que usava a Silver inteira para idade/pessoas no domicílio;
aqui ficou mais consistente: uma métrica só, sempre "entre ocupados").

Usado por:
- `src/analise/analise.py` — gera `dashboard/censo_informalidade.html`
  automaticamente a cada `pipeline.analisar()`, com o dado mais recente.
- `scripts/gerar_boletins_eda.py` — regera sob demanda (ex.: depois de
  reprocessar mais trimestres), sem precisar rodar o pipeline inteiro.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency

ESCALA_MAX_TAXA = 0.8  # domínio do eixo Y dos gráficos de taxa (0-80%)

# As 16 features candidatas discutidas com o time (exclui IDs, o grupo-
# alvo VD4009/V4019/VD4012/VD4002, peso amostral e renda — ver
# `docs/03-dicionario-de-dados.md`). Usado pra medir força de associação
# com `informal` (Seção 05) e ajudar a decidir a lista final do modelo.
FEATURES_CATEGORICAS = {
    "UF": "UF", "V2007": "Sexo", "V2010": "Raça/cor", "V1022": "Urbano/rural",
    "V1023": "Tipo de área", "VD2002": "Posição no domicílio", "VD3004": "Nível de instrução",
    "V3002": "Frequenta escola", "VD4010": "Setor de atividade", "VD4011": "Grupamento ocupacional",
    "V4018": "Tamanho do negócio", "V4025": "É temporário?", "V4040": "Tempo no emprego",
}
FEATURES_NUMERICAS = {"V2009": "Idade", "VD2003": "Pessoas no domicílio", "VD4031": "Horas semanais"}

# Colunas numéricas descritas na Seção 02, e o rótulo exibido.
VARS_DESCRITIVAS = {
    "V2009": "Idade",
    "VD4031": "Horas semanais trabalhadas",
    "VD4016": "Renda habitual",
    "VD2003": "Pessoas no domicílio",
}

# Colunas usadas na matriz de correlação da Seção 03.
VARS_CORRELACAO = ["V2009", "VD2003", "VD4031", "VD4016", "V1028", "VD3004"]
LABELS_CORRELACAO = {
    "V2009": "Idade",
    "VD2003": "Pessoas dom.",
    "VD4031": "Horas/sem.",
    "VD4016": "Renda",
    "V1028": "Peso amostral",
    "VD3004": "Instrução",
}

RACA_LABELS = {1: "Branca", 2: "Preta", 3: "Amarela", 4: "Parda", 5: "Indígena", 9: "Ignorado"}
SEXO_LABELS = {1: "Homem", 2: "Mulher"}

# Rótulos oficiais (dicionário do IBGE, dados/bronze/documentacao/dicionario_
# PNADC_microdados_trimestral.xls) para os recortes que RF-04 pede
# explicitamente e ainda não tinham rótulo decodificado nesta etapa (a
# Silver guarda só o código numérico — ver `src/preprocessamento`).
VD3004_LABELS = {
    1: "Sem instrução / menos de 1 ano de estudo", 2: "Fundamental incompleto", 3: "Fundamental completo",
    4: "Médio incompleto", 5: "Médio completo", 6: "Superior incompleto", 7: "Superior completo",
}
VD4010_LABELS = {
    1: "Agropecuária, pesca e aquicultura", 2: "Indústria geral", 3: "Construção",
    4: "Comércio e reparação de veículos", 5: "Transporte, armazenagem e correio",
    6: "Alojamento e alimentação", 7: "Informação, finanças, imóveis e serv. profissionais",
    8: "Administração pública, defesa e seguridade", 9: "Educação, saúde e serviços sociais",
    10: "Outros serviços", 11: "Serviços domésticos", 12: "Atividades mal definidas",
}
VD4011_LABELS = {
    1: "Diretores e gerentes", 2: "Profissionais das ciências e intelectuais",
    3: "Técnicos de nível médio", 4: "Apoio administrativo",
    5: "Serviços, vendedores do comércio", 6: "Agropecuária, floresta, caça e pesca",
    7: "Construção, artes mecânicas e ofícios", 8: "Operadores de instalações e máquinas",
    9: "Ocupações elementares", 10: "Forças armadas e policiais", 11: "Ocupações mal definidas",
}
V4018_LABELS = {1: "1–5 pessoas", 2: "6–10 pessoas", 3: "11–50 pessoas", 4: "51+ pessoas"}
V4040_LABELS = {1: "Menos de 1 mês", 2: "1 mês – 1 ano", 3: "1 – 2 anos", 4: "2+ anos"}

# UF -> Região (divisão oficial do IBGE) — usada pra segmentar a taxa de
# informalidade por região (Seção 03), um recorte que a análise isolada por
# UF não deixa claro de tão fragmentada (27 categorias).
REGIAO_MAP = {
    11: "Norte", 12: "Norte", 13: "Norte", 14: "Norte", 15: "Norte", 16: "Norte", 17: "Norte",
    21: "Nordeste", 22: "Nordeste", 23: "Nordeste", 24: "Nordeste", 25: "Nordeste",
    26: "Nordeste", 27: "Nordeste", 28: "Nordeste", 29: "Nordeste",
    31: "Sudeste", 32: "Sudeste", 33: "Sudeste", 35: "Sudeste",
    41: "Sul", 42: "Sul", 43: "Sul",
    50: "Centro-Oeste", 51: "Centro-Oeste", 52: "Centro-Oeste", 53: "Centro-Oeste",
}

# VD4002 (Condição de ocupação) só é preenchida para quem está na força de
# trabalho e tem 14+ anos — código 1 (ocupados) já vira a Gold, ver
# `Transformacao`; usado aqui para reconstruir o funil de exclusão da Seção
# 00 a partir da Silver/amostra completa (antes do filtro de ocupados).
CODIGO_OCUPADO = 1
CODIGO_DESOCUPADO = 2
IDADE_MINIMA_FORCA_TRABALHO = 14

# Grupos de variáveis pra Seção 04 (percentual de nulo) — precisa da
# Silver (não só da Gold, que já veio filtrada) pra calcular corretamente
# contra a base inteira de respondentes.
GRUPOS_NULOS = [
    ("Identificação, demografia, domicílio, peso amostral",
     ["Ano", "Trimestre", "UF", "V2007", "V2010", "V2009", "VD2002", "VD2003", "V1022", "V1023", "V1028"]),
    ("Educação", ["VD3004", "V3002"]),
    ("Filtro de ocupação", ["VD4002"]),
    ("Posição ocupação, setor, horas", ["VD4009", "VD4012", "VD4010", "VD4011", "V4040", "VD4031"]),
    ("Renda", ["VD4016", "VD4017"]),
    ("Tamanho do negócio", ["V4018"]),
    ("Emprego temporário", ["V4025"]),
    ("Tem CNPJ", ["V4019"]),
]


def calcular_metricas(gold: pd.DataFrame, silver: pd.DataFrame | None = None) -> dict:
    """Calcula todas as métricas usadas no boletim a partir da Gold
    (ocupados, já com `informal`). `silver` é opcional — só é usada pra
    Seção 04 (percentual de nulo precisa da base inteira, antes do
    filtro de ocupados); se não for passada, a seção é omitida.
    """
    m: dict = {}
    m["n_ocupados"] = int(len(gold))
    m["taxa_geral"] = float(gold["informal"].mean())
    m["ano_min"] = int(gold["Ano"].min())
    m["ano_max"] = int(gold["Ano"].max())
    m["n_trimestres"] = gold[["Ano", "Trimestre"]].drop_duplicates().shape[0]

    periodo = (
        gold.groupby(["Ano", "Trimestre"])
        .agg(n=("informal", "size"), taxa=("informal", "mean"))
        .reset_index()
        .sort_values(["Ano", "Trimestre"])
    )
    periodo["label"] = periodo["Ano"].astype(str) + "Q" + periodo["Trimestre"].astype(str)
    m["periodo_rows"] = periodo.to_dict("records")
    m["taxa_min"] = float(periodo["taxa"].min())
    m["taxa_max"] = float(periodo["taxa"].max())
    m["periodo_taxa_min"] = periodo.loc[periodo["taxa"].idxmin(), "label"]
    m["periodo_taxa_max"] = periodo.loc[periodo["taxa"].idxmax(), "label"]
    # tendência: primeiro vs último ano (só é um sinal confiável com >=2 anos)
    taxa_por_ano = gold.groupby("Ano")["informal"].mean()
    m["tendencia_disponivel"] = len(taxa_por_ano) >= 2
    if m["tendencia_disponivel"]:
        m["tendencia_delta_pp"] = 100 * (taxa_por_ano.iloc[-1] - taxa_por_ano.iloc[0])

    m["descritivas"] = {}
    for col, label in VARS_DESCRITIVAS.items():
        serie = gold[col].dropna()
        if serie.empty:
            continue
        hist_counts, hist_bins = np.histogram(serie, bins=10)
        m["descritivas"][col] = {
            "label": label,
            "n": int(serie.count()),
            "mean": float(serie.mean()),
            "median": float(serie.median()),
            "std": float(serie.std()),
            "min": float(serie.min()),
            "max": float(serie.max()),
            "p25": float(serie.quantile(0.25)),
            "p75": float(serie.quantile(0.75)),
            "hist_counts": hist_counts.tolist(),
            "hist_bins": hist_bins.tolist(),
        }
        q1, q3 = serie.quantile(0.25), serie.quantile(0.75)
        iqr = q3 - q1
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        n_out = int(((serie < lo) | (serie > hi)).sum())
        m["descritivas"][col]["outliers_n"] = n_out
        m["descritivas"][col]["outliers_pct"] = round(100 * n_out / len(serie), 2)

    cols_presentes = [c for c in VARS_CORRELACAO if c in gold.columns]
    m["correlacao_colunas"] = cols_presentes
    m["correlacao_matriz"] = gold[cols_presentes].corr(method="pearson").round(3).values.tolist()

    pb = {}
    for col in ["V2009", "VD4031", "VD3004", "VD2003"]:
        sub = gold[[col, "informal"]].dropna()
        if len(sub) > 5:
            pb[col] = float(sub[col].corr(sub["informal"].astype(int)))
    m["ponto_bisserial"] = pb

    m["sexo_rows"] = _sexo_rows(gold)
    m["raca_rows"] = _raca_rows(gold)
    m["regiao_rows"] = _regiao_rows(gold)
    m["segmentacao_por_ano"] = _segmentacao_por_ano(gold, m["sexo_rows"], m["raca_rows"], m["regiao_rows"])

    # Recortes adicionais exigidos por RF-04 (escolaridade, setor, ocupação,
    # tamanho do negócio, tempo no emprego) — não entram no filtro por ano
    # (JS), só na visão agregada do período inteiro.
    m["escolaridade_rows"] = _categoria_rows(gold, "VD3004", VD3004_LABELS, ordenar_por_codigo=True)
    m["setor_rows"] = _categoria_rows(gold, "VD4010", VD4010_LABELS)
    m["ocupacao_rows"] = _categoria_rows(gold, "VD4011", VD4011_LABELS)
    m["tamanho_negocio_rows"] = _categoria_rows(gold, "V4018", V4018_LABELS, ordenar_por_codigo=True)
    m["tempo_emprego_rows"] = _categoria_rows(gold, "V4040", V4040_LABELS, ordenar_por_codigo=True)

    m["renda_gap"] = _calcular_renda_gap(gold)

    m["features_forca"] = _calcular_forca_features(gold)

    if silver is not None and not silver.empty:
        nulos_pct = (silver.isna().mean() * 100)
        m["n_silver_total"] = int(len(silver))
        m["nulos_grupos"] = [
            {"label": nome, "colunas": cols, "pct": round(float(nulos_pct[cols].iloc[0]), 2)}
            for nome, cols in GRUPOS_NULOS
            if all(c in nulos_pct.index for c in cols)
        ]
        if "V2009" in silver.columns and "VD4002" in silver.columns:
            m["funil"] = _calcular_funil(silver)

    return m


def _sexo_rows(df: pd.DataFrame) -> list[dict]:
    sexo = df.groupby("V2007").agg(n=("informal", "size"), taxa=("informal", "mean")).reset_index()
    return [
        {"label": SEXO_LABELS.get(int(r["V2007"]), str(r["V2007"])), "n": int(r["n"]), "taxa": float(r["taxa"])}
        for _, r in sexo.iterrows()
    ]


def _raca_rows(df: pd.DataFrame) -> list[dict]:
    raca = df.groupby("V2010").agg(n=("informal", "size"), taxa=("informal", "mean")).reset_index()
    rows = [
        {"label": RACA_LABELS.get(int(r["V2010"]), str(r["V2010"])), "n": int(r["n"]), "taxa": float(r["taxa"])}
        for _, r in raca.iterrows()
    ]
    return sorted(rows, key=lambda r: -r["taxa"])


def _categoria_rows(
    df: pd.DataFrame, coluna: str, labels: dict | None = None, ordenar_por_codigo: bool = False
) -> list[dict]:
    """Taxa de informalidade por categoria de uma variável qualquer — usado
    pelos recortes de escolaridade, setor, ocupação, tamanho do negócio e
    tempo no emprego que RF-04 pede explicitamente (ver
    `docs/01-requisitos-funcionais.md`), além de sexo/raça/região.
    `ordenar_por_codigo=True` mantém a ordem natural de variáveis ordinais
    (ex.: escolaridade crescente) em vez de ordenar pela taxa.
    """
    if coluna not in df.columns:
        return []
    sub = df[[coluna, "informal"]].dropna()
    if sub.empty:
        return []
    grupo = sub.groupby(coluna).agg(n=("informal", "size"), taxa=("informal", "mean")).reset_index()
    rows = [
        {
            "label": (labels or {}).get(int(r[coluna]), str(int(r[coluna]))),
            "n": int(r["n"]),
            "taxa": float(r["taxa"]),
            "codigo": int(r[coluna]),
        }
        for _, r in grupo.iterrows()
    ]
    return sorted(rows, key=lambda r: r["codigo"]) if ordenar_por_codigo else sorted(rows, key=lambda r: -r["taxa"])


def _calcular_renda_gap(gold: pd.DataFrame) -> dict | None:
    """Compara renda habitual (`VD4016`) entre formais e informais — a
    variável não entra como feature (data leakage, ver
    `docs/03-dicionario-de-dados.md`), mas o gap salarial é o contexto
    econômico que RF-04 pede mostrar mesmo sem virar preditor.
    """
    if "VD4016" not in gold.columns:
        return None
    sub = gold[["VD4016", "informal"]].dropna()
    if sub.empty:
        return None
    grupos: dict = {}
    for valor, chave in [(False, "formal"), (True, "informal")]:
        serie = sub.loc[sub["informal"] == valor, "VD4016"]
        if serie.empty:
            continue
        grupos[chave] = {"n": int(len(serie)), "media": float(serie.mean()), "mediana": float(serie.median())}
    return grupos if len(grupos) == 2 else None


def _regiao_rows(df: pd.DataFrame) -> list[dict]:
    """Taxa de informalidade por região (agrega as 27 UFs em 5 regiões) —
    segmentação explícita que a matriz de correlação e o ranking de
    features (que trata UF como uma única variável de 27 categorias) não
    deixam visível.
    """
    sub = df[["UF", "informal"]].dropna().copy()
    sub["regiao"] = sub["UF"].astype(int).map(REGIAO_MAP)
    sub = sub.dropna(subset=["regiao"])
    grupo = sub.groupby("regiao").agg(n=("informal", "size"), taxa=("informal", "mean")).reset_index()
    rows = [{"label": r["regiao"], "n": int(r["n"]), "taxa": float(r["taxa"])} for _, r in grupo.iterrows()]
    return sorted(rows, key=lambda r: -r["taxa"])


def _segmentacao_por_ano(
    gold: pd.DataFrame, sexo_rows_todos: list[dict], raca_rows_todos: list[dict], regiao_rows_todos: list[dict]
) -> dict:
    """Recorta sexo/raça/região por ano — dado embarcado no HTML e lido por
    JS para o filtro "Ano" da Seção 03, sem precisar de backend. `"todos"`
    reaproveita as linhas já calculadas sobre a Gold inteira (evita
    recalcular a mesma coisa duas vezes).
    """
    resultado = {
        "todos": {
            "n_ocupados": int(len(gold)),
            "taxa_geral": float(gold["informal"].mean()),
            "sexo_rows": sexo_rows_todos,
            "raca_rows": raca_rows_todos,
            "regiao_rows": regiao_rows_todos,
        }
    }
    for ano in sorted(gold["Ano"].dropna().unique().tolist()):
        sub = gold[gold["Ano"] == ano]
        resultado[str(int(ano))] = {
            "n_ocupados": int(len(sub)),
            "taxa_geral": float(sub["informal"].mean()),
            "sexo_rows": _sexo_rows(sub),
            "raca_rows": _raca_rows(sub),
            "regiao_rows": _regiao_rows(sub),
        }
    return resultado


def _calcular_funil(silver: pd.DataFrame) -> dict:
    """Reconstrói, a partir da Silver (ou amostra) completa — antes do
    filtro de ocupados que gera a Gold —, quem fica de fora da análise e
    por quê. `VD4002` só é preenchido para quem tem 14+ anos e está na
    força de trabalho (ver dicionário oficial da PNAD); por isso o grupo
    "fora da força de trabalho" abaixo é uma aproximação por exclusão
    (14+ com `VD4002` nulo), não vem de uma variável dedicada — a Silver
    não ingere `VD4001` (força de trabalho), que discriminaria com
    precisão. Ver Seção 00 do boletim.
    """
    total = len(silver)
    menor_14 = silver["V2009"] < IDADE_MINIMA_FORCA_TRABALHO
    adultos = silver.loc[~menor_14]

    def _resumo(sub: pd.DataFrame, n_total_base: int, label: str) -> dict:
        n = len(sub)
        return {
            "label": label,
            "n": n,
            "pct_total": round(100 * n / n_total_base, 1) if n_total_base else 0.0,
            "pct_mulheres": float((sub["V2007"] == 2).mean()) if n and "V2007" in sub.columns else None,
            "idade_media": float(sub["V2009"].mean()) if n else None,
        }

    grupos = [
        _resumo(silver.loc[menor_14], total, f"Menor de {IDADE_MINIMA_FORCA_TRABALHO} anos (fora do universo da pergunta)"),
        _resumo(adultos.loc[adultos["VD4002"].isna()], total, "Fora da força de trabalho (14+ anos — aprox. por exclusão)"),
        _resumo(adultos.loc[adultos["VD4002"] == CODIGO_DESOCUPADO], total, "Desocupados — buscando trabalho"),
        _resumo(adultos.loc[adultos["VD4002"] == CODIGO_OCUPADO], total, "Ocupados — população analisada a partir daqui"),
    ]
    return {"total": total, "grupos": grupos}


def _calcular_forca_features(gold: pd.DataFrame) -> list[dict]:
    """Mede a força de associação de cada feature candidata com o alvo
    `informal`: V de Cramér para categóricas (baseado em qui-quadrado,
    0=nenhuma associação, 1=perfeita), |r| ponto-bisserial para
    numéricas — escalas comparáveis entre si (convenção usual: <0.1
    muito fraca, 0.1-0.3 fraca/moderada, 0.3-0.5 moderada/forte, >0.5
    forte). Serve pra decidir a lista final de features do modelo
    (RF-05) com evidência, não só intuição.
    """
    resultados = []
    for col, label in FEATURES_CATEGORICAS.items():
        if col not in gold.columns:
            continue
        sub = gold[[col, "informal"]].dropna()
        if sub.empty or sub[col].nunique() < 2:
            continue
        tabela = pd.crosstab(sub[col], sub["informal"])
        chi2 = chi2_contingency(tabela)[0]
        n = int(tabela.sum().sum())
        k = min(tabela.shape) - 1
        forca = float(np.sqrt(chi2 / (n * k))) if k > 0 else 0.0
        resultados.append({"col": col, "label": label, "tipo": "categórica", "forca": forca, "n": n})

    for col, label in FEATURES_NUMERICAS.items():
        if col not in gold.columns:
            continue
        sub = gold[[col, "informal"]].dropna()
        if sub.empty:
            continue
        r = float(sub[col].corr(sub["informal"].astype(int)))
        resultados.append({"col": col, "label": label, "tipo": "numérica", "forca": abs(r), "n": len(sub)})

    return sorted(resultados, key=lambda r: -r["forca"])


def _feature_ranking_rows(rows: list[dict], escala_max: float = 0.6) -> str:
    linhas = []
    for r in rows:
        largura = min(100 * r["forca"] / escala_max, 100)
        fraca = r["forca"] < 0.05
        classe = " thin" if fraca else ""
        linhas.append(
            f'<div class="hbar-row{classe}"><div class="hbar-label">{r["label"]}</div>'
            f'<div class="hbar-track"><div class="hbar-fill" style="width:{largura:.1f}%"></div></div>'
            f'<div class="hbar-val">{r["forca"]:.3f} · n={r["n"]:,}</div></div>'.replace(",", ".")
        )
    return '<div class="hbar-rows">' + "".join(linhas) + "</div>"


# ---------------------------------------------------------------------
# Fragmentos HTML (SVG/CSS) construídos a partir das métricas acima.
# ---------------------------------------------------------------------

def _linha_chart_svg(periodo_rows: list[dict]) -> str:
    n = len(periodo_rows)
    pad_l, pad_r, pad_t, pad_b = 40, 10, 20, 30
    w, h = 960, 300
    plot_w, plot_h = w - pad_l - pad_r, h - pad_t - pad_b

    def x_of(i: int) -> float:
        return pad_l + i * (plot_w / (n - 1)) if n > 1 else pad_l

    def y_of(v: float) -> float:
        return pad_t + (ESCALA_MAX_TAXA - v) / ESCALA_MAX_TAXA * plot_h

    pontos = [(x_of(i), y_of(r["taxa"])) for i, r in enumerate(periodo_rows)]
    linha = " L ".join(f"{x:.1f},{y:.1f}" for x, y in pontos)
    area = f"M {linha} L {pontos[-1][0]:.1f},{pad_t + plot_h} L {pontos[0][0]:.1f},{pad_t + plot_h} Z"

    circulos = "\n".join(
        f'<circle class="pt" cx="{x:.1f}" cy="{y:.1f}" r="4.5" tabindex="0">'
        f'<title>{r["label"]} — taxa {r["taxa"]*100:.1f}% (n={r["n"]:,})</title></circle>'.replace(",", ".")
        for (x, y), r in zip(pontos, periodo_rows)
    )
    rotulos_x = "\n".join(
        f'<text class="axis-x" x="{x:.1f}" y="{h-8}">{r["label"] if r["label"].endswith("Q1") else r["label"][-2:]}</text>'
        for (x, _), r in zip(pontos, periodo_rows)
    )
    y_labels = "".join(
        f'<text class="axis-y-label" x="34" y="{pad_t + (ESCALA_MAX_TAXA - v) / ESCALA_MAX_TAXA * plot_h + 4:.1f}" text-anchor="end">{int(v*100)}%</text>'
        for v in [0.8, 0.6, 0.4, 0.2, 0.0]
    )
    grid_lines = "".join(
        f'<line class="grid-line" x1="{pad_l}" y1="{pad_t + (ESCALA_MAX_TAXA - v) / ESCALA_MAX_TAXA * plot_h:.1f}" '
        f'x2="{w-pad_r}" y2="{pad_t + (ESCALA_MAX_TAXA - v) / ESCALA_MAX_TAXA * plot_h:.1f}" '
        f'{"style=\"stroke:var(--border-strong)\"" if v == 0 else ""}/>'
        for v in [0.8, 0.6, 0.4, 0.2, 0.0]
    )
    return f'''<svg class="linechart-svg" viewBox="0 0 {w} {h}" role="img" aria-label="Taxa de informalidade por trimestre">
        {grid_lines}
        {y_labels}
        <path class="area-fill" d="{area}"/>
        <path class="line-path" d="M {linha}"/>
        {circulos}
        {rotulos_x}
      </svg>'''


def _hist_bars(hist_counts: list[int], hist_bins: list[float]) -> str:
    maximo = max(hist_counts) or 1
    cols = []
    for i, c in enumerate(hist_counts):
        lo, hi = hist_bins[i], hist_bins[i + 1]
        altura = 100 * c / maximo
        cols.append(f'<div class="hist-col"><div class="hist-bar" style="height:{altura:.1f}%"></div><div class="hist-lbl">{lo:.0f}-{hi:.0f}</div></div>')
    return '<div class="hist-row">' + "".join(cols) + "</div>"


def _heatmap(colunas: list[str], matriz: list[list[float]]) -> str:
    labels = [LABELS_CORRELACAO.get(c, c) for c in colunas]
    colheads = "".join(f'<div class="heat-colhead">{lbl}</div>' for lbl in labels)
    linhas = []
    for i, rowlab in enumerate(labels):
        linhas.append(f'<div class="heat-rowhead">{rowlab}</div>')
        for j, collab in enumerate(labels):
            v = matriz[i][j]
            a = min(0.06 + min(abs(v), 1.0) * 0.75, 0.87)
            cor = f"rgba(42,120,214,{a:.2f})" if v >= 0 else f"rgba(227,73,72,{a:.2f})"
            linhas.append(f'<div class="cell" style="background:{cor}" title="{rowlab} × {collab}: r={v:+.2f}">{v:+.2f}</div>')
    return '<div class="heat"><div class="heat-corner"></div>' + colheads + "".join(linhas) + "</div>"


def _divbar_rows(pb: dict, escala_max: float = 0.40) -> str:
    nomes = {"VD3004": "Nível de instrução", "VD4031": "Horas semanais", "V2009": "Idade", "VD2003": "Pessoas no domicílio"}
    ordenado = sorted(pb.items(), key=lambda kv: -abs(kv[1]))
    linhas = []
    for col, v in ordenado:
        largura = min(100 * abs(v) / escala_max, 100)
        classe = "pos" if v >= 0 else "neg"
        cor = "var(--accent-ink)" if v >= 0 else "var(--negative)"
        linhas.append(
            f'<div class="div-row"><div class="div-label">{nomes.get(col, col)}</div>'
            f'<div class="div-track"><div class="div-mid"></div><div class="div-bar {classe}" style="width:{largura:.1f}%"></div></div>'
            f'<div class="div-val" style="color:{cor}">{v:+.3f}</div></div>'
        )
    return '<div class="div-rows">' + "".join(linhas) + "</div>"


def _hbar_rows(rows: list[dict], escala_max: float = 0.8) -> str:
    linhas = []
    for r in rows:
        largura = min(100 * r["taxa"] / escala_max, 100)
        thin = " thin" if r["n"] < 500 else ""
        linhas.append(
            f'<div class="hbar-row{thin}"><div class="hbar-label">{r["label"]}</div>'
            f'<div class="hbar-track"><div class="hbar-fill" style="width:{largura:.1f}%"></div></div>'
            f'<div class="hbar-val">{r["taxa"]*100:.1f}% · n={r["n"]:,}</div></div>'.replace(",", ".")
        )
    return '<div class="hbar-rows">' + "".join(linhas) + "</div>"


def _stat_card(dados: dict, n_label: str) -> str:
    unidade = " anos" if dados["label"] == "Idade" else (" h" if "Horas" in dados["label"] else "")
    prefixo = "R$ " if "Renda" in dados["label"] else ""
    return f'''<div class="stat-card">
        <div class="stat-name">{dados["label"]}</div><div class="stat-n">{n_label}</div>
        <div class="stat-rows">
          <div class="stat-r hl"><span class="k">Média</span><span class="v">{prefixo}{dados["mean"]:,.1f}{unidade}</span></div>
          <div class="stat-r"><span class="k">Mediana</span><span class="v">{prefixo}{dados["median"]:,.1f}</span></div>
          <div class="stat-r"><span class="k">Desvio-padrão</span><span class="v">{prefixo}{dados["std"]:,.1f}</span></div>
          <div class="stat-r"><span class="k">P25 – P75</span><span class="v">{dados["p25"]:,.0f} – {dados["p75"]:,.0f}</span></div>
          <div class="stat-r"><span class="k">Min – Max</span><span class="v">{dados["min"]:,.0f} – {dados["max"]:,.0f}</span></div>
        </div>
      </div>'''.replace(",", ".")


def _null_rows(grupos: list[dict]) -> str:
    linhas = []
    for g in grupos:
        classe_zero = " zero" if g["pct"] < 0.5 else ""
        cols_txt = " · ".join(g["colunas"][:6]) + (" ..." if len(g["colunas"]) > 6 else "")
        linhas.append(
            f'<div class="null-row"><div class="null-label">{g["label"]}<span class="cols">{cols_txt}</span></div>'
            f'<div class="null-track"><div class="null-fill{classe_zero}" style="width:{max(g["pct"],0.5):.1f}%"></div></div>'
            f'<div class="null-val">{g["pct"]:.2f}%</div></div>'
        )
    return '<div class="null-rows">' + "".join(linhas) + "</div>"


def _renda_gap_html(renda_gap: dict) -> str:
    linhas = []
    for chave, titulo in [("formal", "Formal"), ("informal", "Informal")]:
        g = renda_gap.get(chave)
        if not g:
            continue
        n_fmt = f'{g["n"]:,}'.replace(",", ".")
        media_fmt = f'{g["media"]:,.0f}'.replace(",", ".")
        mediana_fmt = f'{g["mediana"]:,.0f}'.replace(",", ".")
        linhas.append(f'<tr><td>{titulo}</td><td>{n_fmt}</td><td>R$ {media_fmt}</td><td>R$ {mediana_fmt}</td></tr>')
    tabela = f'''<table class="data">
      <thead><tr><th>Grupo</th><th>N</th><th>Renda média</th><th>Renda mediana</th></tr></thead>
      <tbody>{"".join(linhas)}</tbody>
    </table>'''
    formal, informal = renda_gap.get("formal"), renda_gap.get("informal")
    caption = ""
    if formal and informal and formal["mediana"]:
        gap_pct = 100 * (formal["mediana"] - informal["mediana"]) / formal["mediana"]
        caption = (
            f'<p class="panel-caption">Quem é informal ganha, em mediana, <b>{gap_pct:.0f}% menos</b> que quem é '
            f'formal — contexto econômico do problema, não feature do modelo (data leakage; ver '
            f'<code>docs/03-dicionario-de-dados.md</code>).</p>'
        )
    return f'''<div class="panel" style="margin-left:0;">
        <div class="panel-head"><div class="panel-title">Renda: gap salarial formal x informal</div><div class="panel-note">rendimento habitual (VD4016)</div></div>
        {tabela}{caption}
      </div>'''


def _highlights_html(m: dict) -> str:
    """Resumo executivo no topo do boletim — o que a EDA já responde, antes
    de qualquer gráfico. RF-05/RF-06 (modelo + SHAP) devem confirmar estes
    pontos com evidência mais forte, não descobri-los do zero.
    """
    bullets = []
    n_fmt = f'{m["n_ocupados"]:,}'.replace(",", ".")
    bullets.append(
        f'Taxa geral de informalidade: <b>{m["taxa_geral"]*100:.1f}%</b> entre {n_fmt} pessoas ocupadas '
        f'({m["ano_min"]}–{m["ano_max"]}).'
    )

    forca = m.get("features_forca") or []
    if forca:
        top = forca[0]
        bullets.append(
            f'<b>{top["label"]}</b> é a variável isolada mais associada à informalidade (força={top["forca"]:.2f}, '
            f'Seção 05) — candidata a maior peso no modelo.'
        )

    regiao = m.get("regiao_rows") or []
    if len(regiao) >= 2:
        maior, menor = regiao[0], regiao[-1]
        gap = 100 * (maior["taxa"] - menor["taxa"])
        bullets.append(
            f'<b>{maior["label"]}</b> ({maior["taxa"]*100:.1f}%) tem informalidade {gap:.0f} pontos percentuais maior '
            f'que <b>{menor["label"]}</b> ({menor["taxa"]*100:.1f}%) — a variação regional supera a por sexo.'
        )

    renda_gap = m.get("renda_gap")
    if renda_gap and renda_gap.get("formal") and renda_gap.get("informal") and renda_gap["formal"]["mediana"]:
        f_, i_ = renda_gap["formal"], renda_gap["informal"]
        gap_pct = 100 * (f_["mediana"] - i_["mediana"]) / f_["mediana"]
        bullets.append(f'Trabalhadores informais ganham, em mediana, <b>{gap_pct:.0f}% menos</b> que formais (Seção 02).')

    if m.get("tendencia_disponivel") and abs(m["tendencia_delta_pp"]) >= 0.5:
        delta = m["tendencia_delta_pp"]
        direcao = "queda" if delta < 0 else "alta"
        bullets.append(f'Tendência do primeiro ao último ano da base: <b>{direcao} de {abs(delta):.1f} ponto(s) percentuais</b>.')

    funil = m.get("funil")
    if funil:
        ocupados = next((g for g in funil["grupos"] if g["label"].startswith("Ocupados")), None)
        if ocupados:
            bullets.append(
                f'A análise cobre <b>{ocupados["pct_total"]:.0f}%</b> da base bruta (pessoas ocupadas) — Seção 00 mostra '
                f'quem fica de fora e por quê, incluindo indício de viés de seleção por sexo.'
            )

    itens = "".join(f"<li>{b}</li>" for b in bullets)
    return f'<div class="callout"><div class="callout-head">Principais achados — o que o modelo (RF-05/06) deve confirmar</div><ul>{itens}</ul></div>'


def _secao_funil_html(funil: dict, base_label: str) -> str:
    total_fmt = f'{funil["total"]:,}'.replace(",", ".")
    return f'''<section class="block">
        <div class="sec-head"><span class="sec-num">00</span><h2>Quem fica de fora: da base bruta à população analisada</h2></div>
        <p class="sec-intro">Toda estatística de informalidade daqui em diante descreve só pessoas ocupadas (<code>VD4002=1</code>) — não a população total. Dos {total_fmt} registros da {base_label}, a tabela mostra cada corte aplicado e como o grupo cortado se compara, em sexo e idade, a quem segue na análise.</p>
        <div class="panel">{_funil_table(funil)}{_funil_interpretacao(funil)}</div>
      </section>'''


def _secao_segmentacao_extra(m: dict) -> str:
    """Painel de região + filtro por ano, adicionado ao final da Seção 03
    (correlações/relações) em ambos os boletins — mesmo bloco de dados
    (`segmentacao_por_ano`) já calculado em `calcular_metricas`.
    """
    anos = sorted(int(a) for a in m["segmentacao_por_ano"] if a != "todos")
    regiao_html = _hbar_rows(m["regiao_rows"])
    n_ocupados_fmt = f'{m["n_ocupados"]:,}'.replace(",", ".")
    kpis_html = f'''<div class="seg-kpis">
          <span class="kpi-mini">Ocupados no recorte: <b id="seg-kpi-n">{n_ocupados_fmt}</b></span>
          <span class="kpi-mini">Taxa: <b id="seg-kpi-taxa">{m["taxa_geral"]*100:.1f}%</b></span>
        </div>'''
    return f'''{_select_ano_html(anos, kpis_html)}
      <div class="grid-2">
        <div class="panel" style="margin-left:0;"><div class="panel-head"><div class="panel-title">Informalidade por sexo</div></div><div id="panel-sexo-body">{_hbar_rows(m["sexo_rows"])}</div></div>
        <div class="panel" style="margin-left:0;"><div class="panel-head"><div class="panel-title">Informalidade por cor/raça</div></div><div id="panel-raca-body">{_hbar_rows(m["raca_rows"])}</div></div>
      </div>
      <div class="panel" style="margin-top:22px;"><div class="panel-head"><div class="panel-title">Informalidade por região</div></div><div id="panel-regiao-body">{regiao_html}</div></div>
      {_segmentacao_script(m["segmentacao_por_ano"])}
      <p class="sec-intro" style="margin-top:34px;">RF-04 pede ainda os recortes abaixo — escolaridade e tamanho do negócio/tempo no emprego em ordem crescente da própria categoria (não por taxa), pra deixar visível se a tendência é monotônica.</p>
      <div class="grid-2">
        <div class="panel" style="margin-left:0;"><div class="panel-head"><div class="panel-title">Informalidade por escolaridade</div></div>{_hbar_rows(m["escolaridade_rows"])}</div>
        <div class="panel" style="margin-left:0;"><div class="panel-head"><div class="panel-title">Informalidade por tamanho do negócio</div></div>{_hbar_rows(m["tamanho_negocio_rows"])}</div>
      </div>
      <div class="grid-2" style="margin-top:22px;">
        <div class="panel" style="margin-left:0;"><div class="panel-head"><div class="panel-title">Informalidade por tempo no emprego</div></div>{_hbar_rows(m["tempo_emprego_rows"])}</div>
        <div class="panel" style="margin-left:0;"><div class="panel-head"><div class="panel-title">Informalidade por grupamento ocupacional</div></div>{_hbar_rows(m["ocupacao_rows"])}</div>
      </div>
      <div class="panel" style="margin-top:22px;"><div class="panel-head"><div class="panel-title">Informalidade por setor de atividade</div></div>{_hbar_rows(m["setor_rows"])}</div>'''


def _funil_table(funil: dict) -> str:
    linhas = []
    for g in funil["grupos"]:
        n_fmt = f'{g["n"]:,}'.replace(",", ".")
        pct_mulheres = f'{g["pct_mulheres"]*100:.1f}%' if g["pct_mulheres"] is not None else "—"
        idade = f'{g["idade_media"]:.1f} anos' if g["idade_media"] is not None else "—"
        linhas.append(
            f'<tr><td>{g["label"]}</td><td>{n_fmt}</td><td>{g["pct_total"]:.1f}%</td>'
            f'<td>{idade}</td><td>{pct_mulheres}</td></tr>'
        )
    corpo = "".join(linhas)
    return f'''<table class="data">
      <thead><tr><th>Grupo</th><th>N</th><th>% da base bruta</th><th>Idade média</th><th>% mulheres</th></tr></thead>
      <tbody>{corpo}</tbody>
    </table>'''


def _funil_interpretacao(funil: dict) -> str:
    """Frase interpretativa automática sobre o grupo "fora da força de
    trabalho" — sinaliza o indício de viés de seleção por sexo direto nos
    números, em vez de deixar só a tabela pro leitor notar sozinho.
    """
    fora_forca = next((g for g in funil["grupos"] if g["label"].startswith("Fora da força")), None)
    ocupados = next((g for g in funil["grupos"] if g["label"].startswith("Ocupados")), None)
    if not fora_forca or not ocupados or fora_forca["pct_mulheres"] is None or ocupados["pct_mulheres"] is None:
        return ""
    gap = 100 * (fora_forca["pct_mulheres"] - ocupados["pct_mulheres"])
    if abs(gap) < 3:
        return ""
    mulheres_maioria = gap > 0
    lado = "mulheres" if mulheres_maioria else "homens"
    pct_fora = fora_forca["pct_mulheres"] if mulheres_maioria else (1 - fora_forca["pct_mulheres"])
    pct_ocup = ocupados["pct_mulheres"] if mulheres_maioria else (1 - ocupados["pct_mulheres"])
    return (
        f'<p class="panel-caption">O grupo "fora da força de trabalho" tem <b>{pct_fora*100:.0f}% de {lado}</b>, '
        f'contra {pct_ocup*100:.0f}% entre ocupados — '
        f'indício de viés de seleção (quem decide entrar no mercado de trabalho já não é uma amostra aleatória da população; ver hipóteses na Seção 06).</p>'
    )


def _select_ano_html(anos_disponiveis: list[int], kpis_html: str = "") -> str:
    opcoes = '<option value="todos" selected>Todos os anos</option>' + "".join(
        f'<option value="{a}">{a}</option>' for a in anos_disponiveis
    )
    return f'''<div class="filtro-row">
      <label for="filtro-ano">Filtrar segmentação por ano</label>
      <select id="filtro-ano" onchange="aplicarFiltroAno(this.value)">{opcoes}</select>
      {kpis_html}
    </div>'''


def _segmentacao_script(segmentacao_por_ano: dict) -> str:
    """JS standalone que reconstrói sexo/raça/região por ano a partir do
    JSON embarcado — sem backend, tudo pré-calculado em Python e só
    trocado de exibição no cliente. Espelha `_hbar_rows` em JS.
    """
    dados_json = json.dumps(segmentacao_por_ano, ensure_ascii=False).replace("</", "<\\/")
    return f'''<script>
      const DADOS_POR_ANO = {dados_json};
      function _fmtN(n) {{ return n.toLocaleString('pt-BR'); }}
      function _renderHbar(rows, escalaMax) {{
        return rows.map(r => {{
          const largura = Math.min(100 * r.taxa / escalaMax, 100).toFixed(1);
          const thin = r.n < 500 ? ' thin' : '';
          return '<div class="hbar-row' + thin + '"><div class="hbar-label">' + r.label + '</div>'
            + '<div class="hbar-track"><div class="hbar-fill" style="width:' + largura + '%"></div></div>'
            + '<div class="hbar-val">' + (r.taxa * 100).toFixed(1) + '% \\u00b7 n=' + _fmtN(r.n) + '</div></div>';
        }}).join('');
      }}
      function aplicarFiltroAno(ano) {{
        const d = DADOS_POR_ANO[ano];
        if (!d) return;
        document.getElementById('seg-kpi-n').textContent = _fmtN(d.n_ocupados);
        document.getElementById('seg-kpi-taxa').textContent = (d.taxa_geral * 100).toFixed(1) + '%';
        document.getElementById('panel-sexo-body').innerHTML = _renderHbar(d.sexo_rows, 0.8);
        document.getElementById('panel-raca-body').innerHTML = _renderHbar(d.raca_rows, 0.8);
        document.getElementById('panel-regiao-body').innerHTML = _renderHbar(d.regiao_rows, 0.8);
      }}
    </script>'''


def _hipoteses_html(m: dict) -> str:
    """Hipóteses para orientar a modelagem futura (RF-05/RF-06) — cada
    bullet é derivado dos números já calculados nesta mesma execução, não
    inventado à parte, pra continuar batendo com o dado se ele mudar.
    """
    bullets = []

    forca = m.get("features_forca") or []
    if len(forca) >= 2:
        top2 = forca[:2]
        nomes = " e ".join(f'<b>{f["label"]}</b>' for f in top2)
        bullets.append(
            f'{nomes} lideram a associação isolada com informalidade (Seção 05) — hipótese: a '
            f'<b>interação entre as duas</b> (ex.: porte do negócio dentro de cada setor) pode ter poder '
            f'preditivo maior que as variáveis somadas separadamente; vale testar como feature composta no modelo.'
        )

    regiao = m.get("regiao_rows") or []
    if len(regiao) >= 2:
        maior, menor = regiao[0], regiao[-1]
        gap = 100 * (maior["taxa"] - menor["taxa"])
        if gap >= 3:
            bullets.append(
                f'A taxa de informalidade varia <b>{gap:.0f} pontos percentuais</b> entre <b>{maior["label"]}</b> '
                f'({maior["taxa"]*100:.1f}%) e <b>{menor["label"]}</b> ({menor["taxa"]*100:.1f}%) — hipótese: fatores '
                f'estruturais regionais (setor predominante, urbanização) explicam parte do gap; região pode valer '
                f'como termo de interação com setor/ocupação, não só como variável aditiva.'
            )

    funil = m.get("funil")
    if funil:
        fora_forca = next((g for g in funil["grupos"] if g["label"].startswith("Fora da força")), None)
        ocupados = next((g for g in funil["grupos"] if g["label"].startswith("Ocupados")), None)
        if fora_forca and ocupados and fora_forca["pct_mulheres"] and ocupados["pct_mulheres"]:
            if fora_forca["pct_mulheres"] - ocupados["pct_mulheres"] > 0.03:
                bullets.append(
                    'Mulheres estão sobrerrepresentadas entre quem está fora da força de trabalho (Seção 00) — '
                    'hipótese de <b>viés de seleção</b>: se decidir participar do mercado formal/informal já '
                    'correlaciona com sexo antes mesmo de alguém ser "ocupado", a taxa de informalidade por sexo '
                    'medida aqui (Seção 03) pode subestimar a exposição real de mulheres à informalidade se '
                    'elas só entram no mercado sob condições mais restritas.'
                )

    if m.get("tendencia_disponivel"):
        delta = m["tendencia_delta_pp"]
        if abs(delta) >= 1:
            direcao = "queda" if delta < 0 else "alta"
            bullets.append(
                f'A taxa caiu/subiu {abs(delta):.1f} ponto(s) percentuais entre o primeiro e o último ano da base '
                f'(<b>{direcao}</b>) — hipótese a validar com mais trimestres: tendência real de mercado de '
                f'trabalho, ou efeito de composição (ex.: setores que mais cresceram no período têm taxa própria '
                f'diferente da média)?'
            )

    bullets.append(
        'Renda (<code>VD4016</code>/<code>VD4017</code>) não entra como feature (data leakage — ver '
        '<code>docs/03-dicionario-de-dados.md</code>), mas o gap salarial formal x informal é um bom '
        'gráfico de contexto para uma futura análise descritiva, não preditiva.'
    )

    itens = "".join(f"<li>{b}</li>" for b in bullets)
    return f'<div class="callout"><div class="callout-head">Hipóteses para orientar a modelagem (RF-05/RF-06)</div><ul>{itens}</ul></div>'


CSS = """
  :root{color-scheme:light;--bg:#f2f4f7;--surface:#ffffff;--surface-2:#eaeef3;--ink:#10131a;--ink-2:#454a58;--ink-muted:#767b8a;--border:rgba(16,19,26,.11);--border-strong:rgba(16,19,26,.18);--accent:#2a78d6;--accent-ink:#164a90;--accent-soft-2:rgba(42,120,214,.10);--negative:#c8302f;--aqua:#0f8f63;--shadow:0 1px 2px rgba(16,19,26,.04),0 8px 24px -12px rgba(16,19,26,.18)}
  @media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;--bg:#0c0e12;--surface:#15171d;--surface-2:#1b1e26;--ink:#f4f5f7;--ink-2:#c6cad6;--ink-muted:#8b8f9e;--border:rgba(255,255,255,.11);--border-strong:rgba(255,255,255,.20);--accent:#4a90e8;--accent-ink:#bcd8f9;--accent-soft-2:rgba(74,144,232,.12);--negative:#e2726f;--aqua:#35b98a;--shadow:0 1px 2px rgba(0,0,0,.3),0 8px 24px -12px rgba(0,0,0,.5)}}
  :root[data-theme="dark"]{color-scheme:dark;--bg:#0c0e12;--surface:#15171d;--surface-2:#1b1e26;--ink:#f4f5f7;--ink-2:#c6cad6;--ink-muted:#8b8f9e;--border:rgba(255,255,255,.11);--border-strong:rgba(255,255,255,.20);--accent:#4a90e8;--accent-ink:#bcd8f9;--accent-soft-2:rgba(74,144,232,.12);--negative:#e2726f;--aqua:#35b98a;--shadow:0 1px 2px rgba(0,0,0,.3),0 8px 24px -12px rgba(0,0,0,.5)}
  *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:"Public Sans",system-ui,-apple-system,"Segoe UI",sans-serif;-webkit-font-smoothing:antialiased}
  .wrap{max-width:1120px;margin:0 auto;padding:56px 28px 96px}
  .eyebrow{font-family:"IBM Plex Mono",monospace;font-size:12.5px;letter-spacing:.11em;text-transform:uppercase;color:var(--accent-ink);font-weight:600;display:flex;align-items:center;gap:10px}.eyebrow::before{content:"";width:22px;height:1px;background:var(--accent)}
  h1{font-family:"Fraunces",Georgia,serif;font-weight:480;font-size:clamp(2.1rem,4.4vw,3.4rem);line-height:1.05;letter-spacing:-.015em;margin:18px 0 0}
  h1 em{font-style:italic;font-weight:460;color:var(--accent-ink)}
  .lede{max-width:68ch;font-size:1.09rem;line-height:1.62;color:var(--ink-2);margin:20px 0 0}.lede b{color:var(--ink);font-weight:600}
  .meta-row{margin-top:12px;font-size:.82rem;color:var(--ink-muted);display:flex;gap:20px;flex-wrap:wrap}
  header.top{padding-bottom:8px;border-bottom:1px solid var(--border);margin-bottom:34px}
  .callout{margin-top:28px;border:1px solid var(--border-strong);background:var(--surface-2);border-radius:14px;padding:22px 26px}
  .callout-head{font-family:"IBM Plex Mono",monospace;font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-muted);font-weight:600;margin-bottom:12px}
  .callout ul{margin:0;padding-left:1.15em;display:grid;gap:9px}.callout li{font-size:.965rem;line-height:1.55;color:var(--ink-2)}.callout li b{color:var(--ink);font-weight:600}
  code{font-family:"IBM Plex Mono",monospace;font-size:.88em;background:var(--surface);border:1px solid var(--border);padding:.05em .4em;border-radius:5px;color:var(--ink)}
  .kpis{margin-top:28px;display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:1px;background:var(--border);border:1px solid var(--border);border-radius:14px;overflow:hidden}
  .kpi{background:var(--surface);padding:20px 22px}.kpi-label{font-size:.8rem;color:var(--ink-muted);font-weight:500}
  .kpi-value{font-family:"IBM Plex Mono",monospace;font-variant-numeric:tabular-nums;font-size:1.9rem;font-weight:600;margin-top:6px}.kpi-sub{font-size:.8rem;color:var(--ink-muted);margin-top:3px}
  section.block{margin-top:76px}.sec-head{display:flex;gap:18px;align-items:baseline;margin-bottom:6px}
  .sec-num{font-family:"Fraunces",serif;font-weight:460;font-style:italic;font-size:1.6rem;color:var(--accent-ink);min-width:2ch}
  h2{font-family:"Fraunces",Georgia,serif;font-weight:500;font-size:1.7rem;margin:0}
  .sec-intro{max-width:72ch;color:var(--ink-2);font-size:1rem;line-height:1.62;margin:14px 0 0 calc(2ch + 18px)}
  .panel{margin-top:26px;margin-left:calc(2ch + 18px);background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:26px 28px 22px;box-shadow:var(--shadow)}
  .panel-head{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap;margin-bottom:4px}
  .panel-title{font-weight:600;font-size:1rem}.panel-note{font-size:.82rem;color:var(--ink-muted)}.panel-caption{font-size:.86rem;color:var(--ink-muted);margin-top:10px;line-height:1.5}
  .grid-2{display:grid;grid-template-columns:1fr 1fr;gap:22px;margin-left:calc(2ch + 18px);margin-top:26px}
  @media (max-width:760px){.grid-2{grid-template-columns:1fr}.panel,.sec-intro{margin-left:0}}
  table.data{width:100%;border-collapse:collapse;margin-top:12px;font-size:.86rem}
  table.data th,table.data td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--border);font-variant-numeric:tabular-nums}
  table.data th{color:var(--ink-muted);font-weight:600;font-size:.78rem;text-transform:uppercase}
  .linechart-svg{width:100%;height:auto;overflow:visible}.grid-line{stroke:var(--border);stroke-width:1}
  .axis-y-label{font-family:"IBM Plex Mono",monospace;font-size:10.5px;fill:var(--ink-muted)}
  .axis-x{font-family:"IBM Plex Mono",monospace;font-size:10.5px;fill:var(--ink-muted);text-anchor:middle}
  .area-fill{fill:var(--accent-soft-2)}.line-path{fill:none;stroke:var(--accent);stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
  .pt{fill:var(--surface);stroke:var(--accent);stroke-width:2}
  .hist-row{display:flex;align-items:flex-end;gap:4px;height:140px;margin-top:18px}
  .hist-col{flex:1;display:flex;flex-direction:column;align-items:center;height:100%;justify-content:flex-end}
  .hist-bar{width:100%;background:var(--accent);border-radius:3px 3px 0 0;min-height:2px}
  .hist-lbl{margin-top:7px;font-size:.62rem;color:var(--ink-muted)}
  .stat-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:16px;margin-top:26px;margin-left:calc(2ch + 18px)}
  @media (max-width:760px){.stat-grid{margin-left:0}}
  .stat-card{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:20px 22px;box-shadow:var(--shadow)}
  .stat-name{font-weight:600;font-size:.98rem}.stat-n{font-size:.76rem;color:var(--ink-muted)}
  .stat-rows{margin-top:14px;display:grid;gap:7px}.stat-r{display:flex;justify-content:space-between;font-size:.87rem}
  .stat-r .k{color:var(--ink-muted)}.stat-r .v{font-family:"IBM Plex Mono",monospace;font-variant-numeric:tabular-nums;font-weight:500}
  .stat-r.hl .v{color:var(--accent-ink);font-weight:700}
  .heat-wrap{overflow-x:auto;margin-top:20px}.heat{display:grid;grid-template-columns:128px repeat(6,minmax(74px,1fr));gap:3px;min-width:620px}
  .heat-colhead,.heat-rowhead{font-size:.72rem;color:var(--ink-muted);font-weight:600;display:flex;align-items:center}
  .heat-colhead{justify-content:center;text-align:center;padding:4px 2px}.heat-rowhead{padding-right:8px}
  .cell{aspect-ratio:1;border-radius:7px;display:flex;align-items:center;justify-content:center;font-family:"IBM Plex Mono",monospace;font-size:.78rem;font-weight:600}
  .div-rows{display:grid;gap:14px;margin-top:20px}.div-row{display:grid;grid-template-columns:150px 1fr 64px;align-items:center;gap:12px}
  .div-label{font-size:.87rem;color:var(--ink-2)}.div-track{position:relative;height:22px;background:var(--surface-2);border-radius:5px;overflow:hidden}
  .div-mid{position:absolute;left:50%;top:0;bottom:0;width:1px;background:var(--border-strong)}
  .div-bar{position:absolute;top:2px;bottom:2px;border-radius:3px}.div-bar.pos{left:50%;background:var(--accent)}.div-bar.neg{right:50%;background:var(--negative)}
  .div-val{font-family:"IBM Plex Mono",monospace;font-size:.82rem;text-align:right}
  .hbar-rows{display:grid;gap:12px;margin-top:18px}.hbar-row{display:grid;grid-template-columns:128px 1fr 118px;align-items:center;gap:12px}
  .hbar-label{font-size:.87rem;color:var(--ink-2)}.hbar-track{height:20px;background:var(--surface-2);border-radius:5px;overflow:hidden}
  .hbar-fill{height:100%;background:var(--accent);border-radius:5px}.hbar-val{font-family:"IBM Plex Mono",monospace;font-size:.8rem;color:var(--ink-muted);text-align:right}
  .hbar-row.thin .hbar-label,.hbar-row.thin .hbar-val{color:var(--ink-muted);font-style:italic}
  .filtro-row{display:flex;align-items:center;gap:10px;margin:26px 0 0 calc(2ch + 18px);flex-wrap:wrap}
  @media (max-width:760px){.filtro-row{margin-left:0}}
  .filtro-row label{font-size:.85rem;color:var(--ink-muted)}
  .filtro-row select{font:inherit;font-size:.86rem;color:var(--ink);background:var(--surface);border:1px solid var(--border-strong);border-radius:8px;padding:6px 10px}
  .seg-kpis{display:flex;gap:26px;margin-top:4px;flex-wrap:wrap}
  .seg-kpis .kpi-mini{font-size:.86rem;color:var(--ink-2)}.seg-kpis .kpi-mini b{font-family:"IBM Plex Mono",monospace;color:var(--accent-ink);font-size:1rem}
  .anom-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px;margin-top:26px;margin-left:calc(2ch + 18px)}
  @media (max-width:760px){.anom-grid{margin-left:0}}
  .anom-card{border:1px solid var(--border);border-left:3px solid var(--negative);background:var(--surface);border-radius:10px;padding:16px 18px}
  .anom-card.ok{border-left-color:var(--aqua)}.anom-card h3{margin:0 0 6px;font-size:.94rem;font-weight:700}.anom-card p{margin:0;font-size:.87rem;line-height:1.5;color:var(--ink-2)}
  .null-rows{display:grid;gap:11px;margin-top:20px}.null-row{display:grid;grid-template-columns:260px 1fr 70px;align-items:center;gap:12px}
  .null-label{font-size:.85rem;color:var(--ink-2)}.null-label .cols{display:block;font-size:.72rem;color:var(--ink-muted);font-family:"IBM Plex Mono",monospace}
  .null-track{height:20px;background:var(--surface-2);border-radius:5px;overflow:hidden}.null-fill{height:100%;border-radius:5px;background:var(--accent)}.null-fill.zero{background:var(--aqua)}
  .null-val{font-family:"IBM Plex Mono",monospace;font-size:.83rem;text-align:right}
  footer{margin-top:88px;padding-top:26px;border-top:1px solid var(--border);display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap;font-size:.82rem;color:var(--ink-muted);line-height:1.6}
  footer .foot-col{max-width:44ch}
"""


def calcular_metricas_amostra(amostra: pd.DataFrame, classificar_informalidade) -> dict:
    """Igual a `calcular_metricas`, mas a partir da amostra versionada
    (`dados_amostra/pnadc_silver_amostra.csv`) — que é Silver, não Gold,
    então ainda precisa filtrar ocupados e classificar informalidade
    aqui. `classificar_informalidade` é injetada (normalmente
    `Transformacao._classificar_informalidade`) pra não duplicar a regra
    em dois lugares.
    """
    ocupados = amostra[amostra["VD4002"] == 1].copy()
    ocupados["informal"] = classificar_informalidade(ocupados)
    return calcular_metricas(ocupados, silver=amostra)


def renderizar_raiox(m: dict, n_amostra_total: int) -> str:
    """Monta o HTML completo do Raio-X da Informalidade — mesma
    linguagem visual do Censo, mas com o alerta de amostra pequena em
    vez da seção de nulos (a amostra é pequena demais pra essa análise
    fazer sentido) e sem comparação com si mesma.
    """
    kpis = f'''<div class="kpis">
      <div class="kpi"><div class="kpi-label">Registros na amostra</div><div class="kpi-value">{n_amostra_total:,}</div><div class="kpi-sub">seed fixa (42)</div></div>
      <div class="kpi"><div class="kpi-label">Pessoas ocupadas</div><div class="kpi-value">{m["n_ocupados"]:,}</div><div class="kpi-sub">{100*m["n_ocupados"]/n_amostra_total:.1f}% da amostra</div></div>
      <div class="kpi"><div class="kpi-label">Taxa de informalidade</div><div class="kpi-value" style="color:var(--accent-ink)">{m["taxa_geral"]*100:.1f}%</div><div class="kpi-sub">entre ocupados, não ponderada</div></div>
      <div class="kpi"><div class="kpi-label">Cobertura temporal</div><div class="kpi-value" style="font-size:1.5rem">{m["ano_min"]}–{m["ano_max"]}</div><div class="kpi-sub">{m["n_trimestres"]} trimestres</div></div>
    </div>'''.replace(",", ".")

    linechart = _linha_chart_svg(m["periodo_rows"])
    stat_cards = "".join(_stat_card(d, f'n={d["n"]:,}'.replace(",", ".")) for d in m["descritivas"].values())
    hist_html = "".join(
        f'''<div class="panel" style="margin-left:0;">
          <div class="panel-head"><div class="panel-title">Distribuição — {d["label"]}</div><div class="panel-note">n={d["n"]:,}</div></div>
          {_hist_bars(d["hist_counts"], d["hist_bins"])}
        </div>'''.replace(",", ".")
        for d in [m["descritivas"].get("V2009"), m["descritivas"].get("VD4031")] if d
    )
    heatmap = _heatmap(m["correlacao_colunas"], m["correlacao_matriz"])
    divbars = _divbar_rows(m["ponto_bisserial"])
    secao_funil = _secao_funil_html(m["funil"], "amostra") if m.get("funil") else ""
    segmentacao_extra = _secao_segmentacao_extra(m)
    highlights = _highlights_html(m)
    renda_gap_html = _renda_gap_html(m["renda_gap"]) if m.get("renda_gap") else ""

    return f'''<title>Raio-X da Informalidade</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,340..700;1,9..144,400..600&family=Public+Sans:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>{CSS}</style>
<div class="wrap">
  <header class="top">
    <div class="eyebrow">Boletim de análise exploratória · PNAD Contínua · amostra · gerado pelo pipeline</div>
    <h1>Raio-X da <em>informalidade</em> no mercado de trabalho</h1>
    <p class="lede">Leitura preliminar sobre a <b>amostra versionada</b> (<code>dados_amostra/pnadc_silver_amostra.csv</code>) — gerado por <code>scripts/gerar_boletins_eda.py</code>. Para o dado completo, ver o Censo da Informalidade.</p>
    <div class="callout">
      <div class="callout-head">Nota metodológica — leia antes dos números</div>
      <ul>
        <li><b>Amostra pequena e por desenho.</b> {n_amostra_total:,} registros — qualquer variação de contagem entre períodos é artefato da amostragem, não sinal real.</li>
        <li><b>Sem peso amostral aplicado</b> — proporções não são estimativa oficial ponderada por <code>V1028</code>.</li>
      </ul>
    </div>
    {kpis}
    {highlights}
  </header>

  {secao_funil}

  <section class="block">
    <div class="sec-head"><span class="sec-num">01</span><h2>Padrões, tendências e sazonalidade</h2></div>
    <p class="sec-intro">Taxa de informalidade por trimestre — leia com cautela dado o tamanho pequeno da amostra por período.</p>
    <div class="panel"><div class="panel-head"><div class="panel-title">Taxa de informalidade por trimestre</div><div class="panel-note">escala 0–80%</div></div>{linechart}</div>
  </section>

  <section class="block">
    <div class="sec-head"><span class="sec-num">02</span><h2>Estatísticas descritivas e distribuição</h2></div>
    <p class="sec-intro">Média, mediana, desvio-padrão e distribuição das variáveis numéricas, entre pessoas ocupadas na amostra.</p>
    <div class="stat-grid">{stat_cards}</div>
    <div class="grid-2">{hist_html}</div>
    {renda_gap_html}
  </section>

  <section class="block">
    <div class="sec-head"><span class="sec-num">03</span><h2>Correlações, relações e segmentação</h2></div>
    <p class="sec-intro">Pearson entre numéricas e ponto-bisserial com o alvo binário — mesma matemática, só muda o que entra no lugar da segunda variável. Sexo, raça/cor e região abaixo são segmentações simples (médias gerais escondem diferenças entre grupos).</p>
    <div class="panel"><div class="panel-head"><div class="panel-title">Matriz de correlação (Pearson)</div></div><div class="heat-wrap">{heatmap}</div></div>
    <div class="panel" style="margin-top:22px;"><div class="panel-head"><div class="panel-title">Correlação ponto-bisserial com informalidade</div></div>{divbars}</div>
    {segmentacao_extra}
  </section>

  <footer>
    <div class="foot-col"><b style="color:var(--ink);">Fonte:</b> PNAD Contínua, IBGE — amostra versionada em <code>dados_amostra/</code>.</div>
    <div class="foot-col"><b style="color:var(--ink);">Gerado por:</b> <code>scripts/gerar_boletins_eda.py</code> — regenere depois de rodar <code>python -m scripts.gerar_amostra</code>.</div>
  </footer>
</div>
'''


def renderizar_censo(m: dict) -> str:
    """Monta o HTML completo do Censo da Informalidade a partir das
    métricas calculadas por `calcular_metricas`."""
    kpis = f'''<div class="kpis">
      <div class="kpi"><div class="kpi-label">Pessoas ocupadas</div><div class="kpi-value">{m["n_ocupados"]:,}</div><div class="kpi-sub">{m["n_trimestres"]} trimestres</div></div>
      <div class="kpi"><div class="kpi-label">Taxa de informalidade</div><div class="kpi-value" style="color:var(--accent-ink)">{m["taxa_geral"]*100:.1f}%</div><div class="kpi-sub">entre ocupados, não ponderada</div></div>
      <div class="kpi"><div class="kpi-label">Cobertura temporal</div><div class="kpi-value" style="font-size:1.5rem">{m["ano_min"]}–{m["ano_max"]}</div><div class="kpi-sub">gerado automaticamente pelo pipeline</div></div>
    </div>'''.replace(",", ".")

    tendencia_txt = ""
    if m["tendencia_disponivel"]:
        delta = m["tendencia_delta_pp"]
        direcao = "queda" if delta < 0 else ("alta" if delta > 0 else "estabilidade")
        tendencia_txt = f"<p class=\"panel-caption\">Do primeiro ao último ano da base: <b>{direcao} de {abs(delta):.1f} ponto(s) percentuais</b> na taxa de informalidade.</p>"

    linechart = _linha_chart_svg(m["periodo_rows"])

    stat_cards = "".join(
        _stat_card(d, f'n={d["n"]:,}'.replace(",", "."))
        for d in m["descritivas"].values()
    )

    hist_html = ""
    for col in ["V2009", "VD4031"]:
        d = m["descritivas"].get(col)
        if d:
            hist_html += f'''<div class="panel" style="margin-left:0;">
              <div class="panel-head"><div class="panel-title">Distribuição — {d["label"]}</div><div class="panel-note">n={d["n"]:,}</div></div>
              {_hist_bars(d["hist_counts"], d["hist_bins"])}
              <p class="panel-caption">{d["outliers_n"]:,} valores ({d["outliers_pct"]}%) fora da faixa IQR.</p>
            </div>'''.replace(",", ".")

    heatmap = _heatmap(m["correlacao_colunas"], m["correlacao_matriz"])
    divbars = _divbar_rows(m["ponto_bisserial"])
    segmentacao_extra = _secao_segmentacao_extra(m)
    secao_funil = _secao_funil_html(m["funil"], "Silver") if m.get("funil") else ""
    highlights = _highlights_html(m)
    renda_gap_html = _renda_gap_html(m["renda_gap"]) if m.get("renda_gap") else ""
    secao_hipoteses = f'''<section class="block">
        <div class="sec-head"><span class="sec-num">06</span><h2>Hipóteses para a modelagem</h2></div>
        <p class="sec-intro">A EDA acima já aponta direções concretas pra RF-05/RF-06 — o modelo entra para confirmar (ou refutar) estas hipóteses com evidência estatística mais forte, não para descobrir os padrões do zero.</p>
        {_hipoteses_html(m)}
      </section>'''

    ranking_html = _feature_ranking_rows(m["features_forca"])
    mais_fraca = m["features_forca"][-1] if m["features_forca"] else None
    nota_fraca = (
        f'<p class="panel-caption">Menor associação do lote: <b>{mais_fraca["label"]}</b> (V={mais_fraca["forca"]:.3f}) — '
        f'candidata a excluir do modelo se continuar assim com mais dado.</p>'
        if mais_fraca and mais_fraca["forca"] < 0.02 else ""
    )
    secao_features = f'''<section class="block">
        <div class="sec-head"><span class="sec-num">05</span><h2>Seleção de features para o modelo</h2></div>
        <p class="sec-intro">Força de associação de cada feature candidata com a informalidade — V de Cramér para categóricas, correlação ponto-bisserial (|r|) para numéricas. Sexo e raça entram no modelo independente da força medida aqui (RF-06 pede medir o peso delas via SHAP, não descartá-las por serem fracas).</p>
        <div class="panel">{ranking_html}{nota_fraca}</div>
      </section>'''

    secao_nulos = ""
    if "nulos_grupos" in m:
        secao_nulos = f'''<section class="block">
        <div class="sec-head"><span class="sec-num">04</span><h2>Percentual de campos nulos</h2></div>
        <p class="sec-intro">Nulo estrutural (desenho de "pulo de pergunta" da PNAD), calculado sobre os {m["n_silver_total"]:,} registros da Silver antes do filtro de ocupados.</p>
        <div class="panel">{_null_rows(m["nulos_grupos"])}</div>
      </section>'''.replace(",", ".")

    return f'''<title>Censo da Informalidade</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,340..700;1,9..144,400..600&family=Public+Sans:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>{CSS}</style>
<div class="wrap">
  <header class="top">
    <div class="eyebrow">Boletim de análise exploratória · PNAD Contínua · gerado pelo pipeline (RF-04)</div>
    <h1>Censo da <em>informalidade</em> — {m["ano_min"]}–{m["ano_max"]}</h1>
    <p class="lede">Gerado automaticamente por <code>src/analise/analise.py</code> a partir da camada Gold mais recente — toda vez que o pipeline reprocessar dados novos, este relatório é regenerado com os números atualizados.</p>
    <div class="callout">
      <div class="callout-head">Nota metodológica</div>
      <ul>
        <li><b>Sem peso amostral aplicado</b> — taxas são proporção da base de respondentes, não estimativa oficial ponderada por <code>V1028</code>.</li>
        <li><b>Regra de informalidade</b>: VD4009 nas categorias 2/4/6/10, ou 8/9 sem CNPJ — ver <code>docs/03-dicionario-de-dados.md</code>. Ainda pendente de validação formal do time.</li>
      </ul>
    </div>
    {kpis}
    {highlights}
  </header>

  {secao_funil}

  <section class="block">
    <div class="sec-head"><span class="sec-num">01</span><h2>Padrões, tendências e sazonalidade</h2></div>
    <p class="sec-intro">Taxa de informalidade por trimestre — mínimo {m["taxa_min"]*100:.1f}% ({m["periodo_taxa_min"]}), máximo {m["taxa_max"]*100:.1f}% ({m["periodo_taxa_max"]}).</p>
    <div class="panel">
      <div class="panel-head"><div class="panel-title">Taxa de informalidade por trimestre</div><div class="panel-note">escala 0–80%</div></div>
      {linechart}
      {tendencia_txt}
    </div>
  </section>

  <section class="block">
    <div class="sec-head"><span class="sec-num">02</span><h2>Estatísticas descritivas e distribuição</h2></div>
    <p class="sec-intro">Média, mediana, desvio-padrão e distribuição das variáveis numéricas, entre pessoas ocupadas.</p>
    <div class="stat-grid">{stat_cards}</div>
    <div class="grid-2">{hist_html}</div>
    {renda_gap_html}
  </section>

  <section class="block">
    <div class="sec-head"><span class="sec-num">03</span><h2>Correlações, relações e segmentação</h2></div>
    <p class="sec-intro">Correlação de Pearson entre numéricas (mede associação linear, escala -1 a +1, fácil de comparar); ponto-bisserial de cada numérica com o alvo binário <code>informal</code> (mesma matemática de Pearson quando um dos lados é 0/1); e V de Cramér na Seção 05 para categóricas (não assume linearidade, funciona com muitas categorias como UF). Escolhidas por serem comparáveis na mesma escala e não exigirem suposição sobre a forma da relação.</p>
    <p class="sec-intro">Segmentar por sexo, raça/cor e região é essencial aqui: a taxa geral (Seção acima) esconde diferenças que só aparecem separando os grupos — e correlação não implica causalidade em nenhum dos recortes abaixo.</p>
    <div class="panel"><div class="panel-head"><div class="panel-title">Matriz de correlação (Pearson)</div></div><div class="heat-wrap">{heatmap}</div></div>
    <div class="panel" style="margin-top:22px;"><div class="panel-head"><div class="panel-title">Correlação ponto-bisserial com informalidade</div></div>{divbars}</div>
    {segmentacao_extra}
  </section>

  {secao_nulos}

  {secao_features}

  {secao_hipoteses}

  <footer>
    <div class="foot-col"><b style="color:var(--ink);">Fonte:</b> PNAD Contínua, IBGE — camada Gold do pipeline InformalidadeBR, gerada por <code>src/transformacao/transformacao.py</code>.</div>
    <div class="foot-col"><b style="color:var(--ink);">Gerado por:</b> <code>src/analise/analise.py</code> (RF-04) — regenere rodando <code>pipeline.analisar()</code> ou <code>python -m src.pipeline</code>.</div>
  </footer>
</div>
'''
