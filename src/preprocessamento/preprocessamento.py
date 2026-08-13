"""Etapa de pré-processamento: limpeza e padronização para a camada Silver."""

from pathlib import Path

import pandas as pd

from src.etapa import Etapa

CAMINHO_BRONZE = Path("dados/bronze")
CAMINHO_SILVER = Path("dados/silver")


class Preprocessamento(Etapa):
    """Limpa e padroniza os dados da camada Bronze, gerando a camada
    Silver (`dados/silver`).
    """

    def __init__(
        self,
        caminho_entrada: Path = CAMINHO_BRONZE,
        caminho_saida: Path = CAMINHO_SILVER,
    ) -> None:
        self.caminho_entrada = caminho_entrada
        self.caminho_saida = caminho_saida

    def executar(self) -> None:
        """Lê os dados da camada Bronze, limpa e grava na camada Silver."""
        self.caminho_saida.mkdir(parents=True, exist_ok=True)
        dados = self._carregar_bronze()
        dados_limpos = self._limpar_dados(dados)
        self._salvar_silver(dados_limpos)

    def _carregar_bronze(self) -> pd.DataFrame:
        """Carrega os dados brutos gravados pela etapa de ingestão."""
        arquivo = self.caminho_entrada / "dados_bronze.parquet"
        if not arquivo.exists():
            return pd.DataFrame()
        return pd.read_parquet(arquivo)

    def _limpar_dados(self, dados: pd.DataFrame) -> pd.DataFrame:
        """Remove duplicidades, trata valores ausentes e padroniza os tipos."""
        # TODO: implementar as regras de limpeza específicas do projeto.
        return dados.drop_duplicates()

    def _salvar_silver(self, dados: pd.DataFrame) -> None:
        """Salva os dados limpos e padronizados na camada Silver."""
        dados.to_parquet(self.caminho_saida / "dados_silver.parquet", index=False)
