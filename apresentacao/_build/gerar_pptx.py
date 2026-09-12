"""Gera apresentacao/InformalidadeBR - Apresentacao.pptx: 12 slides, storytelling
(problema -> dados -> analise -> modelo -> resultado -> valor), identidade
visual Mackenzie (vermelho #EB0029, Helvetica/Arial, fundo claro).

Nao usa nenhum template pronto de IA — layout construido do zero em
python-pptx: barra de destaque, kicker + headline, cards e diagramas nativos
(retangulos/setas), graficos reais embutidos como imagem (gerados por
gerar_graficos.py a partir dos artefatos oficiais da modelagem).
"""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.action import PP_ACTION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

RAIZ = Path(__file__).resolve().parents[2]
ASSETS_LOGO = RAIZ / "apresentacao" / "_assets_identidade" / "mck_png" / "MCK_PNG"
ASSETS_GRAFICOS = RAIZ / "apresentacao" / "_assets_graficos"
SAIDA = RAIZ / "apresentacao" / "InformalidadeBR - Apresentacao.pptx"

LOGO_VERMELHO_H = ASSETS_LOGO / "MCK_horizontal_vermelho.png"
LOGO_BRANCO_H = ASSETS_LOGO / "MCK_horizontal_branca-01.png"
LOGO_VERMELHO_V = ASSETS_LOGO / "MCK_vertical_vermelho-01.png"
LOGO_PRETO_H = ASSETS_LOGO / "MCK_horizontal_preto-01.png"

# ---------------------------------------------------------------- identidade
VERMELHO = RGBColor(0xEB, 0x00, 0x29)
VERMELHO_ESCURO = RGBColor(0xB5, 0x00, 0x20)
PRETO = RGBColor(0x1A, 0x1A, 0x1A)
CINZA = RGBColor(0x6E, 0x6E, 0x6E)
CINZA_CLARO = RGBColor(0xE7, 0xE7, 0xE7)
QUASE_BRANCO = RGBColor(0xFA, 0xF9, 0xF8)
BRANCO = RGBColor(0xFF, 0xFF, 0xFF)
ROSA_FUNDO = RGBColor(0xFC, 0xE9, 0xEB)

FONTE = "Arial"

EMU_POR_POL = 914400
LARGURA = Inches(13.333)
ALTURA = Inches(7.5)

INTEGRANTES = [
    "Jefferson Aparecido Nunes Lopes",
    "Guilherme Ramon Santos Camargo",
    "Bruno Roberto Muniz Cabral",
]

prs = Presentation()
prs.slide_width = LARGURA
prs.slide_height = ALTURA
LAYOUT_BRANCO = prs.slide_layouts[6]  # em branco


# --------------------------------------------------------------- utilidades
def nova_slide(cor_fundo=BRANCO):
    slide = prs.slides.add_slide(LAYOUT_BRANCO)
    fundo = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, LARGURA, ALTURA)
    fundo.fill.solid()
    fundo.fill.fore_color.rgb = cor_fundo
    fundo.line.fill.background()
    fundo.shadow.inherit = False
    _enviar_para_fundo(slide, fundo)
    return slide


def _enviar_para_fundo(slide, shape):
    spTree = slide.shapes._spTree
    spTree.remove(shape._element)
    spTree.insert(2, shape._element)


def sem_sombra(shape):
    shape.shadow.inherit = False


def retangulo(slide, x, y, w, h, cor, linha=False, cor_linha=None, arredondado=False):
    tipo = MSO_SHAPE.ROUNDED_RECTANGLE if arredondado else MSO_SHAPE.RECTANGLE
    forma = slide.shapes.add_shape(tipo, x, y, w, h)
    if arredondado:
        try:
            forma.adjustments[0] = 0.06
        except Exception:
            pass
    forma.fill.solid()
    forma.fill.fore_color.rgb = cor
    if linha:
        forma.line.color.rgb = cor_linha or cor
        forma.line.width = Pt(1)
    else:
        forma.line.fill.background()
    sem_sombra(forma)
    return forma


def texto(slide, x, y, w, h, corpo, tamanho=18, cor=PRETO, negrito=False,
          alinhamento=PP_ALIGN.LEFT, fonte=FONTE, espacamento=1.0,
          ancora=MSO_ANCHOR.TOP, maiusculas=False, espacamento_letras=None,
          wrap=True):
    caixa = slide.shapes.add_textbox(x, y, w, h)
    tf = caixa.text_frame
    tf.word_wrap = wrap
    tf.vertical_anchor = ancora
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    linhas = corpo if isinstance(corpo, list) else [corpo]
    for i, linha in enumerate(linhas):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = alinhamento
        p.line_spacing = espacamento
        run = p.add_run()
        run.text = linha.upper() if maiusculas else linha
        run.font.size = Pt(tamanho)
        run.font.bold = negrito
        run.font.name = fonte
        run.font.color.rgb = cor
        if espacamento_letras is not None:
            _definir_espacamento_letras(run, espacamento_letras)
    return caixa


def _definir_espacamento_letras(run, pontos):
    rPr = run._r.get_or_add_rPr()
    rPr.set("spc", str(int(pontos * 100)))


def kicker(slide, txt, cor=VERMELHO, x=Inches(0.75), y=Inches(0.55)):
    return texto(slide, x, y, Inches(9), Inches(0.4), txt, tamanho=13, cor=cor,
                 negrito=True, maiusculas=True, espacamento_letras=1.5, fonte=FONTE)


def headline(slide, txt, x=Inches(0.75), y=Inches(0.95), w=Inches(11.6), tamanho=30):
    return texto(slide, x, y, w, Inches(1.3), txt, tamanho=tamanho, cor=PRETO,
                 negrito=True, espacamento=1.02, fonte=FONTE)


def barra_lateral(slide, cor=VERMELHO):
    retangulo(slide, 0, 0, Inches(0.14), ALTURA, cor)


def logo(slide, variante="vermelho_h", x=None, y=Inches(0.5), largura=Inches(1.5)):
    caminho = {"vermelho_h": LOGO_VERMELHO_H, "branco_h": LOGO_BRANCO_H,
               "vermelho_v": LOGO_VERMELHO_V, "preto_h": LOGO_PRETO_H}[variante]
    if x is None:
        x = LARGURA - largura - Inches(0.6)
    slide.shapes.add_picture(str(caminho), x, y, width=largura)


