"""Regera o boletim de EDA em `dashboard/` sob demanda, sem precisar
rodar o pipeline inteiro.

- Censo da Informalidade: a partir da Gold (mesma lógica de
  `src/analise/analise.py`, que já roda isso automaticamente a cada
  `pipeline.analisar()` — rodar este script só é necessário se você
  quiser regenerar sem reprocessar o resto do pipeline).

Uso:
    python -m scripts.gerar_boletins_eda
"""

from pathlib import Path

import pandas as pd

from src.analise.relatorios import calcular_metricas, renderizar_censo

CAMINHO_GOLD = Path("dados/gold/dados_gold.parquet")
CAMINHO_SILVER = Path("dados/silver/dados_silver.parquet")
CAMINHO_DASHBOARD = Path("dashboard")


def gerar_censo() -> None:
    if not CAMINHO_GOLD.exists():
        print(f"Gold nao encontrada em {CAMINHO_GOLD.resolve()} — rode a transformacao antes.")
        return
    gold = pd.read_parquet(CAMINHO_GOLD)
    silver = pd.read_parquet(CAMINHO_SILVER) if CAMINHO_SILVER.exists() else None
    metricas = calcular_metricas(gold, silver)
    html = renderizar_censo(metricas)
    destino = CAMINHO_DASHBOARD / "censo_informalidade.html"
    destino.write_text(html, encoding="utf-8")
    print(f"Censo atualizado: {destino.resolve()}")


if __name__ == "__main__":
    CAMINHO_DASHBOARD.mkdir(parents=True, exist_ok=True)
    gerar_censo()
