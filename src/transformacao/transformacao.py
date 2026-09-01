"""Etapa de transformação: curadoria e agregação para a camada Gold.

Implementa RF-03: aplica a regra de negócio de informalidade sobre a
Silver consolidada e filtra o dataset para as pessoas ocupadas, gerando
a coluna-alvo binária (`informal`) e o conjunto de dados pronto para EDA
(RF-04) e modelagem (RF-05/RF-06).

Regra de informalidade (ver `docs/03-dicionario-de-dados.md`): baseada em
`VD4009` (posição na ocupação), com `V4019` (tem CNPJ?) desempatando
empregador/conta-própria — é a convenção acadêmica mais comum, mas o
próprio dicionário registra a alternativa mais simples de usar só
`VD4012` (contribuinte de previdência) como proxy binário direto. Time
deve validar esta escolha antes de considerá-la definitiva; ver
"Trabalho futuro" em `docs/04-arquitetura.md`.

Vazamento de dado (data leakage) a evitar na modelagem (RF-05): as
colunas usadas para construir o alvo (`VD4009`, `V4019`, `VD4012`) e o
próprio filtro (`VD4002`) são descartadas aqui — mantê-las como feature
faria o modelo aprender a copiar a definição do alvo. `VD4016`/`VD4017`
(renda) são mantidas só para uso em EDA (ex.: gap salarial formal x
informal), pelo mesmo motivo não devem virar feature do modelo.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.etapa import Etapa

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

CAMINHO_SILVER = Path("dados/silver")
CAMINHO_GOLD = Path("dados/gold")

# VD4009: posição na ocupação e categoria do emprego no trabalho principal.
# Categorias 2/4/6/10 são informais em qualquer caso (empregado/doméstico
# sem carteira, trabalhador familiar auxiliar). 8/9 (empregador/conta-
# própria) dependem de V4019 (tem CNPJ?) para desempate.
CATEGORIAS_INFORMAIS_DIRETAS = {2, 4, 6, 10}
CATEGORIAS_DEPENDEM_DE_CNPJ = {8, 9}

# Colunas usadas só para construir o alvo/filtro — descartadas da Gold
# para não vazarem para a modelagem (ver docstring do módulo).
COLUNAS_ALVO_BRUTO = ["VD4009", "V4019", "VD4012", "VD4002"]

# Colunas mantidas só para EDA (RF-04) — não usar como feature (RF-05).
COLUNAS_SO_EDA = ["VD4016", "VD4017"]


@dataclass
class ResultadoTransformacao:
    """Resultado da curadoria da camada Gold."""

    linhas_entrada: int
    linhas_ocupados: int
    taxa_informalidade: float | None


class Transformacao(Etapa):
    """Cura e agrega os dados da camada Silver, gerando a camada Gold
    (`dados/gold`), pronta para análise e modelagem.
    """

    def __init__(
        self,
        caminho_entrada: Path = CAMINHO_SILVER,
        caminho_saida: Path = CAMINHO_GOLD,
    ) -> None:
        self.caminho_entrada = caminho_entrada
        self.caminho_saida = caminho_saida
        self.resultado: ResultadoTransformacao | None = None

    def executar(self) -> ResultadoTransformacao:
        """Lê os dados da camada Silver, cura/agrega e grava na camada Gold."""
        logger.info("=" * 70)
        logger.info("TRANSFORMACAO (GOLD) — INICIO")
        self.caminho_saida.mkdir(parents=True, exist_ok=True)
        dados = self._carregar_silver()
        linhas_entrada = len(dados)
        logger.info("Silver carregada: %d linhas", linhas_entrada)

        dados_curados = self._curar_dados(dados)
        self._salvar_gold(dados_curados)

        taxa = float(dados_curados["informal"].mean()) if len(dados_curados) else None
        self.resultado = ResultadoTransformacao(
            linhas_entrada=linhas_entrada,
            linhas_ocupados=len(dados_curados),
            taxa_informalidade=taxa,
        )
        logger.info(
            "Gold gerada: %d linhas (de %d na Silver, %.1f%% eram ocupados)",
            self.resultado.linhas_ocupados,
            linhas_entrada,
            100 * self.resultado.linhas_ocupados / linhas_entrada if linhas_entrada else 0,
        )
        if taxa is not None:
            logger.info("Taxa de informalidade (não ponderada): %.1f%%", 100 * taxa)
        logger.info(
            "Arquivo consolidado: %s",
            (self.caminho_saida / "dados_gold.parquet").resolve(),
        )
        logger.info("=" * 70)
        return self.resultado

    def _carregar_silver(self) -> pd.DataFrame:
        """Carrega os dados limpos gravados pela etapa de pré-processamento."""
        arquivo = self.caminho_entrada / "dados_silver.parquet"
        if not arquivo.exists():
            logger.warning("Nenhum arquivo Silver encontrado em %s — rode o pré-processamento antes.", arquivo.resolve())
            return pd.DataFrame()
        return pd.read_parquet(arquivo)

    def _curar_dados(self, dados: pd.DataFrame) -> pd.DataFrame:
        """Filtra pessoas ocupadas e aplica a regra de informalidade (RF-03).

        1. Filtra `VD4002 == 1` (ocupados) — informalidade só é definida
           para quem trabalha; ver `docs/03-dicionario-de-dados.md`.
        2. Deriva a coluna-alvo `informal` a partir de `VD4009`/`V4019`.
        3. Descarta as colunas usadas para construir o alvo/filtro
           (evita vazamento de dado na modelagem).
        """
        if dados.empty:
            return dados

        ocupados = dados[dados["VD4002"] == 1].copy()
        ocupados["informal"] = self._classificar_informalidade(ocupados)

        colunas_descartar = [c for c in COLUNAS_ALVO_BRUTO if c in ocupados.columns]
        return ocupados.drop(columns=colunas_descartar)

    @staticmethod
    def _classificar_informalidade(ocupados: pd.DataFrame) -> pd.Series:
        """Aplica a regra de informalidade sobre pessoas já filtradas como
        ocupadas (`VD4002 == 1`). Vetorizado — não usar `.apply(axis=1)`
        aqui, a Gold roda sobre milhões de linhas.
        """
        categoria_informal_direta = ocupados["VD4009"].isin(CATEGORIAS_INFORMAIS_DIRETAS)
        empregador_ou_conta_propria = ocupados["VD4009"].isin(CATEGORIAS_DEPENDEM_DE_CNPJ)
        sem_cnpj = ocupados["V4019"] != 1
        return categoria_informal_direta | (empregador_ou_conta_propria & sem_cnpj)

    def _salvar_gold(self, dados: pd.DataFrame) -> None:
        """Salva os dados curados e agregados na camada Gold."""
        dados.to_parquet(self.caminho_saida / "dados_gold.parquet", index=False)


if __name__ == "__main__":
    Transformacao().executar()
