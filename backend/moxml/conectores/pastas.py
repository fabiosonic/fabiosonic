"""Conector D — pastas de XML do emissor (ERP/PDV) autorizadas pelo cliente.

O emitente é obrigado a guardar os XMLs que emite; quando o ERP/PDV do cliente grava os
arquivos em uma pasta (local, rede ou sincronizada), esta é a fonte mais completa e barata.

- Importação incremental (tamanho + mtime + SHA-256 já vistos são ignorados).
- Arquivos modificados há menos de ``idade_minima`` segundos ou cujo tamanho muda entre duas
  leituras são tratados como INCOMPLETOS e reavaliados na próxima varredura.
- Aceita .xml e .zip (XMLs dentro do zip). Não altera nem move os arquivos de origem.
"""

from __future__ import annotations

import time
import zipfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

from .base import Capacidade, Conector, Disponibilidade, StatusFonte

TAMANHO_MAXIMO = 50 * 1024 * 1024


@dataclass
class ArquivoEncontrado:
    caminho: str  # para zip: "arquivo.zip!interno.xml"
    tamanho: int
    mtime: float
    conteudo: bytes | None
    situacao: str = "OK"  # OK | INCOMPLETO | GRANDE_DEMAIS | ERRO


class PastaEmissorConector(Conector):
    nome = "pasta_emissor"
    descricao = "Pastas de XML do emissor do cliente (ERP/PDV), importação incremental."
    oficial = False
    capacidades = frozenset({Capacidade.IMPORTAR})

    def __init__(self, idade_minima: float = 60.0, relogio: Callable[[], float] = time.time):
        self.idade_minima = idade_minima
        self.relogio = relogio

    def suporta(self, uf: str, modelo: str) -> Disponibilidade:
        return Disponibilidade(StatusFonte.DISPONIVEL, "Depende de o emissor do cliente gravar os XMLs em pasta acessível",
                               "Obrigação de guarda do XML pelo emitente (Ajuste SINIEF 07/05, cl. décima)")

    def varrer(self, pasta: Path, recursivo: bool = True,
               ja_visto: Callable[[str, int, float], bool] = lambda *_: False) -> Iterator[ArquivoEncontrado]:
        pasta = Path(pasta)
        if not pasta.exists():
            raise FileNotFoundError(f"pasta não encontrada: {pasta}")
        padrao = "**/*" if recursivo else "*"
        for p in sorted(pasta.glob(padrao)):
            if not p.is_file() or p.suffix.lower() not in (".xml", ".zip"):
                continue
            try:
                st = p.stat()
            except OSError:
                continue
            if ja_visto(str(p), st.st_size, st.st_mtime):
                continue
            if self.relogio() - st.st_mtime < self.idade_minima:
                yield ArquivoEncontrado(str(p), st.st_size, st.st_mtime, None, "INCOMPLETO")
                continue
            if st.st_size > TAMANHO_MAXIMO:
                yield ArquivoEncontrado(str(p), st.st_size, st.st_mtime, None, "GRANDE_DEMAIS")
                continue
            try:
                dados = p.read_bytes()
                if p.stat().st_size != len(dados):
                    yield ArquivoEncontrado(str(p), st.st_size, st.st_mtime, None, "INCOMPLETO")
                    continue
            except OSError:
                yield ArquivoEncontrado(str(p), st.st_size, st.st_mtime, None, "ERRO")
                continue
            if p.suffix.lower() == ".zip":
                yield from self._zip(p, dados, st.st_mtime)
            else:
                yield ArquivoEncontrado(str(p), st.st_size, st.st_mtime, dados)

    def _zip(self, p: Path, dados: bytes, mtime: float) -> Iterator[ArquivoEncontrado]:
        import io
        try:
            with zipfile.ZipFile(io.BytesIO(dados)) as z:
                for info in z.infolist():
                    if info.is_dir() or not info.filename.lower().endswith(".xml"):
                        continue
                    if info.file_size > TAMANHO_MAXIMO:  # proteção contra zip-bomb
                        yield ArquivoEncontrado(f"{p}!{info.filename}", info.file_size, mtime, None, "GRANDE_DEMAIS")
                        continue
                    yield ArquivoEncontrado(f"{p}!{info.filename}", info.file_size, mtime, z.read(info))
        except zipfile.BadZipFile:
            yield ArquivoEncontrado(str(p), len(dados), mtime, None, "INCOMPLETO")
