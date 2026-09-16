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
ASSETS_FERRAMENTAS = RAIZ / "apresentacao" / "_assets_identidade" / "ferramentas"
ASSETS_GRAFICOS = RAIZ / "apresentacao" / "_assets_graficos"
SAIDA = RAIZ / "apresentacao" / "InformalidadeBR - Apresentacao.pptx"

LOGO_VERMELHO_H = ASSETS_LOGO / "MCK_horizontal_vermelho.png"
LOGO_BRANCO_H = ASSETS_LOGO / "MCK_horizontal_branca-01.png"
LOGO_VERMELHO_V = ASSETS_LOGO / "MCK_vertical_vermelho-01.png"
LOGO_PRETO_H = ASSETS_LOGO / "MCK_horizontal_preto-01.png"

LOGO_IBGE = ASSETS_FERRAMENTAS / "ibge.png"
LOGO_PYTHON = ASSETS_FERRAMENTAS / "python.png"
LOGO_CLAUDE = ASSETS_FERRAMENTAS / "claude.png"

# ---------------------------------------------------------------- identidade
VERMELHO = RGBColor(0xEB, 0x00, 0x29)
VERMELHO_ESCURO = RGBColor(0xB5, 0x00, 0x20)
PRETO = RGBColor(0x1A, 0x1A, 0x1A)
CINZA = RGBColor(0x6E, 0x6E, 0x6E)
CINZA_CLARO = RGBColor(0xE7, 0xE7, 0xE7)
QUASE_BRANCO = RGBColor(0xFA, 0xF9, 0xF8)
BRANCO = RGBColor(0xFF, 0xFF, 0xFF)
ROSA_FUNDO = RGBColor(0xFC, 0xE9, 0xEB)
DOURADO = RGBColor(0xC9, 0x9A, 0x2C)  # realce de "conquista" — usado com moderacao
CINZA_BORDA = RGBColor(0xBF, 0xBF, 0xBF)  # borda visivel (o CINZA_CLARO antigo era claro demais)

FONTE = "Arial"
FONTE_DESTAQUE = "Arial Black"  # numeros/estatisticas "hero" que precisam gritar mais

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
        forma.line.width = Pt(1.5)
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


def bullets_destaque(slide, x, y, w, h, itens, tamanho=12, cor=PRETO, cor_forte=None,
                      espacamento=1.3, marcador="• "):
    """Bullets com o "gancho" em negrito no inicio de cada linha (tecnica
    de bullet escaneavel: quem so bate o olho ja pega a ideia, sem
    precisar ler a frase inteira) — cada item e (trecho_forte, resto)."""
    caixa = slide.shapes.add_textbox(x, y, w, h)
    tf = caixa.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    for i, (forte, resto) in enumerate(itens):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.line_spacing = espacamento
        r1 = p.add_run()
        r1.text = f"{marcador}{forte}"
        r1.font.size = Pt(tamanho)
        r1.font.bold = True
        r1.font.name = FONTE
        r1.font.color.rgb = cor_forte or cor
        r2 = p.add_run()
        r2.text = resto
        r2.font.size = Pt(tamanho)
        r2.font.bold = False
        r2.font.name = FONTE
        r2.font.color.rgb = cor
    return caixa


def texto_com_links(slide, x, y, w, h, segmentos, tamanho=10.5, cor=CINZA, fonte=FONTE,
                     ancora=MSO_ANCHOR.TOP, alinhamento=PP_ALIGN.LEFT):
    """Uma linha com trechos clicaveis de verdade — cada item de
    `segmentos` e (texto, url_ou_None). So o(s) trecho(s) com url viram
    hyperlink real (ppt abre no navegador ao clicar)."""
    caixa = slide.shapes.add_textbox(x, y, w, h)
    tf = caixa.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = ancora
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    p = tf.paragraphs[0]
    p.alignment = alinhamento
    for texto_seg, url in segmentos:
        run = p.add_run()
        run.text = texto_seg
        run.font.size = Pt(tamanho)
        run.font.name = fonte
        run.font.color.rgb = cor
        if url:
            run.hyperlink.address = url
    return caixa


def kicker(slide, txt, cor=VERMELHO, x=Inches(0.75), y=Inches(0.55)):
    return texto(slide, x, y, Inches(9), Inches(0.4), txt, tamanho=13, cor=cor,
                 negrito=True, maiusculas=True, espacamento_letras=1.5, fonte=FONTE)


def headline(slide, txt, x=Inches(0.75), y=Inches(0.95), w=Inches(11.6), tamanho=30):
    return texto(slide, x, y, w, Inches(1.3), txt, tamanho=tamanho, cor=PRETO,
                 negrito=True, espacamento=1.02, fonte=FONTE)


def subtitulo(slide, txt, x=Inches(0.75), y=Inches(1.28), w=Inches(11.6), tamanho=16.5):
    return texto(slide, x, y, w, Inches(0.85), txt, tamanho=tamanho, cor=CINZA,
                 fonte=FONTE, espacamento=1.2)


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


def cabecalho_padrao(slide, num, titulo_txt, subtitulo_txt, tam_titulo=32, w_titulo=Inches(11.6)):
    barra_lateral(slide)
    logo(slide, "vermelho_h", largura=Inches(1.35))
    headline(slide, titulo_txt, tamanho=tam_titulo, y=Inches(0.55), w=w_titulo)
    subtitulo(slide, subtitulo_txt, w=w_titulo)
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
    texto(slide, Inches(0.75), ALTURA - Inches(0.55), Inches(3), Inches(0.35),
          "InformalidadeBR", tamanho=9.5, cor=CINZA, fonte=FONTE, negrito=True,
          espacamento_letras=0.8)


