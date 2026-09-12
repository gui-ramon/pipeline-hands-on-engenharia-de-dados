"""Linguagem visual compartilhada pelos boletins HTML do projeto.

Um só lugar para paleta, tipografia, layout e os componentes didáticos
(takeaway no topo, selos de tipo de bloco, réguas, glossário) — para que o
boletim de EDA (`src/analise/relatorios.py`) e o de modelagem
(`src/modelagem/relatorio.py`) pareçam do mesmo projeto numa apresentação.

Cada boletim monta a página com `montar_pagina(titulo, corpo, css_extra)`,
passando em `css_extra` só as regras específicas dele (gráficos próprios,
etc.). Tudo aqui é string de HTML/CSS puro — sem dependência externa, o
arquivo final abre local sem servidor.
"""

from __future__ import annotations

# ---------------------------------------------------------------------
# Folha de estilo base — paleta, tipografia, layout e os componentes
# reutilizados pelos dois boletins. Regras específicas de cada boletim
# entram via `css_extra` em `montar_pagina`.
# ---------------------------------------------------------------------

CSS_BASE = """
  :root{color-scheme:light;--bg:#f2f4f7;--surface:#ffffff;--surface-2:#eaeef3;--ink:#10131a;--ink-2:#454a58;--ink-muted:#767b8a;--border:rgba(16,19,26,.11);--border-strong:rgba(16,19,26,.18);--accent:#2a78d6;--accent-ink:#164a90;--accent-soft-2:rgba(42,120,214,.10);--negative:#c8302f;--aqua:#0f8f63;--roxo:#7c5cbf;--roxo-ink:#5b3fa0;--shadow:0 1px 2px rgba(16,19,26,.04),0 8px 24px -12px rgba(16,19,26,.18)}
  @media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;--bg:#0c0e12;--surface:#15171d;--surface-2:#1b1e26;--ink:#f4f5f7;--ink-2:#c6cad6;--ink-muted:#8b8f9e;--border:rgba(255,255,255,.11);--border-strong:rgba(255,255,255,.20);--accent:#4a90e8;--accent-ink:#bcd8f9;--accent-soft-2:rgba(74,144,232,.12);--negative:#e2726f;--aqua:#35b98a;--roxo:#a98fe0;--roxo-ink:#c7b3ec;--shadow:0 1px 2px rgba(0,0,0,.3),0 8px 24px -12px rgba(0,0,0,.5)}}
  :root[data-theme="dark"]{color-scheme:dark;--bg:#0c0e12;--surface:#15171d;--surface-2:#1b1e26;--ink:#f4f5f7;--ink-2:#c6cad6;--ink-muted:#8b8f9e;--border:rgba(255,255,255,.11);--border-strong:rgba(255,255,255,.20);--accent:#4a90e8;--accent-ink:#bcd8f9;--accent-soft-2:rgba(74,144,232,.12);--negative:#e2726f;--aqua:#35b98a;--roxo:#a98fe0;--roxo-ink:#c7b3ec;--shadow:0 1px 2px rgba(0,0,0,.3),0 8px 24px -12px rgba(0,0,0,.5)}
  :root{--type-comp-for:#c9cfd9;--type-forca:var(--roxo);--type-forca-strong:var(--roxo-ink);--over:#0f8f63;--under:#c8302f}
  @media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--type-comp-for:#39404e}}
  :root[data-theme="dark"]{--type-comp-for:#39404e}
  *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:"Public Sans",system-ui,-apple-system,"Segoe UI",sans-serif;-webkit-font-smoothing:antialiased}
  .wrap{max-width:1120px;margin:0 auto;padding:56px 28px 96px}
  .eyebrow{font-family:"IBM Plex Mono",monospace;font-size:12.5px;letter-spacing:.11em;text-transform:uppercase;color:var(--accent-ink);font-weight:600;display:flex;align-items:center;gap:10px}.eyebrow::before{content:"";width:22px;height:1px;background:var(--accent)}
  h1{font-family:"Fraunces",Georgia,serif;font-weight:480;font-size:clamp(2.1rem,4.4vw,3.4rem);line-height:1.05;letter-spacing:-.015em;margin:18px 0 0}
  h1 em{font-style:italic;font-weight:460;color:var(--accent-ink)}
  .lede{max-width:68ch;font-size:1.09rem;line-height:1.62;color:var(--ink-2);margin:20px 0 0}.lede b{color:var(--ink);font-weight:600}
  .meta-row{margin-top:12px;font-size:.82rem;color:var(--ink-muted);display:flex;gap:20px;flex-wrap:wrap}
  header.top{padding-bottom:8px;border-bottom:1px solid var(--border);margin-bottom:34px}
  .callout{margin-top:28px;border:1px solid var(--border-strong);background:var(--surface-2);border-radius:14px;padding:22px 26px}
  .callout--metodo{border-color:var(--negative)}
  .callout-head{font-family:"IBM Plex Mono",monospace;font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-muted);font-weight:600;margin-bottom:12px}
  .callout ul{margin:0;padding-left:1.15em;display:grid;gap:9px}.callout li{font-size:.965rem;line-height:1.55;color:var(--ink-2)}.callout li b{color:var(--ink);font-weight:600}
  code{font-family:"IBM Plex Mono",monospace;font-size:.88em;background:var(--surface);border:1px solid var(--border);padding:.05em .4em;border-radius:5px;color:var(--ink)}
  .kpis{margin-top:28px;display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:1px;background:var(--border);border:1px solid var(--border);border-radius:14px;overflow:hidden}
  .kpi{background:var(--surface);padding:20px 22px}.kpi-label{font-size:.8rem;color:var(--ink-muted);font-weight:500}
  .kpi-value{font-family:"IBM Plex Mono",monospace;font-variant-numeric:tabular-nums;font-size:1.9rem;font-weight:600;margin-top:6px}.kpi-sub{font-size:.8rem;color:var(--ink-muted);margin-top:3px}
  section.block{margin-top:76px}.sec-head{display:flex;gap:18px;align-items:baseline;margin-bottom:6px}
  .sec-num{font-family:"Fraunces",serif;font-weight:460;font-style:italic;font-size:1.6rem;color:var(--accent-ink);min-width:2ch}
  h2{font-family:"Fraunces",Georgia,serif;font-weight:500;font-size:1.7rem;margin:0}
  .sec-intro{max-width:72ch;color:var(--ink-2);font-size:1rem;line-height:1.62;margin:14px 0 0 calc(2ch + 18px)}
  .panel{margin-top:26px;margin-left:calc(2ch + 18px);background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:26px 28px 22px;box-shadow:var(--shadow)}
  .panel-head{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap;margin-bottom:4px}
  .panel-title{font-weight:600;font-size:1rem}.panel-note{font-size:.82rem;color:var(--ink-muted)}.panel-caption{font-size:.86rem;color:var(--ink-muted);margin-top:10px;line-height:1.5}
  .grid-2{display:grid;grid-template-columns:1fr 1fr;gap:22px;margin-left:calc(2ch + 18px);margin-top:26px}
  @media (max-width:760px){.grid-2{grid-template-columns:1fr}.panel,.sec-intro{margin-left:0}}
  table.data{width:100%;border-collapse:collapse;margin-top:12px;font-size:.86rem}
  table.data th,table.data td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--border);font-variant-numeric:tabular-nums}
  table.data th{color:var(--ink-muted);font-weight:600;font-size:.78rem;text-transform:uppercase}
  table.data td.melhor{background:var(--accent-soft-2);color:var(--accent-ink);font-weight:700}
  footer{margin-top:88px;padding-top:26px;border-top:1px solid var(--border);display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap;font-size:.82rem;color:var(--ink-muted);line-height:1.6}
  footer .foot-col{max-width:44ch}
  .takeaway{margin:20px 0 0 calc(2ch + 18px);border-left:3px solid var(--accent);background:var(--surface-2);border-radius:0 12px 12px 0;padding:15px 20px}
  .takeaway-tag{font-family:"IBM Plex Mono",monospace;font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;color:var(--accent-ink);font-weight:600}
  .takeaway p{margin:6px 0 0;font-size:1.06rem;line-height:1.55;color:var(--ink)}.takeaway p b{color:var(--accent-ink)}
  .selo{font-family:"IBM Plex Mono",monospace;font-size:10px;font-weight:600;letter-spacing:.03em;text-transform:uppercase;padding:4px 9px;border-radius:999px;white-space:nowrap;border:1px solid var(--border-strong);color:var(--ink-2);align-self:flex-start}
  .selo--1{background:var(--accent-soft-2);color:var(--accent-ink);border-color:var(--accent)}
  .selo--2{background:var(--accent-soft-2);color:var(--accent-ink)}
  .selo--3{background:linear-gradient(90deg,rgba(200,48,47,.16),rgba(42,120,214,.16))}
  .selo--4{background:rgba(124,92,191,.14);color:var(--type-forca-strong);border-color:var(--type-forca)}
  .selo--5{background:var(--surface-2);color:var(--ink-muted)}
  .selo--6{background:rgba(200,48,47,.1);color:var(--negative);border-color:var(--negative)}
  .hl{margin-top:28px;border:1px solid var(--border-strong);border-radius:16px;overflow:hidden;background:var(--surface)}
  .hl-head{font-family:"IBM Plex Mono",monospace;font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-muted);font-weight:600;padding:16px 22px 4px}
  .hl-tier{padding:12px 22px 16px;border-top:1px solid var(--border)}
  .hl-tier-head{font-weight:700;font-size:.9rem;margin-bottom:7px}
  .hl-tier--ocup .hl-tier-head,.hl-tier--inf .hl-tier-head{color:var(--accent-ink)}
  .hl-tier--inf{background:var(--accent-soft-2)}
  .hl-tier ul{margin:0;padding-left:1.15em;display:grid;gap:6px}
  .hl-tier li{font-size:.95rem;line-height:1.5;color:var(--ink-2)}.hl-tier li b{color:var(--ink)}
  .cards{margin-top:28px;display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px}
  .card{border:1px solid var(--border);border-radius:14px;padding:16px 18px;background:var(--surface);box-shadow:var(--shadow)}
  .card.warn{border-left:3px solid var(--negative)}
  .card-label{font-size:.78rem;color:var(--ink-muted);font-weight:500}
  .card-value{font-family:"IBM Plex Mono",monospace;font-size:1.5rem;font-weight:700;margin-top:5px;color:var(--accent-ink)}
  .card.warn .card-value{color:var(--negative)}
  .card-sub{font-size:.78rem;color:var(--ink-muted);margin-top:3px;line-height:1.4}
  .painel-tk{font-size:.92rem;line-height:1.5;color:var(--ink-2);margin:8px 0 0}.painel-tk b{color:var(--ink)}
  .ler{margin-top:20px;border:1px dashed var(--border-strong);border-radius:14px;padding:20px 24px;background:var(--surface)}
  .ler-head{font-family:"IBM Plex Mono",monospace;font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-muted);font-weight:600}
  .ler-p{font-size:.92rem;color:var(--ink-2);margin:8px 0 14px;line-height:1.5}
  .ler-tipos{display:grid;gap:9px}
  .ler-tipo{display:flex;gap:12px;align-items:center;flex-wrap:wrap;font-size:.9rem;color:var(--ink-2)}
  .ler-nota{font-size:.86rem;color:var(--ink-muted);margin:14px 0 0;line-height:1.5}
  .regua{margin-top:14px}
  .regua-ticks{display:flex;justify-content:space-between;font-family:"IBM Plex Mono",monospace;font-size:10px;color:var(--ink-muted);margin-top:4px}
  .regua-faixas{display:flex;justify-content:space-between;font-size:11px;color:var(--ink-muted);margin-top:2px}
  .regua-frase{font-size:.85rem;color:var(--ink-2);margin:8px 0 0;line-height:1.5}
  .tend{margin-top:12px;font-size:.85rem;padding:8px 12px;border-radius:8px;line-height:1.45}
  .tend--ok{background:rgba(15,143,99,.1);color:var(--aqua)}
  .tend--break{background:rgba(200,48,47,.09);color:var(--negative)}
  .aviso{border-left:3px solid var(--negative);background:rgba(200,48,47,.07);padding:12px 16px;border-radius:0 8px 8px 0;font-size:.88rem;line-height:1.5;color:var(--ink-2);margin:4px 0 6px}
  .aviso b{color:var(--negative)}
  .gloss{margin-top:24px;border:1px solid var(--border);border-radius:12px;padding:0 20px;background:var(--surface)}
  .gloss summary{cursor:pointer;padding:15px 0;font-weight:600;font-size:.94rem}
  .gloss dl{margin:0 0 18px;display:grid;gap:10px}
  .gloss dt{font-weight:700;font-size:.87rem;color:var(--ink)}
  .gloss dd{margin:2px 0 0;font-size:.87rem;line-height:1.5;color:var(--ink-2)}
  @media (max-width:760px){.takeaway{margin-left:0}}
"""

