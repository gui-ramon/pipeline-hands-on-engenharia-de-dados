# -*- coding: utf-8 -*-
"""Gera apresentacao/Roteiro de Apresentacao.docx — roteiro completo da fala,
formatado em padrao ABNT (NBR 14724: margens 3-2-3-2 cm, Times New Roman 12,
espacamento 1,5, capa, sumario, secoes numeradas, referencias).

Conteudo: script de fala continua (storytelling, nao passo a passo tecnico),
alinhado 1:1 aos 12 slides do InformalidadeBR - Apresentacao.pptx, mais um
roteiro de perguntas e respostas antecipadas e um checklist de ensaio.
"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

RAIZ = Path(__file__).resolve().parents[2]
SAIDA = RAIZ / "apresentacao" / "Roteiro de Apresentacao.docx"

VERMELHO = RGBColor(0xB5, 0x00, 0x20)
PRETO = RGBColor(0x00, 0x00, 0x00)

INTEGRANTES = [
    "Jefferson Aparecido Nunes Lopes",
    "Guilherme Ramon Santos Camargo",
    "Bruno Roberto Muniz Cabral",
]

doc = Document()

# forca o Word a recalcular campos (TOC, PAGE) automaticamente ao abrir
settings_element = doc.settings.element
update_fields = OxmlElement("w:updateFields")
update_fields.set(qn("w:val"), "true")
settings_element.append(update_fields)

# --------------------------------------------------------------- pagina/estilo
secao = doc.sections[0]
secao.page_width = Cm(21.0)
secao.page_height = Cm(29.7)
secao.top_margin = Cm(3)
secao.left_margin = Cm(3)
secao.bottom_margin = Cm(2)
secao.right_margin = Cm(2)

estilo_normal = doc.styles["Normal"]
estilo_normal.font.name = "Times New Roman"
estilo_normal.font.size = Pt(12)
estilo_normal.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
estilo_normal.paragraph_format.space_after = Pt(0)
rpr = estilo_normal.element.get_or_add_rPr()
rFonts = rpr.find(qn("w:rFonts"))
if rFonts is None:
    rFonts = OxmlElement("w:rFonts")
    rpr.append(rFonts)
rFonts.set(qn("w:eastAsia"), "Times New Roman")


def numero_pagina_no_rodape(secao):
    footer = secao.footer
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    fld1 = OxmlElement("w:fldChar")
    fld1.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = "PAGE"
    fld2 = OxmlElement("w:fldChar")
    fld2.set(qn("w:fldCharType"), "end")
    run._r.append(fld1)
    run._r.append(instr)
    run._r.append(fld2)
    run.font.name = "Times New Roman"
    run.font.size = Pt(10)


def paragrafo(texto, tamanho=12, negrito=False, italico=False, alinhamento=WD_ALIGN_PARAGRAPH.JUSTIFY,
              espacamento_antes=0, espacamento_depois=0, recuo_primeira_linha=None, cor=None,
              espacamento_linha=WD_LINE_SPACING.ONE_POINT_FIVE):
    p = doc.add_paragraph()
    p.alignment = alinhamento
    p.paragraph_format.line_spacing_rule = espacamento_linha
    p.paragraph_format.space_before = Pt(espacamento_antes)
    p.paragraph_format.space_after = Pt(espacamento_depois)
    if recuo_primeira_linha is not None:
        p.paragraph_format.first_line_indent = Cm(recuo_primeira_linha)
    run = p.add_run(texto)
    run.font.name = "Times New Roman"
    run.font.size = Pt(tamanho)
    run.bold = negrito
    run.italic = italico
    if cor:
        run.font.color.rgb = cor
    return p


def titulo1(numero, texto_titulo):
    texto_final = f"{numero} {texto_titulo}" if numero else texto_titulo
    p = doc.add_paragraph(texto_final.upper(), style="Heading 1")
    p.paragraph_format.space_before = Pt(24)
    p.paragraph_format.space_after = Pt(12)
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
    p.paragraph_format.keep_with_next = True
    for run in p.runs:
        run.font.name = "Times New Roman"
        run.font.size = Pt(13)
        run.bold = True
        run.font.color.rgb = PRETO
    return p


def titulo2(numero, texto_titulo):
    p = doc.add_paragraph(f"{numero} {texto_titulo}", style="Heading 2")
    p.paragraph_format.space_before = Pt(16)
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
    p.paragraph_format.keep_with_next = True
    for run in p.runs:
        run.font.name = "Times New Roman"
        run.font.size = Pt(12)
        run.bold = True
        run.font.color.rgb = PRETO
    return p


def bloco_cabecalho(slide_num, titulo_slide, tempo):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
    p.paragraph_format.keep_with_next = True
    run = p.add_run(f"SLIDE {slide_num:02d} · {titulo_slide.upper()}")
    run.font.name = "Times New Roman"
    run.font.size = Pt(11.5)
    run.bold = True
    run.font.color.rgb = VERMELHO
    run2 = p.add_run(f"   (~{tempo})")
    run2.font.name = "Times New Roman"
    run2.font.size = Pt(11)
    run2.italic = True


def fala(texto):
    paragrafo(texto, tamanho=12, recuo_primeira_linha=1.25, espacamento_depois=8)


def nota(texto):
    paragrafo(texto, tamanho=11, italico=True, cor=RGBColor(0x55, 0x55, 0x55),
              espacamento_depois=10, espacamento_linha=WD_LINE_SPACING.SINGLE)


def quebrar_pagina():
    doc.add_page_break()


# ======================================================================
# CAPA
# ======================================================================
for _ in range(2):
    doc.add_paragraph()
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p.add_run("UNIVERSIDADE PRESBITERIANA MACKENZIE")
run.font.name = "Times New Roman"
run.font.size = Pt(12)
run.bold = True
p2 = doc.add_paragraph()
p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p2.add_run("Pós-Graduação em Engenharia de Dados")
run.font.name = "Times New Roman"
run.font.size = Pt(12)

for _ in range(5):
    doc.add_paragraph()

p3 = doc.add_paragraph()
p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p3.add_run("INFORMALIDADEBR")
run.font.name = "Times New Roman"
run.font.size = Pt(16)
run.bold = True
p4 = doc.add_paragraph()
p4.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p4.add_run("Predição de trabalho informal a partir da PNAD Contínua:")
run.font.name = "Times New Roman"
run.font.size = Pt(13)
p4b = doc.add_paragraph()
p4b.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p4b.add_run("roteiro de apresentação")
run.font.name = "Times New Roman"
run.font.size = Pt(13)

for _ in range(5):
    doc.add_paragraph()

p5 = doc.add_paragraph()
p5.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p5.add_run("Integrantes:")
run.font.name = "Times New Roman"
run.font.size = Pt(12)
run.bold = True
for nome in INTEGRANTES:
    px = doc.add_paragraph()
    px.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = px.add_run(nome)
    run.font.name = "Times New Roman"
    run.font.size = Pt(12)

for _ in range(6):
    doc.add_paragraph()

p6 = doc.add_paragraph()
p6.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p6.add_run("São Paulo")
run.font.name = "Times New Roman"
run.font.size = Pt(12)
p7 = doc.add_paragraph()
p7.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p7.add_run("2026")
run.font.name = "Times New Roman"
run.font.size = Pt(12)

# secao 2: a partir daqui, numeracao de pagina no rodape (capa nao numera)
secao2 = doc.add_section(WD_SECTION.NEW_PAGE)
secao2.top_margin = Cm(3)
secao2.left_margin = Cm(3)
secao2.bottom_margin = Cm(2)
secao2.right_margin = Cm(2)
secao2.footer.is_linked_to_previous = False
numero_pagina_no_rodape(secao2)

# ======================================================================
# SUMARIO (campo TOC automatico — atualizado no passo de exportacao/PDF)
# ======================================================================
p_sumario = doc.add_paragraph()
p_sumario.paragraph_format.space_after = Pt(12)
p_sumario.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
run = p_sumario.add_run("SUMÁRIO")
run.font.name = "Times New Roman"
run.font.size = Pt(13)
run.bold = True


def inserir_campo_toc(paragrafo):
    run = paragrafo.add_run()
    run.font.name = "Times New Roman"
    run.font.size = Pt(12)
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = 'TOC \\o "1-2" \\h \\z \\u'
    fld_sep = OxmlElement("w:fldChar")
    fld_sep.set(qn("w:fldCharType"), "separate")
    texto_provisorio = OxmlElement("w:t")
    texto_provisorio.text = ("Sumário gerado automaticamente ao abrir/salvar "
                              "este documento no Word (Referências > Atualizar Sumário).")
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run._r.append(fld_begin)
    run._r.append(instr)
    run._r.append(fld_sep)
    run._r.append(texto_provisorio)
    run._r.append(fld_end)


p_toc = doc.add_paragraph()
p_toc.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
inserir_campo_toc(p_toc)

quebrar_pagina()

# ======================================================================
# 1 INTRODUCAO
# ======================================================================
titulo1("1", "Introdução")
fala(
    "Este documento é o roteiro de apoio à apresentação oral do projeto "
    "InformalidadeBR, desenvolvido para a disciplina de Engenharia de Dados "
    "da Pós-Graduação da Universidade Presbiteriana Mackenzie. O objetivo "
    "não é um script decorado palavra por palavra, e sim um guia de "
    "conteúdo e de tempo: o que dizer em cada slide, quanto tempo isso deve "
    "ocupar, e como conectar uma etapa à próxima sem que a apresentação "
    "vire uma lista de tarefas técnicas."
)
fala(
    "O fio condutor é uma história de negócio guiada por dados, não uma "
    "sequência de \"primeiro fizemos a coleta, depois o pré-processamento, "
    "depois a análise exploratória\". A estrutura segue, em vez disso, o "
    "movimento: tínhamos um problema → buscamos dados → tratamos e "
    "entendemos os dados → construímos uma solução → avaliamos os "
    "resultados → geramos valor."
)

# ======================================================================
# 2 FORMATO
# ======================================================================
titulo1("2", "Formato da apresentação e divisão de tempo")
fala(
    "A apresentação ocorre na Sala Mack Graphe, com 10 minutos de "
    "exposição por grupo, seguidos de 10 minutos de perguntas e respostas. "
    "O deck (InformalidadeBR - Apresentacao.pptx) tem 12 slides, "
    "organizados em quatro blocos de tempo:"
)
tabela = doc.add_table(rows=1, cols=3)
tabela.style = "Light Grid Accent 1"
hdr = tabela.rows[0].cells
hdr[0].text = "Bloco"
hdr[1].text = "Slides"
hdr[2].text = "Tempo"
linhas_tabela = [
    ("1. Introdução e problema", "1 – 3", "2 min"),
    ("2. Dados e preparação", "4 – 6", "3 min"),
    ("3. Modelagem e solução", "7 – 9", "3 min"),
    ("4. Resultados e conclusão", "10 – 12", "2 min"),
]
for bloco, slides, tempo in linhas_tabela:
    row = tabela.add_row().cells
    row[0].text = bloco
    row[1].text = slides
    row[2].text = tempo
for row in tabela.rows:
    for cell in row.cells:
        for p in cell.paragraphs:
            p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
            for run in p.runs:
                run.font.name = "Times New Roman"
                run.font.size = Pt(11)
doc.add_paragraph()
fala(
    "A divisão entre os três integrantes (quem fala qual bloco) fica a "
    "critério do grupo. Este roteiro traz o conteúdo completo da fala, "
    "não a atribuição por pessoa."
)
nota(
    "Dica de ensaio: cada bloco tem uma margem apertada. Ensaiar com "
    "cronômetro por bloco, não só a apresentação inteira, ajuda a notar "
    "onde o tempo está sendo perdido."
)

quebrar_pagina()

# ======================================================================
# 3 ROTEIRO DA FALA
# ======================================================================
titulo1("3", "Roteiro da fala")
fala(
    "A seguir, o conteúdo falado para cada um dos 12 slides, organizado "
    "nos quatro blocos de tempo. O texto é uma referência de conteúdo e "
    "tom, não precisa ser reproduzido literalmente, mas cada bloco cobre "
    "exatamente o que o slide correspondente mostra, para que fala e "
    "imagem nunca se desconectem."
)

# ---------------------------------------------------------- BLOCO 1
titulo2("3.1", "Bloco 1: Introdução e problema (2 min)")

bloco_cabecalho(1, "Abertura", "30 s")
fala(
    "Boa tarde a todos. Nosso projeto se chama InformalidadeBR e parte de "
    "uma pergunta simples de fazer e difícil de responder: dá para prever, "
    "a partir de dados públicos, se um trabalhador brasileiro está na "
    "informalidade? Somos Jefferson Lopes, Guilherme Camargo e Bruno "
    "Cabral, e vamos contar como saímos de uma pergunta até um modelo "
    "capaz de responder isso com mais de 90% de capacidade de separar "
    "quem está e quem não está na informalidade."
)

bloco_cabecalho(2, "O Problema", "50 s")
fala(
    "Começamos pelo problema, porque é ele que justifica tudo o que vem "
    "depois. Na PNAD Contínua de 2023 a 2025, olhando 2,52 milhões de "
    "trabalhadores ocupados, 47,6% estão na informalidade: sem carteira "
    "assinada, sem CNPJ, sem contribuição ao INSS. Isso não é uma minoria "
    "marginal: é quase metade do mercado de trabalho brasileiro. E o "
    "custo disso é concreto, sem acesso a crédito, sem proteção "
    "trabalhista, sem previdência. E o mais importante para o nosso "
    "projeto: essa informalidade não se distribui ao acaso. Ela se "
    "concentra por setor, por região, por gênero, por raça. Um problema "
    "desse tamanho, com esse padrão, é exatamente o tipo de problema que "
    "dado consegue enxergar."
)

bloco_cabecalho(3, "Objetivo do Projeto", "40 s")
fala(
    "Isso nos levou a uma pergunta central: dá para prever quem está na "
    "informalidade e enxergar quem ela mais afeta? A partir dela, "
    "definimos três objetivos. Primeiro, prever a condição de "
    "informalidade a partir de características observáveis do "
    "trabalhador. Segundo, explicar quais fatores mais pesam nessa "
    "condição, não só prever, mas entender o porquê. E terceiro, medir "
    "se o modelo trata todos os grupos de forma equilibrada, porque um "
    "modelo que erra mais para um grupo específico reproduz a própria "
    "desigualdade que estamos tentando entender."
)

# ---------------------------------------------------------- BLOCO 2
titulo2("3.2", "Bloco 2: Dados e preparação (3 min)")

bloco_cabecalho(4, "Os Dados", "60 s")
fala(
    "Para responder isso, buscamos a fonte mais robusta disponível: a "
    "PNAD Contínua, a maior pesquisa domiciliar do Brasil, direto do "
    "IBGE. Usamos 12 trimestres, de 2023 a 2025, cerca de 500 mil "
    "registros por trimestre. Das quase 420 variáveis disponíveis, "
    "selecionamos 22 por relevância direta ao problema. Evitamos "
    "\"pegar tudo\" só porque estava disponível. É uma fonte pública "
    "única, mas isso não significa dado bruto confiável por padrão: cada "
    "período baixado passa por retentativa automática e é validado por "
    "um manifesto com checksum e contagem de linhas, para detectar "
    "corrupção ou incompletude antes de qualquer análise."
)

bloco_cabecalho(5, "Pré-processamento", "60 s")
fala(
    "Dado bruto não é dado utilizável. Organizamos o pipeline em três "
    "camadas. A camada Bronze guarda os microdados exatamente como o "
    "IBGE publica, sem nenhuma transformação: é o nosso registro de "
    "verdade. A camada Silver decodifica os códigos em categorias "
    "legíveis, trata valores nulos e consolida os 12 trimestres em "
    "5.748.375 linhas, e aqui vale destacar que zero linhas foram "
    "perdidas nessa reconciliação, o que validamos formalmente. A camada "
    "Gold aplica um único filtro, manter só quem está ocupado, e isso já "
    "derruba a base de 5,7 milhões para 2.522.338 pessoas: 43,9% do "
    "total. Não é perda de qualidade, é escopo: para quem não está "
    "ocupado, \"informalidade\" nem é um conceito que se aplica."
)
fala(
    "E o que conta como informal, exatamente? Não é intuição nossa: "
    "seguimos a mesma regra que o IBGE usa em estudos oficiais, baseada "
    "na posição na ocupação. Sem carteira assinada, no setor privado, "
    "doméstico ou público; trabalhador familiar sem remuneração; ou "
    "empregador e conta-própria sem CNPJ. Aplicando essa regra sobre os "
    "2.522.338 ocupados, chegamos aos 47,6% de informalidade que abriram "
    "esta apresentação."
)

bloco_cabecalho(6, "Análise Exploratória", "60 s")
fala(
    "Antes de treinar qualquer modelo, deixamos os dados falarem. Medimos "
    "a força de associação de cada variável candidata com a "
    "informalidade, V de Cramér para categóricas, correlação "
    "ponto-bisserial para numéricas. E dois achados lideraram claramente: "
    "tamanho do negócio, com associação de 0,570, e ter vínculo "
    "temporário, com 0,460. Setor de atividade, grupamento ocupacional e "
    "nível de instrução vêm na sequência. Esses números guiaram "
    "diretamente a escolha das features e, como vamos ver a seguir, "
    "também a escolha do algoritmo."
)
fala(
    "Mas o boletim de análise exploratória mostra mais que correlação: "
    "mostra quem é esse trabalhador. Entre os informais, 53% não "
    "concluíram o ensino médio, contra 25% entre os formais. 35% moram "
    "no Nordeste, contra 20% entre os formais. E a renda mediana é 42% "
    "menor: 1.400 reais contra 2.400 reais. Esses três números não "
    "entraram no modelo como feature, renda é consequência da "
    "informalidade, não causa, mas ajudam a enxergar o perfil por trás "
    "da estatística."
)
fala(
    "Essa escolha de variáveis foi, sem dúvida, a decisão mais difícil do "
    "projeto, em duas etapas. Primeiro, no pré-processamento: das quase "
    "420 variáveis da PNAD, selecionamos 22 por relevância direta ao "
    "problema, para não carregar ruído para a Silver. Depois, na "
    "modelagem: dessas 22, 15 seguiram como feature. Duas delas, sexo e "
    "raça, entraram não pela força estatística, que é baixa, mas porque "
    "expor desigualdade nesses dois eixos é um objetivo declarado do "
    "projeto, não um efeito colateral."
)

# ---------------------------------------------------------- BLOCO 3
titulo2("3.3", "Bloco 3: Modelagem e solução (3 min)")

bloco_cabecalho(7, "A Solução", "50 s")
fala(
    "Todo esse trabalho está organizado em um pipeline completo, com "
    "seis etapas conectadas: ingestão, pré-processamento, transformação, "
    "análise exploratória, modelagem e interpretação. Cada etapa é uma "
    "classe própria em Python, orientada a uma interface comum, "
    "executável isoladamente ou em cadeia. Usamos pandas para "
    "manipulação de dados, scikit-learn para os modelos, e SHAP para "
    "interpretabilidade. Nada exótico, ferramentas maduras, mas "
    "organizadas de um jeito que torna o projeto inteiro reprodutível do "
    "início ao fim."
)

bloco_cabecalho(8, "Construção do Modelo", "70 s")
fala(
    "Para a predição em si, treinamos três modelos. Regressão Logística, "
    "como baseline interpretável: se um modelo bem mais complexo não "
    "superasse essa baseline por uma margem clara, não valeria a pena "
    "perder interpretabilidade. Random Forest, robusto, com o custo "
    "computacional controlado para não estourar memória em milhões de "
    "linhas. E HistGradientBoosting, escolhido porque lida nativamente "
    "com variável categórica e com valor nulo, e não é coincidência: as "
    "duas features mais fortes que vimos na análise exploratória têm 20% "
    "e 40% de valores nulos. Um ponto que não abrimos mão em nenhum dos "
    "três modelos: o split é temporal, não aleatório. Treinamos com "
    "2023 e 2024, testamos só com 2025. A PNAD é um painel rotativo, a "
    "mesma pessoa aparece em trimestres seguidos, então um split "
    "aleatório vazaria a mesma pessoa entre treino e teste e infl"
    "aria os resultados de forma artificial."
)

bloco_cabecalho(9, "O que o Modelo Aprendeu (Interpretabilidade e Equidade)", "60 s")
fala(
    "Um modelo que não conseguimos explicar não serve para um problema "
    "social como este. Usamos SHAP para abrir a caixa do modelo campeão, "
    "e os fatores que mais pesaram na decisão foram exatamente os mesmos "
    "que a análise exploratória já apontava: vínculo temporário e "
    "tamanho do negócio na frente, seguidos de horas semanais. Isso é uma "
    "validação cruzada informal: o modelo aprendeu o mesmo padrão que os "
    "dados já mostravam antes de qualquer treino. Mas essa mesma análise "
    "expôs algo que não estava óbvio de início: o recall para o grupo "
    "\"Amarelos\" caiu de 84% geral para 72%, uma diferença de 12 pontos "
    "percentuais, com uma amostra de mais de 4 mil pessoas, então não é "
    "ruído estatístico. Registramos isso como um sinal de atenção real no "
    "nosso Model Card. Não é motivo para descartar o modelo, mas é "
    "exatamente o tipo de coisa que só aparece quando você olha além da "
    "métrica geral."
)

# ---------------------------------------------------------- BLOCO 4
titulo2("3.4", "Bloco 4: Resultados e conclusão (2 min)")

bloco_cabecalho(10, "Resultados Obtidos", "50 s")
fala(
    "Este é o slide mais importante da nossa apresentação: a tabela "
    "completa dos três modelos, a mesma que está no boletim de "
    "modelagem. AUC-ROC é a métrica que mais importa aqui: numa escala "
    "de 0 a 1, ela mede a chance de o modelo dar uma nota de risco maior "
    "a um trabalhador informal do que a um formal, sorteando um "
    "aleatoriamente de cada. 0,5 é chute puro, 1,0 é perfeito. No ano "
    "de 2025, que nenhum dos três modelos viu durante o treino, o "
    "HistGradientBoosting atingiu 92,6% de AUC-ROC, acurácia de 84,7%, "
    "precisão de 83,8%, recall de 83,6%. Traduzindo para o negócio: de "
    "cada 100 trabalhadores informais reais no teste, o modelo identifica "
    "corretamente 84, com a mesma performance em treino e em "
    "teste, sem overfitting relevante."
)
fala(
    "E a última coluna da tabela é a que menos aparece nesse tipo de "
    "apresentação, mas que pesou de verdade na nossa decisão: tempo de "
    "treino. O HistGradientBoosting não é só o mais preciso, é também o "
    "mais rápido dos dois modelos fortes, 179 segundos contra 2.172 "
    "segundos do Random Forest, mais de 36 minutos. Doze vezes mais "
    "lento por um ganho de apenas 0,9 ponto de AUC. Isso importa porque "
    "tempo de treino é custo de engenharia: quanto mais rápido, mais "
    "vezes dá para retreinar, ajustar hiperparâmetro e comparar. Se "
    "interpretabilidade importar mais que esse último ponto percentual "
    "de desempenho, o Random Forest segue como alternativa real; mas em "
    "precisão e em velocidade, o HistGradientBoosting venceu nos dois "
    "eixos."
)

bloco_cabecalho(11, "Conclusões, Limitações e Próximos Passos", "40 s")
fala(
    "Em resumo: funcionou, e mostrou exatamente onde melhorar. "
    "Construímos um pipeline reprodutível de ponta a ponta, um modelo com "
    "bom poder preditivo e interpretabilidade real, não uma caixa-preta. "
    "As limitações também são claras: a disparidade de recall no grupo "
    "Amarelos precisa de tratamento, reponderação no treino ou um "
    "threshold específico por grupo. O peso amostral complexo da PNAD "
    "ainda não entrou na avaliação, e fica como próximo passo natural, "
    "assim como monitorar novas safras trimestrais à medida que o IBGE "
    "publica."
)

bloco_cabecalho(12, "Conclusão Geral e Encerramento", "10 s")
fala(
    "Para fechar, duas frases. Sobre o tema: a informalidade não é um "
    "detalhe estatístico, é quase metade do mercado de trabalho "
    "brasileiro, distribuída de forma desigual entre região, setor e "
    "cor. Sobre o projeto: entregamos mais que um modelo, um pipeline "
    "completo, do dado bruto do IBGE até uma predição interpretável, "
    "reprodutível do início ao fim. Muito obrigado. Ficamos à "
    "disposição para perguntas."
)

quebrar_pagina()

# ======================================================================
# 4 PERGUNTAS E RESPOSTAS ANTECIPADAS
# ======================================================================
titulo1("4", "Perguntas e respostas antecipadas")
fala(
    "Os 10 minutos de perguntas e respostas costumam mirar exatamente nos "
    "pontos que a apresentação resume em uma frase. As perguntas abaixo "
    "foram antecipadas a partir das decisões técnicas documentadas no "
    "projeto. A resposta de cada uma já existe na documentação, não "
    "precisa ser inventada na hora."
)

perguntas = [
    (
        "Por que renda não foi usada como variável preditiva, já que é um "
        "indicador óbvio de informalidade?",
        "Porque é vazamento circular: renda está fortemente correlacionada "
        "com a própria condição de informalidade, então usá-la como "
        "feature infla a métrica artificialmente e destrói a "
        "interpretabilidade que o projeto se propõe a entregar. Ela foi "
        "mantida apenas para um gráfico de apoio na análise exploratória "
        "(gap salarial entre formal e informal), nunca como entrada do "
        "classificador.",
    ),
    (
        "Por que HistGradientBoosting e não XGBoost ou LightGBM, que são "
        "mais populares?",
        "Decisão consciente de não adicionar uma dependência nova ao "
        "projeto sem necessidade comprovada. O HistGradientBoosting do "
        "próprio scikit-learn já resolve os dois problemas concretos que "
        "tínhamos: suporte nativo a variável categórica de alta "
        "cardinalidade (UF, setor) e a valor nulo nas duas features mais "
        "fortes. XGBoost e LightGBM ficam como upgrade futuro possível, "
        "não descartados por mérito técnico.",
    ),
    (
        "Como garantiram que não houve vazamento de dado (data leakage) "
        "entre a definição do alvo e as features usadas para prevê-lo?",
        "As variáveis usadas para construir a própria variável-alvo "
        "`informal` na camada Gold, como VD4009, V4019, VD4012 e VD4002, "
        "foram explicitamente excluídas da lista de features. Incluí-"
        "las faria o modelo aprender a copiar a definição do alvo, não a "
        "prever a partir de características reais do trabalhador.",
    ),
    (
        "O que explica a queda de recall no grupo \"Amarelos\"?",
        "Ainda não temos uma causa raiz confirmada. É um achado do "
        "diagnóstico automático, não uma conclusão fechada. As hipóteses "
        "mais prováveis são menor representatividade do grupo na amostra "
        "de treino e possível diferença na distribuição das features mais "
        "fortes (tamanho do negócio, vínculo temporário) dentro desse "
        "grupo. É por isso que virou explicitamente um próximo passo: "
        "investigar antes de propor uma correção.",
    ),
    (
        "Os dados são representativos da população brasileira?",
        "A PNAD Contínua é uma amostra complexa, estratificada, por "
        "conglomerados, não uma amostra aleatória simples. Estatísticas "
        "descritivas exigem ponderação pelo peso amostral (V1028) para "
        "representar a população corretamente. Nosso projeto ainda não "
        "incorpora esse peso na avaliação do modelo; é uma limitação "
        "conhecida e registrada como próximo passo.",
    ),
    (
        "Esse modelo poderia ser usado para decisões automatizadas sobre "
        "pessoas específicas?",
        "Não é essa a proposta. Os microdados do IBGE são anonimizados, "
        "sem identificação direta, e o objetivo do projeto é diagnóstico "
        "agregado: entender fatores e desigualdades estruturais, não "
        "rotular ou tomar decisão sobre um indivíduo. A própria análise "
        "de equidade por SHAP existe para expor onde o modelo trata "
        "grupos de forma diferente, não para justificar uso individual.",
    ),
    (
        "Por que 15 features e não todas as variáveis disponíveis?",
        "Cada uma das 15 features tem uma justificativa registrada: força "
        "de associação medida na análise exploratória, ou inclusão "
        "obrigatória por escopo do projeto (sexo e raça, mesmo com "
        "associação individual fraca, porque expor desigualdade nesses "
        "eixos é objetivo declarado do RF-06). Variáveis com associação "
        "praticamente nula, como frequenta escola, foram excluídas "
        "deliberadamente para não introduzir ruído.",
    ),
    (
        "Se tivessem mais tempo, qual seria o próximo passo?",
        "Três, em ordem de prioridade: tratar a disparidade de equidade "
        "encontrada (reponderação ou threshold por grupo), incorporar o "
        "peso amostral da PNAD na avaliação, e criar um processo de "
        "monitoramento contínuo à medida que o IBGE publica novos "
        "trimestres. Hoje o pipeline roda sob demanda, não em produção.",
    ),
]

for pergunta, resposta in perguntas:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    run = p.add_run("P: ")
    run.bold = True
    run.font.name = "Times New Roman"
    run.font.size = Pt(12)
    run2 = p.add_run(pergunta)
    run2.italic = True
    run2.font.name = "Times New Roman"
    run2.font.size = Pt(12)
    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p2.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    p2.paragraph_format.space_after = Pt(6)
    run3 = p2.add_run("R: ")
    run3.bold = True
    run3.font.name = "Times New Roman"
    run3.font.size = Pt(12)
    run4 = p2.add_run(resposta)
    run4.font.name = "Times New Roman"
    run4.font.size = Pt(12)

quebrar_pagina()

# ======================================================================
# 5 SLIDES DE APOIO (MATERIAL OCULTO)
# ======================================================================
titulo1("5", "Slides de apoio (material oculto)")
fala(
    "O arquivo InformalidadeBR - Apresentacao.pptx tem 16 slides no "
    "total: os 12 numerados acima, que contam a história em 10 minutos, "
    "e mais 4 marcados como \"ocultos\" no PowerPoint. Eles não aparecem "
    "ao apertar F5 e avançar normalmente. Para abri-los, basta clicar no "
    "círculo preto com \"+\" que aparece nos slides 5 (dois círculos), 6 "
    "e 10. O clique pula direto para o slide de apoio correspondente, "
    "mesmo durante a apresentação. Cada slide de apoio tem um ícone de "
    "casinha no canto superior esquerdo, que retorna exatamente para "
    "onde a apresentação estava antes do clique. (Alternativa manual, "
    "se algum botão falhar: clique direito → Ver Todos os Slides, ou "
    "digite o número do slide e Enter.) Servem para aprofundar uma "
    "resposta na rodada de perguntas sem atropelar o tempo da "
    "apresentação principal."
)
apoio_slides = [
    ("Slide 13: O funil completo dos dados",
     "Detalha Bronze (12 arquivos, cerca de 19 GB), Silver (5.748.375 "
     "linhas) e Gold (2.522.338 ocupados, 43,9% de retenção), com a "
     "composição completa de quem fica de fora (menores de 14, fora da "
     "força de trabalho, desocupados) e um achado extra: mulheres são "
     "64% do grupo fora da força de trabalho e 53% dos desocupados "
     "buscando emprego, contra 43% entre os ocupados. Puxar se "
     "perguntarem sobre volume de dados ou quem fica fora do filtro."),
    ("Slide 14: A regra completa de informalidade",
     "Tabela com as 10 categorias de VD4009 e a classificação formal/"
     "informal de cada uma, incluindo o desempate por V4019 (CNPJ) e a "
     "alternativa mais simples (VD4012) que foi considerada e descartada. "
     "Puxar se perguntarem exatamente como \"informal\" foi definido."),
    ("Slide 15: Por que essas 15 features",
     "As 15 features com a força de associação de cada uma, mais a lista "
     "do que foi excluído e por quê (vazamento de dado, associação "
     "quase nula, chaves de deduplicação). Puxar se perguntarem sobre "
     "uma variável específica que não apareceu, ou sobre a decisão de "
     "features em geral."),
    ("Slide 16: Matrizes de confusão dos 3 modelos",
     "Os números completos de acerto e erro por modelo no teste de 2025 "
     "(864.940 pessoas), com destaque para o custo do falso negativo. "
     "Puxar se perguntarem sobre onde exatamente o modelo erra."),
]
for titulo_apoio, corpo_apoio in apoio_slides:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
    run = p.add_run(titulo_apoio)
    run.bold = True
    run.font.name = "Times New Roman"
    run.font.size = Pt(12)
    paragrafo(corpo_apoio, tamanho=12, espacamento_depois=4)

quebrar_pagina()

# ======================================================================
# 6 CHECKLIST DE ENSAIO
# ======================================================================
titulo1("6", "Checklist de ensaio")
fala(
    "Itens práticos para revisar antes do dia da apresentação, com base "
    "nas armadilhas mais comuns desse tipo de apresentação:"
)
checklist = [
    "Ensaiar com cronômetro por bloco (2-3-3-2 min), não só o tempo total. "
    "É onde o estouro de tempo costuma se esconder.",
    "Cada gráfico deve vir acompanhado da pergunta que ele responde em "
    "voz alta (\"o que aprendemos com isso?\"). Nunca mostrar um gráfico "
    "sem interpretá-lo.",
    "Evitar reproduzir código ou termos técnicos sem tradução (AUC-ROC, "
    "SHAP, overfitting), sempre seguidos de uma explicação em uma frase.",
    "Não esconder a limitação de equidade do grupo Amarelos. Apresentá-"
    "la com confiança, como prova de rigor metodológico, não como falha.",
    "Praticar a transição entre blocos em voz alta, não só o conteúdo de "
    "cada slide. É onde a apresentação costuma soar fragmentada.",
    "Confirmar que os três integrantes concordam com a divisão de tempo "
    "e sabem em qual slide cada um assume a fala.",
    "Revisar as oito perguntas antecipadas (seção 4) na véspera, em voz "
    "alta, não só lendo.",
]
for item in checklist:
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    p.paragraph_format.space_after = Pt(4)
    for run in p.runs:
        run.font.name = "Times New Roman"
        run.font.size = Pt(12)
    if not p.runs:
        run = p.add_run(item)
        run.font.name = "Times New Roman"
        run.font.size = Pt(12)

quebrar_pagina()

# ======================================================================
# REFERENCIAS
# ======================================================================
titulo1("", "REFERÊNCIAS")
refs = [
    "INSTITUTO BRASILEIRO DE GEOGRAFIA E ESTATÍSTICA. Pesquisa Nacional "
    "por Amostra de Domicílios Contínua (PNAD Contínua): microdados "
    "trimestrais, 2023-2025. Rio de Janeiro: IBGE, 2025. Disponível em: "
    "https://ftp.ibge.gov.br/Trabalho_e_Rendimento/"
    "Pesquisa_Nacional_por_Amostra_de_Domicilios_continua/Trimestral/"
    "Microdados/. Acesso em: 2026.",
    "MITCHELL, Margaret et al. Model Cards for Model Reporting. In: "
    "CONFERENCE ON FAIRNESS, ACCOUNTABILITY, AND TRANSPARENCY (FAT*), "
    "2019, Atlanta. Proceedings [...]. New York: ACM, 2019.",
    "InformalidadeBR: repositório do projeto, documentação de "
    "requisitos, arquitetura e plano de modelagem. Disponível em: "
    "github.com/gui-ramon/pipeline-hands-on-engenharia-de-dados.",
]
for ref in refs:
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
    p.paragraph_format.space_after = Pt(12)
    p.paragraph_format.left_indent = Cm(0)
    run = p.add_run(ref)
    run.font.name = "Times New Roman"
    run.font.size = Pt(12)

SAIDA.parent.mkdir(parents=True, exist_ok=True)
doc.save(SAIDA)
print(f"[ok] {SAIDA}")
