# Mapa do Diretório de Documentação

Este arquivo serve como um índice para os documentos deste projeto
(**InformalidadeBR** — predição de trabalho informal a partir da PNAD Contínua).

| # | Documento | Status |
|---|-----------|--------|
| 1 | [Requisitos Funcionais](01-requisitos-funcionais.md) | ✅ Definido |
| 2 | [Requisitos Não Funcionais](02-requisitos-nao-funcionais.md) | ✅ Definido |
| 3 | [Dicionário de Dados](03-dicionario-de-dados.md) | ✅ Definido |
| 4 | [Arquitetura](04-arquitetura.md) | ✅ Definido |
| 5 | Matriz de Rastreabilidade de Requisitos (RTM) | ⏳ Pendente |
| 6 | Plano de Teste de Carga | ⏳ Pendente |
| 7 | Plano de Teste de Segurança | ⏳ Pendente |
| 8 | Plano de Teste de Modelagem | ⏳ Pendente |

## Ordem sugerida de leitura/elaboração

1. **Requisitos Funcionais (RF)** e **Requisitos Não Funcionais (RNF)** — o que o
   pipeline precisa fazer e com qual nível de qualidade/confiabilidade.
2. **Dicionário de Dados** — quais variáveis da PNAD Contínua sustentam o
   alvo de informalidade, as features e a análise de equidade; resolve a
   ambiguidade de regra de negócio deixada em aberto no RF-01.
3. **Arquitetura** — como o pipeline local (ingestão → Bronze/Silver/Gold →
   modelagem → dashboard) atende aos RF/RNF, com revisão de táticas
   arquiteturais (AIOX, baseado em Len Bass).
4. **RTM** — rastreia cada RF/RNF até o código/teste que o implementa/valida.
5. **Planos de Teste** (Carga, Segurança, Modelagem) — como cada categoria de
   risco é verificada antes da entrega final.

> Este projeto roda **100% local** (sem AWS/cloud): dados públicos do IBGE,
> processamento em pandas/parquet, modelagem em scikit-learn, apresentação em
> Streamlit. Os documentos abaixo refletem essa restrição — não há
> requisitos de infraestrutura cloud (SSM, RDS, EC2 etc.).
