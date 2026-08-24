# Dicionário de Dados — PNAD Contínua (InformalidadeBR)

## Onde encontrar

A ingestão (`src/ingestao/ingestao.py`, RF-01) já baixa o dicionário oficial
do IBGE junto com os microdados, uma vez por execução, em:

```
dados/bronze/documentacao/
├── dicionario_PNADC_microdados_trimestral.xls   ← dicionário completo (código, posição, tamanho, categorias)
├── input_PNADC_trimestral.sas                   ← layout de colunas (formato SAS)
└── input_PNADC_trimestral.txt                   ← mesmo layout, texto puro
```

O `.xls` é a fonte de verdade: cada linha traz `Posição inicial`, `Tamanho`,
`Código da variável`, a descrição do quesito e, quando aplicável, a lista de
categorias (código → rótulo). As posições são **1-indexadas** (convenção
SAS/IBGE) — para fatiar com `pandas.read_fwf` na Silver, o offset inicial é
`posição - 1`.

Para abrir programaticamente (precisa de `xlrd`, já adicionado a
`requirements.txt`):

```python
import pandas as pd
xls = pd.ExcelFile("dados/bronze/documentacao/dicionario_PNADC_microdados_trimestral.xls")
df = xls.parse(xls.sheet_names[0], header=None, skiprows=4)
```

## Variáveis recomendadas para este projeto

O dicionário completo tem ~420 variáveis (a PNAD Contínua cobre muito mais
que trabalho: migração, deficiência, TIC em alguns trimestres etc.). A
maioria não interessa ao problema de informalidade. Lista abaixo o subconjunto
que sustenta RF-02 (decodificação/Silver), RF-03 (variável-alvo/Gold), RF-04
(EDA) e RF-05/RF-06 (modelo + interpretabilidade por gênero/raça).

### Identificação (sempre necessárias)

| Código | Posição | Tam. | Descrição |
|---|---|---|---|
| `Ano` | 1 | 4 | Ano de referência |
| `Trimestre` | 5 | 1 | Trimestre de referência (1-4) |
| `UF` | 6 | 2 | Unidade da Federação |

### Identificador único de registro (não são features)

