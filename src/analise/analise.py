"""Etapa de análise exploratória dos dados da camada Gold."""

from pathlib import Path

import pandas as pd

from src.etapa import Etapa

CAMINHO_GOLD = Path("dados/gold")


class Analise(Etapa):
    """Realiza a análise exploratória (EDA) dos dados da camada Gold."""

    def __init__(self, caminho_entrada: Path = CAMINHO_GOLD) -> None:
        self.caminho_entrada = caminho_entrada

    def executar(self) -> None:
        """Carrega os dados da camada Gold e gera um resumo exploratório."""
        dados = self._carregar_gold()
        self._gerar_estatisticas_descritivas(dados)

    def _carregar_gold(self) -> pd.DataFrame:
        """Carrega os dados curados/agregados da camada Gold."""
        arquivo = self.caminho_entrada / "dados_gold.parquet"
        if not arquivo.exists():
            return pd.DataFrame()
        return pd.read_parquet(arquivo)

    def _gerar_estatisticas_descritivas(self, dados: pd.DataFrame) -> pd.DataFrame:
        """Gera e exibe estatísticas descritivas dos dados (EDA)."""
        # TODO: complementar com gráficos e análises específicas do projeto.
        resumo = dados.describe(include="all")
        print(resumo)
        return resumo
