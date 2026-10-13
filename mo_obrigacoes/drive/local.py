"""Implementação sobre uma pasta local.

Útil para testes, homologação e para escritórios que usam o Google Drive para
computador (a pasta sincronizada "G:/Meu Drive/Clientes" pode ser monitorada
diretamente). ``pasta_id`` é o caminho relativo à raiz configurada.
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Iterator

from .base import ArquivoDrive, DriveClient


class LocalDriveClient(DriveClient):
    def __init__(self, raiz: str | Path):
        self.raiz = Path(raiz).resolve()
        self.raiz.mkdir(parents=True, exist_ok=True)

    def _resolver(self, pasta_id: str) -> Path:
        p = (self.raiz / pasta_id).resolve()
        if self.raiz not in p.parents and p != self.raiz:
            raise ValueError("pasta fora da raiz monitorada")
        return p

    def listar_arquivos(self, pasta_id: str, modificado_apos: datetime | None = None) -> Iterator[ArquivoDrive]:
        base = self._resolver(pasta_id)
        if not base.exists():
            return
        for f in sorted(base.rglob("*")):
            if not f.is_file() or f.name.startswith((".", "~$")):
                continue
            if f.is_symlink():
                continue
            st = f.stat()
            modificado = datetime.fromtimestamp(st.st_mtime)
            if modificado_apos and modificado <= modificado_apos:
                continue
            rel_raiz = f.relative_to(self.raiz).as_posix()
            yield ArquivoDrive(
                id=f"local:{rel_raiz}",
                nome=f.name,
                mime_type="application/pdf" if f.suffix.lower() == ".pdf" else "",
                caminho=f.relative_to(base).as_posix(),
                tamanho=st.st_size,
                md5=hashlib.md5(f.read_bytes()).hexdigest(),
                criado_em=datetime.fromtimestamp(min(st.st_ctime, st.st_mtime)),
                modificado_em=modificado,
                link=f.as_uri(),
            )

    def baixar(self, arquivo: ArquivoDrive) -> bytes:
        return self._resolver(arquivo.id.removeprefix("local:")).read_bytes()

    def garantir_pasta(self, nome: str, pai_id: str) -> str:
        destino = self._resolver(pai_id) / nome
        destino.mkdir(parents=True, exist_ok=True)
        return destino.relative_to(self.raiz).as_posix()
