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

from src.relatorio_visual import CSS_BASE, glossario, montar_pagina
from src.relatorio_visual import selo as _selo_base
from src.relatorio_visual import takeaway as _takeaway

ESCALA_MAX_TAXA = 0.8  # domínio do eixo Y dos gráficos de taxa (0-80%)

# As 16 features candidatas discutidas com o time (exclui IDs, o grupo-
# alvo VD4009/V4019/VD4012/VD4002, peso amostral e renda — ver
# `docs/03-dicionario-de-dados.md`). Usado pra medir força de associação
# com `informal` (Seção 04) e ajudar a decidir a lista final do modelo.
FEATURES_CATEGORICAS = {
    "UF": "UF", "V2007": "Sexo", "V2010": "Raça/cor", "V1022": "Urbano/rural",
    "V1023": "Tipo de área", "VD2002": "Posição no domicílio", "VD3004": "Nível de instrução",
    "V3002": "Frequenta escola", "VD4010": "Setor de atividade", "VD4011": "Grupamento ocupacional",
    "V4018": "Tamanho do negócio", "V4025": "É temporário?", "V4040": "Tempo no emprego",
}
FEATURES_NUMERICAS = {"V2009": "Idade", "VD2003": "Pessoas no domicílio", "VD4031": "Horas semanais"}

# Variáveis numéricas comparadas entre formais e informais na Seção 02
# (perfil do trabalhador informal — o recorte que introduz o alvo do
# modelo RF-05/RF-06). As categóricas do mesmo comparativo usam os
# LABELS já definidos abaixo e são montadas dentro de `_perfil_cat`.
PERFIL_NUM_VARS = {"V2009": "Idade", "VD4031": "Horas semanais", "VD2003": "Pessoas no domicílio"}

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

    # Perfil comparado formal x informal (Seção 02) — descreve QUEM é o
    # trabalhador informal dentro dos ocupados, não só onde a taxa é alta.
    m["perfil_num"] = _perfil_num(gold)
    m["perfil_cat"] = _perfil_cat(gold)

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


def _perfil_num(gold: pd.DataFrame) -> dict:
    """Estatísticas de cada variável numérica separadas por grupo
    (formal x informal) — base do comparativo de perfil da Seção 02:
    responde QUEM é o trabalhador informal dentro dos ocupados, não só
    onde a taxa é alta.
    """
    out: dict = {}
    for col, label in PERFIL_NUM_VARS.items():
        if col not in gold.columns:
            continue
        sub = gold[[col, "informal"]].dropna()
        if sub.empty:
            continue
        grupo: dict = {"label": label}
        for valor, chave in [(False, "formal"), (True, "informal")]:
            serie = sub.loc[sub["informal"] == valor, col]
            if serie.empty:
                continue
            grupo[chave] = {
                "n": int(len(serie)),
                "media": float(serie.mean()),
                "mediana": float(serie.median()),
                "p25": float(serie.quantile(0.25)),
                "p75": float(serie.quantile(0.75)),
            }
        if "formal" in grupo and "informal" in grupo:
            out[col] = grupo
    return out


def _perfil_cat(gold: pd.DataFrame) -> dict:
    """Distribuição percentual de cada variável categórica DENTRO de cada
    grupo — P(categoria | informal) x P(categoria | formal). Deixa ver,
    por exemplo, que a maioria dos informais parou no ensino fundamental
    enquanto a maioria dos formais tem superior. Complementa
    `_calcular_forca_features` (que mede intensidade da associação, não
    composição do grupo).
    """
    fontes: list[tuple] = []
    for col, label, labels, ordinal in [
        ("VD3004", "Escolaridade", VD3004_LABELS, True),
        ("V4040", "Tempo no emprego", V4040_LABELS, True),
        ("VD4010", "Setor de atividade", VD4010_LABELS, False),
        ("V2010", "Cor/raça", RACA_LABELS, False),
        ("V2007", "Sexo", SEXO_LABELS, False),
    ]:
        if col in gold.columns:
            fontes.append((col, label, gold[col], labels, ordinal))
    if "UF" in gold.columns:
        fontes.append(("regiao", "Região", gold["UF"].map(REGIAO_MAP), None, False))

    out: dict = {}
    for chave, label, serie, labels, ordinal in fontes:
        sub = pd.DataFrame({"cat": serie.to_numpy(), "informal": gold["informal"].to_numpy()}).dropna()
        if sub.empty or sub["cat"].nunique() < 2:
            continue
        ct = pd.crosstab(sub["cat"], sub["informal"], normalize="columns")
        n_por_grupo = sub.groupby("informal").size()
        categorias = []
        for cat in ct.index:
            try:
                codigo = int(cat)
            except (TypeError, ValueError):
                codigo = None
            rotulo = (labels or {}).get(codigo, str(cat)) if labels else str(cat)
            categorias.append({
                "label": rotulo,
                "codigo": codigo,
                "pct_formal": float(ct.loc[cat, False]) if False in ct.columns else 0.0,
                "pct_informal": float(ct.loc[cat, True]) if True in ct.columns else 0.0,
            })
        if ordinal and all(c["codigo"] is not None for c in categorias):
            categorias.sort(key=lambda c: c["codigo"])
        else:
            categorias.sort(key=lambda c: -c["pct_informal"])
        out[chave] = {
            "label": label,
            "ordinal": ordinal,
            "n_formal": int(n_por_grupo.get(False, 0)),
            "n_informal": int(n_por_grupo.get(True, 0)),
            "categorias": categorias,
        }
    return out


# ---------------------------------------------------------------------
# Componentes de apresentação. A paleta/tipografia e os componentes
# genéricos (takeaway, selo, glossário, wrapper de página) vivem em
# `src/relatorio_visual.py`, compartilhados com o boletim de modelagem.
# Abaixo ficam só os pedaços específicos da EDA.
# ---------------------------------------------------------------------

# Selos de tipo de bloco da EDA — o número escolhe a cor (ver
# `relatorio_visual.selo`), o texto é o significado neste boletim.
SELOS = {
    "taxa": (1, "TAXA % DO GRUPO"),
    "comp": (2, "COMPARAÇÃO FORMAL × INFORMAL"),
    "grupos": (2, "COMPARAÇÃO ENTRE GRUPOS"),
    "corr": (3, "CORRELAÇÃO −1 a +1"),
    "forca": (4, "FORÇA DE ASSOCIAÇÃO 0 a 1"),
    "dist": (5, "DISTRIBUIÇÃO"),
    "leak": (6, "CONTEXTO — NÃO É FEATURE"),
}


def _selo(tipo: str) -> str:
    variante, texto = SELOS[tipo]
    return _selo_base(texto, variante)


def _regua_correlacao() -> str:
    return '''<div class="regua">
      <div class="regua-bar regua-bar--corr"></div>
      <div class="regua-ticks"><span>−1</span><span>−0.5</span><span>0</span><span>+0.5</span><span>+1</span></div>
      <div class="regua-faixas"><span>forte negativa</span><span>fraca / quase nula</span><span>forte positiva</span></div>
      <p class="regua-frase">Sinal negativo = quando uma medida sobe, a outra desce. Perto de 0 = sem relação clara.</p>
    </div>'''


def _regua_forca() -> str:
    zonas = [("muito fraca", 1.67), ("fraca / moderada", 3.33), ("moderada / forte", 3.33), ("forte", 1.67)]
    segs = "".join(f'<span class="fb" style="flex:{w}">{t}</span>' for t, w in zonas)
    return (f'<div class="regua"><div class="regua-bar--forca">{segs}</div>'
            f'<div class="regua-ticks"><span>0</span><span>0.1</span><span>0.3</span><span>0.5</span><span>0.6+</span></div>'
            f'<p class="regua-frase">Mede só a intensidade da associação — não a direção nem se é causa.</p></div>')