def card(slide, x, y, w, h, titulo_txt, corpo_txt, cor_titulo=VERMELHO, cor_fundo=QUASE_BRANCO,
          tam_titulo=15, tam_corpo=13, borda=CINZA_BORDA):
    retangulo(slide, x, y, w, h, cor_fundo, arredondado=True,
              linha=borda is not None, cor_linha=borda)
    # inset vertical pra nao vazar past o canto arredondado do card (uma
    # barra reta encostada nos 4 cantos "escapa" da curva do container)
    retangulo(slide, x, y + Inches(0.12), Inches(0.06), h - Inches(0.24), cor_titulo,
              arredondado=True)
    texto(slide, x + Inches(0.28), y + Inches(0.22), w - Inches(0.5), Inches(0.5),
          titulo_txt, tamanho=tam_titulo, cor=PRETO, negrito=True, fonte=FONTE, espacamento=1.05)
    texto(slide, x + Inches(0.28), y + Inches(0.7), w - Inches(0.5), h - Inches(0.9),
          corpo_txt, tamanho=tam_corpo, cor=PRETO, fonte=FONTE, espacamento=1.15)


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


def badge_numero(slide, x, y, numero, diametro=Inches(0.62), cor_fundo=VERMELHO, cor_texto=BRANCO):
    """Circulo solido com um numero/texto curto dentro — usado como indice
    visual real (substitui numeros 'fantasma' em cor pastel, ilegiveis a
    distancia)."""
    circulo = slide.shapes.add_shape(MSO_SHAPE.OVAL, x, y, diametro, diametro)
    circulo.fill.solid()
    circulo.fill.fore_color.rgb = cor_fundo
    circulo.line.fill.background()
    sem_sombra(circulo)
    tf = circulo.text_frame
    tf.word_wrap = False
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    run = p.add_run()
    run.text = numero
    run.font.size = Pt(20)
    run.font.bold = True
    run.font.name = FONTE
    run.font.color.rgb = cor_texto
    return circulo


def icone_cilindro(slide, x, y, w, h, cor):
    """Icone de 'banco de dados' (cilindro) — mesma linguagem visual de
    diagramas de arquitetura de dados (ETL, data warehouse)."""
    forma = slide.shapes.add_shape(MSO_SHAPE.CAN, x, y, w, h)
    forma.fill.solid()
    forma.fill.fore_color.rgb = cor
    forma.line.color.rgb = PRETO
    forma.line.width = Pt(1)
    sem_sombra(forma)
    return forma


def icone_barras(slide, x, y, w, h, cor=VERMELHO):
    """Icone de 'mini histograma' (3 barras crescentes) — representa
    analise/modelagem sem precisar de um logo de terceiro."""
    n = 3
    gap = w * 0.18
    w_barra = (w - gap * (n - 1)) / n
    alturas = [h * 0.45, h * 0.72, h]
    for i, h_barra in enumerate(alturas):
        retangulo(slide, x + i * (w_barra + gap), y + (h - h_barra), Emu(int(w_barra)),
                   Emu(int(h_barra)), cor, arredondado=False)


def icone_documento(slide, x, y, w, h, cor=VERMELHO):
    """Icone de 'relatorio/boletim' (pagina com linhas de texto) — o
    entregavel final (boletim HTML + modelo), sem logo de terceiro."""
    retangulo(slide, x, y, w, h, QUASE_BRANCO, linha=True, cor_linha=cor, arredondado=True)
    n_linhas = 3
    margem = w * 0.18
    y_linha = y + h * 0.28
    for i in range(n_linhas):
        largura_linha = w - 2 * margem if i < n_linhas - 1 else (w - 2 * margem) * 0.6
        retangulo(slide, x + margem, y_linha + i * (h * 0.2), Emu(int(largura_linha)), Pt(2.6), cor)


def icone_lupa(slide, x, y, w, h, cor):
    """Icone de 'lupa' (explorar/analisar) — a etapa de Analise
    Exploratoria, entre a Gold e o Modelo. Geometria calculada por
    trigonometria (a versao anterior posicionava o cabo com um offset
    aproximado que nao batia com o raio real da lente — ficava com o
    cabo cortando a lente em vez de sair da borda dela)."""
    tam = min(w, h)
    diam = tam * 0.6
    r = diam / 2
    lente = slide.shapes.add_shape(MSO_SHAPE.OVAL, Emu(int(x)), Emu(int(y)),
                                    Emu(int(diam)), Emu(int(diam)))
    lente.fill.background()
    lente.line.color.rgb = cor
    lente.line.width = Pt(2.4)
    sem_sombra(lente)

    lx, ly = x + r, y + r  # centro da lente
    comprimento = tam * 0.5
    espessura = tam * 0.15
    k = 0.7071  # cos/sen de 45 graus
    cx = lx + (r + comprimento / 2) * k
    cy = ly + (r + comprimento / 2) * k
    cabo = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE, Emu(int(cx - comprimento / 2)), Emu(int(cy - espessura / 2)),
        Emu(int(comprimento)), Emu(int(espessura)),
    )
    cabo.rotation = 45
    cabo.fill.solid()
    cabo.fill.fore_color.rgb = cor
    cabo.line.fill.background()
    sem_sombra(cabo)


def icone_check(slide, x, y, w, h, cor_fundo, cor_check=BRANCO):
    """Icone de 'resultado validado' (circulo com check) — a etapa final
    do pipeline, antes da entrega."""
    diam = min(w, h)
    circulo = slide.shapes.add_shape(MSO_SHAPE.OVAL, x + (w - diam) / 2, y + (h - diam) / 2,
                                      Emu(int(diam)), Emu(int(diam)))
    circulo.fill.solid()
    circulo.fill.fore_color.rgb = cor_fundo
    circulo.line.fill.background()
    sem_sombra(circulo)
    tf = circulo.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    run = p.add_run()
    run.text = "✓"
    run.font.size = Pt(int(diam / 914400 * 32))
    run.font.bold = True
    run.font.color.rgb = cor_check


def pill_zona(slide, x, y, w, h, texto_str, tamanho=11.5, cor_fundo=PRETO):
    retangulo(slide, x, y, w, h, cor_fundo, arredondado=True)
    texto(slide, x, y, w, h, texto_str, tamanho=tamanho, cor=BRANCO, negrito=True,
          alinhamento=PP_ALIGN.CENTER, fonte=FONTE, espacamento_letras=0.4,
          ancora=MSO_ANCHOR.MIDDLE, maiusculas=True)