_LINKS_FONTES = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,340..700;'
    '1,9..144,400..600&family=Public+Sans:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@400;500;600'
    '&display=swap" rel="stylesheet">'
)


def montar_pagina(titulo: str, corpo: str, css_extra: str = "") -> str:
    """Envelopa o corpo do boletim: `<title>`, fontes, CSS (base + extra) e
    o container `.wrap`. `css_extra` são as regras específicas do boletim.
    """
    return (f"<title>{titulo}</title>\n{_LINKS_FONTES}\n"
            f"<style>{CSS_BASE}{css_extra}</style>\n"
            f'<div class="wrap">\n{corpo}\n</div>\n')


def takeaway(texto: str, rotulo: str = "Em uma frase") -> str:
    """Frase-resumo em destaque, em linguagem humana, ANTES do gráfico."""
    return f'<div class="takeaway"><span class="takeaway-tag">{rotulo}</span><p>{texto}</p></div>'


def selo(label: str, variante: int) -> str:
    """Etiqueta de tipo de bloco no canto do painel. `variante` 1-6 escolhe
    a cor (1 azul-forte, 2 azul-suave, 3 gradiente, 4 roxo, 5 neutro, 6
    alerta) — o significado é dado pelo `label`, próprio de cada boletim.
    """
    return f'<span class="selo selo--{variante}">{label}</span>'


