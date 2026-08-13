"""Etapa de ingestão: extração dos dados da fonte para a camada Bronze."""

from pathlib import Path

import pandas as pd

from src.etapa import Etapa

CAMINHO_BRONZE = Path("dados/bronze")


class Ingestao(Etapa):
    """Extrai os dados da fonte original e os grava, sem transformação,
    na camada Bronze (`dados/bronze`).
    """

    def __init__(self, caminho_saida: Path = CAMINHO_BRONZE) -> None:
        self.caminho_saida = caminho_saida

    def executar(self) -> None:
        """Extrai os dados da fonte e grava o resultado na camada Bronze."""
        self.caminho_saida.mkdir(parents=True, exist_ok=True)
        dados = self._extrair_dados()
        self._salvar_bronze(dados)

    def _extrair_dados(self) -> pd.DataFrame:
        """Extrai os dados brutos da fonte (API, arquivo, banco de dados etc.)."""
        # TODO: implementar a extração real dos dados da fonte escolhida.
        return pd.DataFrame()

    def _salvar_bronze(self, dados: pd.DataFrame) -> None:
        """Salva os dados brutos, sem nenhuma transformação, na camada Bronze."""
        dados.to_parquet(self.caminho_saida / "dados_bronze.parquet", index=False)