def rodape(slide, numero, cor=CINZA, cor_fundo_clara=True):
    texto(slide, Inches(0.75), ALTURA - Inches(0.55), Inches(3), Inches(0.35),
          "InformalidadeBR", tamanho=9.5, cor=cor, fonte=FONTE, negrito=True,
          espacamento_letras=0.8)
    texto(slide, LARGURA - Inches(1.4), ALTURA - Inches(0.55), Inches(0.8), Inches(0.35),
          f"{numero:02d} / 12", tamanho=9.5, cor=cor, alinhamento=PP_ALIGN.RIGHT, fonte=FONTE)


def imagem_centrada(slide, caminho, x, y, w=None, h=None):
    return slide.shapes.add_picture(str(caminho), x, y, width=w, height=h)


def cabecalho_padrao(slide, num, kicker_txt, titulo_txt, tam_titulo=29, w_titulo=Inches(11.6)):
    barra_lateral(slide)
    logo(slide, "vermelho_h", largura=Inches(1.35))
    kicker(slide, kicker_txt)
    headline(slide, titulo_txt, tamanho=tam_titulo, w=w_titulo)
    rodape(slide, num)


def marcar_oculto(slide):
    """Marca o slide como oculto no modo apresentacao (F5 pula, mas fica
    acessivel via 'ver todos os slides' ou numero+Enter) — material de apoio
    para perguntas, fora dos 10 min cronometrados."""
    slide._element.set("show", "0")


def cabecalho_apoio(slide, kicker_txt, titulo_txt, tam_titulo=27, w_titulo=Inches(11.6)):
    barra_lateral(slide, cor=CINZA)
    logo(slide, "preto_h", largura=Inches(1.35))
    kicker(slide, f"MATERIAL DE APOIO · {kicker_txt}", cor=CINZA, y=Inches(0.55))
    headline(slide, titulo_txt, tamanho=tam_titulo, y=Inches(0.95), w=w_titulo)
    texto(slide, Inches(0.75), ALTURA - Inches(0.55), Inches(6), Inches(0.35),
          "InformalidadeBR: apoio para perguntas (fora dos 10 min)", tamanho=9.5, cor=CINZA,
          fonte=FONTE)


def card(slide, x, y, w, h, titulo_txt, corpo_txt, cor_titulo=VERMELHO, cor_fundo=QUASE_BRANCO,
          tam_titulo=15, tam_corpo=13):
    retangulo(slide, x, y, w, h, cor_fundo, arredondado=True)
    retangulo(slide, x, y, Inches(0.06), h, cor_titulo)
    texto(slide, x + Inches(0.28), y + Inches(0.22), w - Inches(0.5), Inches(0.5),
          titulo_txt, tamanho=tam_titulo, cor=PRETO, negrito=True, fonte=FONTE, espacamento=1.05)
    texto(slide, x + Inches(0.28), y + Inches(0.7), w - Inches(0.5), h - Inches(0.9),
          corpo_txt, tamanho=tam_corpo, cor=CINZA, fonte=FONTE, espacamento=1.15)


def seta_horizontal(slide, x, y, w, h=Inches(0.5), cor=VERMELHO):
    seta = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, x, y, w, h)
    seta.fill.solid()
    seta.fill.fore_color.rgb = cor
    seta.line.fill.background()
    sem_sombra(seta)
    try:
        seta.adjustments[0] = 0.55
        seta.adjustments[1] = 0.35
    except Exception:
        pass
    return seta


def etapa_pipeline(slide, x, y, w, h, numero, titulo_txt, cor=PRETO, cor_fundo=QUASE_BRANCO):
    retangulo(slide, x, y, w, h, cor_fundo, arredondado=True)
    cor_numero = BRANCO if cor_fundo == VERMELHO else VERMELHO
    texto(slide, x, y + Inches(0.16), w, Inches(0.4), numero, tamanho=13, cor=cor_numero,
          negrito=True, alinhamento=PP_ALIGN.CENTER, fonte=FONTE)
    texto(slide, x + Inches(0.12), y + Inches(0.58), w - Inches(0.24), h - Inches(0.7),
          titulo_txt, tamanho=12.5, cor=cor, negrito=True, alinhamento=PP_ALIGN.CENTER,
          fonte=FONTE, espacamento=1.05)


def stat_grande(slide, x, y, w, valor, legenda, tam_valor=54, cor=VERMELHO, alinhamento=PP_ALIGN.LEFT,
                 espaco=Inches(1.4)):
    texto(slide, x, y, w, Inches(1.0), valor, tamanho=tam_valor, cor=cor, negrito=True,
          fonte=FONTE, alinhamento=alinhamento)
    texto(slide, x, y + espaco, w, Inches(0.8), legenda, tamanho=12.5, cor=CINZA,
          fonte=FONTE, espacamento=1.15, alinhamento=alinhamento)


def linha_divisoria(slide, x, y, w, cor=CINZA_CLARO):
    retangulo(slide, x, y, w, Pt(1.1), cor)


def botao_mais(slide, x, y, slide_alvo, diametro=Inches(0.4)):
    """Circulo '+' que pula para um slide oculto de apoio ao ser clicado
    durante a apresentacao (Slide Show) — o slide oculto continua fora da
    sequencia normal de avanco (F5/seta), so abre por este link ou por
    'Ver Todos os Slides'."""
    botao = slide.shapes.add_shape(MSO_SHAPE.OVAL, x, y, diametro, diametro)
    botao.fill.solid()
    botao.fill.fore_color.rgb = PRETO
    botao.line.fill.background()
    sem_sombra(botao)
    tf = botao.text_frame
    tf.word_wrap = False
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    run = p.add_run()
    run.text = "+"
    run.font.size = Pt(18)
    run.font.bold = True
    run.font.name = FONTE
    run.font.color.rgb = BRANCO
    botao.click_action.target_slide = slide_alvo
    return botao