Chave única de pessoa/domicílio dentro de um período, convenção padrão do
IBGE. Necessária para deduplicar corretamente — ver "Achado de validação"
em [`docs/04-arquitetura.md`](04-arquitetura.md#9-validação-com-agentes-de-ia-aiox):
sem esses 4 campos, uma deduplicação ingênua pelas variáveis de conteúdo
descartava ~0,2% dos registros por período (pessoas *diferentes* que
coincidem em todas as 22 variáveis de conteúdo, principalmente quem está
fora da força de trabalho).

| Código | Posição | Tam. | Descrição |
|---|---|---|---|
| `UPA` | 12 | 9 | Unidade Primária de Amostragem |
| `V1008` | 28 | 2 | Número de seleção do domicílio |
| `V1014` | 30 | 2 | Painel |
| `V2003` | 91 | 2 | Número de ordem (da pessoa dentro do domicílio) |

Chave completa de deduplicação: `Ano + Trimestre + UPA + V1008 + V1014 + V2003`.

### Variável-alvo — informalidade (resolve a ambiguidade do RF-01)

| Código | Posição | Tam. | Descrição |
|---|---|---|---|
| **`VD4009`** | 417 | 2 | Posição na ocupação e categoria do emprego no trabalho principal |
| `V4019` | 186 | 1 | O negócio/empresa era registrado no CNPJ? (refina conta-própria/empregador) |
| `VD4012` | 423 | 1 | Contribuinte de instituto de previdência (proxy alternativo, mais simples) |
| `VD4002` | 410 | 1 | Condição de ocupação — usar para **filtrar apenas ocupados** antes de aplicar a regra abaixo |

`VD4009` é a variável derivada que o próprio IBGE usa para estudos de
informalidade. Categorias:

| Categoria | Descrição | Classificação sugerida |
|---|---|---|
| 1 | Empregado no setor privado **com** carteira assinada | Formal |
| 2 | Empregado no setor privado **sem** carteira assinada | **Informal** |
| 3 | Trabalhador doméstico **com** carteira assinada | Formal |
| 4 | Trabalhador doméstico **sem** carteira assinada | **Informal** |
| 5 | Empregado no setor público **com** carteira assinada | Formal |
| 6 | Empregado no setor público **sem** carteira assinada | **Informal** |
| 7 | Militar e servidor estatutário | Formal |
| 8 | Empregador | Formal se `V4019=1` (tem CNPJ), senão **Informal** |
| 9 | Conta-própria | Formal se `V4019=1` (tem CNPJ), senão **Informal** |
| 10 | Trabalhador familiar auxiliar | **Informal** (não remunerado, sem proteção) |
| *não aplicável* | Pessoa não ocupada | Excluir (filtrar com `VD4002`) |

> Ambiguidade do RF-01 fica resolvida assim: **informalidade = VD4009 nas
> categorias 2, 4, 6, 10, ou 8/9 sem CNPJ (`V4019≠1`)**, calculada apenas
> sobre pessoas ocupadas (`VD4002`). Time deve validar essa regra antes de
> travar o RF-03 — é a convenção acadêmica mais comum, mas existe a
> alternativa mais simples de usar só `VD4012` (contribui/não contribui
> para a previdência) como proxy binário direto.

### Features demográficas (o diferencial do projeto)

| Código | Posição | Tam. | Descrição |
|---|---|---|---|
| `V2007` | 95 | 1 | Sexo (1=Homem, 2=Mulher) |
| `V2010` | 107 | 1 | Cor ou raça (1=Branca, 2=Preta, 3=Amarela, 4=Parda, 5=Indígena, 9=Ignorado) |
| `V2009` | 104 | 3 | Idade |

### Domicílio e família

| Código | Posição | Tam. | Descrição |
|---|---|---|---|
| `VD2002` | 398 | 2 | Posição no domicílio (1=Pessoa responsável, 2=Cônjuge, 3=Filho(a), ... 17 categorias) |
| `VD2003` | 400 | 2 | Número de componentes do domicílio |
| `V1022` | 33 | 1 | Situação do domicílio (1=Urbana, 2=Rural) |
| `V1023` | 34 | 1 | Tipo de área (1=Capital, 2=Resto da RM, 3=Resto da RIDE, 4=Resto da UF) |

Cruzar `VD2002` com sexo/raça é um bom recorte de EDA: mostra se mulheres
responsáveis pelo domicílio têm taxa de informalidade diferente de mulheres
cônjuges, por exemplo.

### Educação

| Código | Posição | Tam. | Descrição |
|---|---|---|---|
| `VD3004` | 405 | 1 | Nível de instrução mais elevado alcançado (7 categorias) |
| `V3002` | 109 | 1 | Frequenta escola atualmente? (1=Sim, 2=Não) |

### Características do trabalho (o que deixa a EDA mais rica)

| Código | Posição | Tam. | Descrição |
|---|---|---|---|
| `VD4010` | 419 | 2 | Setor de atividade do trabalho principal (12 grupos — agropecuária, indústria, comércio, serviços domésticos etc.) |
| `VD4011` | 421 | 2 | Grupamento ocupacional (diretor/gerente, técnico, operário, ocupações elementares... 11 grupos) |
| `V4018` | 180 | 1 | Tamanho do negócio/empresa (1=1-5 pessoas, 2=6-10, 3=11-50, 4=51+) |
| `V4025` | 191 | 1 | É empregado temporário? (1=Sim, 2=Não) |
| `V4040` | 247 | 1 | Tempo nesse trabalho (1=<1 mês, 2=1 mês a 1 ano, 3=1-2 anos, 4=2+ anos) |
| `VD4031` | 462 | 3 | Horas habitualmente trabalhadas por semana, todos os trabalhos |

`V4018` (tamanho do negócio) e `V4040` (tempo no emprego) são achados
clássicos na literatura de informalidade — negócios pequenos e vínculos
recentes concentram informalidade — e devem render bons gráficos de EDA além
de boas features para o modelo.

### Peso amostral (representatividade — ver Pontos de Atenção no README)

| Código | Posição | Tam. | Descrição |
|---|---|---|---|
| `V1028` | 50 | 15 | Peso do domicílio e das pessoas |

A PNAD Contínua é uma amostra complexa (estratificada, por conglomerados,
com probabilidades desiguais de seleção) — **não** é uma amostra aleatória
simples. Estatísticas descritivas e proporções (taxa de informalidade por
grupo etc.) devem ser ponderadas por `V1028` para serem representativas da
população; sem isso, a EDA sub/superestima grupos conforme o desenho
amostral. As 200 colunas `V1028001`...`V1028200` (réplicas *bootstrap* para
erro-padrão) explicam por que cada linha do bruto tem ~3480 caracteres — não
são necessárias para este projeto (servem para intervalo de confiança fino,
fora do escopo do hands-on).

### Complementares — só para EDA, **não** usar como feature do modelo

| Código | Posição | Tam. | Descrição |
|---|---|---|---|
| `VD4016` | 427 | 8 | Rendimento mensal habitual do trabalho principal |
| `VD4017` | 435 | 8 | Rendimento mensal efetivo do trabalho principal |

> **Cuidado com vazamento de dado (data leakage)**: renda/rendimento
> (`VD4016`/`VD4017`/`VD4019`/`VD4020`) é fortemente circular com a condição
> de informalidade (quem é CLT tende a ter faixas de renda características).
> Ótimo para gráfico de EDA ("gap salarial formal x informal"), mas **não**
> deve entrar como variável preditiva do modelo de RF-05 — isso inflaria a
> métrica artificialmente e destruiria a interpretabilidade pretendida em
> RF-06 (o modelo "aprenderia" a copiar a própria definição do alvo).

## Lista consolidada (22 variáveis de conteúdo + 4 identificadores)

```
Identificação:      Ano, Trimestre, UF
Identificador único: UPA, V1008, V1014, V2003 (não são features — só deduplicação)
Alvo:                VD4009, V4019, VD4012, VD4002
Demográficas:        V2007, V2010, V2009
Domicílio/família:   VD2002, VD2003, V1022, V1023
Educação:            VD3004, V3002
Trabalho:            VD4010, VD4011, V4018, V4025, V4040, VD4031
Peso amostral:       V1028
Só EDA (renda):      VD4016, VD4017
```

## Resumo por etapa do pipeline

- **Silver (RF-02)**: decodificar todas as 22 variáveis de conteúdo acima
  usando as posições desta tabela + as categorias do `.xls` (decodificação
  de rótulos ainda pendente — hoje a Silver só seleciona/limpa, mantém os
  códigos numéricos). Os 4 identificadores servem só para deduplicar.
- **Gold (RF-03)**: aplicar a regra de informalidade sobre `VD4009`/`V4019`
  filtrado por `VD4002`, gerando a coluna-alvo binária.
- **EDA (RF-04)**: cruzar a taxa de informalidade com sexo, raça, região,
  escolaridade, setor, grupamento ocupacional, tamanho do negócio, tempo no
  emprego e posição no domicílio; mostrar o gap de `VD4016`/`VD4017` como
  contexto (não como feature).
- **Modelo (RF-05/RF-06)**: features = demográficas + domicílio + educação +
  região + setor + ocupação + tamanho do negócio + temporário + tempo no
  emprego + horas trabalhadas; alvo = informalidade; SHAP recortado por
  `V2007`/`V2010` para a análise de equidade (RNF-11).