def _feature_ranking_rows(rows: list[dict], escala_max: float = 0.6) -> str:
    linhas = []
    for r in rows:
        largura = min(100 * r["forca"] / escala_max, 100)
        classe = " thin" if r["forca"] < 0.05 else ""
        n_fmt = f'{r["n"]:,}'.replace(",", ".")
        linhas.append(
            f'<div class="rank-row{classe}"><div class="rank-label">{r["label"]}'
            f'<span class="rank-tipo">{r["tipo"]}</span></div>'
            f'<div class="rank-track"><div class="rank-fill" style="width:{largura:.1f}%"></div></div>'
            f'<div class="rank-val">{r["forca"]:.3f}<span class="rank-n">n={n_fmt}</span></div></div>'
        )
    return '<div class="rank-rows">' + "".join(linhas) + "</div>"


def _cmp_legenda() -> str:
    return ('<div class="cmp-legend"><span class="cmp-k cmp-k--inf">Informais</span>'
            '<span class="cmp-k cmp-k--for">Formais</span></div>')


def _barra_comparacao_rows(rows: list[dict]) -> str:
    """Barra 100% empilhada informal x formal por grupo — o número em
    destaque é sempre a fatia informal (o lado que interessa concluir).
    Marca visualmente o grupo de maior e o de menor informalidade.
    """
    if not rows:
        return ""
    taxas = [r["taxa"] for r in rows]
    marcar = len(rows) > 1 and max(taxas) != min(taxas)
    i_max, i_min = taxas.index(max(taxas)), taxas.index(min(taxas))
    linhas = []
    for i, r in enumerate(rows):
        inf = 100 * r["taxa"]
        marca = ""
        if marcar and i == i_max:
            marca = '<span class="cmp-mark cmp-mark--max" title="maior informalidade">▲</span>'
        elif marcar and i == i_min:
            marca = '<span class="cmp-mark cmp-mark--min" title="menor informalidade">▽</span>'
        thin = " thin" if r["n"] < 500 else ""
        n_fmt = f'{r["n"]:,}'.replace(",", ".")
        rotulo = f"{inf:.0f}%" if inf >= 12 else ""
        linhas.append(
            f'<div class="cmp-row{thin}"><div class="cmp-label">{marca}{r["label"]}</div>'
            f'<div class="cmp-track">'
            f'<div class="cmp-seg cmp-seg--inf" style="width:{inf:.1f}%">{rotulo}</div>'
            f'<div class="cmp-seg cmp-seg--for" style="width:{100 - inf:.1f}%"></div></div>'
            f'<div class="cmp-val"><b>{inf:.1f}%</b> informais<span class="cmp-n">n={n_fmt}</span></div></div>'
        )
    return '<div class="cmp-rows">' + "".join(linhas) + "</div>"


def _tendencia_texto(rows: list[dict]) -> str:
    """Para recortes ordinais (escolaridade, tempo no emprego, tamanho do
    negócio): diz se a taxa sobe/desce de forma monotônica ao longo da
    escala, ou onde a tendência quebra.
    """
    if len(rows) < 3:
        return ""
    taxas = [r["taxa"] for r in rows]
    difs = [b - a for a, b in zip(taxas, taxas[1:])]
    eps = 1e-6
    if all(d >= -eps for d in difs):
        return '<div class="tend tend--ok">Tendência monotônica: a informalidade sobe a cada degrau da escala.</div>'
    if all(d <= eps for d in difs):
        return '<div class="tend tend--ok">Tendência monotônica: a informalidade cai a cada degrau da escala.</div>'
    descidas = sum(1 for d in difs if d < 0)
    dominante_desc = descidas >= len(difs) - descidas
    for i, d in enumerate(difs):
        if (d > eps and dominante_desc) or (d < -eps and not dominante_desc):
            direc = "queda" if dominante_desc else "alta"
            return (f'<div class="tend tend--break">Tendência de {direc}, mas com uma quebra entre '
                    f'<b>{rows[i]["label"]}</b> e <b>{rows[i + 1]["label"]}</b>.</div>')
    return ""


def _perfil_num_html(perfil_num: dict) -> str:
    if not perfil_num:
        return ""
    linhas = []
    for _col, d in perfil_num.items():
        f_, i_ = d["formal"], d["informal"]
        unidade = " anos" if d["label"] == "Idade" else (" h" if "Horas" in d["label"] else "")
        limiar = 1.0 if unidade else 0.3
        delta = i_["mediana"] - f_["mediana"]
        seta = "≈ igual" if abs(delta) < limiar else (f"▲ {delta:+.1f}" if delta > 0 else f"▼ {delta:+.1f}")
        linhas.append(
            f'<tr><td>{d["label"]}</td>'
            f'<td>{f_["mediana"]:.1f}{unidade} <span class="faixa-iqr">({f_["p25"]:.0f}–{f_["p75"]:.0f})</span></td>'
            f'<td>{i_["mediana"]:.1f}{unidade} <span class="faixa-iqr">({i_["p25"]:.0f}–{i_["p75"]:.0f})</span></td>'
            f'<td class="cmp-delta-cell">{seta}</td></tr>'
        )
    return (f'<table class="data cmp-num"><thead><tr>'
            f'<th>Variável — mediana (P25–P75)</th><th>Formal</th><th>Informal</th><th>Dif.</th>'
            f'</tr></thead><tbody>{"".join(linhas)}</tbody></table>')


def _pc_legenda() -> str:
    return ('<div class="pc-legend"><span class="pc-k pc-k--inf">% dos informais nesta categoria</span>'
            '<span class="pc-k pc-k--for">% dos formais</span></div>')


def _perfil_cat_bloco(dados: dict, top: int | None = None) -> str:
    cats = dados["categorias"][:top] if top else dados["categorias"]
    linhas = []
    for c in cats:
        pi, pf = 100 * c["pct_informal"], 100 * c["pct_formal"]
        delta = pi - pf
        cls = "pc-over" if delta > 2 else ("pc-under" if delta < -2 else "")
        linhas.append(
            f'<div class="pc-row"><div class="pc-label">{c["label"]}</div>'
            f'<div class="pc-bars">'
            f'<div class="pc-bar pc-bar--inf" style="width:{min(pi, 100):.0f}%"></div>'
            f'<div class="pc-bar pc-bar--for" style="width:{min(pf, 100):.0f}%"></div></div>'
            f'<div class="pc-val">{pi:.0f}% <span class="pc-vs">vs {pf:.0f}%</span>'
            f'<span class="pc-delta {cls}">{delta:+.0f} p.p.</span></div></div>'
        )
    return '<div class="pc-rows">' + "".join(linhas) + "</div>"