def botao_casa(slide):
    """No slide oculto: uma 'casinha' no topo que volta para onde a
    apresentacao estava antes do clique no botao_mais (PP_ACTION acao
    'ultimo slide visto' funciona para qualquer slide de origem, sem
    fixar um alvo especifico)."""
    diametro = Inches(0.44)
    x, y = Inches(0.75), Inches(0.08)
    botao = slide.shapes.add_shape(MSO_SHAPE.OVAL, x, y, diametro, diametro)
    botao.fill.solid()
    botao.fill.fore_color.rgb = QUASE_BRANCO
    botao.line.color.rgb = CINZA_CLARO
    botao.line.width = Pt(1)
    sem_sombra(botao)

    # icone de casa desenhado em vetor (telhado + parede) — nao depende de
    # fonte de emoji, renderiza igual em qualquer maquina/versao do Office
    cx = x + diametro / 2
    cy = y + diametro / 2
    telhado = slide.shapes.add_shape(
        MSO_SHAPE.ISOSCELES_TRIANGLE, cx - Inches(0.12), cy - Inches(0.15), Inches(0.24), Inches(0.13)
    )
    telhado.fill.solid()
    telhado.fill.fore_color.rgb = CINZA
    telhado.line.fill.background()
    sem_sombra(telhado)
    parede = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, cx - Inches(0.08), cy - Inches(0.03), Inches(0.16), Inches(0.13)
    )
    parede.fill.solid()
    parede.fill.fore_color.rgb = CINZA
    parede.line.fill.background()
    sem_sombra(parede)

    hlink = botao.click_action._element.get_or_add_hlinkClick()
    hlink.action = "ppaction://hlinkshowjump?jump=lastslideviewed"
    # o link precisa estar no conjunto clicavel — replica a mesma acao nos
    # dois shapes do icone, para o clique funcionar em qualquer ponto dele
    for parte in (telhado, parede):
        hlink_parte = parte.click_action._element.get_or_add_hlinkClick()
        hlink_parte.action = "ppaction://hlinkshowjump?jump=lastslideviewed"
    return botao


def tabela_comparacao(slide, x, y, w, h, cabecalhos, linhas, largura_col0, linha_destaque=None,
                       wrap=False):
    """Tabela nativa pptx: cabecalho preto, linha do campeao em vermelho."""
    n_linhas = len(linhas) + 1
    n_cols = len(cabecalhos)
    grafico = slide.shapes.add_table(n_linhas, n_cols, x, y, w, h)
    tabela = grafico.table
    tabela.first_row = False
    tabela.horz_banding = False

    largura_resto = (w - largura_col0) // (n_cols - 1)
    tabela.columns[0].width = largura_col0
    for c in range(1, n_cols):
        tabela.columns[c].width = largura_resto

    def _formatar_celula(cel, texto_str, negrito, cor_texto, cor_fundo, tamanho=12.5,
                          alinhamento=PP_ALIGN.CENTER):
        cel.fill.solid()
        cel.fill.fore_color.rgb = cor_fundo
        cel.vertical_anchor = MSO_ANCHOR.MIDDLE
        cel.margin_left = Inches(0.08)
        cel.margin_right = Inches(0.08)
        cel.margin_top = Inches(0.02)
        cel.margin_bottom = Inches(0.02)
        tf = cel.text_frame
        tf.word_wrap = wrap
        p = tf.paragraphs[0]
        p.alignment = alinhamento
        run = p.add_run()
        run.text = texto_str
        run.font.size = Pt(tamanho)
        run.font.bold = negrito
        run.font.name = FONTE
        run.font.color.rgb = cor_texto

    for c, titulo_col in enumerate(cabecalhos):
        _formatar_celula(tabela.cell(0, c), titulo_col, True, BRANCO, PRETO, tamanho=12,
                          alinhamento=(PP_ALIGN.LEFT if c == 0 else PP_ALIGN.CENTER))

    for r, linha in enumerate(linhas, start=1):
        destaque = linha[0] == linha_destaque
        cor_fundo = VERMELHO if destaque else (QUASE_BRANCO if r % 2 else BRANCO)
        cor_texto = BRANCO if destaque else PRETO
        for c, valor in enumerate(linha):
            _formatar_celula(
                tabela.cell(r, c), str(valor), destaque, cor_texto, cor_fundo, tamanho=12.5,
                alinhamento=(PP_ALIGN.LEFT if c == 0 else PP_ALIGN.CENTER),
            )
    return tabela


# ============================================================ 1. ABERTURA
s = nova_slide(BRANCO)
logo(s, "vermelho_v", x=Inches(0.75), y=Inches(0.6), largura=Inches(1.15))
kicker(s, "PÓS-GRADUAÇÃO EM ENGENHARIA DE DADOS · MACKENZIE",
       x=Inches(0.75), y=Inches(2.55))
texto(s, Inches(0.75), Inches(2.95), Inches(9.6), Inches(1.5), "InformalidadeBR",
      tamanho=58, cor=PRETO, negrito=True, fonte=FONTE)
texto(s, Inches(0.75), Inches(4.05), Inches(8.3), Inches(1.1),
      "Prevendo o trabalho informal no Brasil a partir de dados públicos da PNAD Contínua",
      tamanho=19, cor=CINZA, fonte=FONTE, espacamento=1.15)
linha_divisoria(s, Inches(0.75), Inches(5.55), Inches(4.2))
texto(s, Inches(0.75), Inches(5.75), Inches(9), Inches(1.2), INTEGRANTES,
      tamanho=13.5, cor=PRETO, fonte=FONTE, espacamento=1.35)
barra_lateral(s)

# ============================================================ 2. O PROBLEMA
s = nova_slide(BRANCO)
cabecalho_padrao(s, 2, "O PROBLEMA",
                 "Quase metade dos trabalhadores ocupados no Brasil está na informalidade")
stat_grande(s, Inches(0.75), Inches(2.2), Inches(3.6), "47,6%",
            "dos 2.522.338 trabalhadores ocupados analisados, PNAD Contínua 2023 a 2025",
            tam_valor=64)
card(s, Inches(4.85), Inches(2.15), Inches(3.7), Inches(1.55),
     "Sem proteção", "Sem carteira assinada, sem CNPJ, sem contribuição ao INSS.")
card(s, Inches(8.75), Inches(2.15), Inches(3.7), Inches(1.55),
     "Sem acesso", "Sem crédito, sem benefícios, sem direitos trabalhistas básicos.")
card(s, Inches(4.85), Inches(3.85), Inches(3.7), Inches(1.55),
     "Distribuição desigual", "Não é acaso: concentra-se por setor, região, gênero e raça.")
card(s, Inches(8.75), Inches(3.85), Inches(3.7), Inches(1.55),
     "Um problema real", "Estrutural no mercado de trabalho brasileiro, não um recorte marginal.")
texto(s, Inches(0.75), Inches(6.15), Inches(8), Inches(0.6),
      "É esse padrão, nos dados, que o projeto tenta prever e explicar.",
      tamanho=14, cor=VERMELHO_ESCURO, negrito=True, fonte=FONTE)

# ============================================================ 3. OBJETIVO
s = nova_slide(BRANCO)
cabecalho_padrao(s, 3, "OBJETIVO",
                 "Prever quem está na informalidade e entender quem ela mais afeta")
