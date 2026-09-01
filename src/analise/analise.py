"""Etapa de análise exploratória dos dados da camada Gold (RF-04).

Além do resumo estatístico básico, gera automaticamente o boletim
`dashboard/censo_informalidade.html` a partir da Gold mais recente —
toda vez que o pipeline reprocessar dados (`pipeline.analisar()` ou
`python -m src.pipeline`), o relatório é regravado com os números
atualizados. Ver `src/analise/relatorios.py` para o cálculo das
métricas e a montagem do HTML.
"""

from pathlib import Path

import pandas as pd

from src.analise.relatorios import calcular_metricas, renderizar_censo
from src.etapa import Etapa

CAMINHO_GOLD = Path("dados/gold")
CAMINHO_SILVER = Path("dados/silver")
CAMINHO_DASHBOARD = Path("dashboard")


class Analise(Etapa):
    """Realiza a análise exploratória (EDA) dos dados da camada Gold e
    gera o boletim HTML correspondente em `dashboard/`.
    """

    def __init__(
        self,
        caminho_entrada: Path = CAMINHO_GOLD,
        caminho_silver: Path = CAMINHO_SILVER,
        caminho_dashboard: Path = CAMINHO_DASHBOARD,
    ) -> None:
        self.caminho_entrada = caminho_entrada
        self.caminho_silver = caminho_silver
        self.caminho_dashboard = caminho_dashboard

    def executar(self) -> None:
        """Carrega a Gold, gera o resumo estatístico e o boletim HTML."""
        dados = self._carregar_gold()
        self._gerar_estatisticas_descritivas(dados)
        if not dados.empty:
            self._gerar_boletim_html(dados)

    def _carregar_gold(self) -> pd.DataFrame:
        """Carrega os dados curados/agregados da camada Gold."""
        arquivo = self.caminho_entrada / "dados_gold.parquet"
        if not arquivo.exists():
            print(f"Nenhum arquivo Gold encontrado em {arquivo.resolve()} — rode a transformação antes.")
            return pd.DataFrame()
        return pd.read_parquet(arquivo)

    def _carregar_silver(self) -> pd.DataFrame:
        """Carrega a Silver — só usada para a seção de percentual de nulo
        (que precisa da base antes do filtro de ocupados). Opcional: se
        não existir, o boletim é gerado sem essa seção.
        """
        arquivo = self.caminho_silver / "dados_silver.parquet"
        if not arquivo.exists():
            return pd.DataFrame()
        return pd.read_parquet(arquivo)

    def _gerar_estatisticas_descritivas(self, dados: pd.DataFrame) -> pd.DataFrame:
        """Gera e exibe estatísticas descritivas dos dados (EDA)."""
        resumo = dados.describe(include="all")
        print(resumo)
        return resumo

    def _gerar_boletim_html(self, gold: pd.DataFrame) -> None:
        """Calcula as métricas e escreve `dashboard/censo_informalidade.html`."""
        silver = self._carregar_silver()
        metricas = calcular_metricas(gold, silver if not silver.empty else None)
        html = renderizar_censo(metricas)
        self.caminho_dashboard.mkdir(parents=True, exist_ok=True)
        destino = self.caminho_dashboard / "censo_informalidade.html"
        destino.write_text(html, encoding="utf-8")
        print(f"Boletim atualizado: {destino.resolve()}")


if __name__ == "__main__":
    Analise().executar()
