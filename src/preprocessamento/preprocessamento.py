"""Etapa de pré-processamento: seleção de variáveis, tratamento de nulos e
consolidação dos períodos brutos da PNAD Contínua para a camada Silver.

Lê os arquivos de largura fixa gravados pela ingestão (`dados/bronze/<ano>/
PNADC_0<trimestre><ano>.txt`), extrai o subconjunto de 22 variáveis de
conteúdo documentado em `docs/03-dicionario-de-dados.md` (RF-02) mais 4
identificadores únicos de pessoa/domicílio (UPA+V1008+V1014+V2003, usados só
para deduplicar corretamente — não são features), converte códigos em branco
para nulo explícito e concatena todos os períodos disponíveis em um único
dataset (`dados/silver/dados_silver.parquet`).

Não decodifica códigos em rótulos de categoria (ex.: `V2007=1` -> "Homem")
nem aplica a regra de negócio de informalidade — isso fica para uma etapa
futura de enriquecimento e para a Transformação (Gold, RF-03).

Segurança e governança (RNF-07/RNF-08): apenas a lista pré-aprovada de
variáveis é lida do bruto — nenhuma combinação nova que viabilize
reidentificação é introduzida, e nenhum segredo/credencial é usado nesta
etapa.

Observabilidade (RF-07/RNF-05): cada período processado é logado com
contagem de linhas de entrada/saída e nulos por coluna, permitindo
reconciliar Bronze -> Silver.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.etapa import Etapa

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

CAMINHO_BRONZE = Path("dados/bronze")
CAMINHO_SILVER = Path("dados/silver")

# Posição inicial (1-indexada, convenção IBGE/SAS) e tamanho de cada
# variável selecionada — ver docs/03-dicionario-de-dados.md ("Lista
# consolidada"). O offset para pandas.read_fwf é posição - 1.
VARIAVEIS: dict[str, tuple[int, int]] = {
    # Identificação
    "Ano": (1, 4),
    "Trimestre": (5, 1),
    "UF": (6, 2),
    # Identificador único de pessoa/domicílio (UPA+V1008+V1014+V2003, convenção
    # IBGE) — não são features, servem só para deduplicar corretamente (ver
    # `CHAVE_UNICA_REGISTRO`). Sem isso, duas pessoas diferentes que coincidem
    # nas variáveis de conteúdo abaixo seriam descartadas como "duplicata".
    "UPA": (12, 9),
    "V1008": (28, 2),
    "V1014": (30, 2),
    "V2003": (91, 2),
    # Alvo — informalidade (RF-03)
    "VD4009": (417, 2),
    "V4019": (186, 1),
    "VD4012": (423, 1),
    "VD4002": (410, 1),
    # Demográficas
    "V2007": (95, 1),
    "V2010": (107, 1),
    "V2009": (104, 3),
    # Domicílio/família
    "VD2002": (398, 2),
    "VD2003": (400, 2),
    "V1022": (33, 1),
    "V1023": (34, 1),
    # Educação
    "VD3004": (405, 1),
    "V3002": (109, 1),
    # Trabalho
    "VD4010": (419, 2),
    "VD4011": (421, 2),
    "V4018": (180, 1),
    "V4025": (191, 1),
    "V4040": (247, 1),
    "VD4031": (462, 3),
    # Peso amostral
    "V1028": (50, 15),
    # Só EDA (renda) — não usar como feature do modelo (data leakage)
    "VD4016": (427, 8),
    "VD4017": (435, 8),
}

# Colunas de identificação: uma linha sem elas é malformada, não apenas
# "não aplicável" — são descartadas na limpeza (ver `_limpar_dados`).
COLUNAS_IDENTIFICACAO = ("Ano", "Trimestre", "UF")

# Chave única de registro (pessoa dentro de um período) — convenção IBGE
# para identificar univocamente um respondente. Usada para deduplicar de
# verdade (ver `_limpar_dados`); deduplicar pelas 25 colunas inteiras faria
# duas pessoas diferentes, que por coincidência têm o mesmo perfil nas
# variáveis de conteúdo selecionadas, serem tratadas como "duplicata".
CHAVE_UNICA_REGISTRO = ("Ano", "Trimestre", "UPA", "V1008", "V1014", "V2003")

ENCODING_BRONZE = "latin-1"


@dataclass
class ResultadoPeriodoSilver:
    """Resultado do processamento de um período (ano/trimestre) na Silver."""

    ano: int
    trimestre: int
    arquivo: str
    linhas_entrada: int
    linhas_saida: int
    duracao_segundos: float


class Preprocessamento(Etapa):
    """Seleciona variáveis, trata nulos e consolida os períodos da camada
    Bronze em um único dataset na camada Silver (`dados/silver`).
    """

    def __init__(
        self,
        caminho_entrada: Path = CAMINHO_BRONZE,
        caminho_saida: Path = CAMINHO_SILVER,
    ) -> None:
        self.caminho_entrada = Path(caminho_entrada)
        self.caminho_saida = Path(caminho_saida)
        self.resultados: list[ResultadoPeriodoSilver] = []

    def executar(self) -> list[ResultadoPeriodoSilver]:
        """Lê cada período da camada Bronze, seleciona as variáveis, trata
        nulos e grava o dataset consolidado (todos os anos/trimestres) na
        camada Silver.

        Retorna a lista de `ResultadoPeriodoSilver` (também disponível em
        `self.resultados`) — útil para montar um resumo legível no notebook.
        """
        inicio = time.perf_counter()
        arquivos = self._listar_arquivos_bronze()

        logger.info("=" * 70)
        logger.info("PRE-PROCESSAMENTO — INICIO")
        logger.info("Pasta de entrada (Bronze): %s", self.caminho_entrada.resolve())
        logger.info("Periodos encontrados (%d): %s", len(arquivos), [a.name for a in arquivos])
        logger.info("Variaveis selecionadas (%d): %s", len(VARIAVEIS), list(VARIAVEIS))
        logger.info("=" * 70)

        if not arquivos:
            logger.warning(
                "Nenhum arquivo *.txt encontrado em %s — rode a ingestao antes.",
                self.caminho_entrada.resolve(),
            )
            self.resultados = []
            return self.resultados

        self.caminho_saida.mkdir(parents=True, exist_ok=True)

        partes: list[pd.DataFrame] = []
        resultados: list[ResultadoPeriodoSilver] = []
        for indice, arquivo in enumerate(arquivos, start=1):
            logger.info("--- Periodo %d/%d: %s ---", indice, len(arquivos), arquivo.name)
            dados_periodo, resultado = self._processar_periodo(arquivo)
            partes.append(dados_periodo)
            resultados.append(resultado)
        self.resultados = resultados

        dados_consolidados = pd.concat(partes, ignore_index=True)
        self._salvar_silver(dados_consolidados)

        duracao = time.perf_counter() - inicio
        total_entrada = sum(r.linhas_entrada for r in resultados)
        total_saida = sum(r.linhas_saida for r in resultados)
        logger.info("=" * 70)
        logger.info("RESUMO DO PRE-PROCESSAMENTO")
        for r in resultados:
            logger.info(
                "  %dQ%d -> entrada=%-8d saida=%-8d duracao=%.1fs",
                r.ano, r.trimestre, r.linhas_entrada, r.linhas_saida, r.duracao_segundos,
            )
        logger.info(
            "Pre-processamento concluido em %.1fs — linhas: entrada=%d saida=%d (%d descartadas)",
            duracao, total_entrada, total_saida, total_entrada - total_saida,
        )
        logger.info(
            "Arquivo consolidado: %s (%d linhas)",
            (self.caminho_saida / "dados_silver.parquet").resolve(),
            len(dados_consolidados),
        )
        logger.info("=" * 70)
        return self.resultados

    # ------------------------------------------------------------------
    # Período (ano/trimestre)
    # ------------------------------------------------------------------

    def _processar_periodo(self, caminho_txt: Path) -> tuple[pd.DataFrame, ResultadoPeriodoSilver]:
        inicio = time.perf_counter()
        dados_brutos = self._ler_largura_fixa(caminho_txt)
        linhas_entrada = len(dados_brutos)
        dados_limpos = self._limpar_dados(dados_brutos)
        duracao = time.perf_counter() - inicio

        ano = int(dados_limpos["Ano"].iloc[0]) if len(dados_limpos) else 0
        trimestre = int(dados_limpos["Trimestre"].iloc[0]) if len(dados_limpos) else 0
        logger.info(
            "[%s] %d linhas lidas -> %d apos tratamento de nulos, em %.1fs",
            caminho_txt.name, linhas_entrada, len(dados_limpos), duracao,
        )
        resultado = ResultadoPeriodoSilver(
            ano=ano,
            trimestre=trimestre,
            arquivo=caminho_txt.name,
            linhas_entrada=linhas_entrada,
            linhas_saida=len(dados_limpos),
            duracao_segundos=duracao,
        )
        return dados_limpos, resultado

    # ------------------------------------------------------------------
    # Leitura / limpeza
    # ------------------------------------------------------------------

    def _listar_arquivos_bronze(self) -> list[Path]:
        """Lista os arquivos de microdados (.txt) da Bronze, um por período,
        ignorando manifestos (`.manifest.json`) e a pasta `documentacao/`.
        """
        if not self.caminho_entrada.exists():
            return []
        return sorted(self.caminho_entrada.glob("*/PNADC_*.txt"))

    @staticmethod
    def _ler_largura_fixa(caminho_txt: Path) -> pd.DataFrame:
        """Lê o arquivo de largura fixa extraindo apenas as colunas de
        `VARIAVEIS`, sem decodificar categorias.
        """
        nomes = list(VARIAVEIS)
        colspecs = [(pos - 1, pos - 1 + tamanho) for pos, tamanho in VARIAVEIS.values()]
        return pd.read_fwf(
            caminho_txt,
            colspecs=colspecs,
            names=nomes,
            dtype=str,
            encoding=ENCODING_BRONZE,
        )

    def _limpar_dados(self, dados: pd.DataFrame) -> pd.DataFrame:
        """Converte campos em branco em nulo explícito, converte as colunas
        para numérico e descarta linhas malformadas (identificação nula) ou
        duplicadas de verdade (mesma pessoa lida duas vezes).

        A deduplicação usa `CHAVE_UNICA_REGISTRO` (UPA+V1008+V1014+V2003 por
        período), não as 25 colunas inteiras — duas pessoas diferentes podem
        coincidir em todas as variáveis de conteúdo (principalmente quem está
        fora da força de trabalho, com várias colunas de trabalho nulas) sem
        serem a mesma pessoa.

        Não filtra por regra de negócio (ex.: pessoas fora da força de
        trabalho, sem `VD4009` preenchido) — quem decide o que é "não
        aplicável" vs. "dado ruim" é a Transformação (Gold, RF-03).
        """
        dados = dados.apply(lambda coluna: coluna.str.strip())
        dados = dados.replace("", pd.NA)
        for coluna in dados.columns:
            dados[coluna] = pd.to_numeric(dados[coluna], errors="coerce")

        nulos_por_coluna = dados.isna().sum()
        colunas_com_nulos = nulos_por_coluna[nulos_por_coluna > 0]
        if not colunas_com_nulos.empty:
            logger.info("  nulos por coluna: %s", colunas_com_nulos.to_dict())

        colunas_obrigatorias = list(dict.fromkeys(COLUNAS_IDENTIFICACAO + CHAVE_UNICA_REGISTRO))
        antes = len(dados)
        dados = dados.dropna(subset=colunas_obrigatorias)
        sem_identificacao_valida = antes - len(dados)

        antes_dedup = len(dados)
        dados = dados.drop_duplicates(subset=list(CHAVE_UNICA_REGISTRO))
        duplicatas_reais = antes_dedup - len(dados)

        if sem_identificacao_valida or duplicatas_reais:
            logger.info(
                "  %d linha(s) sem identificacao valida, %d duplicata(s) real (mesma UPA/V1008/V1014/V2003)",
                sem_identificacao_valida, duplicatas_reais,
            )
        return dados

    def _salvar_silver(self, dados: pd.DataFrame) -> None:
        """Salva o dataset consolidado (todos os períodos) na camada Silver."""
        dados.to_parquet(self.caminho_saida / "dados_silver.parquet", index=False)


if __name__ == "__main__":
    Preprocessamento().executar()
