"""Interface comum a todas as etapas do pipeline de engenharia de dados."""

from abc import ABC, abstractmethod


class Etapa(ABC):
    """Classe base que define o contrato de uma etapa do pipeline.

    Cada etapa (ingestão, pré-processamento, transformação, análise e
    modelagem) deve herdar desta classe e implementar o método `executar`.
    """

    @abstractmethod
    def executar(self) -> None:
        """Executa a lógica principal da etapa."""
        raise NotImplementedError
