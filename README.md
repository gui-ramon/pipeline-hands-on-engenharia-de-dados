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

## Fonte de dados

Microdados anuais da **PNAD Contínua** (módulo Educação/Trabalho), IBGE,
aproximadamente 3 anos recentes. Fonte única. Formato de texto de largura
fixa + dicionário de variáveis para decodificação.

## Modelagem (ML)

Classificação binária (formal vs. informal).

- **Modelos**: Regressão Logística (baseline interpretável), Random Forest e Gradient Boosting.
- **Avaliação**: acurácia, precisão, recall, F1 e AUC-ROC.
- **Interpretabilidade**: camada com SHAP / importância de variáveis para revelar o peso de cada fator — com destaque para gênero e raça — na predição da informalidade.

## Diferencial

Foge das sugestões genéricas ao focar num problema social específico
(informalidade) com camada de interpretabilidade que expõe desigualdades de
gênero e raça — em vez de apenas prever renda ou desemprego de forma direta.

Pipeline de engenharia de dados organizado segundo a **arquitetura Medallion**
(Bronze / Silver / Gold) e orquestrado por uma classe principal (`Pipeline`),
seguindo o ciclo:

**ingestão → pré-processamento → análise exploratória → modelagem ML → apresentação**

> Este repositório contém a **estrutura** do pipeline (classes, camadas e
> orquestração). A lógica específica de cada etapa (parsing dos microdados da
> PNAD Contínua, decodificação de variáveis, construção da variável-alvo de
> informalidade e treino do modelo) está marcada com `# TODO` nos módulos em
> `src/` e deve ser preenchida ao longo do desenvolvimento.

## Arquitetura Medallion

| Camada     | Pasta          | Descrição                                                       |
|------------|----------------|-------------------------------------------------------------------|
| **Bronze** | `dados/bronze/`| Microdados brutos da PNAD Contínua (largura fixa), como baixados do IBGE. |
| **Silver** | `dados/silver/`| Variáveis decodificadas (ex: VD4001, V2007), nulos tratados e padronizados. |
| **Gold**   | `dados/gold/`  | Dataset curado com a variável-alvo de informalidade, pronto para modelagem. |

> `dados/` é ignorada pelo git (ver `.gitignore`), pois arquivos de dados
> costumam ser grandes e/ou não devem ser versionados.

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
│   └── gold/                  # Dados prontos para análise/modelo
├── docs/                       # Proposta do projeto, dicionário de dados, relatório final
├── dashboard/                  # Aplicação de apresentação (ex: Streamlit)
├── requirements.txt            # Dependências Python do projeto
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
2. Preencha os `# TODO` de `src/ingestao/`, `src/preprocessamento/`,
   `src/transformacao/` e `src/modelagem/` de acordo com o tema/dataset do
   projeto.
3. Rode o pipeline completo:
   ```bash
   python -m src.pipeline
   ```
   Ou explore cada etapa individualmente pelos notebooks em `notebooks/`.
4. Documente decisões, dicionário de dados e relatório final em `docs/`.
5. Apresente os resultados via `dashboard/`.
