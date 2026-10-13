"""Interface comum para o armazenamento monitorado (Google Drive ou pasta local)."""
from __future__ import annotations

import io
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator

log = logging.getLogger(__name__)

TAMANHO_MAXIMO_LEITURA = 20 * 1024 * 1024  # 20 MB
EXTENSOES_TEXTO = (".xml", ".txt", ".ofx", ".csv", ".json", ".html", ".htm", ".rec")


@dataclass
class ArquivoDrive:
    id: str
    nome: str
    mime_type: str
    caminho: str              # caminho relativo à pasta da empresa, ex.: "2026/09 - Setembro/Fiscal/DAS.pdf"
    tamanho: int = 0
    md5: str = ""
    criado_em: datetime | None = None
    modificado_em: datetime | None = None
    link: str = ""
    enviado_por: str = ""


class ErroLeitura(Exception):
    """Falha (possivelmente temporária) ao baixar o arquivo: o monitor deve tentar de novo na próxima varredura."""


class DriveClient(ABC):
    @abstractmethod
    def listar_arquivos(self, pasta_id: str, modificado_apos: datetime | None = None) -> Iterator[ArquivoDrive]:
        """Lista recursivamente os arquivos (não pastas) abaixo de ``pasta_id``."""

    @abstractmethod
    def baixar(self, arquivo: ArquivoDrive) -> bytes:
        """Conteúdo binário do arquivo."""

    @abstractmethod
    def garantir_pasta(self, nome: str, pai_id: str) -> str:
        """Retorna o id da subpasta ``nome`` dentro de ``pai_id``, criando-a se necessário."""

    def ler_texto(self, arquivo: ArquivoDrive) -> str:
        if arquivo.tamanho and arquivo.tamanho > TAMANHO_MAXIMO_LEITURA:
            return ""
        try:
            dados = self.baixar(arquivo)
        except Exception as exc:  # noqa: BLE001
            log.warning("Falha ao baixar %s: %s", arquivo.nome, exc)
            raise ErroLeitura(f"falha ao baixar '{arquivo.nome}': {exc}") from exc
        return extrair_texto(dados, arquivo.nome, arquivo.mime_type)


def extrair_texto(dados: bytes, nome: str, mime_type: str = "") -> str:
    nome_l = nome.lower()
    if nome_l.endswith(".pdf") or mime_type == "application/pdf" or dados[:5] == b"%PDF-":
        return _texto_pdf(dados)
    if nome_l.endswith(EXTENSOES_TEXTO) or mime_type.startswith("text/") or "xml" in mime_type:
        for enc in ("utf-8", "latin-1"):
            try:
                return dados.decode(enc)
            except UnicodeDecodeError:
                continue
    return ""


def _texto_pdf(dados: bytes, max_paginas: int = 15) -> str:
    try:
        from pypdf import PdfReader

        leitor = PdfReader(io.BytesIO(dados))
        partes = []
        for i, pagina in enumerate(leitor.pages):
            if i >= max_paginas:
                break
            partes.append(pagina.extract_text() or "")
        return "\n".join(partes)
    except Exception as exc:  # noqa: BLE001
        log.info("PDF sem texto extraível (%s)", exc)
        return ""