def _retrato_informal_html(m: dict) -> str:
    """O bloco que responde, em frases diretas, QUEM é o trabalhador
    informal — cada frase derivada de `perfil_num`/`perfil_cat`/`renda_gap`
    desta mesma execução, nada hardcoded.
    """
    pc = m.get("perfil_cat") or {}
    pn = m.get("perfil_num") or {}
    frases = []

    esc = pc.get("VD3004")
    if esc and all(c["codigo"] is not None for c in esc["categorias"]):
        baixa_i = sum(c["pct_informal"] for c in esc["categorias"] if c["codigo"] <= 4)
        baixa_f = sum(c["pct_formal"] for c in esc["categorias"] if c["codigo"] <= 4)
        frases.append(
            f'<b>Estudou menos.</b> {baixa_i * 100:.0f}% dos informais não concluíram o ensino médio — '
            f'entre os formais são {baixa_f * 100:.0f}%.'
        )

    setor = pc.get("VD4010")
    if setor:
        top_s = max(setor["categorias"], key=lambda c: c["pct_informal"])
        frases.append(
            f'<b>Trabalha mais em {top_s["label"].lower()}.</b> {top_s["pct_informal"] * 100:.0f}% dos informais '
            f'estão nesse setor, contra {top_s["pct_formal"] * 100:.0f}% dos formais.'
        )

    reg = pc.get("regiao")
    if reg:
        top_r = max(reg["categorias"], key=lambda c: c["pct_informal"])
        frases.append(
            f'<b>Mora mais no {top_r["label"]}.</b> {top_r["pct_informal"] * 100:.0f}% dos informais vivem lá '
            f'(formais: {top_r["pct_formal"] * 100:.0f}%).'
        )

    idade = pn.get("V2009")
    if idade:
        di = idade["informal"]["mediana"] - idade["formal"]["mediana"]
        if abs(di) < 2:
            frases.append(
                f'<b>Tem a mesma idade dos formais</b> (mediana ~{idade["informal"]["mediana"]:.0f} anos) — '
                f'informalidade não é "coisa de jovem".'
            )
        else:
            frases.append(
                f'<b>É {"mais velho" if di > 0 else "mais jovem"}</b> — mediana de '
                f'{idade["informal"]["mediana"]:.0f} anos, contra {idade["formal"]["mediana"]:.0f} dos formais.'
            )

    horas = pn.get("VD4031")
    if horas:
        dh = horas["informal"]["mediana"] - horas["formal"]["mediana"]
        if abs(dh) < 2:
            frases.append(
                f'<b>Cumpre carga horária parecida</b> (mediana {horas["informal"]["mediana"]:.0f} h/semana).'
            )
        else:
            frases.append(
                f'<b>Trabalha {"mais" if dh > 0 else "menos"} horas</b> — mediana '
                f'{horas["informal"]["mediana"]:.0f} h/semana, contra {horas["formal"]["mediana"]:.0f} dos formais.'
            )

    rg = m.get("renda_gap")
    if rg and rg.get("formal") and rg.get("informal") and rg["formal"]["mediana"]:
        gp = 100 * (rg["formal"]["mediana"] - rg["informal"]["mediana"]) / rg["formal"]["mediana"]
        frases.append(
            f'<b>Ganha menos.</b> Renda mediana {gp:.0f}% abaixo da de um formal — contexto econômico, '
            f'não entra no modelo (data leakage).'
        )

    sexo = pc.get("V2007")
    if sexo:
        top_sx = max(sexo["categorias"], key=lambda c: c["pct_informal"])
        frases.append(
            f'<b>É maioria {top_sx["label"].lower()}</b> ({top_sx["pct_informal"] * 100:.0f}% dos informais), '
            f'acompanhando a composição dos ocupados.'
        )

    itens = "".join(f"<li>{f}</li>" for f in frases)
    n_inf = round(m["n_ocupados"] * m["taxa_geral"])
    n_inf_fmt = f'{n_inf:,}'.replace(",", ".")
    return (f'<div class="retrato">'
            f'<div class="retrato-head">O trabalhador informal em uma olhada — {n_inf_fmt} pessoas, '
            f'{m["taxa_geral"] * 100:.1f}% dos ocupados</div>'
            f'<p class="retrato-sub">É este o perfil que o modelo (RF-05/RF-06) vai aprender a reconhecer:</p>'
            f'<ul>{itens}</ul></div>')


def _definicao_informal_html() -> str:
    """Explica POR QUE este boletim usa esta definição de informalidade —
    rastreável a `docs/03-dicionario-de-dados.md`, não é invenção.
    """
    return '''<details class="gloss def-informal">
      <summary>Por que "informal" foi definido assim neste boletim</summary>
      <div class="def-body">
        <p>A classificação parte de <code>VD4009</code> — a <b>variável derivada que o próprio IBGE
        usa</b> em estudos de informalidade. Uma pessoa ocupada é contada como <b>informal</b> quando:</p>
        <ul>
          <li>é assalariada <b>sem carteira assinada</b> — no setor privado, no trabalho doméstico ou no
          setor público (<code>VD4009</code> = 2, 4 ou 6);</li>
          <li>é <b>trabalhador familiar auxiliar</b> não remunerado (categoria 10);</li>
          <li>é <b>empregador ou conta-própria sem CNPJ</b> (categorias 8/9 com <code>V4019 ≠ 1</code>).</li>
        </ul>
        <p>É a <b>convenção acadêmica mais comum</b>: informalidade = ausência de proteção
        trabalhista/previdenciária pelo vínculo. A alternativa mais simples considerada — usar só
        <code>VD4012</code> (contribui ou não para a previdência) como proxy — <b>não</b> foi adotada.</p>
        <p>Escolha conservadora: quem não respondeu à pergunta do CNPJ entra como "sem CNPJ" (informal).
        A regra <b>ainda está pendente de validação formal do time</b> (RF-03) — ver
        <code>docs/03-dicionario-de-dados.md</code>.</p>
      </div>
    </details>'''


def _glossario_html() -> str:
    termos = [
        ("Taxa (de informalidade)", "Proporção de um grupo que é informal, de 0 a 100%. Taxa de 60% = 6 em cada 10 daquele grupo."),
        ("Correlação", "Número de −1 a +1 que resume se duas medidas variam juntas. Perto de 0 = quase sem relação."),
        ("Ponto-bisserial", "A mesma correlação de Pearson, usada quando um dos lados é sim/não (aqui: ser informal ou não)."),
        ("V de Cramér", "Mede a força da associação entre duas variáveis categóricas, de 0 (nenhuma) a 1 (perfeita). Não indica direção."),
        ("Mediana", "O valor do meio: metade das pessoas está abaixo, metade acima. Menos sensível a extremos do que a média."),
        ("IQR (P25–P75)", "A faixa onde estão os 50% centrais do grupo — do percentil 25 ao 75."),
        ("Monotônico", "Tendência que só sobe (ou só desce) a cada degrau de uma escala ordenada, sem voltar atrás."),
        ("Ponderação amostral (V1028)", "Peso que cada respondente tem para a PNAD representar o Brasil. Este boletim NÃO aplica esse peso."),
        ("Data leakage", "Usar como preditora uma informação que só existe por causa do resultado. Renda é consequência da informalidade — fica fora do modelo."),
    ]
    return glossario(termos)


