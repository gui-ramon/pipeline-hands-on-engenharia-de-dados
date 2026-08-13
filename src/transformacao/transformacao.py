"""Etapa de transformação: curadoria e agregação para a camada Gold."""

from pathlib import Path

import pandas as pd

from src.etapa import Etapa

CAMINHO_SILVER = Path("dados/silver")
CAMINHO_GOLD = Path("dados/gold")


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

    def executar(self) -> None:
        """Lê os dados da camada Silver, cura/agrega e grava na camada Gold."""
        self.caminho_saida.mkdir(parents=True, exist_ok=True)
        dados = self._carregar_silver()
        dados_curados = self._curar_dados(dados)
        self._salvar_gold(dados_curados)

    def _carregar_silver(self) -> pd.DataFrame:
        """Carrega os dados limpos gravados pela etapa de pré-processamento."""
        arquivo = self.caminho_entrada / "dados_silver.parquet"
        if not arquivo.exists():
            return pd.DataFrame()
        return pd.read_parquet(arquivo)

    def _curar_dados(self, dados: pd.DataFrame) -> pd.DataFrame:
        """Aplica regras de negócio, junções e agregações aos dados."""
        # TODO: implementar as regras de curadoria/agregação do projeto.
        return dados

    def _salvar_gold(self, dados: pd.DataFrame) -> None:
        """Salva os dados curados e agregados na camada Gold."""
        dados.to_parquet(self.caminho_saida / "dados_gold.parquet", index=False)
