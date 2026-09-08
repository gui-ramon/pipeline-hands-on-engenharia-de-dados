"""Etapa de modelagem: treino, avaliação e interpretabilidade dos modelos de
informalidade (RF-05/RF-06), a partir da camada Gold.

Toda a matemática (split, treino, métricas, SHAP) está em
`src/modelagem/treino.py`; toda a apresentação (tabela de comparação,
gráficos, relatório de texto) está em `src/modelagem/relatorio.py`. Este
arquivo só orquestra os dois, seguindo o mesmo padrão de
`src/analise/analise.py` + `src/analise/relatorios.py`.

IMPORTANTE — custo computacional na base cheia (2,5M linhas): `n_amostra`
existe justamente pra permitir testar o código com uma fração minúscula da
base antes de rodar oficialmente. Rodar `Modelagem().executar()` (sem
`n_amostra`) treina os 3 modelos na base inteira — decisão de quando fazer
isso é de quem chama, não deste código.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd

from src.etapa import Etapa
from src.modelagem import relatorio, treino

CAMINHO_GOLD = Path("dados/gold")
CAMINHO_MODELOS = Path("dados/modelos")


class Modelagem(Etapa):
    """Treina, avalia e interpreta os modelos de informalidade a partir da
    camada Gold, seguindo `docs/05-plano-de-modelagem.md`.
    """

    def __init__(
        self,
        caminho_entrada: Path = CAMINHO_GOLD,
        caminho_saida: Path = CAMINHO_MODELOS,
        n_amostra: int | None = None,
        ajustar_hiperparametros: bool = True,
        n_iter_busca: int = 5,
        max_amostras_shap: int = 3000,
        seed: int = 42,
    ) -> None:
        self.caminho_entrada = caminho_entrada
        self.caminho_saida = caminho_saida
        self.n_amostra = n_amostra
        self.ajustar_hiperparametros = ajustar_hiperparametros
        self.n_iter_busca = n_iter_busca
        self.max_amostras_shap = max_amostras_shap
        self.seed = seed

    def executar(self) -> None:
        gold = self._carregar_gold()
        if gold.empty:
            return

        dados = gold
        if self.n_amostra is not None:
            dados = treino.amostrar_para_teste(gold, self.n_amostra, self.seed)
            print(f"[MODO TESTE] amostra de {len(dados):,} linhas (de {len(gold):,} na Gold completa).")

        x_treino, x_teste, y_treino, y_teste = treino.split_temporal(dados)
        print(f"Treino (2023-2024): {len(x_treino):,} linhas | Teste (2025): {len(x_teste):,} linhas")

        modelos = treino.treinar_modelos(
            x_treino, y_treino, self.ajustar_hiperparametros, self.n_iter_busca, self.seed
        )

        metricas_treino = {nome: treino.avaliar_modelo(info, x_treino, y_treino) for nome, info in modelos.items()}
        metricas_teste = {nome: treino.avaliar_modelo(info, x_teste, y_teste) for nome, info in modelos.items()}
        tempos = {nome: info.tempo_treino_segundos for nome, info in modelos.items()}

        confusao_por_grupo = self._matriz_confusao_todos(modelos, x_teste, y_teste)
        shap_importancia, shap_por_grupo = self._shap_todos(modelos, x_teste)

        matriz_comparacao = relatorio.matriz_comparacao_modelos(metricas_teste, tempos)
        print("\n" + matriz_comparacao.to_string(index=False))

        self.caminho_saida.mkdir(parents=True, exist_ok=True)
        relatorio.gerar_graficos(modelos, x_teste, y_teste, self.caminho_saida / "graficos")
        relatorio.gerar_relatorio_txt(
            metricas_treino, metricas_teste, matriz_comparacao,
            confusao_por_grupo, shap_importancia, shap_por_grupo,
            self.caminho_saida / "relatorio_modelagem.txt",
        )
        self._salvar_artefatos(modelos, matriz_comparacao)
        print(f"\nArtefatos salvos em: {self.caminho_saida.resolve()}")

    def _carregar_gold(self) -> pd.DataFrame:
        arquivo = self.caminho_entrada / "dados_gold.parquet"
        if not arquivo.exists():
            print(f"Nenhum arquivo Gold encontrado em {arquivo.resolve()} — rode a transformação antes.")
            return pd.DataFrame()
        return pd.read_parquet(arquivo)

    def _matriz_confusao_todos(self, modelos, x_teste, y_teste) -> dict[str, list[dict]]:
        resultado = {}
        for nome, info in modelos.items():
            y_pred = info.modelo.predict(info.transformar(x_teste))
            linhas = []
            for coluna in treino.COLUNAS_EQUIDADE:
                linhas.extend(treino.matriz_confusao_por_grupo(y_teste, y_pred, x_teste[coluna]))
            resultado[nome] = linhas
        return resultado

    def _shap_todos(self, modelos, x_teste):
        importancia, por_grupo = {}, {}
        for nome, info in modelos.items():
            shap_dict = treino.explicar_shap(info, x_teste, self.max_amostras_shap, self.seed)
            if shap_dict is None:  # Regressão Logística — sem SHAP, é interpretável por coeficiente
                continue
            importancia[nome] = treino.resumo_shap_importancia(shap_dict)
            por_grupo[nome] = {}
            for coluna in treino.COLUNAS_EQUIDADE:
                resumo = treino.resumo_shap_por_grupo(shap_dict, x_teste[coluna])
                por_grupo[nome].update({f"{coluna}={valor}": ranking for valor, ranking in resumo.items()})
        return importancia, por_grupo

    def _salvar_artefatos(self, modelos, matriz_comparacao: pd.DataFrame) -> None:
        for nome, info in modelos.items():
            joblib.dump(info.modelo, self.caminho_saida / f"{nome.lower()}.joblib")
            if info.preprocessador is not None:
                joblib.dump(info.preprocessador, self.caminho_saida / f"{nome.lower()}_preprocessador.joblib")

        metadata = {
            "features": treino.FEATURES,
            "features_categoricas": treino.FEATURES_CATEGORICAS,
            "features_numericas": treino.FEATURES_NUMERICAS,
            "alvo": treino.ALVO,
            "anos_treino": list(treino.ANOS_TREINO),
            "ano_teste": treino.ANO_TESTE,
            "matriz_comparacao": matriz_comparacao.to_dict("records"),
            "melhores_parametros": {nome: info.melhores_parametros for nome, info in modelos.items()},
        }
        (self.caminho_saida / "metadata.json").write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
        )


def prever(caminho_modelos: Path, dados_novos: pd.DataFrame, nome_modelo: str = "HistGradientBoosting") -> pd.Series:
    """Pipeline de inferência em lote — carrega um modelo salvo por
    `Modelagem` e aplica em dados novos (mesmas 15 features/`docs/05`), sem
    precisar retreinar. Uso 100% local (`joblib.load` + `predict_proba`);
    sem API/cloud, conforme RNF do projeto — basta chamar de outro script
    ou notebook com um DataFrame no mesmo formato da Gold.
    """
    modelo = joblib.load(caminho_modelos / f"{nome_modelo.lower()}.joblib")
    caminho_preproc = caminho_modelos / f"{nome_modelo.lower()}_preprocessador.joblib"
    x = dados_novos[treino.FEATURES]
    if caminho_preproc.exists():
        x_proc = joblib.load(caminho_preproc).transform(x)
    else:
        x_proc = treino.preparar_x_categorica(x)
    probabilidades = modelo.predict_proba(x_proc)[:, 1]
    return pd.Series(probabilidades, index=dados_novos.index, name="probabilidade_informal")


if __name__ == "__main__":
    Modelagem().executar()