def _highlights_html(m: dict) -> str:
    """Bloco "O que os dados dizem" no topo — 3 níveis (público total →
    ocupados → trabalhador informal), cada bullet gerado dos próprios
    números desta execução (maior força, maior gap, composição do perfil).
    """
    n_ocup_fmt = f'{m["n_ocupados"]:,}'.replace(",", ".")
    n_inf = round(m["n_ocupados"] * m["taxa_geral"])
    n_inf_fmt = f'{n_inf:,}'.replace(",", ".")

    total = []
    funil = m.get("funil")
    if funil:
        ocup = next((g for g in funil["grupos"] if g["label"].startswith("Ocupados")), None)
        tot_fmt = f'{funil["total"]:,}'.replace(",", ".")
        if ocup:
            total.append(
                f'A base bruta tem <b>{tot_fmt}</b> pessoas; <b>{ocup["pct_total"]:.0f}%</b> estão ocupadas — '
                f'e é só sobre elas que este boletim fala.'
            )
        fora = next((g for g in funil["grupos"] if g["label"].startswith("Fora da força")), None)
        if fora and ocup and fora["pct_mulheres"] is not None and ocup["pct_mulheres"] is not None:
            g = 100 * (fora["pct_mulheres"] - ocup["pct_mulheres"])
            if abs(g) >= 3:
                total.append(
                    f'Quem está fora da força de trabalho é {fora["pct_mulheres"] * 100:.0f}% mulheres, contra '
                    f'{ocup["pct_mulheres"] * 100:.0f}% entre ocupados — indício de viés de seleção (Seção 00).'
                )
    else:
        total.append(f'Este boletim cobre <b>{n_ocup_fmt}</b> pessoas ocupadas ({m["ano_min"]}–{m["ano_max"]}).')

    ocupados = [f'<b>{m["taxa_geral"] * 100:.1f}%</b> dos ocupados são informais — <b>{n_inf_fmt}</b> pessoas.']
    forca = m.get("features_forca") or []
    if forca:
        t = forca[0]
        ocupados.append(
            f'A variável isolada mais associada à informalidade é <b>{t["label"]}</b> '
            f'(força {t["forca"]:.2f} de 1 — Seção 04).'
        )
    gaps = []
    reg = m.get("regiao_rows") or []
    if len(reg) >= 2:
        gaps.append(("região", reg[0], reg[-1], 100 * (reg[0]["taxa"] - reg[-1]["taxa"])))
    esc = m.get("escolaridade_rows") or []
    if len(esc) >= 2:
        hi, lo = max(esc, key=lambda r: r["taxa"]), min(esc, key=lambda r: r["taxa"])
        gaps.append(("escolaridade", hi, lo, 100 * (hi["taxa"] - lo["taxa"])))
    if gaps:
        nome, hi, lo, g = max(gaps, key=lambda x: x[3])
        ocupados.append(
            f'O maior contraste é por <b>{nome}</b>: {hi["label"]} ({hi["taxa"] * 100:.0f}%) contra '
            f'{lo["label"]} ({lo["taxa"] * 100:.0f}%) — <b>{g:.0f} pontos</b> de diferença.'
        )
    if m.get("tendencia_disponivel") and abs(m["tendencia_delta_pp"]) >= 0.5:
        d = m["tendencia_delta_pp"]
        ocupados.append(
            f'Do primeiro ao último ano da base, a taxa teve <b>{"queda" if d < 0 else "alta"} de '
            f'{abs(d):.1f} p.p.</b>'
        )

    informal = []
    pc = m.get("perfil_cat") or {}
    esc_c = pc.get("VD3004")
    if esc_c and all(c["codigo"] is not None for c in esc_c["categorias"]):
        bi = sum(c["pct_informal"] for c in esc_c["categorias"] if c["codigo"] <= 4)
        bf = sum(c["pct_formal"] for c in esc_c["categorias"] if c["codigo"] <= 4)
        informal.append(
            f'<b>{bi * 100:.0f}%</b> dos informais não concluíram o ensino médio (formais: {bf * 100:.0f}%).'
        )
    setor_c = pc.get("VD4010")
    if setor_c:
        ts = max(setor_c["categorias"], key=lambda c: c["pct_informal"])
        informal.append(f'O setor que mais emprega informais é <b>{ts["label"].lower()}</b> ({ts["pct_informal"] * 100:.0f}%).')
    rg = m.get("renda_gap")
    if rg and rg.get("formal") and rg.get("informal") and rg["formal"]["mediana"]:
        gp = 100 * (rg["formal"]["mediana"] - rg["informal"]["mediana"]) / rg["formal"]["mediana"]
        informal.append(f'Ganha, na mediana, <b>{gp:.0f}% menos</b> que um trabalhador formal.')
    informal.append('Esse é o perfil que RF-05/RF-06 devem aprender a prever — os achados acima são a régua para o modelo.')

    def _tier(titulo: str, itens: list[str], cls: str) -> str:
        lis = "".join(f"<li>{x}</li>" for x in itens)
        return f'<div class="hl-tier hl-tier--{cls}"><div class="hl-tier-head">{titulo}</div><ul>{lis}</ul></div>'

    return (f'<div class="hl"><div class="hl-head">O que os dados dizem</div>'
            f'{_tier("1 · O público total", total, "total")}'
            f'{_tier("2 · Entre os ocupados", ocupados, "ocup")}'
            f'{_tier("3 · O trabalhador informal", informal, "inf")}</div>')


def _como_ler_html() -> str:
    tipos = "".join(
        f'<div class="ler-tipo">{_selo(t)}<span>{desc}</span></div>'
        for t, desc in [
            ("taxa", "Quantos, de 0 a 100%, de um grupo são informais."),
            ("comp", "Como o grupo se divide entre os dois lados — formal e informal."),
            ("corr", "Se duas medidas sobem juntas (+), em sentidos opostos (−) ou nada (perto de 0)."),
            ("forca", "O quanto uma variável acompanha a informalidade — sem dizer a direção."),
        ]
    )
    return (f'<div class="ler"><div class="ler-head">Como ler este boletim</div>'
            f'<p class="ler-p">Cada painel tem um <b>selo</b> no título dizendo que tipo de número mostra. '
            f'Eles não são comparáveis entre si — uma correlação de 0,3 e uma taxa de 30% não querem dizer a mesma coisa.</p>'
            f'<div class="ler-tipos">{tipos}</div>{_regua_correlacao()}'
            f'<p class="ler-nota"><b>Correlação e associação não são causa.</b> E a taxa geral '
            f'é uma média — ela esconde grupos com muito mais e muito menos informalidade.</p></div>')


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


def _heatmap(colunas: list[str], matriz: list[list[float]], limiar: float = 0.20) -> str:
    """Só as células com |r| >= `limiar` ganham cor cheia; o resto fica
    esmaecido, pra não competir visualmente com o que importa. Peso
    amostral (V1028) é sempre esmaecido — é checagem metodológica, não
    uma característica das pessoas.
    """
    labels = [LABELS_CORRELACAO.get(c, c) for c in colunas]
    colheads = "".join(
        f'<div class="heat-colhead{" heat-mute" if colunas[j] == "V1028" else ""}">{lbl}</div>'
        for j, lbl in enumerate(labels)
    )
    linhas = []
    for i, rowlab in enumerate(labels):
        linha_peso = colunas[i] == "V1028"
        linhas.append(f'<div class="heat-rowhead{" heat-mute" if linha_peso else ""}">{rowlab}</div>')
        for j, collab in enumerate(labels):
            v = matriz[i][j]
            fraco = i == j or linha_peso or colunas[j] == "V1028" or abs(v) < limiar
            if fraco:
                linhas.append(
                    f'<div class="cell cell--mute" title="{rowlab} × {collab}: r={v:+.2f}">{v:+.2f}</div>'
                )
            else:
                a = min(0.18 + min(abs(v), 1.0) * 0.7, 0.9)
                cor = f"rgba(42,120,214,{a:.2f})" if v >= 0 else f"rgba(227,73,72,{a:.2f})"
                linhas.append(
                    f'<div class="cell cell--strong" style="background:{cor}" '
                    f'title="{rowlab} × {collab}: r={v:+.2f}">{v:+.2f}</div>'
                )
    return '<div class="heat"><div class="heat-corner"></div>' + colheads + "".join(linhas) + "</div>"


