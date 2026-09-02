# Plano de Modelagem — InformalidadeBR

Define o que RF-05 (modelagem) e RF-06 (interpretabilidade) vão efetivamente
usar: quais algoritmos, com qual justificativa, e quais features — cada
decisão baseada na evidência levantada na EDA (RF-04, ver
[`docs/03-dicionario-de-dados.md`](03-dicionario-de-dados.md#seleção-de-features-para-o-modelo-evidência-medida)
e a Seção 05 de `dashboard/censo_informalidade.html`), não em intuição.

## 1. Objetivo do modelo

Classificação binária: `informal` (alvo derivado na Gold, RF-03) a partir de
características do trabalhador. Base: 2.522.338 pessoas ocupadas,
2023-2025, taxa real de informalidade 47,6% (razoavelmente balanceada).

## 2. Algoritmos que vamos usar

| Modelo | Por que usar |
|---|---|
| **Regressão Logística** | Baseline interpretável — coeficiente de cada variável é direto de explicar na apresentação. Rápida mesmo em 2,5M linhas. Serve de "sanity check": se um modelo bem mais complexo não superar essa baseline por margem clara, não compensa a perda de interpretabilidade. |
| **Random Forest** | Lida nativamente com a mistura de categórica+numérica das 15 features (após encoding), robusto a overfitting com floresta grande, dá feature importance própria pra comparar com o V de Cramér já medido na EDA. |
| **Gradient Boosting — `HistGradientBoostingClassifier` (scikit-learn)** | Escolhido em vez de `GradientBoostingClassifier` clássico (muito lento nessa escala) e em vez de XGBoost/LightGBM (dependência nova). Dois motivos concretos pro nosso caso: (1) **suporta categórica nativa**, sem precisar one-hot em `UF` (27 categorias), `VD4010`/`VD4011` (11-12 categorias cada); (2) **suporta `NaN` nativo** — `V4018` e `V4025`, que são justamente as duas features com maior associação medida (V=0,570 e 0,460), têm 19,9% e 40,2% de nulo entre ocupados. Imputar ou descartar essas linhas custaria caro; o `HistGradientBoostingClassifier` usa o padrão de nulo como informação, não como problema a resolver antes. |

## 3. Algoritmos que **não** vamos usar

| Modelo | Por que não |
|---|---|
| **KNN** | Alta cardinalidade categórica (`UF`, setor, ocupação) e mistura de escalas tornam a métrica de distância pouco confiável sem um trabalho grande de encoding/normalização; não dá interpretabilidade nem por coeficiente nem por importância nativa. |
| **Naive Bayes** | Assume as features condicionalmente independentes dado o alvo — não vale aqui: setor de atividade e grupamento ocupacional são claramente correlacionados entre si, assim como tamanho do negócio e tempo no emprego. Violar essa premissa tende a distorcer as probabilidades estimadas. |
| **SVM** | Custo computacional alto em 2,5 milhões de linhas (escala mal com N), não produz probabilidade calibrada nativamente (precisaria de calibração extra), sem vantagem clara sobre o Gradient Boosting pra dado tabular. |
| **Redes neurais / Deep Learning** | Dataset tabular com 15 features, sem estrutura sequencial/imagem/texto que justifique uma rede — literatura de ML tabular consistentemente mostra árvores/boosting igualando ou superando DL nesse tipo de problema, com muito menos custo de treino e mais interpretabilidade. Overkill pro escopo (RNF já registra "simplicidade e velocidade de iteração" como prioridade do projeto). |
| **XGBoost / LightGBM** | Ficam como upgrade futuro possível, não descartados por mérito técnico — só adiam a decisão de adicionar uma dependência nova ao `requirements.txt` até o `HistGradientBoostingClassifier` nativo do scikit-learn mostrar alguma limitação real. |
| **Clustering (K-means etc.)** | Não se aplica — o problema é classificação supervisionada com alvo binário já definido (`informal`), não descoberta de grupos sem rótulo. |

## 4. Estratégia de treino/validação/teste

**Split temporal, não aleatório** — a PNAD Contínua é um painel rotativo (a
mesma pessoa aparece em até 5 trimestres seguidos antes de sair da
amostra). Um split aleatório nas linhas consolidadas deixaria a mesma
pessoa no treino em um trimestre e no teste em outro, vazando informação e
inflando as métricas artificialmente.

- **Treino**: 2023–2024.
- **Teste**: 2025 completo.
- Ajuste de hiperparâmetro (se necessário): `TimeSeriesSplit` dentro do
  período de treino, nunca tocando 2025.

Com 2,5 milhões de linhas, um único holdout já é estatisticamente robusto
para a métrica final — não é preciso k-fold pesado.

## 5. Features que vamos usar (15)

Ordenadas pela força de associação com `informal` medida na Gold completa
(V de Cramér para categóricas, `|r|` ponto-bisserial para numéricas — ver
cálculo em `src/analise/relatorios.py::_calcular_forca_features`):

| Feature | Força | Justificativa |
|---|---|---|
| `V4018` (tamanho do negócio) | 0,570 — forte | Achado clássico da literatura, confirmado com dado real; maior associação medida. |
| `V4025` (é temporário?) | 0,460 — forte | Segunda maior associação; vínculo temporário concentra informalidade. |
| `VD4010` (setor de atividade) | 0,404 — forte | Setores como serviços domésticos/agropecuária concentram informalidade. |
| `VD4011` (grupamento ocupacional) | 0,373 — forte | Complementa setor com o tipo de função exercida. |
| `VD3004` (nível de instrução) | 0,325 — moderada | Mais anos de estudo associam a menos informalidade — estável nas 3 versões da EDA (amostra, 2025, completo). |
| `VD4031` (horas semanais) | 0,272 — moderada | Estável nas 3 versões da EDA; horas atípicas concentram informalidade. |
| `V1022` (urbano/rural) | 0,255 — moderada | Zona rural historicamente mais informal no Brasil. |
| `UF` | 0,243 — moderada | Desigualdade regional de informalidade é um fator real, não ruído. |
| `V4040` (tempo no emprego) | 0,144 — fraca | Achado clássico da literatura (vínculos recentes concentram informalidade), mesmo com associação individual fraca. |
| `V1023` (tipo de área) | 0,135 — fraca | Complementa `V1022` com granularidade capital/RM/interior. |
| `V2010` (raça/cor) | 0,118 — fraca | **Obrigatória por escopo do projeto** (RF-06): expor desigualdade racial é objetivo declarado, não critério de força estatística. |
| `VD2002` (posição no domicílio) | 0,042 — muito fraca | Mantida pelo potencial de interação com sexo (ver `docs/03`: mulher responsável vs. cônjuge), não pela força isolada. |
| `V2009` (idade) | 0,042 — muito fraca | Demografia básica, custo zero de incluir (0% nulo), plausível em interação com outras features. |
| `VD2003` (pessoas no domicílio) | 0,030 — muito fraca | Mesmo raciocínio de `V2009`. |
| `V2007` (sexo) | 0,026 — muito fraca | **Obrigatória por escopo do projeto** (RF-06): SHAP precisa medir o peso desse fator mesmo sendo pequeno — é o próprio objeto de estudo. |

## 6. Features que **não** vamos usar

| Feature(s) | Motivo |
|---|---|
| `VD4009`, `V4019`, `VD4012`, `VD4002` | **Vazamento de dado (leakage)** — são as variáveis usadas para *construir* o próprio alvo `informal` na Gold (`src/transformacao/transformacao.py`). Incluí-las faria o modelo aprender a copiar a definição do alvo em vez de prever a partir de características reais. |
| `VD4016`, `VD4017` (renda) | **Vazamento circular** — renda é fortemente correlacionada com a própria condição de informalidade (já documentado em `docs/03`); usar como feature infla a métrica artificialmente e destrói a interpretabilidade pretendida em RF-06. Mantidas só para gráfico de EDA (gap salarial formal x informal). |
| `V3002` (frequenta escola) | **Associação praticamente nula** (V de Cramér = 0,003) — entre pessoas já ocupadas, quase todo mundo responde "não", a variável quase não varia nessa população e não agrega poder preditivo. |
| `UPA`, `V1008`, `V1014`, `V2003` | **Não são features** — são a chave de deduplicação de pessoa/domicílio (ver `docs/03`), servem só pra garantir que a Silver não tem duplicata real. Um identificador não tem relação causal/preditiva genuína com informalidade; incluí-lo arriscaria o modelo "decorar" pessoas em vez de generalizar. |
| `V1028` (peso amostral) | **Não é feature preditiva** — representa o peso de representatividade da PNAD Contínua (amostra complexa, estratificada). Reservado para eventual ponderação de treino/avaliação (ainda em aberto, ver `docs/04-arquitetura.md` "Trabalho futuro"), nunca como input direto do classificador. |
| `Ano`, `Trimestre` | **Não generalizam sob split temporal** — como o treino cobre só 2023-2024, o modelo nunca veria o valor literal "Ano=2025" durante o treino; incluir arriscaria uma árvore aprender um corte inútil num valor que não existe no lado de teste. `Trimestre` isolado (sazonalidade dentro do ano) pode ser testado depois como feature auxiliar, mas fica de fora da primeira versão. |

## 7. Métricas de avaliação

Acurácia, precisão, recall, F1 e AUC-ROC (já previstas no RF-05) — a base é
razoavelmente balanceada (47,6%/52,4%), então acurácia não engana tanto
quanto enganaria num problema desbalanceado, mas não deve ser a métrica
única. Complementar com:

- **Matriz de confusão separada por `V2007`/`V2010`** — verifica se o
  modelo erra mais falso-negativo/falso-positivo pra um grupo que pra
  outro, antes mesmo do SHAP.

## 8. Interpretabilidade (RF-06)

Random Forest e `HistGradientBoostingClassifier` são compatíveis com
`shap.TreeExplainer` (rápido e exato) — treinar já pensando nisso. SHAP
recortado por `V2007` (sexo) e `V2010` (raça/cor) para expor o peso
relativo de cada fator na predição de informalidade por grupo (RNF-11).