objetivos = [
    ("01", "Prever", "Se um trabalhador está na informalidade, a partir de características observáveis (escolaridade, setor, região...)."),
    ("02", "Explicar", "Quais fatores mais pesam nessa condição, não só o quê, mas por quê."),
    ("03", "Medir equidade", "Se o modelo trata igualmente todos os grupos, gênero e raça, não só a média geral."),
]
largura_card = Inches(3.72)
for i, (num, tit, corpo) in enumerate(objetivos):
    x = Inches(0.75) + i * (largura_card + Inches(0.28))
    retangulo(s, x, Inches(2.35), largura_card, Inches(3.7), QUASE_BRANCO, arredondado=True)
    texto(s, x + Inches(0.3), Inches(2.62), largura_card - Inches(0.6), Inches(0.9),
          num, tamanho=34, cor=ROSA_FUNDO, negrito=True, fonte=FONTE)
    retangulo(s, x + Inches(0.3), Inches(3.55), Inches(0.5), Pt(3), VERMELHO)
    texto(s, x + Inches(0.3), Inches(3.72), largura_card - Inches(0.6), Inches(0.5),
          tit, tamanho=18, cor=PRETO, negrito=True, fonte=FONTE)
    texto(s, x + Inches(0.3), Inches(4.28), largura_card - Inches(0.6), Inches(1.6),
          corpo, tamanho=13, cor=CINZA, fonte=FONTE, espacamento=1.25)
rodape(s, 3)

# ============================================================ 4. OS DADOS
s = nova_slide(BRANCO)
cabecalho_padrao(s, 4, "OS DADOS",
                 "PNAD Contínua, a maior pesquisa domiciliar do Brasil, direto do IBGE")
stats = [
    ("12", "trimestres\n2023 – 2025"),
    ("~500 mil", "registros por\ntrimestre"),
    ("22 / 420", "variáveis selecionadas\npor relevância direta"),
    ("1", "fonte pública única\n(FTP do IBGE)"),
]
w_stat = Inches(2.85)
for i, (valor, legenda) in enumerate(stats):
    x = Inches(0.75) + i * (w_stat + Inches(0.15))
    retangulo(s, x, Inches(2.3), w_stat, Inches(2.0), QUASE_BRANCO, arredondado=True)
    texto(s, x, Inches(2.62), w_stat, Inches(0.85), valor, tamanho=30, cor=VERMELHO,
          negrito=True, alinhamento=PP_ALIGN.CENTER, fonte=FONTE)
    texto(s, x + Inches(0.15), Inches(3.5), w_stat - Inches(0.3), Inches(0.7), legenda,
          tamanho=11.5, cor=CINZA, alinhamento=PP_ALIGN.CENTER, fonte=FONTE, espacamento=1.15)
texto(s, Inches(0.75), Inches(4.75), Inches(11.6), Inches(1.6),
      "Microdados de largura fixa, exatamente como publicados pelo IBGE. Cada período baixado "
      "com retentativa automática e validado por manifesto (checksum SHA-256 e contagem de "
      "linhas), para detectar corrupção antes de qualquer análise.",
      tamanho=14.5, cor=PRETO, fonte=FONTE, espacamento=1.3)

# ============================================================ 5. PREPARAÇÃO
s = nova_slide(BRANCO)
s5 = s
cabecalho_padrao(s, 5, "PREPARAÇÃO DOS DADOS",
                 "De microdados brutos a uma base curada, em três camadas")
camadas = [
    ("BRONZE", "Dados brutos", "Como recebidos do IBGE, sem transformação"),
    ("SILVER", "Decodificados", "Nulos tratados, 0 linhas perdidas na consolidação"),
    ("GOLD", "Base pronta", "Filtro de ocupados + variável-alvo `informal`"),
]
w_camada = Inches(3.55)
y_camada = Inches(2.35)
h_camada = Inches(1.55)
for i, (nome, tit, corpo) in enumerate(camadas):
    x = Inches(0.9) + i * (w_camada + Inches(0.75))
    cor_fundo = [RGBColor(0xCD, 0x7F, 0x32), RGBColor(0xB8, 0xB8, 0xB8), VERMELHO][i]
    retangulo(s, x, y_camada, w_camada, h_camada, QUASE_BRANCO, arredondado=True)
    retangulo(s, x, y_camada, w_camada, Inches(0.42), cor_fundo, arredondado=True)
    texto(s, x, y_camada + Inches(0.07), w_camada, Inches(0.32), nome, tamanho=13.5, cor=BRANCO,
          negrito=True, alinhamento=PP_ALIGN.CENTER, fonte=FONTE, espacamento_letras=1.2)
    texto(s, x + Inches(0.22), y_camada + Inches(0.55), w_camada - Inches(0.44), Inches(0.35),
          tit, tamanho=13.5, cor=PRETO, negrito=True, fonte=FONTE)
    texto(s, x + Inches(0.22), y_camada + Inches(0.92), w_camada - Inches(0.44), Inches(0.6),
          corpo, tamanho=10.8, cor=CINZA, fonte=FONTE, espacamento=1.15)
    if i < 2:
        seta_horizontal(s, x + w_camada + Inches(0.08), y_camada + Inches(0.58), Inches(0.6), Inches(0.4))

y_row2 = Inches(4.15)
h_row2 = Inches(2.68)
w_col = Inches(5.72)
gap_col = Inches(0.4)

# esquerda: funil de filtragem Silver -> Gold
x_esq = Inches(0.75)
retangulo(s, x_esq, y_row2, w_col, h_row2, QUASE_BRANCO, arredondado=True)
retangulo(s, x_esq, y_row2, Inches(0.06), h_row2, VERMELHO)
texto(s, x_esq + Inches(0.28), y_row2 + Inches(0.2), w_col - Inches(0.5), Inches(0.4),
      "DA SILVER À GOLD: O FILTRO", tamanho=12.5, cor=VERMELHO, negrito=True, fonte=FONTE,
      espacamento_letras=0.8)
texto(s, x_esq + Inches(0.28), y_row2 + Inches(0.62), w_col - Inches(0.5), Inches(0.55),
      "5.748.375  →  2.522.338", tamanho=21, cor=PRETO, negrito=True, fonte=FONTE)
texto(s, x_esq + Inches(0.28), y_row2 + Inches(1.16), w_col - Inches(0.5), Inches(0.35),
      "linhas na Silver  →  pessoas ocupadas na Gold (43,9% retido)", tamanho=11, cor=CINZA,
      fonte=FONTE)