def stat_grande(slide, x, y, w, valor, legenda, tam_valor=54, cor=VERMELHO, alinhamento=PP_ALIGN.LEFT,
                 espaco=Inches(1.4)):
    texto(slide, x, y, w, Inches(1.0), valor, tamanho=tam_valor, cor=cor, negrito=True,
          fonte=FONTE, alinhamento=alinhamento)
    texto(slide, x, y + espaco, w, Inches(0.8), legenda, tamanho=12.5, cor=CINZA,
          fonte=FONTE, espacamento=1.15, alinhamento=alinhamento)


def linha_divisoria(slide, x, y, w, cor=CINZA_CLARO):
    retangulo(slide, x, y, w, Pt(1.1), cor)


def botao_mais(slide, x, y, slide_alvo, diametro=Inches(0.4), rotulo=None, rotulo_w=Inches(2.6)):
    """Circulo '+' que pula para um slide oculto de apoio ao ser clicado
    durante a apresentacao (Slide Show) — o slide oculto continua fora da
    sequencia normal de avanco (F5/seta), so abre por este link ou por
    'Ver Todos os Slides'. `rotulo`, quando passado, desenha uma legenda
    curta a esquerda do circulo (necessario quando o botao nao esta dentro
    de um painel com titulo proprio, senao fica um '+' sem contexto)."""
    if rotulo:
        texto(slide, x - rotulo_w - Inches(0.12), y + diametro / 2 - Inches(0.11), rotulo_w,
              Inches(0.24), rotulo, tamanho=10, cor=CINZA, negrito=True,
              alinhamento=PP_ALIGN.RIGHT, fonte=FONTE, espacamento_letras=0.4, wrap=False)
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
                       wrap=False, cor_destaque=VERMELHO, cor_texto_destaque=BRANCO,
                       tamanho=13.5, tamanho_cabecalho=13):
    """Tabela nativa pptx: cabecalho preto, linha destacada na cor_destaque."""
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
        _formatar_celula(tabela.cell(0, c), titulo_col, True, BRANCO, PRETO, tamanho=tamanho_cabecalho,
                          alinhamento=(PP_ALIGN.LEFT if c == 0 else PP_ALIGN.CENTER))

    for r, linha in enumerate(linhas, start=1):
        destaque = linha[0] == linha_destaque
        cor_fundo = cor_destaque if destaque else (QUASE_BRANCO if r % 2 else BRANCO)
        cor_texto = cor_texto_destaque if destaque else PRETO
        for c, valor in enumerate(linha):
            _formatar_celula(
                tabela.cell(r, c), str(valor), destaque, cor_texto, cor_fundo, tamanho=tamanho,
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
cabecalho_padrao(s, 2, "O Problema",
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
cabecalho_padrao(s, 3, "Objetivo",
                 "Prever quem está na informalidade e entender quem ela mais afeta")
objetivos = [
    ("01", "Prever", "Se um trabalhador está na informalidade, a partir de características observáveis (escolaridade, setor, região...)."),
    ("02", "Explicar", "Quais fatores mais pesam nessa condição, não só o quê, mas por quê."),
    ("03", "Medir equidade", "Se o modelo trata igualmente todos os grupos, gênero e raça, não só a média geral."),
]
largura_card = Inches(3.72)
for i, (num, tit, corpo) in enumerate(objetivos):
    x = Inches(0.75) + i * (largura_card + Inches(0.28))
    caixa = retangulo(s, x, Inches(2.35), largura_card, Inches(3.7), QUASE_BRANCO,
                       linha=True, cor_linha=CINZA_BORDA, arredondado=True)
    caixa.line.width = Pt(1.5)
    badge_numero(s, x + Inches(0.3), Inches(2.62), num)
    retangulo(s, x + Inches(0.36), Inches(3.38), Inches(0.5), Pt(3), VERMELHO)
    texto(s, x + Inches(0.3), Inches(3.72), largura_card - Inches(0.6), Inches(0.5),
          tit, tamanho=18, cor=PRETO, negrito=True, fonte=FONTE)
    texto(s, x + Inches(0.3), Inches(4.28), largura_card - Inches(0.6), Inches(1.6),
          corpo, tamanho=13, cor=PRETO, fonte=FONTE, espacamento=1.25)
rodape(s, 3)

# ============================================================ 4. OS DADOS
s = nova_slide(BRANCO)
cabecalho_padrao(s, 4, "Os Dados",
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
    retangulo(s, x, Inches(2.3), w_stat, Inches(2.0), QUASE_BRANCO,
              linha=True, cor_linha=CINZA_BORDA, arredondado=True)
    texto(s, x, Inches(2.6), w_stat, Inches(0.85), valor, tamanho=36, cor=VERMELHO,
          negrito=True, alinhamento=PP_ALIGN.CENTER, fonte=FONTE)
    texto(s, x + Inches(0.1), Inches(3.48), w_stat - Inches(0.2), Inches(0.75), legenda,
          tamanho=13.5, cor=CINZA, negrito=True, alinhamento=PP_ALIGN.CENTER, fonte=FONTE,
          espacamento=1.15)
texto(s, Inches(0.75), Inches(4.75), Inches(11.6), Inches(1.6), [
    "• Microdados de largura fixa, exatamente como publicados pelo IBGE",
    "• Cada período baixado com retentativa automática",
    "• Validado por manifesto (checksum SHA-256 + contagem de linhas) antes de qualquer análise",
], tamanho=16.5, cor=PRETO, fonte=FONTE, espacamento=1.3)

# ============================================================ 5. PREPARAÇÃO
s = nova_slide(BRANCO)
s5 = s
cabecalho_padrao(s, 5, "Preparação dos Dados",
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
    retangulo(s, x, y_camada, w_camada, h_camada, QUASE_BRANCO,
              linha=True, cor_linha=CINZA_BORDA, arredondado=True)
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
retangulo(s, x_esq, y_row2, w_col, h_row2, QUASE_BRANCO,
          linha=True, cor_linha=CINZA_BORDA, arredondado=True)
retangulo(s, x_esq, y_row2 + Inches(0.12), Inches(0.06), h_row2 - Inches(0.24), VERMELHO,
          arredondado=True)
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
retangulo(s, x_dir, y_row2, w_col, h_row2, ROSA_FUNDO,
          linha=True, cor_linha=CINZA_BORDA, arredondado=True)
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
cabecalho_padrao(s, 6, "Análise Exploratória",
                 "Tamanho do negócio e vínculo temporário são os sinais mais fortes")
imagem_centrada(s, ASSETS_GRAFICOS / "fig_eda_top_features.png", Inches(0.85), Inches(2.15), w=Inches(7.6))
texto(s, Inches(8.85), Inches(2.35), Inches(3.7), Inches(0.4), "FORÇA DE ASSOCIAÇÃO", tamanho=12,
      cor=CINZA, negrito=True, fonte=FONTE, espacamento_letras=1.2)
texto(s, Inches(8.85), Inches(2.75), Inches(3.7), Inches(0.5), "com a condição de informalidade",
      tamanho=12.5, cor=CINZA, fonte=FONTE, espacamento=1.15)
texto(s, Inches(8.85), Inches(3.5), Inches(3.75), Inches(0.4), "V de Cramér / ponto-bisserial",
      tamanho=11, cor=CINZA, fonte=FONTE)
retangulo(s, Inches(8.85), Inches(4.0), Inches(3.75), Inches(1.85), QUASE_BRANCO,
          linha=True, cor_linha=CINZA_BORDA, arredondado=True)
retangulo(s, Inches(8.85), Inches(4.12), Inches(0.06), Inches(1.61), VERMELHO, arredondado=True)
texto(s, Inches(9.13), Inches(4.15), Inches(3.3), Inches(0.4), "O TRABALHADOR INFORMAL, EM NÚMEROS",
      tamanho=11.5, cor=PRETO, negrito=True, fonte=FONTE, espacamento=1.05)
texto(s, Inches(9.13), Inches(4.58), Inches(3.3), Inches(1.2), [
    "53% não concluíram o ensino médio (25% entre os formais)",
    "35% moram no Nordeste (20% entre os formais)",
    "Renda mediana 42% menor: R$ 1.400 x R$ 2.400",
], tamanho=10.8, cor=PRETO, fonte=FONTE, espacamento=1.25)
retangulo(s, Inches(0.75), Inches(5.92), Inches(11.83), Inches(0.98), QUASE_BRANCO,
          linha=True, cor_linha=CINZA_BORDA, arredondado=True)
texto(s, Inches(1.0), Inches(6.02), Inches(9.8), Inches(0.25),
      "DECISÃO DE VARIÁVEIS, A MAIS DIFÍCIL DO PROJETO", tamanho=10.5, cor=VERMELHO,
      negrito=True, fonte=FONTE, espacamento_letras=0.7)
texto(s, Inches(1.0), Inches(6.28), Inches(11.3), Inches(0.6), [
    "• 22 das 420 variáveis da PNAD entraram no pré-processamento por relevância direta; 15 seguiram para o modelo",
    "• Sexo e raça entraram por escopo obrigatório do projeto (RF-06), não por força estatística",
    "• Fora do modelo: variáveis que constroem o próprio alvo, renda (vazamento circular) e chaves de deduplicação",
], tamanho=9.8, cor=PRETO, fonte=FONTE, espacamento=1.2)

# ============================================================ 7. A SOLUÇÃO
# Diagrama de arquitetura de dados de verdade (referencia: pills marcando
# cada zona + icones conectados por setas + logo real só nas pontas onde
# ha uma ferramenta de fato nomeada) — não mais caixas genericas de
# passo-a-passo. Pills em VERMELHO (identidade do projeto); DOURADO fica
# reservado só pro destaque estrategico da etapa MODELO (assunto dos
# proximos slides). Claude/AIOX aparecem so como nota leve de
# "auxiliares" (embaixo do Python, nao mais uma faixa/explicacao grande).
s = nova_slide(BRANCO)
cabecalho_padrao(s, 7, "A Solução", "Um pipeline completo, do dado bruto à predição")

x0 = Inches(0.75)
w_a, w_c, gap_zona = Inches(1.7), Inches(2.75), Inches(0.55)
w_b = Inches(11.83) - w_a - w_c - 2 * gap_zona
x_b = x0 + w_a + gap_zona
x_c = x_b + w_b + gap_zona
y_pill, h_pill = Inches(1.95), Inches(0.42)
y_icone, h_icone = Inches(2.55), Inches(0.6)
y_rotulo, h_rotulo = Inches(3.22), Inches(0.25)
y_seta = Inches(2.71)
pad = Inches(0.15)
y_card, h_card = Inches(1.8), Inches(1.82)

# --- blocos de fundo (cada zona vira um "card", nao fica so jogado no
# branco) — mesma linguagem visual (fundo + borda) do resto do deck
for x_zona, w_zona in ((x0, w_a), (x_b, w_b), (x_c, w_c)):
    retangulo(s, x_zona - pad, y_card, w_zona + 2 * pad, h_card, QUASE_BRANCO,
              linha=True, cor_linha=CINZA_BORDA, arredondado=True)
# setas conectando os 3 cards, no vao entre eles
seta_horizontal(s, x0 + w_a + pad + Inches(0.02), y_seta, gap_zona - 2 * pad - Inches(0.04), Inches(0.28))
seta_horizontal(s, x_b + w_b + pad + Inches(0.02), y_seta, gap_zona - 2 * pad - Inches(0.04), Inches(0.28))

# --- zona A: fonte dos dados
pill_zona(s, x0, y_pill, w_a, h_pill, "Fonte")
logo_ibge = imagem_centrada(s, LOGO_IBGE, x0 + Inches(0.5), Inches(2.6), h=Inches(0.5))
texto(s, x0, y_rotulo, w_a, h_rotulo, "PNAD Contínua", tamanho=9.5, cor=PRETO, negrito=True,
      alinhamento=PP_ALIGN.CENTER, fonte=FONTE)

# --- zona B: pipeline Python — Bronze/Silver/Gold (dados) + EDA + Modelo/Resultados
# (destaque vermelho cobre Modelo+Resultados: sao os "proximos 3 slides"
# mencionados na transicao abaixo, junto com a Interpretacao)
retangulo(s, x_b, y_pill, w_b, h_pill, PRETO, arredondado=True)
logo_python_pill = imagem_centrada(s, LOGO_PYTHON, x_b + Inches(0.18), y_pill + Inches(0.06), h=Inches(0.3))
texto(s, x_b + Inches(0.62), y_pill, w_b - Inches(0.75), h_pill, "Pipeline Python",
      tamanho=11.5, cor=BRANCO, negrito=True, fonte=FONTE, espacamento_letras=0.3,
      ancora=MSO_ANCHOR.MIDDLE)

slot_w = w_b / 5
etapas_dados = [
    ("BRONZE", RGBColor(0xCD, 0x7F, 0x32)),
    ("SILVER", RGBColor(0xB8, 0xB8, 0xB8)),
    ("GOLD", DOURADO),
    ("EDA", PRETO),
]
for i, (nome, cor_icone) in enumerate(etapas_dados):
    x_slot = x_b + i * slot_w
    icone_x = x_slot + (slot_w - Inches(0.45)) / 2
    if nome == "EDA":
        icone_lupa(s, icone_x, y_icone, Inches(0.45), Inches(0.55), cor_icone)
    else:
        icone_cilindro(s, icone_x, y_icone, Inches(0.45), Inches(0.55), cor_icone)
    texto(s, x_slot, y_rotulo, slot_w, h_rotulo, nome, tamanho=9.5, cor=PRETO, negrito=True,
          alinhamento=PP_ALIGN.CENTER, fonte=FONTE)
    if i < len(etapas_dados) - 1:
        seta_horizontal(s, x_b + (i + 1) * slot_w - Inches(0.13), y_seta, Inches(0.26), Inches(0.28))

# azulejo vermelho do Modelo — centralizado no ultimo slot. A seta ate ele
# e calculada a partir do proprio tile_x (nao da formula generica de
# fronteira de slot) pra nunca encostar/ficar por baixo do azulejo — bug
# da rodada anterior, onde a seta ficava coberta pelo retangulo do tile.
tile_w, tile_h = Inches(1.02), Inches(1.08)
tile_x = x_b + 4 * slot_w + (slot_w - tile_w) / 2
tile_y = y_icone - Inches(0.08)
seta_horizontal(s, x_b + 4 * slot_w - Inches(0.26), y_seta, tile_x - (x_b + 4 * slot_w - Inches(0.26))
                 - Inches(0.06), Inches(0.28))
retangulo(s, tile_x, tile_y, tile_w, tile_h, VERMELHO, arredondado=True)
icone_barras(s, tile_x + (tile_w - Inches(0.5)) / 2, y_icone, Inches(0.5), h_icone, BRANCO)
texto(s, x_b + 4 * slot_w, y_rotulo, slot_w, h_rotulo, "MODELO", tamanho=9.5, cor=BRANCO,
      negrito=True, alinhamento=PP_ALIGN.CENTER, fonte=FONTE)

# --- zona C: entrega = os resultados (nao um "boletim" generico separado)
pill_zona(s, x_c, y_pill, w_c, h_pill, "Entrega")
icone_check(s, x_c + (w_c - Inches(0.6)) / 2, y_icone - Inches(0.05), Inches(0.6), Inches(0.6),
            cor_fundo=VERMELHO, cor_check=BRANCO)
texto(s, x_c, y_rotulo, w_c, h_rotulo, "Resultados", tamanho=9.5, cor=PRETO, negrito=True,
      alinhamento=PP_ALIGN.CENTER, fonte=FONTE)

texto(s, x0, Inches(3.75), Inches(11.83), Inches(0.3),
      "pandas · scikit-learn · SHAP · classes `Etapa` → `Pipeline`, cada etapa executável "
      "isoladamente ou em cadeia.", tamanho=11.5, cor=PRETO, fonte=FONTE,
      ancora=MSO_ANCHOR.MIDDLE)

# --- nota leve: Claude/AIOX so como auxiliares no desenvolvimento (nao mais
# uma faixa/explicacao grande — pedido do usuario, o foco aqui e o processo)
imagem_centrada(s, LOGO_CLAUDE, x0, Inches(4.08), h=Inches(0.28))
texto_com_links(s, x0 + Inches(0.4), Inches(4.06), Inches(9), Inches(0.32), [
    ("Auxiliares no desenvolvimento: ", None),
    ("Claude Code", "https://claude.com/claude-code"),
    (" · ", None),
    ("framework AIOX", "https://github.com/SynkraAI/aiox-core"),
], tamanho=10.5, cor=CINZA, ancora=MSO_ANCHOR.MIDDLE)

# --- resumo curto da arquitetura, em bullets (nao mais uma chamada pro
# proximo slide)
texto(s, x0, Inches(4.75), Inches(11.83), Inches(1.3), [
    "• Dados brutos do IBGE, tratados em três camadas — Bronze, Silver, Gold",
    "• Análise exploratória revela os sinais mais fortes de informalidade",
    "• Modelo treinado, validado e interpretável via SHAP",
], tamanho=13.5, cor=PRETO, fonte=FONTE, espacamento=1.35)

# ============================================================ 8. CONSTRUÇÃO DO MODELO
s = nova_slide(BRANCO)
cabecalho_padrao(s, 8, "Modelagem",
                 "Três modelos avaliados sob a mesma regra de validação")
modelos_txt = [
    ("Regressão Logística", ["• Baseline interpretável", "• Sanity check dos outros dois modelos"]),
    ("Random Forest", ["• Robusto, custo controlado por amostra/árvore", "• O mais lento dos três em treino"]),
    ("HistGradientBoosting", ["• Lida nativamente com categórica e nulo", "• O mais rápido dos dois modelos fortes"]),
]
w_m = Inches(3.72)
for i, (tit, corpo) in enumerate(modelos_txt):
    x = Inches(0.75) + i * (w_m + Inches(0.28))
    card(s, x, Inches(2.3), w_m, Inches(2.15), tit, corpo, tam_titulo=15.5, tam_corpo=13)

# --- split temporal: virou uma linha do tempo visual (destaque pedido pelo
# professor, ja que essa caixa mostra a estrategia de validacao do projeto)
y_split = Inches(4.75)
h_split = Inches(1.7)
retangulo(s, Inches(0.75), y_split, Inches(11.83), h_split, ROSA_FUNDO,
          linha=True, cor_linha=CINZA_BORDA, arredondado=True)
texto(s, Inches(1.05), y_split + Inches(0.2), Inches(2.5), Inches(0.9), "SPLIT\nTEMPORAL", tamanho=17,
      cor=VERMELHO_ESCURO, negrito=True, fonte=FONTE, espacamento=1.05)

x_bar, y_bar = Inches(3.75), y_split + Inches(0.3)
w_bar, h_bar = Inches(7.9), Inches(0.55)
w_treino = Emu(int(w_bar * 2 / 3))
w_teste = w_bar - w_treino
retangulo(s, x_bar, y_bar, w_treino, h_bar, PRETO)
retangulo(s, x_bar + w_treino, y_bar, w_teste, h_bar, VERMELHO)
texto(s, x_bar, y_bar, w_treino, h_bar, "2023 – 2024  ·  TREINO", tamanho=12.5, cor=BRANCO,
      negrito=True, alinhamento=PP_ALIGN.CENTER, fonte=FONTE, ancora=MSO_ANCHOR.MIDDLE)
texto(s, x_bar + w_treino, y_bar, w_teste, h_bar, "2025 · TESTE", tamanho=12.5, cor=BRANCO,
      negrito=True, alinhamento=PP_ALIGN.CENTER, fonte=FONTE, ancora=MSO_ANCHOR.MIDDLE)

texto(s, x_bar, y_bar + Inches(0.7), w_bar, Inches(0.6),
      "Nunca ao acaso: a PNAD é um painel rotativo, e um split aleatório vazaria a mesma "
      "pessoa entre treino e teste.",
      tamanho=13.5, cor=PRETO, fonte=FONTE, espacamento=1.25, ancora=MSO_ANCHOR.MIDDLE)

# ============================================================ 9. INTERPRETABILIDADE / EQUIDADE
s = nova_slide(BRANCO)
cabecalho_padrao(s, 9, "Interpretabilidade e Equidade",
                 "O modelo é interpretável, e isso expôs uma desigualdade real")
imagem_centrada(s, ASSETS_GRAFICOS / "fig_shap_top_features.png", Inches(0.75), Inches(2.2), w=Inches(6.9))
texto(s, Inches(0.85), Inches(5.75), Inches(6.6), Inches(0.5),
      "SHAP: o que mais pesou na decisão do modelo campeão", tamanho=11.5, cor=CINZA,
      fonte=FONTE, espacamento=1.1)
imagem_centrada(s, ASSETS_GRAFICOS / "fig_equidade.png", Inches(8.1), Inches(2.15), h=Inches(3.15))
retangulo(s, Inches(7.95), Inches(5.55), Inches(4.65), Inches(1.35), ROSA_FUNDO,
          linha=True, cor_linha=CINZA_BORDA, arredondado=True)
texto(s, Inches(8.2), Inches(5.72), Inches(4.2), Inches(1.1),
      "Recall 12 p.p. menor para o grupo Amarelos (n = 4.214): um sinal de atenção real, "
      "registrado no Model Card, não motivo para descartar o modelo.",
      tamanho=12, cor=VERMELHO_ESCURO, negrito=True, fonte=FONTE, espacamento=1.25)

# ============================================================ 10. RESULTADOS (mais importante)
s = nova_slide(BRANCO)
s10 = s
cabecalho_padrao(s, 10, "Resultados",
                 "92,6% de AUC-ROC no ano que o modelo nunca viu")
cabecalhos_tab = ["Modelo", "Accuracy", "Precision", "Recall", "F1", "AUC-ROC", "Tempo (s)"]
linhas_tab = [
    ["HistGradientBoosting", "0.8474", "0.8384", "0.8360", "0.8372", "0.9261", "178.70"],
    ["Random Forest", "0.8355", "0.8123", "0.8446", "0.8281", "0.9166", "2171.53"],
    ["Regressão Logística", "0.8259", "0.7995", "0.8397", "0.8191", "0.9011", "41.67"],
]
tabela10 = tabela_comparacao(
    s, Inches(0.75), Inches(1.95), Inches(11.83), Inches(1.4), cabecalhos_tab, linhas_tab,
    largura_col0=Inches(2.6), linha_destaque="HistGradientBoosting", tamanho=15, tamanho_cabecalho=13.5,
)
# realces pontuais em dourado (fonte, nao a celula) — pedido do usuario: o
# tempo do Random Forest (é o lento), o AUC do campeao e o precision da
# Regressao Logistica. cabecalhos_tab = [Modelo,Accuracy,Precision,Recall,F1,AUC-ROC,Tempo]
for r, c in ((1, 5), (2, 6), (3, 2)):
    run_destaque = tabela10.cell(r, c).text_frame.paragraphs[0].runs[0]
    run_destaque.font.color.rgb = DOURADO
    run_destaque.font.bold = True

# texto reduzido a um resumo curto: numa TV/projetor o grafico e que
# precisa chamar atencao, nao um bloco de texto competindo com ele
texto(s, Inches(0.75), Inches(3.55), Inches(6.6), Inches(0.4), "Campeão: HistGradientBoosting",
      tamanho=15, cor=PRETO, negrito=True, fonte=FONTE)
texto(s, Inches(0.75), Inches(4.02), Inches(6.6), Inches(1.6), [
    "• Acerta 84 de cada 100 informais reais, sem overfitting",
    "• O mais rápido dos dois modelos fortes: 3 min contra 36 min do Random Forest",
], tamanho=14, cor=PRETO, negrito=True, fonte=FONTE, espacamento=1.3)
imagem_centrada(s, ASSETS_GRAFICOS / "fig_roc.png", Inches(7.75), Inches(3.5), h=Inches(3.4))

# ============================================================ 11. CONCLUSÃO GERAL
# Conclusao sobre TODO o trabalho (problema + pipeline + modelo), nao so o
# modelo — 3 blocos lado a lado no lugar dos 2 anteriores.
s = nova_slide(BRANCO)
cabecalho_padrao(s, 11, "Conclusão Geral",
                 "Sobre a informalidade, sobre o processo, e se o objetivo foi atingido")
retangulo(s, Inches(0.75), Inches(1.95), Inches(11.83), Inches(0.95), ROSA_FUNDO,
          linha=True, cor_linha=CINZA_BORDA, arredondado=True)
texto(s, Inches(1.05), Inches(1.95), Inches(11.25), Inches(0.95),
      "A informalidade não é um detalhe estatístico: é quase metade do mercado de trabalho "
      "brasileiro, distribuída de forma desigual entre região, setor e cor. Foi esse padrão "
      "que motivou todo o projeto.",
      tamanho=13.5, cor=VERMELHO_ESCURO, negrito=True, fonte=FONTE, espacamento=1.2,
      ancora=MSO_ANCHOR.MIDDLE)

y_col, h_col, w_col, gap_col = Inches(3.15), Inches(3.3), Inches(3.75), Inches(0.29)
x_a = Inches(0.75)
x_b = x_a + w_col + gap_col
x_c = x_b + w_col + gap_col

# Cada card agora tem um "gancho" visual (estatistica grande) em vez de
# so texto corrido — pesquisa rapida sobre slides de conclusao confirma:
# alto contraste, 1 estatistica marcante por bloco, bullets escaneaveis
# com o ponto principal em negrito (quem so bate o olho ja entende).


def _caixa_conclusao(x, cor_titulo, titulo_txt):
    retangulo(s, x, y_col, w_col, h_col, QUASE_BRANCO, linha=True, cor_linha=CINZA_BORDA,
              arredondado=True)
    retangulo(s, x, y_col + Inches(0.12), Inches(0.06), h_col - Inches(0.24), cor_titulo,
              arredondado=True)
    texto(s, x + Inches(0.28), y_col + Inches(0.22), w_col - Inches(0.5), Inches(0.3),
          titulo_txt, tamanho=13, cor=PRETO, negrito=True, fonte=FONTE, espacamento_letras=0.4)


def _stat_card(x, valor, cor_valor, legenda):
    texto(s, x + Inches(0.28), y_col + Inches(0.58), w_col - Inches(0.5), Inches(0.48),
          valor, tamanho=30, cor=cor_valor, negrito=True, fonte=FONTE_DESTAQUE)
    texto(s, x + Inches(0.28), y_col + Inches(1.06), w_col - Inches(0.5), Inches(0.42),
          legenda, tamanho=10.3, cor=PRETO, fonte=FONTE, espacamento=1.15)


_caixa_conclusao(x_a, VERMELHO, "SOBRE A INFORMALIDADE")
_stat_card(x_a, "47,6%", VERMELHO, "dos ocupados analisados estão na informalidade")
bullets_destaque(s, x_a + Inches(0.28), y_col + Inches(1.52), w_col - Inches(0.5), Inches(1.65), [
    ("Concentrada ", "em quem não tem instrução, na agropecuária e no Nordeste"),
    ("Renda 42% menor", " — é consequência, não causa"),
], tamanho=11, espacamento=1.3)

_caixa_conclusao(x_b, VERMELHO_ESCURO, "DIFICULDADES DO PROJETO")
_stat_card(x_b, "5,7M", VERMELHO_ESCURO, "linhas na base bruta — volume que já era um desafio de engenharia")
bullets_destaque(s, x_b + Inches(0.28), y_col + Inches(1.52), w_col - Inches(0.5), Inches(1.65), [
    ("Volume: ", "trabalhar com quase 6 milhões de linhas exigiu cuidado de performance em cada etapa"),
    ("Seleção de variáveis: ", "decidir quais das 420 podiam entrar, já pensando no modelo, sem colar a resposta"),
    ("Peso amostral: ", "o desenho complexo da PNAD ainda não entrou na avaliação"),
], tamanho=10.5, espacamento=1.25)

_caixa_conclusao(x_c, VERMELHO, "O OBJETIVO FOI ATINGIDO?")
_stat_card(x_c, "3 de 3", VERMELHO, "objetivos atingidos: prever, explicar, medir equidade")
bullets_destaque(s, x_c + Inches(0.28), y_col + Inches(1.52), w_col - Inches(0.5), Inches(1.65), [
    ("Prever — ", "AUC 0,93 no ano que o modelo nunca viu"),
    ("Explicar — ", "SHAP confirma os mesmos fatores da EDA"),
    ("Medir equidade — ", "sim, e revelou um problema real"),
], tamanho=11, espacamento=1.25, marcador="✓ ")

# ============================================================ 12. ENCERRAMENTO
s = nova_slide(VERMELHO)
logo(s, "branco_h", x=Inches(0.75), y=Inches(0.6), largura=Inches(1.6))
texto(s, Inches(0.75), Inches(2.7), Inches(10), Inches(1.3), "Obrigado.", tamanho=58, cor=BRANCO,
      negrito=True, fonte=FONTE)
texto(s, Inches(0.75), Inches(3.85), Inches(9), Inches(0.7), "Perguntas?", tamanho=22, cor=BRANCO,
      fonte=FONTE)
linha_divisoria(s, Inches(0.75), Inches(5.5), Inches(4.2), cor=RGBColor(0xFF, 0xB3, 0xC0))
texto(s, Inches(0.75), Inches(5.7), Inches(9), Inches(1.2), INTEGRANTES, tamanho=13.5, cor=BRANCO,
      fonte=FONTE, espacamento=1.35)
texto_com_links(s, LARGURA - Inches(4.4), ALTURA - Inches(0.6), Inches(3.8), Inches(0.35), [
    ("github.com/gui-ramon/pipeline-hands-on-engenharia-de-dados",
     "https://github.com/gui-ramon/pipeline-hands-on-engenharia-de-dados"),
], tamanho=9.5, cor=RGBColor(0xFF, 0xD8, 0xDD), alinhamento=PP_ALIGN.RIGHT)

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
x_fora, y_fora, w_fora, h_fora = Inches(8.35), Inches(1.95), Inches(4.25), Inches(4.55)
card(s, x_fora, y_fora, w_fora, h_fora, "O que ficou de fora, e por quê", "",
     tam_titulo=13.5)
bullets_destaque(s, x_fora + Inches(0.28), y_fora + Inches(0.75), w_fora - Inches(0.5),
                  h_fora - Inches(0.95), [
    ("Já diz a resposta: ", "tem variável que já diz se a pessoa é informal. Usar ela seria trapaça"),
    ("Consequência, não causa: ", "a renda ficou de fora por isso"),
    ("Só identifica: ", "tem código que só serve pra achar pessoa ou domicílio, não diz nada sobre o problema"),
    ("Coisa da pesquisa: ", "ano, trimestre e peso amostral não são da pessoa"),
    ("Quase não muda nada: ", "ir à escola quase não muda a chance de ser informal"),
], tamanho=12.5, espacamento=1.25)

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

# ------------------------------------------------------------ E. Gráficos da EDA
# Layout segue "storytelling with data": titulo de acao (a conclusao, nao um
# rotulo descritivo), 1 grafico so com so os extremos coloridos e o resto em
# cinza (preattentive attributes — Knaflic), e os 2 achados mais fortes
# repetidos como "big numbers" ao lado (formula McKinsey: destaque + texto
# com a implicacao). Ver referencias no rodape do roteiro, secao 5.
s = nova_slide(BRANCO)
s17 = s
cabecalho_apoio(s, "ANÁLISE EXPLORATÓRIA",
                "Sem instrução e agropecuária concentram a informalidade")
marcar_oculto(s)

texto(s, Inches(0.75), Inches(1.6), Inches(11.83), Inches(0.32),
      "Cada barra mostra quantas vezes a categoria é mais comum num grupo do que no outro "
      "(escala logarítmica). Cor só nos 3 casos mais extremos — o resto fica em cinza, perto "
      "do equilíbrio (linha central = 1x).",
      tamanho=10.5, cor=CINZA, fonte=FONTE, espacamento=1.15)

imagem_centrada(s, ASSETS_GRAFICOS / "fig_eda_indice.png", Inches(0.75), Inches(2.0), w=Inches(6.85))

x_lat = Inches(7.95)
w_lat = Inches(4.63)

retangulo(s, x_lat, Inches(1.95), w_lat, Inches(1.4), ROSA_FUNDO, arredondado=True)
texto(s, x_lat + Inches(0.25), Inches(2.06), Inches(2.0), Inches(0.7), "5,0x",
      tamanho=38, cor=VERMELHO, negrito=True, fonte=FONTE)
texto(s, x_lat + Inches(0.25), Inches(2.75), w_lat - Inches(0.5), Inches(0.55),
      "mais informalidade entre quem não tem instrução (5% dos informais, 1% dos formais)",
      tamanho=10.5, cor=PRETO, fonte=FONTE, espacamento=1.15)

retangulo(s, x_lat, Inches(3.5), w_lat, Inches(1.4), ROSA_FUNDO, arredondado=True)
texto(s, x_lat + Inches(0.25), Inches(3.61), Inches(2.0), Inches(0.7), "4,0x",
      tamanho=38, cor=VERMELHO, negrito=True, fonte=FONTE)
texto(s, x_lat + Inches(0.25), Inches(4.3), w_lat - Inches(0.5), Inches(0.55),
      "mais informalidade na agropecuária, pesca e aquicultura (24% x 6% entre os formais)",
      tamanho=10.5, cor=PRETO, fonte=FONTE, espacamento=1.15)

retangulo(s, x_lat, Inches(4.95), w_lat, Inches(2.0), QUASE_BRANCO, arredondado=True)
texto(s, x_lat + Inches(0.25), Inches(5.05), Inches(3.5), Inches(0.22), "RENDA MEDIANA",
      tamanho=10, cor=CINZA, negrito=True, fonte=FONTE, espacamento_letras=0.6)
imagem_centrada(s, ASSETS_GRAFICOS / "fig_eda_renda.png", x_lat + Inches(0.25), Inches(5.28), w=Inches(3.9))
texto(s, x_lat + Inches(0.25), Inches(6.62), w_lat - Inches(0.5), Inches(0.32),
      "Informal ganha 42% menos. Não entra no modelo: é consequência da informalidade, não causa.",
      tamanho=10, cor=PRETO, fonte=FONTE, espacamento=1.15)

# ======================================================================
# BOTÕES "+" — atalho clicável dos slides principais para os ocultos
# ======================================================================

# slide 5: funil (esquerda) e conceito de informal (direita)
botao_mais(s5, Inches(5.92), Inches(4.3), s13)
botao_mais(s5, Inches(12.04), Inches(4.3), s14)

# slide 6: destaques do trabalhador informal (gráficos da EDA) — decisão de
# variáveis passou a ser sequencial no próprio slide (sem hiperlink pro apêndice)
botao_mais(s6, Inches(12.12), Inches(4.08), s17)

# slide 10: matrizes de confusão
botao_mais(s10, Inches(12.03), Inches(1.5), s16, rotulo="MATRIZES DE CONFUSÃO")

for slide_oculto in (s13, s14, s15, s16, s17):
    botao_casa(slide_oculto)

SAIDA.parent.mkdir(parents=True, exist_ok=True)
prs.save(SAIDA)
n_ocultos = sum(1 for sl in prs.slides if sl._element.get("show") == "0")
print(f"[ok] {SAIDA}  ({len(prs.slides)} slides, {n_ocultos} ocultos)")
