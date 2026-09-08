"""Funções puras de treino/avaliação/interpretabilidade do modelo de
informalidade (RF-05/RF-06).

Toda decisão de design aqui (algoritmos, split, features, métricas) segue
`docs/05-plano-de-modelagem.md` — não é intuição nem cópia de exemplo genérico.
Resumo do que está fixado lá e implementado aqui:

- **3 algoritmos**: Regressão Logística (baseline interpretável),
  RandomForestClassifier, `HistGradientBoostingClassifier` — este último
  escolhido em vez de LightGBM/XGBoost pra não adicionar dependência nova, e
  porque lida nativamente com categórica (sem one-hot) e com `NaN` (`V4018`/
  `V4025`, as duas features mais fortes, têm 19,9%/40,2% de nulo).
- **Split temporal**, não aleatório: treino = 2023-2024, teste = 2025 — a
  PNAD é um painel rotativo, um split aleatório vazaria a mesma pessoa entre
  treino e teste.
- **15 features fixas** (ver `FEATURES` abaixo) — não incluir Ano/Trimestre
  (não generaliza sob split temporal), renda (vazamento circular) nem as
  colunas usadas pra construir o próprio alvo (já descartadas na Gold).
- **Sem SMOTE** — o alvo é razoavelmente balanceado (47,6%/52,4%).
- **SHAP `TreeExplainer`** em RF e HGB (a Regressão Logística já é
  interpretável via coeficiente), recortado por `V2007`/`V2010` (RNF-11).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.stats import loguniform, randint
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import RandomizedSearchCV, TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

FEATURES_CATEGORICAS = [
    "V4018", "V4025", "VD4010", "VD4011", "VD3004", "V1022", "UF", "V4040",
    "V1023", "V2010", "VD2002", "V2007",
]
FEATURES_NUMERICAS = ["VD4031", "V2009", "VD2003"]
FEATURES = FEATURES_CATEGORICAS + FEATURES_NUMERICAS
ALVO = "informal"

ANOS_TREINO = (2023, 2024)
ANO_TESTE = 2025

# Colunas usadas pra medir equidade entre grupos (RNF-11) — não entram como
# feature isolada aqui, servem só pra fatiar y_teste/y_pred/SHAP depois.
COLUNAS_EQUIDADE = ["V2007", "V2010"]


def amostrar_para_teste(gold: pd.DataFrame, n_amostra: int, seed: int = 42) -> pd.DataFrame:
    """Amostra estratificada por (Ano, informal) — só para smoke test do
    código antes de rodar oficialmente na base cheia. Mantém as duas classes
    e os três anos representados mesmo numa amostra minúscula, senão o split
    temporal (`split_temporal`) pode ficar sem treino ou sem teste.
    """
    if n_amostra >= len(gold):
        return gold.reset_index(drop=True)
    frac = n_amostra / len(gold)
    amostra = gold.groupby(["Ano", ALVO], group_keys=False).sample(frac=frac, random_state=seed)
    return amostra.reset_index(drop=True)


def split_temporal(dados: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """Treino = 2023-2024, teste = 2025 (ver docstring do módulo). Ordena por
    Ano/Trimestre antes de fatiar — necessário pro `TimeSeriesSplit` usado no
    tuning de hiperparâmetro fazer sentido (senão as "dobras" não respeitam
    a ordem cronológica).
    """
    dados_ordenados = dados.sort_values(["Ano", "Trimestre"]).reset_index(drop=True)
    treino = dados_ordenados[dados_ordenados["Ano"].isin(ANOS_TREINO)]
    teste = dados_ordenados[dados_ordenados["Ano"] == ANO_TESTE]
    if treino.empty or teste.empty:
        raise ValueError(
            f"Split temporal ficou sem treino ou sem teste (treino={len(treino)}, teste={len(teste)}) "
            "— aumente n_amostra ou verifique se a base cobre 2023-2024 e 2025."
        )
    x_treino = treino[FEATURES].reset_index(drop=True)
    x_teste = teste[FEATURES].reset_index(drop=True)
    y_treino = treino[ALVO].astype(int).reset_index(drop=True)
    y_teste = teste[ALVO].astype(int).reset_index(drop=True)
    return x_treino, x_teste, y_treino, y_teste


def criar_preprocessador_encoded() -> ColumnTransformer:
    """Pré-processador compartilhado por Regressão Logística e Random
    Forest — as duas precisam de entrada numérica sem `NaN`. `sparse_output`
    padrão (esparso) é importante em escala: 2,5M linhas × ~100 colunas
    one-hot densas passariam de 1GB de RAM só pra essa matriz.
    """
    numerico = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])
    categorico = Pipeline([
        ("imputer", SimpleImputer(strategy="constant", fill_value=-1)),
        ("onehot", OneHotEncoder(handle_unknown="ignore")),
    ])
    return ColumnTransformer([
        ("num", numerico, FEATURES_NUMERICAS),
        ("cat", categorico, FEATURES_CATEGORICAS),
    ])


def preparar_x_categorica(x: pd.DataFrame) -> pd.DataFrame:
    """Converte as colunas categóricas pra dtype `category` do pandas —
    formato que `HistGradientBoostingClassifier(categorical_features=
    'from_dtype')` reconhece nativamente, `NaN` incluso (ver docstring do
    módulo: por isso HGB não precisa do `criar_preprocessador_encoded`).
    """
    x_cat = x.copy()
    for coluna in FEATURES_CATEGORICAS:
        x_cat[coluna] = x_cat[coluna].astype("category")
    return x_cat


@dataclass
class ModeloTreinado:
    """Um modelo treinado + o que é necessário pra reaplicar o mesmo
    pré-processamento em dados novos (teste, inferência)."""

    nome: str
    modelo: object
    preprocessador: ColumnTransformer | None  # None para HistGradientBoosting (não precisa)
    usa_categoria: bool  # True = passar por `preparar_x_categorica`, False = pelo preprocessador
    tempo_treino_segundos: float
    melhores_parametros: dict = field(default_factory=dict)

    def transformar(self, x: pd.DataFrame):
        if self.usa_categoria:
            return preparar_x_categorica(x)
        return self.preprocessador.transform(x)


def _buscar_hiperparametros(modelo, distribuicoes: dict, x, y, n_iter: int, seed: int):
    """`RandomizedSearchCV` com `TimeSeriesSplit` — não `KFold` aleatório,
    pra respeitar a ordem cronológica dentro do período de treino (ver
    `docs/05-plano-de-modelagem.md` §4). scipy puro (sem Optuna) pra não
    adicionar dependência nova.
    """
    cv = TimeSeriesSplit(n_splits=3)
    busca = RandomizedSearchCV(
        modelo, distribuicoes, n_iter=n_iter, scoring="roc_auc", cv=cv,
        random_state=seed, n_jobs=-1, refit=True,
    )
    busca.fit(x, y)
    return busca.best_estimator_, busca.best_params_


def treinar_modelos(
    x_treino: pd.DataFrame,
    y_treino: pd.Series,
    ajustar_hiperparametros: bool = True,
    n_iter_busca: int = 5,
    seed: int = 42,
) -> dict[str, ModeloTreinado]:
    """Treina os 3 modelos definidos em `docs/05-plano-de-modelagem.md`.

    `ajustar_hiperparametros=False` pula o `RandomizedSearchCV` inteiro e
    treina com parâmetros default razoáveis — use isso pra uma primeira
    passada rápida na base cheia (2,5M linhas) antes de gastar tempo em
    tuning. `n_iter_busca` controla quantas combinações o RandomForest (o
    modelo mais caro dos três) vai tentar — mantenha baixo (5-10) em 2,5M
    linhas, cada combinação já é um treino completo de floresta.
    """
    resultados: dict[str, ModeloTreinado] = {}

    # --- Regressão Logística (baseline interpretável) ---
    preproc_lr = criar_preprocessador_encoded()
    x_treino_enc = preproc_lr.fit_transform(x_treino)
    inicio = time.time()
    if ajustar_hiperparametros:
        modelo_lr, params_lr = _buscar_hiperparametros(
            LogisticRegression(max_iter=2000, random_state=seed),
            {"C": loguniform(1e-3, 10)}, x_treino_enc, y_treino, n_iter_busca, seed,
        )
    else:
        modelo_lr = LogisticRegression(max_iter=2000, random_state=seed).fit(x_treino_enc, y_treino)
        params_lr = {}
    resultados["LogisticRegression"] = ModeloTreinado(
        "LogisticRegression", modelo_lr, preproc_lr, usa_categoria=False,
        tempo_treino_segundos=time.time() - inicio, melhores_parametros=params_lr,
    )

    # --- Random Forest (compartilha o mesmo encoded do LR) ---
    # `max_samples` limita quantas linhas cada árvore individual vê (bootstrap
    # parcial) — é o principal freio de RAM/tempo numa floresta em milhões de
    # linhas; sem isso, cada uma das `n_estimators` árvores tenta crescer sobre
    # a base de treino inteira. Em amostras pequenas (smoke test) o teto de
    # 300 mil não faz efeito nenhum (usa tudo); só entra em jogo na base cheia.
    max_amostras_por_arvore = min(1.0, 300_000 / max(len(x_treino), 1))
    preproc_rf = criar_preprocessador_encoded()
    x_treino_enc_rf = preproc_rf.fit_transform(x_treino)
    inicio = time.time()
    if ajustar_hiperparametros:
        modelo_rf, params_rf = _buscar_hiperparametros(
            RandomForestClassifier(
                n_estimators=150, max_samples=max_amostras_por_arvore, n_jobs=-1, random_state=seed
            ),
            {"max_depth": randint(6, 20), "min_samples_leaf": randint(5, 50)},
            x_treino_enc_rf, y_treino, n_iter_busca, seed,
        )
    else:
        modelo_rf = RandomForestClassifier(
            n_estimators=150, max_samples=max_amostras_por_arvore, max_depth=15,
            min_samples_leaf=10, n_jobs=-1, random_state=seed,
        ).fit(x_treino_enc_rf, y_treino)
        params_rf = {}
    resultados["RandomForest"] = ModeloTreinado(
        "RandomForest", modelo_rf, preproc_rf, usa_categoria=False,
        tempo_treino_segundos=time.time() - inicio, melhores_parametros=params_rf,
    )

    # --- HistGradientBoosting (categórica + NaN nativos, sem preprocessador) ---
    x_treino_cat = preparar_x_categorica(x_treino)
    inicio = time.time()
    if ajustar_hiperparametros:
        modelo_hgb, params_hgb = _buscar_hiperparametros(
            HistGradientBoostingClassifier(categorical_features="from_dtype", random_state=seed),
            {
                "max_depth": randint(3, 15),
                "learning_rate": loguniform(0.01, 0.3),
                "max_iter": randint(80, 300),
            },
            x_treino_cat, y_treino, n_iter_busca, seed,
        )
    else:
        modelo_hgb = HistGradientBoostingClassifier(
            categorical_features="from_dtype", random_state=seed
        ).fit(x_treino_cat, y_treino)
        params_hgb = {}
    resultados["HistGradientBoosting"] = ModeloTreinado(
        "HistGradientBoosting", modelo_hgb, None, usa_categoria=True,
        tempo_treino_segundos=time.time() - inicio, melhores_parametros=params_hgb,
    )

    return resultados


def avaliar_modelo(info: ModeloTreinado, x: pd.DataFrame, y: pd.Series) -> dict:
    """Accuracy/precision/recall/F1/AUC-ROC (RF-05 §7). Chamar tanto em
    treino quanto em teste permite detectar overfitting (gap grande entre
    as duas é o sinal clássico)."""
    x_proc = info.transformar(x)
    y_pred = info.modelo.predict(x_proc)
    y_proba = info.modelo.predict_proba(x_proc)[:, 1]
    return {
        "accuracy": float(accuracy_score(y, y_pred)),
        "precision": float(precision_score(y, y_pred, zero_division=0)),
        "recall": float(recall_score(y, y_pred)),
        "f1": float(f1_score(y, y_pred)),
        "auc_roc": float(roc_auc_score(y, y_proba)),
    }


def matriz_confusao_por_grupo(y_teste: pd.Series, y_pred: np.ndarray, grupo: pd.Series) -> list[dict]:
    """Matriz de confusão fatiada por grupo demográfico (RF-05 §7, RNF-11) —
    verifica se o modelo erra mais falso-negativo/falso-positivo pra um
    grupo que pra outro, antes mesmo do SHAP.
    """
    linhas = []
    for valor in sorted(grupo.dropna().unique()):
        indice = (grupo == valor).to_numpy()
        if indice.sum() < 2:
            continue
        cm = confusion_matrix(y_teste[indice], y_pred[indice], labels=[0, 1])
        tn, fp, fn, tp = cm.ravel()
        linhas.append({
            "grupo": grupo.name,
            "valor": valor,
            "n": int(indice.sum()),
            "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
            "recall": float(tp / (tp + fn)) if (tp + fn) else None,
            "fpr": float(fp / (fp + tn)) if (fp + tn) else None,
        })
    return linhas


def explicar_shap(info: ModeloTreinado, x: pd.DataFrame, max_amostras: int = 3000, seed: int = 42) -> dict | None:
    """SHAP `TreeExplainer` (RF-06) — só se aplica a RF/HGB (árvores); a
    Regressão Logística já é interpretável via coeficiente, não precisa.
    Roda numa subamostra do que for passado (`max_amostras`) — padrão comum
    mesmo com `TreeExplainer` sendo exato/rápido, porque o relatório fica
    ilegível com centenas de milhares de linhas de SHAP.
    """
    import shap

    if info.nome == "LogisticRegression":
        return None

    amostra = x.sample(n=min(max_amostras, len(x)), random_state=seed)
    x_explicar = info.transformar(amostra)
    if hasattr(x_explicar, "toarray"):  # OneHotEncoder (LR/RF) sai esparso — SHAP precisa denso
        x_explicar = x_explicar.toarray()

    explicador = shap.TreeExplainer(info.modelo)
    valores = explicador.shap_values(x_explicar)
    valores = np.asarray(valores)
    if valores.ndim == 3:  # RandomForest: (n_amostras, n_features, n_classes)
        valores = valores[:, :, 1]  # classe positiva (informal=1)

    if info.usa_categoria:
        nomes_features = list(amostra.columns)
    else:
        nomes_features = list(info.preprocessador.get_feature_names_out())

    return {
        "shap_values": valores,
        "indices_amostra": amostra.index,
        "feature_names": nomes_features,
    }


def resumo_shap_importancia(shap_dict: dict, top_n: int = 15) -> list[dict]:
    """Ranking de |SHAP| médio por feature — importância global do modelo."""
    media_abs = np.abs(shap_dict["shap_values"]).mean(axis=0)
    ranking = sorted(
        zip(shap_dict["feature_names"], media_abs), key=lambda par: -par[1]
    )[:top_n]
    return [{"feature": nome, "shap_medio_abs": float(valor)} for nome, valor in ranking]


def resumo_shap_por_grupo(shap_dict: dict, grupo: pd.Series, top_n: int = 10) -> dict[str, list[dict]]:
    """Recorta a importância SHAP por valor de grupo (`V2007`/`V2010`) —
    RF-06/RNF-11: mostra se o peso de cada feature na predição muda entre
    homens/mulheres ou entre raças, não só a força agregada.
    """
    grupo_alinhado = grupo.loc[shap_dict["indices_amostra"]].reset_index(drop=True)
    valores = shap_dict["shap_values"]
    resultado = {}
    for valor_grupo in sorted(grupo_alinhado.dropna().unique()):
        mascara = (grupo_alinhado == valor_grupo).to_numpy()
        if mascara.sum() < 5:
            continue
        media_abs = np.abs(valores[mascara]).mean(axis=0)
        ranking = sorted(zip(shap_dict["feature_names"], media_abs), key=lambda par: -par[1])[:top_n]
        resultado[str(valor_grupo)] = [
            {"feature": nome, "shap_medio_abs": float(v)} for nome, v in ranking
        ]
    return resultado