texto(s, x_esq + Inches(0.28), y_row2 + Inches(1.62), w_col - Inches(0.5), Inches(0.95), [
    "• Único filtro aplicado: VD4002 = 1 (pessoa ocupada). Sem isso,",
    "  \"informalidade\" nem está definida para a pessoa",
    "• Dos 2.522.338 ocupados, 47,6% são informais pela regra ao lado",
], tamanho=10.8, cor=PRETO, fonte=FONTE, espacamento=1.2)

# direita: conceito de informal (OBS)
x_dir = x_esq + w_col + gap_col
retangulo(s, x_dir, y_row2, w_col, h_row2, ROSA_FUNDO, arredondado=True)
texto(s, x_dir + Inches(0.28), y_row2 + Inches(0.2), w_col - Inches(0.5), Inches(0.4),
      "OBS: O QUE É \"INFORMAL\" AQUI?", tamanho=12.5, cor=VERMELHO_ESCURO, negrito=True,
      fonte=FONTE, espacamento_letras=0.6)
texto(s, x_dir + Inches(0.28), y_row2 + Inches(0.68), w_col - Inches(0.5), Inches(1.55), [
    "Sem carteira assinada (privado, doméstico ou público), OU",
    "trabalhador familiar sem remuneração, OU empregador/conta-",
    "própria sem CNPJ.",
], tamanho=12, cor=PRETO, fonte=FONTE, espacamento=1.25)
texto(s, x_dir + Inches(0.28), y_row2 + Inches(1.95), w_col - Inches(0.5), Inches(0.65),
      "Regra VD4009 do IBGE (com V4019 de desempate p/ empregador/conta-"
      "própria), a mesma que o IBGE usa em estudos oficiais de informalidade.",
      tamanho=10.3, cor=CINZA, fonte=FONTE, espacamento=1.2)

# ============================================================ 6. EDA
s = nova_slide(BRANCO)
s6 = s
cabecalho_padrao(s, 6, "ANÁLISE EXPLORATÓRIA",
                 "Tamanho do negócio e vínculo temporário são os sinais mais fortes", tam_titulo=27)
imagem_centrada(s, ASSETS_GRAFICOS / "fig_eda_top_features.png", Inches(0.85), Inches(2.15), w=Inches(7.6))
texto(s, Inches(8.85), Inches(2.35), Inches(3.7), Inches(0.4), "FORÇA DE ASSOCIAÇÃO", tamanho=12,
      cor=CINZA, negrito=True, fonte=FONTE, espacamento_letras=1.2)
texto(s, Inches(8.85), Inches(2.75), Inches(3.7), Inches(0.5), "com a condição de informalidade",
      tamanho=12.5, cor=CINZA, fonte=FONTE, espacamento=1.15)
texto(s, Inches(8.85), Inches(3.5), Inches(3.75), Inches(0.4), "V de Cramér / ponto-bisserial",
      tamanho=11, cor=CINZA, fonte=FONTE)
retangulo(s, Inches(8.85), Inches(4.0), Inches(3.75), Inches(1.85), QUASE_BRANCO, arredondado=True)
retangulo(s, Inches(8.85), Inches(4.0), Inches(0.06), Inches(1.85), VERMELHO)
texto(s, Inches(9.13), Inches(4.15), Inches(3.3), Inches(0.4), "O TRABALHADOR INFORMAL, EM NÚMEROS",
      tamanho=11.5, cor=PRETO, negrito=True, fonte=FONTE, espacamento=1.05)
texto(s, Inches(9.13), Inches(4.58), Inches(3.3), Inches(1.2), [
    "53% não concluíram o ensino médio (25% entre os formais)",
    "35% moram no Nordeste (20% entre os formais)",
    "Renda mediana 42% menor: R$ 1.400 x R$ 2.400",
], tamanho=10.8, cor=PRETO, fonte=FONTE, espacamento=1.25)
retangulo(s, Inches(0.75), Inches(6.05), Inches(11.83), Inches(0.75), QUASE_BRANCO, arredondado=True)
texto(s, Inches(1.0), Inches(6.16), Inches(9.4), Inches(0.55),
      "Decisão em 2 etapas, a mais difícil do projeto: das quase 420 variáveis da PNAD, 22 "
      "entraram no pré-processamento por relevância direta. Dessas, 15 seguiram para o modelo, "
      "2 delas (sexo e raça) por escopo obrigatório do projeto, não por força estatística.",
      tamanho=11, cor=PRETO, fonte=FONTE, espacamento=1.2, ancora=MSO_ANCHOR.MIDDLE)

# ============================================================ 7. A SOLUÇÃO
s = nova_slide(BRANCO)
cabecalho_padrao(s, 7, "A SOLUÇÃO", "Um pipeline completo, do dado bruto à predição")
etapas = ["Ingestão", "Pré-\nprocessamento", "Transformação", "Análise\nexploratória",
          "Modelagem\n& ML", "Interpretação\n& equidade"]
w_etapa = Inches(1.72)
gap = Inches(0.2)
x0 = Inches(0.75)
y0 = Inches(2.85)
for i, nome in enumerate(etapas):
    x = x0 + i * (w_etapa + gap)
    etapa_pipeline(s, x, y0, w_etapa, Inches(1.5), f"{i + 1:02d}", nome,
                   cor_fundo=(VERMELHO if i == 4 else QUASE_BRANCO),
                   cor=(BRANCO if i == 4 else PRETO))
    if i < len(etapas) - 1:
        seta_horizontal(s, x + w_etapa + Inches(0.02), y0 + Inches(0.55), gap - Inches(0.04), Inches(0.4))
texto(s, Inches(0.75), Inches(4.85), Inches(11.6), Inches(0.4), "FERRAMENTAS", tamanho=12,
      cor=CINZA, negrito=True, fonte=FONTE, espacamento_letras=1.2)
texto(s, Inches(0.75), Inches(5.25), Inches(11.6), Inches(0.6),
      "Python · pandas · scikit-learn · SHAP · arquitetura Medallion orientada a classes "
      "(`Etapa` → `Pipeline`), cada etapa executável isoladamente ou em cadeia.",
      tamanho=14, cor=PRETO, fonte=FONTE, espacamento=1.25)

# ============================================================ 8. CONSTRUÇÃO DO MODELO
s = nova_slide(BRANCO)
cabecalho_padrao(s, 8, "A CONSTRUÇÃO DO MODELO",
                 "Três modelos avaliados sob a mesma regra de validação")
