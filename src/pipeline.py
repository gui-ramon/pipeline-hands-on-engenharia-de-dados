"""Classe orquestradora do pipeline de engenharia de dados.

Executa, em ordem, o ciclo completo do pipeline seguindo a arquitetura
Medallion: ingestão (Bronze) → pré-processamento (Silver) → transformação
(Gold) → análise exploratória → modelagem de Machine Learning.
"""

from src.analise.analise import Analise
from src.ingestao.ingestao import Ingestao
from src.modelagem.modelagem import Modelagem
from src.preprocessamento.preprocessamento import Preprocessamento
from src.transformacao.transformacao import Transformacao


class Pipeline:
    """Orquestra a execução de todas as etapas do pipeline de dados."""

    def __init__(self) -> None:
        self.etapa_ingestao = Ingestao()
        self.etapa_preprocessamento = Preprocessamento()
        self.etapa_transformacao = Transformacao()
        self.etapa_analise = Analise()
        self.etapa_modelagem = Modelagem()

    def ingerir(self) -> None:
        """Executa a etapa de ingestão (extração da fonte → camada Bronze)."""
        self.etapa_ingestao.executar()

    def preprocessar(self) -> None:
        """Executa a etapa de pré-processamento (limpeza → camada Silver)."""
        self.etapa_preprocessamento.executar()

    def transformar(self) -> None:
        """Executa a etapa de transformação (curadoria/agregação → camada Gold)."""
        self.etapa_transformacao.executar()

    def analisar(self) -> None:
        """Executa a etapa de análise exploratória dos dados."""
        self.etapa_analise.executar()

    def treinar_modelo(self) -> None:
        """Executa a etapa de treino e avaliação do modelo de Machine Learning."""
        self.etapa_modelagem.executar()

    def executar(self) -> None:
        """Executa todas as etapas do pipeline, em ordem."""
        self.ingerir()
        self.preprocessar()
        self.transformar()
        self.analisar()
        self.treinar_modelo()


if __name__ == "__main__":
    Pipeline().executar()