def callout(titulo: str, itens: list[str], variante: str | None = None) -> str:
    cls = f" callout--{variante}" if variante else ""
    lis = "".join(f"<li>{i}</li>" for i in itens)
    return f'<div class="callout{cls}"><div class="callout-head">{titulo}</div><ul>{lis}</ul></div>'


def cards(itens: list[dict]) -> str:
    """Fileira de cartões de destaque. Cada item: {label, value, sub,
    warn?} — `warn=True` pinta de alerta (ex.: maior disparidade)."""
    blocos = []
    for c in itens:
        cls = " warn" if c.get("warn") else ""
        blocos.append(
            f'<div class="card{cls}"><div class="card-label">{c["label"]}</div>'
            f'<div class="card-value">{c["value"]}</div>'
            f'<div class="card-sub">{c.get("sub", "")}</div></div>'
        )
    return '<div class="cards">' + "".join(blocos) + "</div>"


def secao(num: str, titulo: str, intro: str, corpo: str) -> str:
    intro_html = f'<p class="sec-intro">{intro}</p>' if intro else ""
    return (f'<section class="block"><div class="sec-head"><span class="sec-num">{num}</span>'
            f"<h2>{titulo}</h2></div>{intro_html}{corpo}</section>")


def glossario(termos: list[tuple[str, str]], titulo: str = "Glossário — o que cada termo significa") -> str:
    itens = "".join(f"<dt>{t}</dt><dd>{d}</dd>" for t, d in termos)
    return f'<details class="gloss"><summary>{titulo}</summary><dl>{itens}</dl></details>'