modelos_txt = [
    ("Regressão Logística", "Baseline interpretável. Coeficiente de cada variável é direto de explicar, sanity check dos outros dois."),
    ("Random Forest", "Robusto, custo controlado por amostra por árvore. Ainda assim, o mais lento dos três em treino."),
    ("HistGradientBoosting", "Lida nativamente com categórica e valor nulo. É também o mais rápido dos dois modelos fortes."),
]
w_m = Inches(3.72)
for i, (tit, corpo) in enumerate(modelos_txt):
    x = Inches(0.75) + i * (w_m + Inches(0.28))
    card(s, x, Inches(2.3), w_m, Inches(2.15), tit, corpo, tam_titulo=15.5, tam_corpo=12.5)
retangulo(s, Inches(0.75), Inches(4.85), Inches(11.83), Inches(1.35), ROSA_FUNDO, arredondado=True)
texto(s, Inches(1.05), Inches(5.05), Inches(2.6), Inches(1.0), "SPLIT\nTEMPORAL", tamanho=15,
      cor=VERMELHO_ESCURO, negrito=True, fonte=FONTE, espacamento=1.1)
texto(s, Inches(3.9), Inches(5.02), Inches(8.4), Inches(1.1),
      "Treino: 2023–2024  →  Teste: 2025 completo. Nunca ao acaso: a PNAD é um painel "
      "rotativo, e um split aleatório vazaria a mesma pessoa entre treino e teste.",
      tamanho=13.5, cor=PRETO, fonte=FONTE, espacamento=1.25, ancora=MSO_ANCHOR.MIDDLE)

# ============================================================ 9. INTERPRETABILIDADE / EQUIDADE
s = nova_slide(BRANCO)
cabecalho_padrao(s, 9, "INTERPRETABILIDADE E EQUIDADE",
                 "O modelo é interpretável, e isso expôs uma desigualdade real", tam_titulo=27)
imagem_centrada(s, ASSETS_GRAFICOS / "fig_shap_top_features.png", Inches(0.75), Inches(2.2), w=Inches(6.9))
texto(s, Inches(0.85), Inches(5.75), Inches(6.6), Inches(0.5),
      "SHAP: o que mais pesou na decisão do modelo campeão", tamanho=11.5, cor=CINZA,
      fonte=FONTE, espacamento=1.1)
imagem_centrada(s, ASSETS_GRAFICOS / "fig_equidade.png", Inches(8.1), Inches(2.15), h=Inches(3.15))
retangulo(s, Inches(7.95), Inches(5.55), Inches(4.65), Inches(1.35), ROSA_FUNDO, arredondado=True)
texto(s, Inches(8.2), Inches(5.72), Inches(4.2), Inches(1.1),
      "Recall 12 p.p. menor para o grupo Amarelos (n = 4.214): um sinal de atenção real, "
      "registrado no Model Card, não motivo para descartar o modelo.",
      tamanho=12, cor=VERMELHO_ESCURO, negrito=True, fonte=FONTE, espacamento=1.25)

# ============================================================ 10. RESULTADOS (mais importante)
s = nova_slide(BRANCO)
s10 = s
cabecalho_padrao(s, 10, "RESULTADOS",
                 "92,6% de AUC-ROC no ano que o modelo nunca viu", tam_titulo=29)
cabecalhos_tab = ["Modelo", "Accuracy", "Precision", "Recall", "F1", "AUC-ROC", "Tempo (s)"]
linhas_tab = [
    ["HistGradientBoosting", "0.8474", "0.8384", "0.8360", "0.8372", "0.9261", "178.70"],
    ["Random Forest", "0.8355", "0.8123", "0.8446", "0.8281", "0.9166", "2171.53"],
    ["Regressão Logística", "0.8259", "0.7995", "0.8397", "0.8191", "0.9011", "41.67"],
]
tabela_comparacao(s, Inches(0.75), Inches(2.05), Inches(11.83), Inches(1.55), cabecalhos_tab,
                   linhas_tab, largura_col0=Inches(3.0), linha_destaque="HistGradientBoosting")
texto(s, Inches(0.75), Inches(3.85), Inches(7.9), Inches(0.4), "HistGradientBoosting é o campeão",
      tamanho=13.5, cor=PRETO, negrito=True, fonte=FONTE)
texto(s, Inches(0.75), Inches(4.3), Inches(7.9), Inches(2.5),
      "De cada 100 trabalhadores informais reais no teste, o modelo identifica corretamente 84, "
      "com a mesma performance em treino e teste, sem overfitting. É também o mais rápido dos "
      "dois modelos fortes: 179s de treino contra 2.172s (36 min) do Random Forest, 12 vezes "
      "mais lento por um ganho de apenas 0,9 ponto de AUC. Tempo de treino também é custo de "
      "engenharia, não só de máquina.",
      tamanho=13.5, cor=PRETO, fonte=FONTE, espacamento=1.3)
imagem_centrada(s, ASSETS_GRAFICOS / "fig_roc.png", Inches(9.15), Inches(3.85), w=Inches(3.3))

# ============================================================ 11. CONCLUSÕES
s = nova_slide(BRANCO)
cabecalho_padrao(s, 11, "CONCLUSÕES", "Funcionou, e mostrou exatamente onde melhorar")
retangulo(s, Inches(0.75), Inches(2.3), Inches(5.75), Inches(4.05), QUASE_BRANCO, arredondado=True)
texto(s, Inches(1.05), Inches(2.55), Inches(5.2), Inches(0.5), "O QUE FUNCIONOU", tamanho=13,
      cor=VERMELHO, negrito=True, fonte=FONTE, espacamento_letras=1.1)
texto(s, Inches(1.05), Inches(3.1), Inches(5.15), Inches(3.1), [
    "• Pipeline reprodutível ponta a ponta, com validação em cada camada (0 linhas perdidas Bronze → Silver)",
    "• Modelo com bom poder preditivo (AUC 0,93) e sem overfitting relevante",
    "• Interpretabilidade real via SHAP, não uma caixa-preta",
], tamanho=13, cor=PRETO, fonte=FONTE, espacamento=1.35)
retangulo(s, Inches(6.85), Inches(2.3), Inches(5.75), Inches(4.05), ROSA_FUNDO, arredondado=True)
texto(s, Inches(7.15), Inches(2.55), Inches(5.2), Inches(0.5), "PRÓXIMOS PASSOS", tamanho=13,
      cor=VERMELHO_ESCURO, negrito=True, fonte=FONTE, espacamento_letras=1.1)
