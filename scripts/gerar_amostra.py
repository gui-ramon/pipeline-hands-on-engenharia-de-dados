"""Gera amostras pequenas da Bronze (bruta) e da Silver (tratada), mais uma
cópia do dicionário oficial do IBGE, em `dados_amostra/` — a única parte de
`dados/` que é versionada no Git.

`dados/` inteira é ignorada pelo `.gitignore` (arquivos grandes: ~63MB só a
Silver consolidada, ~19GB a Bronze). Só que os orientadores/avaliadores
precisam conseguir abrir algo direto no GitHub, sem rodar o pipeline
localmente — por isso essas amostras pequenas e o dicionário ficam fora de
`dados/`, em uma pasta própria que **é** versionada. A amostra da Bronze dá
o "antes" (exatamente como o IBGE publica, largura fixa, sem tratamento) e
a da Silver dá o "depois" (as 22 variáveis selecionadas, nulos tratados,
deduplicadas pela chave real) — o par serve como evidência visual do
antes/depois do pré-processamento.

Uso (depois de rodar a ingestão e o pré-processamento):
    python -m scripts.gerar_amostra
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pandas as pd

RAIZ_PROJETO = Path(__file__).resolve().parent.parent
CAMINHO_BRONZE = RAIZ_PROJETO / "dados" / "bronze"
CAMINHO_SILVER = RAIZ_PROJETO / "dados" / "silver" / "dados_silver.parquet"
CAMINHO_DICIONARIO = (
    RAIZ_PROJETO
    / "dados"
    / "bronze"
    / "documentacao"
    / "dicionario_PNADC_microdados_trimestral.xls"
)
CAMINHO_AMOSTRA = RAIZ_PROJETO / "dados_amostra"

N_LINHAS_AMOSTRA = 1000
N_LINHAS_AMOSTRA_BRONZE = 500
SEED = 42  # reprodutibilidade (RNF-12)
ENCODING_BRONZE = "latin-1"


def _periodo_bronze_mais_recente() -> Path:
    """Encontra o arquivo .txt do período mais recente na Bronze (maior
    ano, depois maior trimestre) — não dá pra ordenar pelo nome do arquivo
    porque `PNADC_0<trimestre><ano>.txt` não ordena cronologicamente como
    string (ex.: "042023" > "012024" na ordenação lexicográfica, mas
    2024-Q1 é depois de 2023-Q4).
    """
    candidatos = []
    for arquivo in CAMINHO_BRONZE.glob("*/PNADC_*.txt"):
        correspondencia = re.match(r"PNADC_0(\d)(\d{4})\.txt$", arquivo.name)
        if correspondencia:
            trimestre, ano = int(correspondencia.group(1)), int(correspondencia.group(2))
            candidatos.append(((ano, trimestre), arquivo))
    if not candidatos:
        raise FileNotFoundError(
            f"Nenhum arquivo PNADC_*.txt encontrado em {CAMINHO_BRONZE} — rode a ingestão antes."
        )
    candidatos.sort(key=lambda item: item[0])
    return candidatos[-1][1]


def gerar_amostra_bronze() -> Path:
    """Copia as primeiras N_LINHAS_AMOSTRA_BRONZE linhas do período mais
    recente da Bronze, byte a byte (mesmo encoding, sem decodificar nada) —
    exatamente como foi baixado do IBGE, pra dar o "antes" do
    pré-processamento.
    """
    arquivo_origem = _periodo_bronze_mais_recente()
    CAMINHO_AMOSTRA.mkdir(parents=True, exist_ok=True)
    destino = CAMINHO_AMOSTRA / "pnadc_bronze_amostra.txt"
    with (
        open(arquivo_origem, encoding=ENCODING_BRONZE) as origem,
        open(destino, "w", encoding=ENCODING_BRONZE, newline="") as saida,
    ):
        for indice, linha in enumerate(origem):
            if indice >= N_LINHAS_AMOSTRA_BRONZE:
                break
            saida.write(linha)
    return destino


def gerar_amostra_silver() -> Path:
    """Sorteia ~N_LINHAS_AMOSTRA linhas da Silver consolidada, com a mesma
    quantidade por período (ano/trimestre) para a amostra não ficar
    concentrada só no período mais recente, e grava como CSV (abre direto
    no GitHub/Excel, sem precisar de pandas/pyarrow para conferir).
    """
    if not CAMINHO_SILVER.exists():
        raise FileNotFoundError(
            f"{CAMINHO_SILVER} não encontrado — rode o pré-processamento antes "
            "(notebooks/02_preprocessamento.ipynb ou "
            "`python -m src.preprocessamento.preprocessamento`)."
        )
    dados = pd.read_parquet(CAMINHO_SILVER)
    n_periodos = dados.groupby(["Ano", "Trimestre"]).ngroups
    n_por_periodo = max(1, N_LINHAS_AMOSTRA // n_periodos)

    amostra = (
        dados.groupby(["Ano", "Trimestre"], group_keys=False)
        .sample(n=n_por_periodo, random_state=SEED)
        .sample(frac=1, random_state=SEED)  # embaralha a ordem final
        .reset_index(drop=True)
    )

    CAMINHO_AMOSTRA.mkdir(parents=True, exist_ok=True)
    destino = CAMINHO_AMOSTRA / "pnadc_silver_amostra.csv"
    amostra.to_csv(destino, index=False)
    return destino


def copiar_dicionario() -> Path:
    """Copia o dicionário oficial de variáveis do IBGE (.xls) para
    `dados_amostra/`, já que `dados/` inteira é ignorada pelo Git.
    """
    if not CAMINHO_DICIONARIO.exists():
        raise FileNotFoundError(f"{CAMINHO_DICIONARIO} não encontrado — rode a ingestão antes.")
    CAMINHO_AMOSTRA.mkdir(parents=True, exist_ok=True)
    destino = CAMINHO_AMOSTRA / CAMINHO_DICIONARIO.name
    shutil.copy2(CAMINHO_DICIONARIO, destino)
    return destino


if __name__ == "__main__":
    caminho_bronze = gerar_amostra_bronze()
    linhas_bronze = sum(1 for _ in open(caminho_bronze, encoding=ENCODING_BRONZE))
    print(f"Amostra da Bronze gravada em {caminho_bronze} ({linhas_bronze} linhas)")

    caminho_csv = gerar_amostra_silver()
    linhas = sum(1 for _ in open(caminho_csv, encoding="utf-8")) - 1
    print(f"Amostra da Silver gravada em {caminho_csv} ({linhas} linhas)")

    caminho_xls = copiar_dicionario()
    print(f"Dicionario do IBGE copiado para {caminho_xls}")
