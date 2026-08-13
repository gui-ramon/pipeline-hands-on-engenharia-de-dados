"""Etapa de modelagem: treino e avaliação de modelos de Machine Learning."""

from pathlib import Path

import joblib
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

from src.etapa import Etapa

CAMINHO_GOLD = Path("dados/gold")
CAMINHO_MODELO = Path("dados/gold/modelo.joblib")


class Modelagem(Etapa):
    """Treina e avalia o modelo de Machine Learning a partir dos dados
    curados da camada Gold.
    """

    def __init__(
        self,
        caminho_entrada: Path = CAMINHO_GOLD,
        caminho_modelo: Path = CAMINHO_MODELO,
        coluna_alvo: str = "alvo",
    ) -> None:
        self.caminho_entrada = caminho_entrada
        self.caminho_modelo = caminho_modelo
        self.coluna_alvo = coluna_alvo

    def executar(self) -> None:
        """Treina o modelo com os dados da camada Gold e avalia seu desempenho."""
        dados = self._carregar_gold()
        if dados.empty or self.coluna_alvo not in dados.columns:
            print("Dados insuficientes para treinar o modelo.")
            return
        x_treino, x_teste, y_treino, y_teste = self._dividir_treino_teste(dados)
        modelo = self._treinar(x_treino, y_treino)
        self._avaliar(modelo, x_teste, y_teste)
        self._salvar_modelo(modelo)

    def _carregar_gold(self) -> pd.DataFrame:
        """Carrega os dados curados/agregados da camada Gold."""
        arquivo = self.caminho_entrada / "dados_gold.parquet"
        if not arquivo.exists():
            return pd.DataFrame()
        return pd.read_parquet(arquivo)

    def _dividir_treino_teste(self, dados: pd.DataFrame):
        """Separa os dados em conjuntos de treino e teste."""
        x = dados.drop(columns=[self.coluna_alvo])
        y = dados[self.coluna_alvo]
        return train_test_split(x, y, test_size=0.2, random_state=42)

    def _treinar(self, x_treino, y_treino) -> LogisticRegression:
        """Treina o modelo de Machine Learning com os dados de treino."""
        # TODO: escolher e ajustar o algoritmo mais adequado ao problema.
        modelo = LogisticRegression(max_iter=1000)
        modelo.fit(x_treino, y_treino)
        return modelo

    def _avaliar(self, modelo: LogisticRegression, x_teste, y_teste) -> None:
        """Avalia o desempenho do modelo treinado nos dados de teste."""
        acuracia = modelo.score(x_teste, y_teste)
        print(f"Acurácia do modelo: {acuracia:.2%}")

    def _salvar_modelo(self, modelo: LogisticRegression) -> None:
        """Salva o modelo treinado em disco."""
        self.caminho_modelo.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(modelo, self.caminho_modelo)