texto(s, Inches(7.15), Inches(3.1), Inches(5.15), Inches(3.1), [
    "• Corrigir a disparidade de recall no grupo Amarelos (reponderação ou threshold por grupo)",
    "• Usar o peso amostral da PNAD (V1028) na avaliação, hoje só o próprio desenho complexo em aberto",
    "• Monitorar novas safras trimestrais e o ganho marginal do campeão frente ao Random Forest",
], tamanho=13, cor=PRETO, fonte=FONTE, espacamento=1.35)

# ============================================================ 12. CONCLUSÃO GERAL + ENCERRAMENTO
s = nova_slide(VERMELHO)
ROSA_CLARO = RGBColor(0xFF, 0xB3, 0xC0)
logo(s, "branco_h", x=Inches(0.75), y=Inches(0.5), largura=Inches(1.45))
texto(s, Inches(0.75), Inches(1.35), Inches(9), Inches(0.4), "CONCLUSÃO GERAL", tamanho=13,
      cor=ROSA_CLARO, negrito=True, fonte=FONTE, espacamento_letras=1.5, maiusculas=True)
texto(s, Inches(0.75), Inches(1.75), Inches(11.6), Inches(0.85),
      "A informalidade não é um detalhe estatístico. É quase metade do mercado de trabalho "
      "brasileiro, distribuída de forma desigual entre região, setor e cor.",
      tamanho=16.5, cor=BRANCO, negrito=True, fonte=FONTE, espacamento=1.2)
texto(s, Inches(0.75), Inches(2.75), Inches(11.6), Inches(0.9),
      "Este projeto entrega mais que um modelo: um pipeline completo, do dado bruto do IBGE "
      "até uma predição interpretável, reprodutível do início ao fim.",
      tamanho=16.5, cor=BRANCO, negrito=True, fonte=FONTE, espacamento=1.2)
linha_divisoria(s, Inches(0.75), Inches(3.95), Inches(4.2), cor=ROSA_CLARO)
texto(s, Inches(0.75), Inches(4.2), Inches(10), Inches(1.0), "Obrigado.", tamanho=44, cor=BRANCO,
      negrito=True, fonte=FONTE)
texto(s, Inches(0.75), Inches(5.05), Inches(9), Inches(0.6), "Perguntas?", tamanho=20, cor=BRANCO,
      fonte=FONTE)
texto(s, Inches(0.75), Inches(6.1), Inches(9), Inches(1.0), INTEGRANTES, tamanho=12.5, cor=BRANCO,
      fonte=FONTE, espacamento=1.3)
texto(s, LARGURA - Inches(4.4), ALTURA - Inches(0.55), Inches(3.8), Inches(0.35),
      "github.com/gui-ramon/pipeline-hands-on-engenharia-de-dados", tamanho=9.5,
      cor=RGBColor(0xFF, 0xD8, 0xDD), alinhamento=PP_ALIGN.RIGHT, fonte=FONTE)

# ======================================================================
# SLIDES OCULTOS — material de apoio para as perguntas (fora dos 10 min)
# ======================================================================

# ------------------------------------------------------------ A. Funil completo
s = nova_slide(BRANCO)
s13 = s
cabecalho_apoio(s, "DADOS", "O funil completo: de 12 arquivos brutos a 2,52M de pessoas")
marcar_oculto(s)
etapas_funil = [
    ("BRONZE", "12 arquivos, ~19 GB brutos"),
    ("SILVER", "5.748.375 linhas decodificadas"),
    ("GOLD", "2.522.338 ocupados (43,9%)"),
]
w_camada_f = Inches(3.75)
gap_camada_f = Inches(0.2)
y_f = Inches(1.8)
for i, (nome, corpo) in enumerate(etapas_funil):
    x = Inches(0.75) + i * (w_camada_f + gap_camada_f)
    cor_fundo = [RGBColor(0xCD, 0x7F, 0x32), RGBColor(0xB8, 0xB8, 0xB8), VERMELHO][i]
    retangulo(s, x, y_f, w_camada_f, Inches(0.4), cor_fundo, arredondado=True)
    texto(s, x, y_f + Inches(0.07), w_camada_f, Inches(0.3), nome, tamanho=12.5, cor=BRANCO,
          negrito=True, alinhamento=PP_ALIGN.CENTER, fonte=FONTE, espacamento_letras=1.0)
    texto(s, x, y_f + Inches(0.48), w_camada_f, Inches(0.4), corpo, tamanho=11.5, cor=PRETO,
          alinhamento=PP_ALIGN.CENTER, fonte=FONTE)

texto(s, Inches(0.75), Inches(2.75), Inches(9), Inches(0.35),
      "De onde vêm os 2,52 milhões de pessoas ocupadas", tamanho=13, cor=CINZA, negrito=True,
      fonte=FONTE, espacamento_letras=0.6)
linhas_funil = [
    ["Menores de 14 anos", "1.026.870", "17,9%", "6,9 anos", "48,8%"],
    ["Fora da força de trabalho", "2.022.961", "35,2%", "49,0 anos", "64,1%"],
    ["Desocupados, buscando trabalho", "176.206", "3,1%", "32,9 anos", "53,0%"],
    ["Ocupados (população do projeto)", "2.522.338", "43,9%", "40,9 anos", "42,9%"],
]
tabela_funil = tabela_comparacao(
    s, Inches(0.75), Inches(3.15), Inches(11.83), Inches(2.0),
    ["Grupo", "N", "% da base", "Idade média", "% mulheres"], linhas_funil,
    largura_col0=Inches(4.2), linha_destaque="Ocupados (população do projeto)",
)
tabela_funil.cell(1, 0).text_frame.paragraphs[0].alignment = PP_ALIGN.LEFT
for r in range(1, 5):
    tabela_funil.cell(r, 0).text_frame.paragraphs[0].alignment = PP_ALIGN.LEFT

retangulo(s, Inches(0.75), Inches(5.5), Inches(11.83), Inches(1.0), ROSA_FUNDO, arredondado=True)
texto(s, Inches(1.0), Inches(5.65), Inches(11.35), Inches(0.7),
      "O grupo fora da força de trabalho tem 64% de mulheres, e os desocupados buscando "
      "emprego, 53%. Os dois acima do 43% entre ocupados: quem decide entrar no mercado de "
      "trabalho já não é uma amostra aleatória da população.",
      tamanho=11.5, cor=VERMELHO_ESCURO, negrito=True, fonte=FONTE, espacamento=1.2,
      ancora=MSO_ANCHOR.MIDDLE)

