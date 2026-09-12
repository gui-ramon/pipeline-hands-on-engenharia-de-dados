# InformalidadeBR — Predição de Trabalho Informal a partir da PNAD Contínua

Atividade Final - Pós Graduação de Engenharia de Dados - Mackenzie 

## Integrantes

| Nome                                  | RA       | GitHub                                                |
|----------------------------------------|----------|--------------------------------------------------------|
| Jefferson Aparecido Nunes Lopes        | 10738951 | [@JeffersonAPLopes1020](https://github.com/JeffersonAPLopes1020) |
| Guilherme Ramon Santos Camargo         | 10734218 | [@gui-ramon](https://github.com/gui-ramon)             |
| Bruno Roberto Muniz Cabral             | 10733637 | [@3runo83](https://github.com/3runo83)                 |

## Contexto

A informalidade é um traço estrutural do mercado de trabalho brasileiro,
afetando uma grande parcela dos trabalhadores e limitando acesso a direitos
trabalhistas, previdência e crédito. Este projeto constrói um pipeline
completo de engenharia de dados sobre os microdados da **PNAD Contínua**
(IBGE), culminando em um modelo de machine learning que prevê a condição de
informalidade de um trabalhador.

## Problema a ser resolvido

Prever se um trabalhador está na informalidade (sem carteira assinada, conta
própria sem CNPJ, etc.) a partir de características socioeconômicas —
escolaridade, idade, região, setor de atividade, gênero e raça — e
identificar quais fatores mais se associam a essa condição.

## Coleta dos Dados

**Objetivo**: ter dados relevantes, confiáveis e representativos do problema
de informalidade no mercado de trabalho brasileiro.

### Entregáveis

| Entregável | Onde está |
|---|---|
| **Dataset bruto (raw data)** | `dados/bronze/<ano>/PNADC_0<trimestre><ano>.txt` — microdados de largura fixa, exatamente como recebidos do IBGE, sem nenhuma transformação. Um manifesto JSON por período (`PNADC_0<trimestre><ano>.manifest.json`) registra `source_url`, `source_file`, contagem de linhas, checksum SHA-256 e `load_timestamp`. Pasta ignorada pelo git (`.gitignore`) — dados grandes não são versionados. |
| **Lista/documentação das fontes** | Fonte única: FTP público do IBGE, `https://ftp.ibge.gov.br/.../Pesquisa_Nacional_por_Amostra_de_Domicilios_continua/Trimestral/Microdados/`. Detalhado em [`docs/01-requisitos-funcionais.md`](docs/01-requisitos-funcionais.md) (RF-01). |
| **Dicionário de dados** | Original do IBGE em `dados/bronze/documentacao/` (baixado junto com os dados). Subconjunto de 22 variáveis selecionadas para este projeto, com posição/tamanho/categorias, em [`docs/03-dicionario-de-dados.md`](docs/03-dicionario-de-dados.md). |
| **Scripts/processos de coleta** | `src/ingestao/ingestao.py` (classe `Ingestao`) — download com retentativa (backoff exponencial), resolução dinâmica do nome do arquivo no índice do IBGE, extração e substituição atômica do período. Executável também célula a célula em `notebooks/01_ingestao.ipynb`, onde `ANOS`/`TRIMESTRES` são parametrizáveis sem editar o `.py`. |
| **Critérios de seleção dos dados** | Ver abaixo. |

**Critérios de seleção**: PNAD Contínua **trimestral** (não a anual/"Visita")
porque já traz trabalho e educação no mesmo arquivo, sem precisar de uma
segunda fonte. Período 2023-2025 (12 trimestres, todos os 4 por ano) —
recente o suficiente para refletir o mercado de trabalho atual, com volume
suficiente (~470-500 mil registros/trimestre) para segmentar por gênero e
raça sem esvaziar subgrupos. Das ~420 variáveis disponíveis, 22 foram
selecionadas por relevância direta ao problema (ver dicionário) — evitar
"pegar tudo" pra não gerar ruído desnecessário na etapa de Silver/EDA.

### Pontos de atenção

- **Qualidade dos dados**: cada período tem manifesto com checksum SHA-256 e
  contagem de linhas, permitindo detectar corrupção/incompletude
  (RF-07/RNF-05 — reconciliação Bronze → Gold).
- **Relevância**: seleção deliberada de 22 das ~420 variáveis (ver critérios
  acima), em vez de ingerir o arquivo inteiro para as camadas seguintes.
- **Viés (bias)**: a PNAD Contínua é amostra complexa (estratificada, por
  conglomerados), não amostra aleatória simples — estatísticas descritivas
  devem ser ponderadas pelo peso amostral `V1028` para serem representativas
  da população (detalhado em `docs/03-dicionario-de-dados.md`). Além disso,
  o próprio tema do projeto (recorte por gênero/raça) exige atenção a
  subgrupos pequenos, que podem ter alta variância amostral.
- **Volume vs. necessidade**: os 12 trimestres somam ~19GB brutos (texto de
  largura fixa não comprimido), mas só 22 colunas serão de fato usadas —
  volume bruto alto não significa volume útil alto.
- **Integração de múltiplas fontes**: não se aplica — fonte única (IBGE). O
  risco correspondente aqui é de outra natureza: o layout de colunas pode
  variar entre revisões do dicionário ao longo dos anos; a ingestão sempre
  baixa a versão mais recente do dicionário junto aos dados (ver RNF-01).
- **Aspectos legais e éticos**: microdados públicos e anonimizados pelo
  IBGE (sem identificação direta), portanto fora do escopo de dado pessoal
  identificável da LGPD. Ainda assim, por usar raça e gênero como eixo de
  análise, os resultados devem ser tratados como diagnóstico agregado — não
  para inferir ou rotular indivíduos (RNF-07/RNF-11).
- **Atualização e temporalidade**: o IBGE revisa/republica trimestres depois
  da divulgação inicial (ex.: uma revisão de 2024-Q2 aparecida meses depois
  da primeira publicação) — por isso a ingestão sempre baixa novamente e
  substitui o arquivo local a cada execução, em vez de assumir que o que já
  está no Bronze é definitivo (RNF-01).

## Modelagem (ML)

Classificação binária (formal vs. informal), sobre as 2.522.338 pessoas
ocupadas da Gold (2023-2025). Detalhado com justificativa em
[`docs/05-plano-de-modelagem.md`](docs/05-plano-de-modelagem.md).

- **Modelos**: Regressão Logística (baseline interpretável), Random Forest
  (com `max_samples` limitado por árvore, pra não estourar RAM em milhões de
  linhas) e `HistGradientBoostingClassifier` (lida nativamente com categoria
  e valor nulo — evita one-hot em `UF`/setor/ocupação e imputação nas duas
  features mais fortes, que têm 20-40% de nulo).
- **Split**: temporal, não aleatório — treino 2023-2024, teste 2025 (a PNAD é
  um painel rotativo; um split aleatório vazaria a mesma pessoa entre treino
  e teste).
- **Avaliação**: acurácia, precisão, recall, F1 e AUC-ROC, comparadas entre
  treino e teste (checagem de overfitting) e fatiadas por sexo/raça
  (equidade, RNF-11).
- **Interpretabilidade**: SHAP (`TreeExplainer`) recortado por gênero e raça
  para revelar o peso de cada fator na predição da informalidade por grupo.

## Diferencial

Foge das sugestões genéricas ao focar num problema social específico
(informalidade) com camada de interpretabilidade que expõe desigualdades de
gênero e raça — em vez de apenas prever renda ou desemprego de forma direta.

Pipeline de engenharia de dados organizado segundo a **arquitetura Medallion**
(Bronze / Silver / Gold) e orquestrado por uma classe principal (`Pipeline`),
seguindo o ciclo:

**ingestão → pré-processamento → análise exploratória → modelagem ML → apresentação**

> Este repositório contém a **estrutura** do pipeline (classes, camadas e
> orquestração). A ingestão (RF-01) já está implementada e baixa os dados
> reais do IBGE. O pré-processamento (RF-02) já seleciona as 22 variáveis do
> [dicionário de dados](docs/03-dicionario-de-dados.md) (+ 4 identificadores
> únicos de pessoa, usados só para deduplicar corretamente), trata nulos e
> consolida todos os períodos em `dados/silver/dados_silver.parquet`
> (**0 linhas perdidas na reconciliação** — ver [`docs/04-arquitetura.md`
> §9](docs/04-arquitetura.md#9-validação-com-agentes-de-ia-aiox)) — falta
> ainda decodificar os códigos em rótulos de categoria (ex.: `V2007=1` →
> "Homem"). A transformação (RF-03) também já está implementada: filtra
> pessoas ocupadas (`VD4002=1`) e deriva a variável-alvo `informal` a partir
> de `VD4009`/`V4019` — **47,6% de informalidade** sobre 2.522.338 ocupados
> na base completa 2023-2025 (regra ainda pendente de validação formal do
> time, ver docstring de `src/transformacao/transformacao.py`). A análise
> exploratória (RF-04) está completa — ver "Boletins de EDA" abaixo. A
> modelagem (RF-05/RF-06, `src/modelagem/`) já está implementada e testada
> com uma amostra pequena da base (smoke test); falta rodar oficialmente na
> base completa (2,5M linhas) e registrar os resultados aqui.

## Boletins (dashboard/)

Boletins HTML standalone (abrem local, sem servidor), com a mesma linguagem
visual — paleta, tipografia e "takeaway no topo" vêm de `src/relatorio_visual.py`,
compartilhado pelos dois:

| Boletim | Gerado por | O que mostra |
|---|---|---|
| [`dashboard/censo_informalidade.html`](dashboard/censo_informalidade.html) | `src/analise/relatorios.py` (RF-04), a cada `pipeline.analisar()` ou `python -m scripts.gerar_boletins_eda` | Do público total ao perfil do trabalhador informal: quem entra na conta (funil de ocupados) e por que a informalidade foi definida assim; tendência temporal; **retrato do informal × formal** (escolaridade, setor, região, idade, jornada, renda); onde a informalidade se concentra (barras de comparação formal × informal por sexo, raça, região, escolaridade, tempo no emprego, tamanho do negócio, setor, ocupação — com seletor por ano); ranking de força de associação das features; matriz de correlação de Pearson; % de nulos; hipóteses para a modelagem. |
| [`dashboard/modelagem_informalidade.html`](dashboard/modelagem_informalidade.html) | `src/modelagem/relatorio.py` (RF-05/RF-06), a cada `pipeline.treinar_modelo()` | Qual dos 3 modelos escolher e por quê; comparação Accuracy/Precision/Recall/F1/AUC/tempo; **simulador de threshold** (recalcula precisão/recall/confusão ao vivo); velocidade × desempenho; overfitting (gap treino vs. teste); o que o modelo aprendeu (SHAP / coeficientes); **Model Card de equidade** (recall e falso-positivo por sexo e raça). O diagnóstico técnico da rodada (flags automáticas + comparação com a rodada anterior) fica em `dados/modelos/diagnostico_modelagem.{json,txt}`. |

## Arquitetura Medallion

| Camada     | Pasta          | Descrição                                                       |
|------------|----------------|-------------------------------------------------------------------|
| **Bronze** | `dados/bronze/`| Microdados brutos da PNAD Contínua (largura fixa), como baixados do IBGE. |
| **Silver** | `dados/silver/`| Variáveis decodificadas (ex: VD4001, V2007), nulos tratados e padronizados. |
| **Gold**   | `dados/gold/`  | Dataset curado com a variável-alvo de informalidade, pronto para modelagem. |

> `dados/` é ignorada pelo git (ver `.gitignore`), pois arquivos de dados
> costumam ser grandes e/ou não devem ser versionados. Para os orientadores
> conseguirem ter uma noção visual dos dados sem rodar o pipeline, uma
> amostra pequena da Bronze bruta (500 linhas), da Silver tratada
> (~1.000 linhas) e o dicionário oficial do IBGE ficam versionados em
> [`dados_amostra/`](dados_amostra/README.md) (gerados via
> `python -m scripts.gerar_amostra`).

## Estrutura do projeto

```
.
├── src/
│   ├── etapa.py              # Classe base (interface) Etapa, com o método executar()
│   ├── pipeline.py           # Classe Pipeline: orquestra todas as etapas em ordem
│   ├── ingestao/              # Extração da fonte de dados → camada Bronze
│   ├── preprocessamento/      # Limpeza e padronização → camada Silver
│   ├── transformacao/         # Curadoria e agregação → camada Gold
│   ├── analise/                # Análise exploratória de dados (EDA)
│   └── modelagem/             # Treino e avaliação de modelos de ML
├── notebooks/
│   ├── 01_ingestao.ipynb
│   ├── 02_preprocessamento.ipynb
│   ├── 03_analise.ipynb
│   └── 04_modelagem.ipynb
├── dados/
│   ├── bronze/                # Dados brutos
│   ├── silver/                # Dados limpos
│   ├── gold/                  # Dados prontos para análise/modelo
│   └── modelos/               # Modelos treinados (.joblib), gráficos e relatório (gerado por Modelagem, gitignored)
├── dados_amostra/               # Amostra bruta + tratada + dicionário do IBGE, versionados (dados/ não é)
├── scripts/
│   ├── gerar_amostra.py        # Gera a amostra acima a partir da Silver
│   └── gerar_boletins_eda.py   # Regera o boletim HTML de EDA sob demanda
├── docs/                       # Requisitos, dicionário de dados, arquitetura, plano de modelagem
├── dashboard/                  # Boletins de EDA (HTML, gerados) + apresentação (ex: Streamlit)
├── requirements.txt            # Dependências Python do projeto (versões fixadas)
└── README.md
```

## Classes do pipeline

### `Etapa` (`src/etapa.py`)

Classe base abstrata que define a interface comum a todas as etapas: todo
módulo do pipeline implementa uma classe que herda de `Etapa` e sobrescreve o
método `executar()`.

### Classes de cada etapa

| Etapa                | Classe             | Módulo                                   | Camada de saída |
|-----------------------|---------------------|-------------------------------------------|------------------|
| Ingestão               | `Ingestao`          | `src/ingestao/ingestao.py`                 | Bronze            |
| Pré-processamento      | `Preprocessamento`  | `src/preprocessamento/preprocessamento.py` | Silver            |
| Transformação          | `Transformacao`     | `src/transformacao/transformacao.py`       | Gold              |
| Análise exploratória   | `Analise`           | `src/analise/analise.py`                   | —                 |
| Modelagem              | `Modelagem`         | `src/modelagem/modelagem.py`               | —                 |

### `Pipeline` (`src/pipeline.py`)

Classe orquestradora com um método por etapa e um método `executar()` que
roda todas em ordem:

```python
from src.pipeline import Pipeline

pipeline = Pipeline()

pipeline.ingerir()         # Ingestão → Bronze
pipeline.preprocessar()    # Pré-processamento → Silver
pipeline.transformar()     # Transformação → Gold
pipeline.analisar()        # Análise exploratória
pipeline.treinar_modelo()  # Treino e avaliação do modelo

# ou, para rodar todas as etapas em ordem:
pipeline.executar()
```

## Como usar

1. Crie um ambiente virtual e instale as dependências:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. A ingestão (`src/ingestao/`) já está implementada — baixa a PNAD
   Contínua real (ver "Coleta dos Dados" acima). O pré-processamento
   (`src/preprocessamento/`) também já está implementado — seleciona as 22
   variáveis, trata nulos e consolida os períodos na Silver. A transformação
   (`src/transformacao/`) já filtra ocupados e deriva a variável-alvo de
   informalidade (Gold). A análise exploratória (`src/analise/`) já gera o
   boletim de EDA automaticamente (ver acima). A modelagem
   (`src/modelagem/`) já está implementada — ver [`docs/05-plano-de-
   modelagem.md`](docs/05-plano-de-modelagem.md) para os algoritmos e
   features usados.
3. Rode o pipeline completo:
   ```bash
   python -m src.pipeline
   ```
   Ou explore cada etapa individualmente pelos notebooks em `notebooks/`.
   Pra testar a modelagem numa amostra pequena antes de rodar na base
   inteira (2,5M linhas pode levar um tempo, especialmente com tuning de
   hiperparâmetro ligado):
   ```python
   from src.modelagem.modelagem import Modelagem
   Modelagem(n_amostra=5000).executar()  # smoke test
   Modelagem().executar()                # base completa (oficial)
   ```
4. Documente decisões, dicionário de dados e relatório final em `docs/`.
5. Apresente os resultados via `dashboard/` (boletim de EDA já pronto) e
   `dados/modelos/` (relatório e gráficos gerados pela modelagem).
