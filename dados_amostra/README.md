# Amostra de dados (versionada no Git)

A pasta `dados/` inteira é ignorada pelo Git (ver `.gitignore`) — a Bronze
soma ~19GB e a Silver consolidada ~63MB, grande demais/desnecessário para
versionar. Esta pasta guarda só uma amostra pequena de cada ponta do
pré-processamento — o **"antes"** (bruto, como o IBGE publica) e o
**"depois"** (tratado) — para que orientadores e avaliadores consigam abrir
direto no GitHub e ter uma noção visual dos dados e do que foi feito, sem
precisar rodar o pipeline localmente.

| Arquivo | Conteúdo |
|---|---|
| `pnadc_bronze_amostra.txt` | **Antes.** As primeiras 500 linhas do período mais recente da camada Bronze (`dados/bronze/<ano>/PNADC_0<tri><ano>.txt`) — largura fixa, ~3.480 caracteres por linha, exatamente como baixado do IBGE (RF-01), byte a byte, **sem nenhum tratamento**. Ilegível sem o dicionário (cada posição de caractere é uma variável diferente — ver `docs/03-dicionario-de-dados.md`). |
| `pnadc_silver_amostra.csv` | **Depois.** ~1.000 linhas (83 por período × 12 períodos, seed fixa = 42) sorteadas da camada Silver consolidada (`dados/silver/dados_silver.parquet`) — as 22 variáveis de conteúdo selecionadas + 4 identificadores únicos de pessoa (`UPA`/`V1008`/`V1014`/`V2003`, ver [dicionário](../docs/03-dicionario-de-dados.md)), já com nulos tratados (RF-02) e deduplicadas pela chave real (ver [`docs/04-arquitetura.md` §9](../docs/04-arquitetura.md#9-validação-com-agentes-de-ia-aiox)), ainda **sem** decodificação de categorias (`V2007=1` continua `1`, não "Homem" — planejado, ver README principal). |
| `dicionario_PNADC_microdados_trimestral.xls` | Dicionário oficial de variáveis do IBGE, cópia do baixado pela ingestão em `dados/bronze/documentacao/`. Necessário para interpretar tanto o arquivo bruto quanto o tratado acima — ver também o resumo já traduzido em [`docs/03-dicionario-de-dados.md`](../docs/03-dicionario-de-dados.md). |

## O que mudou do bruto pro tratado

Comparando os dois arquivos acima, dá pra ver na prática (RF-02):

- **Seleção**: de ~420 variáveis (posições dentro da linha de largura fixa)
  para as 22 relevantes ao problema de informalidade + 4 identificadores.
- **Nulos explícitos**: campos em branco no bruto (espaços) viram `NaN` de
  verdade no tratado, em vez de string vazia ambígua.
- **Deduplicação por chave real**: usa `UPA+V1008+V1014+V2003`, não as
  colunas de conteúdo — evita descartar pessoas diferentes que coincidem
  nas variáveis selecionadas (achado documentado em
  [`docs/04-arquitetura.md` §9](../docs/04-arquitetura.md#9-validação-com-agentes-de-ia-aiox)).
- **O que ainda não muda aqui**: decodificação de categorias (código →
  rótulo), tratamento de outliers e normalização/encoding — são decisões
  de etapas posteriores (Gold/EDA/Modelagem), não do pré-processamento
  (Silver). Ver `docs/04-arquitetura.md` §8 "Trabalho futuro".

## Como regenerar

Depois de rodar a ingestão e o pré-processamento (`notebooks/01` e `02`, ou
`python -m src.pipeline`):

```bash
python -m scripts.gerar_amostra
```

Isso sobrescreve os três arquivos acima com os dados mais recentes.