def _par_pearson_texto(colunas: list[str], matriz: list[list[float]], limiar: float = 0.20) -> str:
    """Leitura em português do par de variáveis com maior |r| (ignorando
    o peso amostral) — o que o heatmap quer que o leitor perceba.
    """
    labels = [LABELS_CORRELACAO.get(c, c) for c in colunas]
    melhor = None
    for i in range(len(colunas)):
        for j in range(i + 1, len(colunas)):
            if "V1028" in (colunas[i], colunas[j]):
                continue
            v = matriz[i][j]
            if melhor is None or abs(v) > abs(melhor[2]):
                melhor = (labels[i], labels[j], v)
    if not melhor:
        return ""
    a, b, v = melhor
    leitura = (f'<b>{a}</b> e <b>{b}</b> tendem a subir juntas' if v >= 0
               else f'quando <b>{a}</b> sobe, <b>{b}</b> tende a cair')
    intens = "forte" if abs(v) >= 0.5 else ("moderada" if abs(v) >= 0.3 else "fraca")
    return (f'<p class="panel-caption">Par mais forte: {leitura} (r = {v:+.2f}, correlação {intens}). '
            f'As células com |r| abaixo de {limiar:.2f} estão esmaecidas de propósito. '
            f'<b>Peso amostral</b> aparece só como checagem — não é característica das pessoas.</p>')


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
        caption = f'<p class="panel-caption">Quem é informal ganha, na mediana, <b>{gap_pct:.0f}% menos</b> que quem é formal.</p>'
    aviso = ('<div class="aviso"><b>Renda não entra no modelo.</b> Ela é <i>consequência</i> da '
             'informalidade, não causa — usá-la como preditora seria <i>data leakage</i> (ver '
             '<code>docs/03-dicionario-de-dados.md</code>). Fica aqui só como contexto econômico do problema.</div>')
    return f'''<div class="panel">
        <div class="panel-head"><div class="panel-title">Renda: o gap salarial formal × informal</div>{_selo("leak")}</div>
        {aviso}{tabela}{caption}
      </div>'''


def _secao_funil_html(funil: dict, base_label: str) -> str:
    total_fmt = f'{funil["total"]:,}'.replace(",", ".")
    ocup = next((g for g in funil["grupos"] if g["label"].startswith("Ocupados")), None)
    tk = ""
    if ocup:
        n_fmt = f'{ocup["n"]:,}'.replace(",", ".")
        tk = _takeaway(
            f'De cada 100 pessoas na base bruta, cerca de <b>{ocup["pct_total"]:.0f}</b> estão ocupadas. '
            f'Todas as taxas deste boletim falam só dessas <b>{n_fmt}</b> pessoas — não da população inteira.'
        )
    return f'''<section class="block">
        <div class="sec-head"><span class="sec-num">00</span><h2>Quem entra na conta</h2></div>
        <p class="sec-intro">Antes de qualquer taxa: a informalidade só é definida para quem está <b>ocupado</b> (<code>VD4002=1</code>). Dos {total_fmt} registros da {base_label}, a tabela mostra cada corte e como o grupo cortado se compara — em sexo e idade — a quem segue na análise.</p>
        {tk}
        {_definicao_informal_html()}
        <div class="panel">
          <div class="panel-head"><div class="panel-title">Funil: da base bruta aos ocupados</div>{_selo("grupos")}</div>
          {_funil_table(funil)}{_funil_interpretacao(funil)}
        </div>
      </section>'''


def _painel_segmentacao(titulo: str, rows: list[dict], body_id: str | None = None,
                        ordinal: bool = False, flush: bool = True) -> str:
    """Um painel de segmentação padronizado: takeaway automático + barra
    de comparação 100% formal × informal + (para recortes ordinais) selo
    de tendência monotônica.
    """
    style = ' style="margin-left:0;"' if flush else ""
    idattr = f' id="{body_id}"' if body_id else ""
    tk = ""
    if len(rows) >= 2:
        hi, lo = max(rows, key=lambda r: r["taxa"]), min(rows, key=lambda r: r["taxa"])
        g = 100 * (hi["taxa"] - lo["taxa"])
        tk = (f'<p class="painel-tk"><b>{hi["label"]}</b>: {hi["taxa"] * 100:.0f}% informais (o maior). '
              f'<b>{lo["label"]}</b>: {lo["taxa"] * 100:.0f}% (o menor). {g:.0f} pontos separam os dois.</p>')
    tend = _tendencia_texto(rows) if ordinal else ""
    return (f'<div class="panel"{style}>'
            f'<div class="panel-head"><div class="panel-title">{titulo}</div>{_selo("comp")}</div>'
            f'{tk}{_cmp_legenda()}<div{idattr}>{_barra_comparacao_rows(rows)}</div>{tend}</div>')


def _secao_segmentacao_extra(m: dict) -> str:
    """Corpo da Seção 03 — onde a informalidade se concentra. Cada recorte
    é uma barra 100% empilhada formal × informal, com o número informal em
    destaque. O seletor de ano é comparação (troca o ano exibido, mantém
    os dois lados), não um filtro que isola informais.
    """
    anos = sorted(int(a) for a in m["segmentacao_por_ano"] if a != "todos")
    n_ocupados_fmt = f'{m["n_ocupados"]:,}'.replace(",", ".")
    kpis_html = f'''<div class="seg-kpis">
          <span class="kpi-mini">Ocupados no recorte: <b id="seg-kpi-n">{n_ocupados_fmt}</b></span>
          <span class="kpi-mini">Taxa: <b id="seg-kpi-taxa">{m["taxa_geral"] * 100:.1f}%</b></span>
        </div>'''
    ordinais_nota = ('<p class="sec-intro" style="margin-top:34px;">Nos recortes com ordem natural '
                     '(escolaridade, tempo no emprego, tamanho do negócio) as categorias ficam na ordem da '
                     'escala — não na ordem da taxa — para deixar ver se a tendência é monotônica ou onde quebra.</p>')
    return f'''{_select_ano_html(anos, kpis_html)}
      <div class="grid-2" style="margin-top:26px;">
        {_painel_segmentacao("Por sexo", m["sexo_rows"], "panel-sexo-body")}
        {_painel_segmentacao("Por cor/raça", m["raca_rows"], "panel-raca-body")}
      </div>
      {_painel_segmentacao("Por região", m["regiao_rows"], "panel-regiao-body", flush=False)}
      {_segmentacao_script(m["segmentacao_por_ano"])}
      {ordinais_nota}
      <div class="grid-2">
        {_painel_segmentacao("Por escolaridade", m["escolaridade_rows"], ordinal=True)}
        {_painel_segmentacao("Por tempo no emprego", m["tempo_emprego_rows"], ordinal=True)}
      </div>
      <div class="grid-2" style="margin-top:22px;">
        {_painel_segmentacao("Por tamanho do negócio", m["tamanho_negocio_rows"], ordinal=True)}
        {_painel_segmentacao("Por grupamento ocupacional", m["ocupacao_rows"])}
      </div>
      {_painel_segmentacao("Por setor de atividade", m["setor_rows"], flush=False)}'''


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
        f'indício de viés de seleção (quem decide entrar no mercado de trabalho já não é uma amostra aleatória da população; ver hipóteses na Seção 07).</p>'
    )


def _select_ano_html(anos_disponiveis: list[int], kpis_html: str = "") -> str:
    opcoes = '<option value="todos" selected>Todos os anos juntos</option>' + "".join(
        f'<option value="{a}">Só {a}</option>' for a in anos_disponiveis
    )
    return f'''<div class="filtro-row">
      <label for="filtro-ano">Ver os recortes abaixo por ano</label>
      <select id="filtro-ano" onchange="aplicarFiltroAno(this.value)">{opcoes}</select>
      <span class="filtro-nota">Troca o ano exibido — cada barra continua mostrando os dois lados (formal e informal).</span>
      {kpis_html}
    </div>'''


