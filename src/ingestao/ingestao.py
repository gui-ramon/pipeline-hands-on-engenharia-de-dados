"""Etapa de ingestão: download dos microdados trimestrais da PNAD Contínua
(IBGE) para a camada Bronze.

Implementa RF-01 (extração com retentativa) e os campos de auditoria de
RF-07 (load_timestamp, source_file, contagem de linhas). Nenhuma
decodificação ou transformação de valores ocorre aqui: os arquivos de
largura fixa são gravados exatamente como recebidos do IBGE.

Idempotência (RNF-01): a cada execução, o período é baixado novamente e
substitui o arquivo local existente (o IBGE republica/revisa trimestres —
ex.: `PNADC_022024_20260324.zip` é uma revisão de `PNADC_022024`). Não há
duplicação porque a substituição é atômica (1 arquivo por período, sempre).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests

from src.etapa import Etapa

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

CAMINHO_BRONZE = Path("dados/bronze")

BASE_URL = (
    "https://ftp.ibge.gov.br/Trabalho_e_Rendimento/"
    "Pesquisa_Nacional_por_Amostra_de_Domicilios_continua/Trimestral/Microdados"
)

ANOS_PADRAO: tuple[int, ...] = (2023, 2024, 2025)
TRIMESTRES_PADRAO: tuple[int, ...] = (1, 2, 3, 4)

TENTATIVAS_MAX = 3
BACKOFF_BASE_SEGUNDOS = 2
TIMEOUT_SEGUNDOS = 60
TAMANHO_CHUNK = 1024 * 1024  # 1 MB
CABECALHOS = {"User-Agent": "informalidade-br-pipeline/1.0 (uso academico)"}


@dataclass
class ResultadoPeriodo:
    """Resultado do processamento de um período (ano/trimestre)."""

    ano: int
    trimestre: int
    status: str  # "baixado", "substituido", "sem_mudanca" ou "erro"
    linhas: int | None = None
    duracao_segundos: float | None = None


class Ingestao(Etapa):
    """Baixa os microdados trimestrais da PNAD Contínua (formato de largura
    fixa) diretamente do FTP público do IBGE e os grava, sem nenhuma
    transformação, na camada Bronze (`dados/bronze/<ano>/`).
    """

    def __init__(
        self,
        caminho_saida: Path = CAMINHO_BRONZE,
        anos: tuple[int, ...] = ANOS_PADRAO,
        trimestres: tuple[int, ...] = TRIMESTRES_PADRAO,
    ) -> None:
        self.caminho_saida = caminho_saida
        self.anos = anos
        self.trimestres = trimestres
        self._sessao = requests.Session()
        self._sessao.headers.update(CABECALHOS)
        self.resultados: list[ResultadoPeriodo] = []

    def executar(self) -> list[ResultadoPeriodo]:
        """Baixa o dicionário de variáveis e os microdados de cada período
        (ano/trimestre) configurado. Todo período é baixado a cada execução
        e substitui o arquivo local existente (RNF-01/RNF-02 — ver docstring
        do módulo), com retentativa em falhas de rede.

        Retorna a lista de `ResultadoPeriodo` (um por ano/trimestre), também
        disponível em `self.resultados` mesmo quando a execução levanta
        exceção — útil para montar um resumo legível no notebook.
        """
        inicio = time.perf_counter()
        periodos = [(ano, trimestre) for ano in self.anos for trimestre in self.trimestres]

        logger.info("=" * 70)
        logger.info("INGESTAO PNAD CONTINUA — INICIO")
        logger.info("Anos configurados: %s", list(self.anos))
        logger.info("Trimestres configurados: %s", list(self.trimestres))
        logger.info("Periodos a processar (%d): %s", len(periodos), [f"{a}Q{t}" for a, t in periodos])
        logger.info("Pasta de saida (Bronze): %s", self.caminho_saida.resolve())
        logger.info("=" * 70)
        self.caminho_saida.mkdir(parents=True, exist_ok=True)

        logger.info("[1/2] Dicionario de variaveis do IBGE")
        try:
            self._baixar_dicionario_variaveis()
        except Exception:
            logger.exception("Falha ao baixar o dicionário de variáveis (não bloqueante).")

        logger.info("[2/2] Microdados por periodo")
        resultados = []
        for indice, (ano, trimestre) in enumerate(periodos, start=1):
            logger.info("--- Periodo %d/%d: %dQ%d ---", indice, len(periodos), ano, trimestre)
            resultados.append(self._processar_periodo(ano, trimestre))
        self.resultados = resultados

        duracao = time.perf_counter() - inicio
        novos = sum(1 for r in resultados if r.status == "baixado")
        substituidos = sum(1 for r in resultados if r.status == "substituido")
        sem_mudanca = sum(1 for r in resultados if r.status == "sem_mudanca")
        erros = [r for r in resultados if r.status == "erro"]

        logger.info("=" * 70)
        logger.info("RESUMO DA INGESTAO")
        for r in resultados:
            duracao_r = f"{r.duracao_segundos:.1f}s" if r.duracao_segundos is not None else "-"
            linhas_r = r.linhas if r.linhas is not None else "-"
            logger.info("  %dQ%d -> %-12s linhas=%-8s duracao=%s", r.ano, r.trimestre, r.status, linhas_r, duracao_r)
        logger.info(
            "Ingestão concluída em %.1fs — novos=%d substituidos=%d sem_mudanca=%d erros=%d",
            duracao,
            novos,
            substituidos,
            sem_mudanca,
            len(erros),
        )
        logger.info("=" * 70)
        if erros:
            periodos_com_erro = [f"{r.ano}Q{r.trimestre}" for r in erros]
            raise RuntimeError(f"Falha ao baixar os períodos: {periodos_com_erro}")
        return resultados

    # ------------------------------------------------------------------
    # Período (ano/trimestre)
    # ------------------------------------------------------------------

    def _processar_periodo(self, ano: int, trimestre: int) -> ResultadoPeriodo:
        pasta_ano = self.caminho_saida / str(ano)
        pasta_ano.mkdir(parents=True, exist_ok=True)
        destino_txt = pasta_ano / f"PNADC_0{trimestre}{ano}.txt"
        destino_manifesto = pasta_ano / f"PNADC_0{trimestre}{ano}.manifest.json"
        logger.info("[%dQ%d] pasta local: %s", ano, trimestre, pasta_ano.resolve())

        checksum_anterior = None
        if destino_manifesto.exists():
            checksum_anterior = json.loads(destino_manifesto.read_text()).get("sha256")
            logger.info("[%dQ%d] manifesto anterior encontrado (checksum %s...)", ano, trimestre, checksum_anterior[:12])
        else:
            logger.info("[%dQ%d] nenhum manifesto anterior — primeira vez.", ano, trimestre)

        inicio = time.perf_counter()
        try:
            logger.info("[%dQ%d] resolvendo nome do arquivo no indice do IBGE...", ano, trimestre)
            nome_arquivo, url_zip = self._resolver_url_periodo(ano, trimestre)
            logger.info("[%dQ%d] arquivo encontrado: %s", ano, trimestre, nome_arquivo)
            destino_zip = pasta_ano / nome_arquivo
            logger.info("[%dQ%d] baixando %s ...", ano, trimestre, url_zip)
            self._baixar_com_retry(url_zip, destino_zip)
            logger.info("[%dQ%d] download concluido, extraindo .txt do zip...", ano, trimestre)

            # Extrai para um arquivo novo e só substitui o existente depois
            # de extrair com sucesso — nunca fica sem o .txt anterior no meio
            # do caminho se a extração falhar.
            destino_txt_novo = destino_txt.with_name(destino_txt.name + ".novo")
            linhas = self._extrair_txt(destino_zip, destino_txt_novo)
            logger.info("[%dQ%d] extraidas %d linhas, calculando checksum SHA-256...", ano, trimestre, linhas)
            checksum = self._sha256(destino_txt_novo)
            destino_zip.unlink(missing_ok=True)
            destino_txt_novo.replace(destino_txt)
            logger.info("[%dQ%d] arquivo gravado em %s", ano, trimestre, destino_txt.resolve())

            self._gravar_manifesto(
                destino_manifesto,
                source_url=url_zip,
                source_file=nome_arquivo,
                linhas=linhas,
                sha256=checksum,
            )
            duracao = time.perf_counter() - inicio

            if checksum_anterior is None:
                status = "baixado"
                logger.info("[%dQ%d] baixado: %d linhas em %.1fs", ano, trimestre, linhas, duracao)
            elif checksum_anterior == checksum:
                status = "sem_mudanca"
                logger.info(
                    "[%dQ%d] rebaixado, conteúdo idêntico ao anterior: %d linhas em %.1fs",
                    ano, trimestre, linhas, duracao,
                )
            else:
                status = "substituido"
                logger.warning(
                    "[%dQ%d] SUBSTITUÍDO — conteúdo mudou desde a última ingestão "
                    "(checksum %s -> %s): %d linhas em %.1fs",
                    ano, trimestre, checksum_anterior[:12], checksum[:12], linhas, duracao,
                )
            return ResultadoPeriodo(ano, trimestre, status, linhas=linhas, duracao_segundos=duracao)
        except Exception:
            logger.exception("[%dQ%d] falhou ao baixar/extrair.", ano, trimestre)
            return ResultadoPeriodo(ano, trimestre, status="erro")

    def _resolver_url_periodo(self, ano: int, trimestre: int) -> tuple[str, str]:
        """Descobre o nome exato do arquivo do período na listagem do FTP.

        O IBGE varia o sufixo de data no nome do arquivo entre períodos
        (ex.: `PNADC_012025.zip` vs. `PNADC_022024_20260324.zip`), então o
        nome não pode ser presumido apenas por ano/trimestre.
        """
        url_indice = f"{BASE_URL}/{ano}/"
        resposta = self._sessao.get(url_indice, timeout=TIMEOUT_SEGUNDOS)
        resposta.raise_for_status()
        padrao = re.compile(rf'href="(PNADC_0{trimestre}{ano}(?:_\d+)?\.zip)"')
        correspondencia = padrao.search(resposta.text)
        if not correspondencia:
            raise ValueError(f"Arquivo do período {ano}Q{trimestre} não encontrado em {url_indice}")
        nome_arquivo = correspondencia.group(1)
        return nome_arquivo, f"{url_indice}{nome_arquivo}"

    # ------------------------------------------------------------------
    # Dicionário de variáveis (documentação — baixado e substituído a cada
    # execução, igual aos períodos)
    # ------------------------------------------------------------------

    def _baixar_dicionario_variaveis(self) -> None:
        pasta_doc = self.caminho_saida / "documentacao"
        marcador = pasta_doc / ".ok"
        logger.info("Pasta local do dicionario: %s", pasta_doc.resolve())

        url_pasta_doc = f"{BASE_URL}/Documentacao/"
        logger.info("Consultando indice: %s", url_pasta_doc)
        resposta = self._sessao.get(url_pasta_doc, timeout=TIMEOUT_SEGUNDOS)
        resposta.raise_for_status()
        correspondencia = re.search(r'href="(Dicionario_e_input[^"]*\.zip)"', resposta.text)
        if not correspondencia:
            logger.warning("Não foi possível localizar o zip do dicionário de variáveis.")
            return

        nome_arquivo = correspondencia.group(1)
        url_zip = f"{url_pasta_doc}{nome_arquivo}"
        pasta_doc.mkdir(parents=True, exist_ok=True)
        destino_zip = pasta_doc / nome_arquivo
        logger.info("Arquivo encontrado: %s — baixando...", nome_arquivo)
        self._baixar_com_retry(url_zip, destino_zip)

        logger.info("Download concluido, extraindo para %s ...", pasta_doc.resolve())
        with zipfile.ZipFile(destino_zip) as arquivo_zip:
            arquivo_zip.extractall(pasta_doc)  # substitui os arquivos existentes
        destino_zip.unlink(missing_ok=True)
        marcador.write_text(datetime.now(timezone.utc).isoformat())
        logger.info("Dicionario de variaveis atualizado.")

    # ------------------------------------------------------------------
    # Utilitários de download/extração
    # ------------------------------------------------------------------

    def _baixar_com_retry(self, url: str, destino: Path) -> None:
        ultimo_erro: Exception | None = None
        for tentativa in range(1, TENTATIVAS_MAX + 1):
            try:
                if tentativa > 1:
                    logger.info("Tentativa %d/%d para %s", tentativa, TENTATIVAS_MAX, url)
                with self._sessao.get(url, stream=True, timeout=TIMEOUT_SEGUNDOS) as resposta:
                    resposta.raise_for_status()
                    tamanho_total = resposta.headers.get("Content-Length")
                    if tamanho_total:
                        logger.info("Tamanho do arquivo: %.1f MB", int(tamanho_total) / (1024 * 1024))
                    destino_tmp = destino.with_name(destino.name + ".part")
                    with open(destino_tmp, "wb") as arquivo:
                        for chunk in resposta.iter_content(chunk_size=TAMANHO_CHUNK):
                            if chunk:
                                arquivo.write(chunk)
                    destino_tmp.rename(destino)
                return
            except (requests.RequestException, OSError) as erro:
                ultimo_erro = erro
                espera = BACKOFF_BASE_SEGUNDOS**tentativa
                logger.warning(
                    "Falha ao baixar %s (tentativa %d/%d): %s. Nova tentativa em %ds.",
                    url,
                    tentativa,
                    TENTATIVAS_MAX,
                    erro,
                    espera,
                )
                time.sleep(espera)
        raise ConnectionError(f"Falha ao baixar {url} após {TENTATIVAS_MAX} tentativas") from ultimo_erro

    @staticmethod
    def _extrair_txt(caminho_zip: Path, destino_txt: Path) -> int:
        """Extrai o único arquivo .txt de largura fixa contido no zip, byte
        a byte (sem decodificar), e retorna a contagem de linhas (registros).
        """
        with zipfile.ZipFile(caminho_zip) as arquivo_zip:
            nomes_txt = [n for n in arquivo_zip.namelist() if n.lower().endswith(".txt")]
            if len(nomes_txt) != 1:
                raise ValueError(
                    f"Esperado 1 arquivo .txt em {caminho_zip.name}, encontrados {len(nomes_txt)}"
                )
            linhas = 0
            with arquivo_zip.open(nomes_txt[0]) as origem, open(destino_txt, "wb") as saida:
                for linha in origem:
                    saida.write(linha)
                    linhas += 1
        return linhas

    @staticmethod
    def _sha256(caminho: Path) -> str:
        digest = hashlib.sha256()
        with open(caminho, "rb") as arquivo:
            for bloco in iter(lambda: arquivo.read(TAMANHO_CHUNK), b""):
                digest.update(bloco)
        return digest.hexdigest()

    @staticmethod
    def _gravar_manifesto(caminho: Path, **campos: object) -> None:
        manifesto = {**campos, "load_timestamp": datetime.now(timezone.utc).isoformat()}
        caminho.write_text(json.dumps(manifesto, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    Ingestao().executar()
