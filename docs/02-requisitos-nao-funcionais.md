# Requisitos Não Funcionais (RNF) — InformalidadeBR

Este documento estabelece os critérios de qualidade e metas de
confiabilidade (SRE) do pipeline InformalidadeBR, baseados na ISO/IEC 25010
(Qualidade de Produto) e ISO/IEC 25012 (Qualidade de Dados), adaptados a uma
execução **100% local** (sem infraestrutura cloud).

## 1. Confiabilidade e Resiliência

- **RNF-01 (Idempotência)**: o pipeline deve permitir re-execuções (mesmo
  período de dados) sem duplicar registros nas camadas Bronze/Silver/Gold.
  - SLI: taxa de duplicidade após re-execução.
  - SLO: 0% de registros duplicados.
- **RNF-02 (Retentativa)**: o download dos microdados do IBGE deve possuir
  lógica de retry com backoff exponencial para falhas temporárias de rede.

## 2. Eficiência de Desempenho

- **RNF-03 (Tempo de execução)**: o pipeline completo (ingestão →
  modelagem) deve rodar em tempo compatível com iteração local.
  - SLI: duração total da execução, para um trimestre de dados.
  - SLO: < 15 minutos em máquina local padrão (a validar).
- **RNF-04 (Uso de memória)**: o pré-processamento deve prever leitura em
  chunks para períodos/volumes que excedam a memória disponível, evitando
  estouro em notebook/laptop.

## 3. Qualidade de Dados (ISO 25012)

- **RNF-05 (Exatidão e Completude)**: a contagem de registros entre Bronze
  e Gold deve ser reconciliável — toda diferença (nulos descartados, filtros
  de regra de negócio) deve ser explicável e documentada nos logs de
  auditoria (RF-07).
  - SLI: diferença de contagem não explicada por regra conhecida.
  - SLO: 0% de perda não documentada.
- **RNF-06 (Consistência)**: toda categoria decodificada na Silver deve
  existir no dicionário de variáveis do IBGE — nenhum código órfão.

## 4. Segurança e Governança

- **RNF-07 (Dados públicos, sem PII)**: os microdados da PNAD Contínua são
  públicos e anonimizados pelo IBGE; ainda assim, nenhuma transformação do
  pipeline deve introduzir combinações de variáveis que viabilizem
  reidentificação de indivíduos.
- **RNF-08 (Segredos)**: nenhuma credencial ou token (se necessário para
  automação de download) deve ser versionado no repositório — uso de `.env`
  (fora do controle de versão, já coberto por `.gitignore`).

## 5. Observabilidade (Golden Signals)

- **RNF-09 (Monitoramento de saúde)**: o pipeline deve expor métricas de
  sucesso por execução.
  - SLI: percentual de execuções bem-sucedidas.
  - SLO: > 95%.
- **RNF-10 (Frescor do dado)**: o dashboard deve exibir o período de
  referência coberto pela última execução do pipeline.

## 6. Equidade e Responsabilidade do Modelo (específico deste projeto)

- **RNF-11 (Equidade entre grupos)**: a diferença de métricas de erro do
  modelo (ex.: recall, taxa de falso positivo) entre grupos demográficos
  (gênero, raça) deve ser mensurada e reportada — não apenas a métrica
  agregada do modelo.
  - SLI: gap da métrica de erro entre grupos protegidos.
  - SLO: gap documentado e reportado no dashboard (sem teto fixo definido
    para este trabalho acadêmico — ver Plano de Teste de Modelagem).
- **RNF-12 (Reprodutibilidade)**: o treino e o split de dados devem usar
  seed fixa, garantindo resultados reproduzíveis entre execuções.

## Tabela de SLIs/SLOs Consolidada

| Categoria | ID | SLI | SLO | Fonte de Dados |
|---|---|---|---|---|
| Confiabilidade | RNF-01 | Taxa de duplicidade | 0% | Contagem por camada (Parquet) |
| Performance | RNF-03 | Tempo de execução do pipeline | < 15 min | Logs de execução |
| Qualidade de Dados | RNF-05 | Reconciliação Bronze → Gold | 0% de perda não documentada | Logs de auditoria (RF-07) |
| Segurança | RNF-08 | Segredos no código | 0 | Revisão manual / scan (ex. gitleaks) |
| Observabilidade | RNF-09 | Taxa de sucesso das execuções | > 95% | Logs de execução |
| Equidade | RNF-11 | Gap de erro entre grupos (gênero/raça) | Reportado no dashboard | Avaliação do modelo (RF-06) |

## Análise de Risco (RNF)

- **Risco de escopo de segurança**: como não há infraestrutura cloud, o
  risco de segurança concentra-se em vazamento acidental de dados/segredos
  no repositório Git público — mitigado por `.gitignore` e revisão manual.
- **Risco de viés não detectado**: sem RNF-11 ativo desde o início da
  modelagem, o time pode entregar um modelo com desempenho desigual entre
  grupos sem perceber, comprometendo o diferencial do projeto.
- **Risco de reprodutibilidade**: ausência de seed fixa (RNF-12) pode gerar
  métricas diferentes a cada execução, dificultando comparação entre
  modelos e apresentação de resultados.
