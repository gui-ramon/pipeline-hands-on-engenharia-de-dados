# Requisitos Funcionais (RF) — InformalidadeBR

Este documento detalha as funcionalidades necessárias para o pipeline de
dados do InformalidadeBR, focado na predição de trabalho informal a partir
dos microdados da **PNAD Contínua** (IBGE), rodando 100% local.

## RF-01: Ingestão de Dados (Extração)

- **Descrição**: O sistema deve extrair os microdados da PNAD Contínua
  (arquivos de texto de largura fixa) e o respectivo dicionário de variáveis,
  diretamente da fonte pública do IBGE, para os ~3 anos recentes selecionados.
- **Requisito SRE**: A extração deve ser idempotente; re-execuções para o
  mesmo período (ano/trimestre) não devem duplicar arquivos na camada Bronze.
- **Saída**: Arquivo de largura fixa (`.txt`) gravado byte a byte, sem
  decodificação, em `dados/bronze/<ano>/`, um por período (trimestre), com
  um manifesto JSON de metadados (`source_url`, `source_file`, contagem de
  linhas, checksum SHA-256, `load_timestamp`). O dicionário de variáveis do
  IBGE é baixado uma única vez para `dados/bronze/documentacao/`.

## RF-02: Pré-processamento (Decodificação e Limpeza)

- **Descrição**: O sistema deve decodificar as variáveis de largura fixa
  usando o dicionário do IBGE (ex.: `VD4001`, `VD4002`, `V2007`, `V2010`) e
  padronizar tipos e categorias.
- **Regras de qualidade**:
  - Tratamento de códigos especiais do IBGE (não aplicável, não declarado)
    como nulo explícito, não como categoria válida.
  - Normalização de categorias (sexo, raça/cor, região, escolaridade, setor
    de atividade) para rótulos consistentes entre períodos.
- **Saída**: Dataset decodificado por período, gravado em `dados/silver/`.

## RF-03: Transformação e Curadoria (Gold)

- **Descrição**: O sistema deve consolidar os períodos processados e
  construir a variável-alvo de informalidade.
- **Regra de negócio (Informalidade)**: classificação binária
  formal/informal derivada das variáveis de posição na ocupação e carteira
  assinada/CNPJ da PNAD Contínua (regra exata a confirmar com o dicionário —
  ver Ambiguidades).
- **Saída**: Dataset único e curado em `dados/gold/`, com as features
  socioeconômicas (escolaridade, idade, região, setor, gênero, raça) e a
  variável-alvo, pronto para EDA e modelagem.

## RF-04: Análise Exploratória de Dados (EDA)

- **Descrição**: O sistema deve gerar estatísticas descritivas e
  visualizações da taxa de informalidade, com recortes por gênero, raça,
  região, escolaridade, setor de atividade, grupamento ocupacional, tamanho
  do negócio e tempo no emprego — ver lista completa de variáveis em
  [Dicionário de Dados](03-dicionario-de-dados.md).
- **Saída**: Gráficos/relatórios reproduzíveis (script ou notebook),
  utilizados como insumo para a etapa de modelagem e para o dashboard.

## RF-05: Modelagem e Avaliação (ML)

- **Descrição**: O sistema deve treinar e comparar modelos de classificação
  binária (Regressão Logística, Random Forest, Gradient Boosting).
- **Avaliação**: acurácia, precisão, recall, F1 e AUC-ROC, reportadas por
  modelo.
- **Saída**: Modelo treinado persistido (`joblib`) e tabela de métricas por
  modelo.

## RF-06: Interpretabilidade e Análise de Equidade

- **Descrição**: O sistema deve expor a importância de variáveis (SHAP ou
  equivalente) do modelo escolhido, com recorte específico para **gênero** e
  **raça**, revelando o peso relativo de cada fator na predição de
  informalidade.
- **Saída**: Artefatos de interpretabilidade (gráficos summary/importância)
  reutilizáveis pelo dashboard.

## RF-07: Observabilidade e Auditoria do Pipeline

- **Descrição**: O sistema deve registrar métricas de execução para cada
  estágio (ingestão, pré-processamento, transformação, modelagem).
- **Métricas de auditoria (reconciliação)**: contagem de registros de
  entrada vs. saída em cada camada (Bronze → Silver → Gold), e volume de
  nulos descartados por regra de qualidade.
- **Rastreabilidade**: cada registro no Gold deve poder ser rastreado até o
  `source_file`/período de origem.
- **Logs**: início, fim e duração de cada etapa.

## RF-08: Dashboard de Apresentação

- **Descrição**: Aplicação Streamlit que responda às perguntas centrais do
  projeto:
  - **Taxa de informalidade**: geral e por corte (gênero, raça, região,
    escolaridade, setor).
  - **Fatores associados**: ranking de importância de variáveis (saída do
    RF-06).
  - **Saúde do pipeline**: status da última execução e período de dados
    coberto (frescor do dado).

## Análise de Risco (RF)

- **Risco de decodificação**: erro na leitura do dicionário de variáveis de
  largura fixa pode corromper silenciosamente os dados (colunas
  deslocadas), sem gerar erro explícito.
- **Risco de viés amostral**: desbalanceamento entre grupos (ex.: raça,
  gênero, região) pode enviesar o modelo e distorcer a análise de
  equidade — deve ser medido, não apenas assumido ausente.
- **Risco de volume**: múltiplos trimestres de microdados da PNAD Contínua
  podem somar múltiplos GB; o pré-processamento deve prever leitura em
  chunks para não estourar memória em máquina local.
- **Risco de desatualização da regra de negócio**: o IBGE pode revisar
  periodicamente a metodologia/variáveis da PNAD Contínua entre anos,
  quebrando a decodificação entre períodos.

## Ambiguidades (RF)

- A definição exata da variável(is) do IBGE que determinam "informalidade"
  (provavelmente derivada de `VD4009` — posição na ocupação — combinada com
  carteira assinada/contribuição previdenciária) precisa ser confirmada com
  o dicionário oficial antes da implementação do RF-03.
- O período exato (quais anos/trimestres) da PNAD Contínua a utilizar ainda
  não foi fixado.
- Tratamento de trabalhadores fora da força de trabalho (não aplicável à
  pergunta de informalidade) — devem ser filtrados na Silver ou mantidos e
  marcados como não aplicável?