def _segmentacao_script(segmentacao_por_ano: dict) -> str:
    """JS standalone que redesenha as barras de comparação de sexo/raça/
    região por ano a partir do JSON embarcado — sem backend, tudo
    pré-calculado em Python. Espelha `_barra_comparacao_rows` em JS.
    """
    dados_json = json.dumps(segmentacao_por_ano, ensure_ascii=False).replace("</", "<\\/")
    return f'''<script>
      const DADOS_POR_ANO = {dados_json};
      function _fmtN(n) {{ return n.toLocaleString('pt-BR'); }}
      function _renderCmp(rows) {{
        if (!rows.length) return '';
        const taxas = rows.map(r => r.taxa);
        const mx = Math.max.apply(null, taxas), mn = Math.min.apply(null, taxas);
        const marcar = rows.length > 1 && mx !== mn;
        return rows.map(r => {{
          const inf = 100 * r.taxa;
          const thin = r.n < 500 ? ' thin' : '';
          let marca = '';
          if (marcar && r.taxa === mx) marca = '<span class="cmp-mark cmp-mark--max">\\u25b2</span>';
          else if (marcar && r.taxa === mn) marca = '<span class="cmp-mark cmp-mark--min">\\u25bd</span>';
          const rotulo = inf >= 12 ? Math.round(inf) + '%' : '';
          return '<div class="cmp-row' + thin + '"><div class="cmp-label">' + marca + r.label + '</div>'
            + '<div class="cmp-track">'
            + '<div class="cmp-seg cmp-seg--inf" style="width:' + inf.toFixed(1) + '%">' + rotulo + '</div>'
            + '<div class="cmp-seg cmp-seg--for" style="width:' + (100 - inf).toFixed(1) + '%"></div></div>'
            + '<div class="cmp-val"><b>' + inf.toFixed(1) + '%</b> informais<span class="cmp-n">n=' + _fmtN(r.n) + '</span></div></div>';
        }}).join('');
      }}
      function aplicarFiltroAno(ano) {{
        const d = DADOS_POR_ANO[ano];
        if (!d) return;
        document.getElementById('seg-kpi-n').textContent = _fmtN(d.n_ocupados);
        document.getElementById('seg-kpi-taxa').textContent = (d.taxa_geral * 100).toFixed(1) + '%';
        document.getElementById('panel-sexo-body').innerHTML = _renderCmp(d.sexo_rows);
        document.getElementById('panel-raca-body').innerHTML = _renderCmp(d.raca_rows);
        document.getElementById('panel-regiao-body').innerHTML = _renderCmp(d.regiao_rows);
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
            f'{nomes} lideram a associação isolada com informalidade (Seção 04) — hipótese: a '
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


_CSS_EDA = """
  .linechart-svg{width:100%;height:auto;overflow:visible}.grid-line{stroke:var(--border);stroke-width:1}
  .axis-y-label{font-family:"IBM Plex Mono",monospace;font-size:10.5px;fill:var(--ink-muted)}
  .axis-x{font-family:"IBM Plex Mono",monospace;font-size:10.5px;fill:var(--ink-muted);text-anchor:middle}
  .area-fill{fill:var(--accent-soft-2)}.line-path{fill:none;stroke:var(--accent);stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
  .pt{fill:var(--surface);stroke:var(--accent);stroke-width:2}
  .hist-row{display:flex;align-items:flex-end;gap:4px;height:140px;margin-top:18px}
  .hist-col{flex:1;display:flex;flex-direction:column;align-items:center;height:100%;justify-content:flex-end}
  .hist-bar{width:100%;background:var(--accent);border-radius:3px 3px 0 0;min-height:2px}
  .hist-lbl{margin-top:7px;font-size:.62rem;color:var(--ink-muted)}
  .heat-wrap{overflow-x:auto;margin-top:20px}.heat{display:grid;grid-template-columns:128px repeat(6,minmax(74px,1fr));gap:3px;min-width:620px}
  .heat-colhead,.heat-rowhead{font-size:.72rem;color:var(--ink-muted);font-weight:600;display:flex;align-items:center}
  .heat-colhead{justify-content:center;text-align:center;padding:4px 2px}.heat-rowhead{padding-right:8px}
  .cell{aspect-ratio:1;border-radius:7px;display:flex;align-items:center;justify-content:center;font-family:"IBM Plex Mono",monospace;font-size:.78rem;font-weight:600}
  .cell--mute{background:var(--surface-2);color:var(--ink-muted);opacity:.5}
  .cell--strong{color:#fff;font-weight:700}
  .heat-mute{opacity:.45;font-style:italic}
  .div-rows{display:grid;gap:14px;margin-top:20px}.div-row{display:grid;grid-template-columns:150px 1fr 64px;align-items:center;gap:12px}
  .div-label{font-size:.87rem;color:var(--ink-2)}.div-track{position:relative;height:22px;background:var(--surface-2);border-radius:5px;overflow:hidden}
  .div-mid{position:absolute;left:50%;top:0;bottom:0;width:1px;background:var(--border-strong)}
  .div-bar{position:absolute;top:2px;bottom:2px;border-radius:3px}.div-bar.pos{left:50%;background:var(--accent)}.div-bar.neg{right:50%;background:var(--negative)}
  .div-val{font-family:"IBM Plex Mono",monospace;font-size:.82rem;text-align:right}
  .filtro-row{display:flex;align-items:center;gap:10px;margin:26px 0 0 calc(2ch + 18px);flex-wrap:wrap}
  @media (max-width:760px){.filtro-row{margin-left:0}}
  .filtro-row label{font-size:.85rem;color:var(--ink-muted)}
  .filtro-row select{font:inherit;font-size:.86rem;color:var(--ink);background:var(--surface);border:1px solid var(--border-strong);border-radius:8px;padding:6px 10px}
  .filtro-nota{font-size:.78rem;color:var(--ink-muted);flex-basis:100%}
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
  .regua-bar--corr{height:14px;border-radius:7px;background:linear-gradient(90deg,#c8302f,#e3b6b5 34%,var(--surface-2) 50%,#a9c8ea 66%,#2a78d6)}
  .regua-bar--forca{display:flex;height:20px;border-radius:6px;overflow:hidden;background:var(--surface-2)}
  .regua-bar--forca .fb{display:flex;align-items:center;justify-content:center;font-size:9px;font-family:"IBM Plex Mono",monospace;color:#fff;text-shadow:0 1px 2px rgba(0,0,0,.4);background:linear-gradient(90deg,rgba(124,92,191,.35),rgba(124,92,191,.95));border-right:1px solid rgba(255,255,255,.25)}
  .regua-bar--forca .fb:last-child{border-right:0}
  .rank-rows{display:grid;gap:12px;margin-top:8px}
  .rank-row{display:grid;grid-template-columns:190px 1fr 120px;align-items:center;gap:12px}
  .rank-label{font-size:.86rem;color:var(--ink-2)}.rank-tipo{display:block;font-size:.68rem;color:var(--ink-muted);font-family:"IBM Plex Mono",monospace}
  .rank-track{height:20px;background:var(--surface-2);border-radius:5px;overflow:hidden}
  .rank-fill{height:100%;background:var(--type-forca);border-radius:5px}
  .rank-val{font-family:"IBM Plex Mono",monospace;font-size:.8rem;text-align:right;color:var(--ink)}.rank-n{display:block;font-size:.7rem;color:var(--ink-muted)}
  .rank-row.thin{opacity:.55}
  .cmp-legend,.pc-legend{display:flex;gap:16px;margin:12px 0 2px;font-size:.76rem;color:var(--ink-muted);flex-wrap:wrap}
  .cmp-k,.pc-k{display:flex;align-items:center;gap:6px}
  .cmp-k::before,.pc-k::before{content:"";width:12px;height:12px;border-radius:3px}
  .cmp-k--inf::before,.pc-k--inf::before{background:var(--accent)}
  .cmp-k--for::before,.pc-k--for::before{background:var(--type-comp-for)}
  .cmp-rows{display:grid;gap:11px;margin-top:12px}
  .cmp-row{display:grid;grid-template-columns:130px 1fr 150px;align-items:center;gap:12px}
  .cmp-label{font-size:.86rem;color:var(--ink-2)}
  .cmp-track{display:flex;height:22px;border-radius:5px;overflow:hidden;background:var(--type-comp-for)}
  .cmp-seg{height:100%;display:flex;align-items:center;justify-content:flex-end;padding-right:6px;font-family:"IBM Plex Mono",monospace;font-size:.72rem;color:#fff;font-weight:600}
  .cmp-seg--inf{background:var(--accent)}.cmp-seg--for{background:transparent}
  .cmp-val{font-family:"IBM Plex Mono",monospace;font-size:.78rem;color:var(--ink-muted);text-align:right}
  .cmp-val b{color:var(--ink);font-size:.9rem}.cmp-n{display:block;font-size:.7rem}
  .cmp-mark{font-size:.7rem;margin-right:5px}.cmp-mark--max{color:var(--negative)}.cmp-mark--min{color:var(--aqua)}
  .cmp-row.thin{opacity:.6}
  .cmp-num td .faixa-iqr{color:var(--ink-muted);font-size:.82em}
  .cmp-num .cmp-delta-cell{font-family:"IBM Plex Mono",monospace}
  .retrato{margin-top:22px;border:1px solid var(--accent);background:var(--accent-soft-2);border-radius:16px;padding:22px 26px}
  .retrato-head{font-weight:700;font-size:1.05rem;color:var(--accent-ink)}
  .retrato-sub{font-size:.9rem;color:var(--ink-2);margin:4px 0 12px}
  .retrato ul{margin:0;padding-left:1.15em;display:grid;gap:8px}
  .retrato li{font-size:.98rem;line-height:1.5;color:var(--ink)}.retrato li b{color:var(--accent-ink)}
  .pc-rows{display:grid;gap:9px;margin-top:12px}
  .pc-row{display:grid;grid-template-columns:200px 1fr 150px;align-items:center;gap:12px}
  .pc-label{font-size:.84rem;color:var(--ink-2)}
  .pc-bars{display:grid;gap:3px}.pc-bar{height:9px;border-radius:3px;min-width:2px}
  .pc-bar--inf{background:var(--accent)}.pc-bar--for{background:var(--type-comp-for)}
  .pc-val{font-family:"IBM Plex Mono",monospace;font-size:.78rem;text-align:right;color:var(--ink)}
  .pc-vs{color:var(--ink-muted)}.pc-delta{display:block;font-size:.72rem}
  .pc-over{color:var(--over)}.pc-under{color:var(--under)}
  .def-informal{margin-left:calc(2ch + 18px);margin-top:18px}
  .def-informal .def-body{padding-bottom:16px}
  .def-informal p{font-size:.9rem;line-height:1.55;color:var(--ink-2);margin:0 0 10px}
  .def-informal ul{margin:0 0 10px;padding-left:1.2em;display:grid;gap:5px}
  .def-informal li{font-size:.9rem;line-height:1.5;color:var(--ink-2)}
  @media (max-width:760px){.def-informal{margin-left:0}
    .rank-row{grid-template-columns:130px 1fr 92px}
    .cmp-row{grid-template-columns:96px 1fr 110px}
    .pc-row{grid-template-columns:120px 1fr 100px}}
"""


def renderizar_censo(m: dict) -> str:
    """Monta o HTML completo do Censo da Informalidade a partir das
    métricas calculadas por `calcular_metricas`. A narrativa vai do
    público total (Seção 00) ao perfil do trabalhador informal (Seção 02)
    e às associações que o modelo RF-05/RF-06 deve confirmar.
    """
    n_inf = round(m["n_ocupados"] * m["taxa_geral"])
    n_for = m["n_ocupados"] - n_inf
    kpis = f'''<div class="kpis">
      <div class="kpi"><div class="kpi-label">Pessoas ocupadas</div><div class="kpi-value">{m["n_ocupados"]:,}</div><div class="kpi-sub">{m["n_trimestres"]} trimestres · {m["ano_min"]}–{m["ano_max"]}</div></div>
      <div class="kpi"><div class="kpi-label">São informais</div><div class="kpi-value" style="color:var(--accent-ink)">{n_inf:,}</div><div class="kpi-sub">{m["taxa_geral"] * 100:.1f}% dos ocupados</div></div>
      <div class="kpi"><div class="kpi-label">São formais</div><div class="kpi-value">{n_for:,}</div><div class="kpi-sub">{(1 - m["taxa_geral"]) * 100:.1f}% dos ocupados</div></div>
      <div class="kpi"><div class="kpi-label">Base</div><div class="kpi-value" style="font-size:1.35rem">PNAD Contínua</div><div class="kpi-sub">IBGE · camada Gold</div></div>
    </div>'''.replace(",", ".")

    tendencia_txt = ""
    if m["tendencia_disponivel"]:
        delta = m["tendencia_delta_pp"]
        direcao = "queda" if delta < 0 else ("alta" if delta > 0 else "estabilidade")
        tendencia_txt = (f'<p class="panel-caption">Do primeiro ao último ano da base: '
                         f'<b>{direcao} de {abs(delta):.1f} ponto(s) percentuais</b> na taxa.</p>')

    linechart = _linha_chart_svg(m["periodo_rows"])
    tk_tempo = _takeaway(
        f'A informalidade fica em torno de <b>{m["taxa_geral"] * 100:.0f}%</b> e varia pouco no tempo — '
        f'entre {m["taxa_min"] * 100:.1f}% ({m["periodo_taxa_min"]}) e {m["taxa_max"] * 100:.1f}% ({m["periodo_taxa_max"]}).'
    )

    hist_html = ""
    for col in ["V2009", "VD4031"]:
        d = m["descritivas"].get(col)
        if d:
            hist_html += f'''<div class="panel" style="margin-left:0;">
              <div class="panel-head"><div class="panel-title">Distribuição — {d["label"]}</div>{_selo("dist")}</div>
              {_hist_bars(d["hist_counts"], d["hist_bins"])}
              <p class="panel-caption">{d["outliers_n"]:,} valores ({d["outliers_pct"]}%) fora da faixa IQR — distribuição no total de ocupados.</p>
            </div>'''.replace(",", ".")

    heatmap = _heatmap(m["correlacao_colunas"], m["correlacao_matriz"])
    par_pearson = _par_pearson_texto(m["correlacao_colunas"], m["correlacao_matriz"])
    divbars = _divbar_rows(m["ponto_bisserial"])
    segmentacao_extra = _secao_segmentacao_extra(m)
    secao_funil = _secao_funil_html(m["funil"], "Silver") if m.get("funil") else ""
    highlights = _highlights_html(m)
    retrato = _retrato_informal_html(m)
    perfil_num_html = _perfil_num_html(m.get("perfil_num") or {})
    renda_gap_html = _renda_gap_html(m["renda_gap"]) if m.get("renda_gap") else ""

    pc = m.get("perfil_cat") or {}
    perfil_cat_paineis = ""
    for chave, top in [("VD3004", None), ("VD4010", 6)]:
        dados = pc.get(chave)
        if dados:
            perfil_cat_paineis += f'''<div class="panel">
              <div class="panel-head"><div class="panel-title">Composição por {dados["label"].lower()}</div>{_selo("comp")}</div>
              <p class="painel-tk">Cada linha: quanto de cada lado (informais / formais) está nessa categoria. Verde = informais aparecem mais aí; vermelho = menos.</p>
              {_pc_legenda()}{_perfil_cat_bloco(dados, top)}
            </div>'''

    secao_hipoteses = f'''<section class="block">
        <div class="sec-head"><span class="sec-num">07</span><h2>Hipóteses para a modelagem</h2></div>
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
    ranking_tk = ""
    if m["features_forca"]:
        top3 = ", ".join(f'<b>{f["label"]}</b>' for f in m["features_forca"][:3])
        ranking_tk = _takeaway(
            f'As variáveis que mais acompanham a informalidade, isoladamente: {top3}. '
            f'Nenhuma sozinha "explica" — o modelo combina todas.'
        )
    secao_features = f'''<section class="block">
        <div class="sec-head"><span class="sec-num">04</span><h2>Quais fatores mais se associam à informalidade</h2></div>
        <p class="sec-intro">Força de associação de cada feature candidata com o alvo — V de Cramér para categóricas, correlação ponto-bisserial (|r|) para numéricas, ambas na mesma escala de 0 a 1. Não dizem direção nem causa. Sexo e raça entram no modelo mesmo com força baixa (RF-06 mede o peso delas via SHAP).</p>
        {ranking_tk}
        <div class="panel">
          <div class="panel-head"><div class="panel-title">Ranking de força de associação</div>{_selo("forca")}</div>
          {_regua_forca()}{ranking_html}{nota_fraca}
        </div>
      </section>'''

    secao_pearson = f'''<section class="block">
        <div class="sec-head"><span class="sec-num">05</span><h2>Matriz de correlação entre as numéricas</h2></div>
        <p class="sec-intro">Correlação de Pearson entre as variáveis numéricas (escala −1 a +1). Só as células com |r| relevante estão destacadas — o resto fica esmaecido de propósito. Correlação não é causa.</p>
        <div class="panel">
          <div class="panel-head"><div class="panel-title">Pearson entre numéricas</div>{_selo("corr")}</div>
          {_regua_correlacao()}
          <div class="heat-wrap">{heatmap}</div>
          {par_pearson}
        </div>
        <div class="panel">
          <div class="panel-head"><div class="panel-title">Ponto-bisserial: cada numérica × ser informal</div>{_selo("corr")}</div>
          <p class="painel-tk">Mesma matemática de Pearson, com "ser informal" (sim/não) no lugar da segunda variável. Barra para a direita = quanto mais daquilo, mais informalidade.</p>
          {divbars}
        </div>
      </section>'''

    secao_nulos = ""
    if "nulos_grupos" in m:
        secao_nulos = f'''<section class="block">
        <div class="sec-head"><span class="sec-num">06</span><h2>Percentual de campos nulos</h2></div>
        <p class="sec-intro">Nulo aqui é <b>estrutural</b> — o desenho de "pulo de pergunta" da PNAD, não falha de coleta. Calculado sobre os {m["n_silver_total"]:,} registros da Silver, antes do filtro de ocupados.</p>
        <div class="panel"><div class="panel-head"><div class="panel-title">Nulos por grupo de variáveis</div></div>{_null_rows(m["nulos_grupos"])}</div>
      </section>'''.replace(",", ".")

    corpo = f'''  <header class="top">
    <div class="eyebrow">Boletim de análise exploratória · PNAD Contínua · gerado pelo pipeline (RF-04)</div>
    <h1>Censo da <em>informalidade</em> — {m["ano_min"]}–{m["ano_max"]}</h1>
    <p class="lede">Quem é o trabalhador informal no Brasil, a partir de <b>{m["n_ocupados"]:,}</b> pessoas ocupadas da PNAD Contínua. Gerado automaticamente por <code>src/analise/analise.py</code> — cada reprocessamento do pipeline regenera este relatório com os números novos.</p>
    <div class="callout callout--metodo">
      <div class="callout-head">Antes dos números — 4 avisos que mudam a leitura</div>
      <ul>
        <li><b>Não é ponderado pelo peso amostral (<code>V1028</code>).</b> As taxas são proporção simples da base de respondentes ocupados — não a estimativa oficial do IBGE para a população. Servem para comparar grupos entre si, não como número de manchete.</li>
        <li><b>Renda fica de fora do modelo.</b> É consequência da informalidade, não causa (data leakage). Aparece só como contexto na Seção 02.</li>
        <li><b>Correlação e associação não são causa</b>, e a taxa geral de {m["taxa_geral"] * 100:.1f}% é uma média que esconde grupos com muito mais e muito menos informalidade.</li>
        <li><b>A regra de "informal" é uma escolha do time</b>, baseada em <code>VD4009</code> — a Seção 00 explica qual e por quê. Ainda pendente de validação formal (RF-03).</li>
      </ul>
    </div>
    {kpis}
    {highlights}
    {_como_ler_html()}
  </header>

  {secao_funil}

  <section class="block">
    <div class="sec-head"><span class="sec-num">01</span><h2>Quanto, e se muda no tempo</h2></div>
    <p class="sec-intro">Taxa de informalidade trimestre a trimestre, entre pessoas ocupadas.</p>
    {tk_tempo}
    <div class="panel">
      <div class="panel-head"><div class="panel-title">Taxa de informalidade por trimestre</div>{_selo("taxa")}</div>
      {linechart}
      {tendencia_txt}
    </div>
  </section>

  <section class="block">
    <div class="sec-head"><span class="sec-num">02</span><h2>Quem é o trabalhador informal</h2></div>
    <p class="sec-intro">O coração do boletim: em que o informal difere do formal. É este contraste que o modelo (RF-05/RF-06) vai aprender a reconhecer.</p>
    {retrato}
    <div class="panel">
      <div class="panel-head"><div class="panel-title">Idade, jornada e domicílio — formal × informal</div>{_selo("comp")}</div>
      {perfil_num_html}
      <p class="panel-caption">Mediana de cada grupo, com a faixa dos 50% centrais (P25–P75) entre parênteses.</p>
    </div>
    {perfil_cat_paineis}
    <div class="grid-2">{hist_html}</div>
    {renda_gap_html}
  </section>

  <section class="block">
    <div class="sec-head"><span class="sec-num">03</span><h2>Onde a informalidade se concentra</h2></div>
    <p class="sec-intro">A taxa geral ({m["taxa_geral"] * 100:.1f}%) é uma média. Cada recorte abaixo abre um grupo e mostra quanto dele é informal e quanto é formal — o número em destaque é sempre a fatia informal.</p>
    {segmentacao_extra}
  </section>

  {secao_features}

  {secao_pearson}

  {secao_nulos}

  {secao_hipoteses}

  {_glossario_html()}

  <footer>
    <div class="foot-col"><b style="color:var(--ink);">Fonte:</b> PNAD Contínua, IBGE — camada Gold do pipeline InformalidadeBR, gerada por <code>src/transformacao/transformacao.py</code>. Estimativas <b>não ponderadas</b> por <code>V1028</code>.</div>
    <div class="foot-col"><b style="color:var(--ink);">Gerado por:</b> <code>src/analise/analise.py</code> (RF-04) — regenere rodando <code>pipeline.analisar()</code> ou <code>python -m src.pipeline</code>.</div>
  </footer>'''
    return montar_pagina("Censo da Informalidade", corpo, _CSS_EDA)
