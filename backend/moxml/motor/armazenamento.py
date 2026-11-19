"""Gravação dos XMLs na estrutura do escritório, sem sobrescrever arquivos existentes.

Estrutura (espelhada no Google Drive):
  1-CLIENTES/CLIENTES ATIVOS/<EMPRESA>/XML/<ANO>/<MM>/NFE_SAIDA|NFCE_SAIDA|EVENTOS/
"""

from __future__ import annotations

import hashlib
import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

PREFIXO_CLIENTES = Path("1-CLIENTES") / "CLIENTES ATIVOS"


def nome_pasta(razao_social: str, cnpj: str, personalizado: str | None = None) -> str:
    if personalizado:
        base = personalizado
    else:
        base = unicodedata.normalize("NFKD", razao_social).encode("ascii", "ignore").decode()
        base = f"{base.upper()} - {cnpj}"
    base = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", base)
    return re.sub(r"\s+", " ", base).strip(" .")[:150]


def subpasta_modelo(modelo: str) -> str:
    return {"55": "NFE_SAIDA", "65": "NFCE_SAIDA"}[modelo]


def caminho_relativo(pasta_empresa: str, data: datetime | None, categoria: str, nome_arquivo: str) -> Path:
    data = data or datetime.now()
    return PREFIXO_CLIENTES / pasta_empresa / "XML" / f"{data:%Y}" / f"{data:%m}" / categoria / nome_arquivo


@dataclass
class ResultadoGravacao:
    caminho: Path
    sha256: str
    situacao: str  # NOVO | IDENTICO | VERSAO


class Armazenamento:
    def __init__(self, raiz: Path):
        self.raiz = Path(raiz)

    def gravar(self, rel: Path, conteudo: bytes) -> ResultadoGravacao:
        """Grava atomicamente. Se o arquivo existe com o mesmo conteúdo, não faz nada; se existe
        com conteúdo diferente, grava como nova versão (-v2, -v3...), nunca sobrescreve."""
        h = hashlib.sha256(conteudo).hexdigest()
        destino = self.raiz / rel
        destino.parent.mkdir(parents=True, exist_ok=True)
        versao = 1
        alvo = destino
        while alvo.exists():
            if hashlib.sha256(alvo.read_bytes()).hexdigest() == h:
                return ResultadoGravacao(alvo, h, "IDENTICO")
            versao += 1
            alvo = destino.with_name(f"{destino.stem}-v{versao}{destino.suffix}")
        tmp = alvo.with_name(alvo.name + ".parcial")
        with open(tmp, "wb") as f:
            f.write(conteudo)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, alvo)
        return ResultadoGravacao(alvo, h, "NOVO" if versao == 1 else "VERSAO")

    def relativo(self, caminho: Path) -> str:
        return Path(caminho).resolve().relative_to(self.raiz.resolve()).as_posix()