# ------------------------------------------------------------ B. Conceito de informal completo
s = nova_slide(BRANCO)
s14 = s
cabecalho_apoio(s, "CONCEITO", "A regra completa de informalidade (VD4009 + V4019)")
marcar_oculto(s)
linhas_vd4009 = [
    ["1", "Empregado no setor privado, com carteira", "Formal"],
    ["2", "Empregado no setor privado, sem carteira", "Informal"],
    ["3", "Trabalhador doméstico, com carteira", "Formal"],
    ["4", "Trabalhador doméstico, sem carteira", "Informal"],
    ["5", "Empregado no setor público, com carteira", "Formal"],
    ["6", "Empregado no setor público, sem carteira", "Informal"],
    ["7", "Militar / servidor estatutário", "Formal"],
    ["8", "Empregador", "Formal se tem CNPJ (V4019), senão Informal"],
    ["9", "Conta-própria", "Formal se tem CNPJ (V4019), senão Informal"],
    ["10", "Trabalhador familiar auxiliar (não remunerado)", "Informal"],
]
tabela_apoio = tabela_comparacao(
    s, Inches(0.75), Inches(2.0), Inches(11.83), Inches(4.15),
    ["VD4009", "Categoria (posição na ocupação)", "Classificação"], linhas_vd4009,
    largura_col0=Inches(1.1), wrap=True,
)
for r in range(1, len(linhas_vd4009) + 1):
    tabela_apoio.cell(r, 1).text_frame.paragraphs[0].alignment = PP_ALIGN.LEFT
    tabela_apoio.cell(r, 2).text_frame.paragraphs[0].alignment = PP_ALIGN.LEFT
texto(s, Inches(0.75), Inches(6.35), Inches(11.6), Inches(0.5),
      "Alternativa mais simples considerada (não usada): VD4012 (contribui para a previdência?) "
      "como proxy binário direto, descartada por perder o refinamento de CNPJ em 8/9.",
      tamanho=11, cor=CINZA, fonte=FONTE, espacamento=1.15)

# ------------------------------------------------------------ C. Por que essas 15 features
s = nova_slide(BRANCO)
s15 = s
cabecalho_apoio(s, "FEATURES", "Por que essas 15 variáveis, e não as outras 405")
marcar_oculto(s)
linhas_features = [
    ["V4018", "Tamanho do negócio", "0.570 forte"],
    ["V4025", "É temporário?", "0.460 forte"],
    ["VD4010", "Setor de atividade", "0.404 forte"],
    ["VD4011", "Grupamento ocupacional", "0.373 forte"],
    ["VD3004", "Nível de instrução", "0.325 moderada"],
    ["VD4031", "Horas semanais", "0.272 moderada"],
    ["V1022", "Urbano / rural", "0.255 moderada"],
    ["UF", "Estado", "0.243 moderada"],
    ["V4040", "Tempo no emprego", "0.144 fraca"],
    ["V1023", "Tipo de área", "0.135 fraca"],
    ["V2010", "Raça / cor", "0.118 fraca (obrigatória RF-06)"],
    ["VD2002", "Posição no domicílio", "0.042 muito fraca"],
    ["V2009", "Idade", "0.042 muito fraca"],
    ["VD2003", "Pessoas no domicílio", "0.030 muito fraca"],
    ["V2007", "Sexo", "0.026 fraca (obrigatória RF-06)"],
]
tabela_feat = tabela_comparacao(
    s, Inches(0.75), Inches(1.95), Inches(7.35), Inches(4.55),
    ["Var.", "O que é", "Força (V de Cramér / |r|)"], linhas_features, largura_col0=Inches(1.0),
    wrap=True,
)
for r in range(1, len(linhas_features) + 1):
    tabela_feat.cell(r, 1).text_frame.paragraphs[0].alignment = PP_ALIGN.LEFT
    tabela_feat.cell(r, 2).text_frame.paragraphs[0].alignment = PP_ALIGN.LEFT
    for c in range(3):
        tabela_feat.cell(r, c).text_frame.paragraphs[0].runs[0].font.size = Pt(9.5)
card(s, Inches(8.35), Inches(1.95), Inches(4.25), Inches(4.55), "O que ficou de fora, e por quê",
     "VD4009/V4019/VD4012/VD4002: constroem o próprio alvo (vazamento). VD4016/VD4017 "
     "(renda): vazamento circular, só usadas em gráfico de EDA. V3002 (frequenta escola): "
     "associação quase nula (0,003). UPA/V1008/V1014/V2003: só chave de deduplicação, sem "
     "relação causal. V1028 (peso amostral): reservado, não é feature. Ano/Trimestre: "
     "vazariam o split temporal.", tam_titulo=13.5, tam_corpo=11.5)

# ------------------------------------------------------------ D. Matrizes de confusão
s = nova_slide(BRANCO)
s16 = s
cabecalho_apoio(s, "RESULTADOS", "Matrizes de confusão: teste 2025, base completa")
marcar_oculto(s)
imagem_centrada(s, ASSETS_GRAFICOS / "fig_confusao.png", Inches(0.75), Inches(2.05), w=Inches(11.5))
texto(s, Inches(0.75), Inches(6.2), Inches(11.6), Inches(0.6),
      "864.940 pessoas no teste. Falso negativo (informal previsto como formal) é o erro mais "
      "custoso para o objetivo do projeto: subestima o tamanho real da informalidade.",
      tamanho=12, cor=PRETO, fonte=FONTE, espacamento=1.2)

# ======================================================================
# BOTÕES "+" — atalho clicável dos slides principais para os ocultos
# ======================================================================

# slide 5: funil (esquerda) e conceito de informal (direita)
botao_mais(s5, Inches(5.92), Inches(4.3), s13)
botao_mais(s5, Inches(12.04), Inches(4.3), s14)

# slide 6: decisão de variáveis
botao_mais(s6, Inches(12.03), Inches(6.225), s15)

# slide 10: matrizes de confusão
botao_mais(s10, Inches(12.03), Inches(1.5), s16)

for slide_oculto in (s13, s14, s15, s16):
    botao_casa(slide_oculto)

SAIDA.parent.mkdir(parents=True, exist_ok=True)
prs.save(SAIDA)
n_ocultos = sum(1 for sl in prs.slides if sl._element.get("show") == "0")
print(f"[ok] {SAIDA}  ({len(prs.slides)} slides, {n_ocultos} ocultos)")
