"""Hash, escrita atômica e leitura segura de XML."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import xml.etree.ElementTree as ET
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path


def sha256_bytes(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()


def sha256_arquivo(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 16), b""):
            h.update(bloco)
    return h.hexdigest()


def escrever_atomico(caminho: Path, dados: bytes) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=caminho.parent, prefix=".tmp_")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(dados)
        os.replace(tmp, caminho)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


class XMLInseguro(ValueError):
    pass


def parse_xml_seguro(dados: bytes) -> ET.Element:
    """Recusa DTD/entidades (XML vem de e-mail de terceiros)."""
    cabeca = dados[:4096].lower()
    if b"<!doctype" in cabeca or b"<!entity" in dados.lower():
        raise XMLInseguro("XML com DTD/ENTITY recusado")
    return ET.fromstring(dados)


def nome_local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def filho(el: ET.Element | None, *caminho: str) -> ET.Element | None:
    """Navega por nomes locais, ignorando namespace."""
    atual = el
    for parte in caminho:
        if atual is None:
            return None
        prox = None
        for c in atual:
            if nome_local(c.tag) == parte:
                prox = c
                break
        atual = prox
    return atual


def texto(el: ET.Element | None, *caminho: str) -> str | None:
    alvo = filho(el, *caminho) if caminho else el
    if alvo is None or alvo.text is None:
        return None
    return alvo.text.strip()


def todos(el: ET.Element | None, nome: str):
    if el is None:
        return []
    return [c for c in el.iter() if nome_local(c.tag) == nome]


def primeiro(el: ET.Element | None, nome: str) -> ET.Element | None:
    for c in todos(el, nome):
        return c
    return None


class CodificadorJSON(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return {"__decimal__": str(o)}
        if isinstance(o, datetime):
            return {"__datetime__": o.isoformat()}
        if isinstance(o, date):
            return {"__date__": o.isoformat()}
        if isinstance(o, (set, frozenset)):
            return sorted(o)
        if isinstance(o, Path):
            return str(o)
        if isinstance(o, (bytes, bytearray)):
            return {"__bytes_sha256__": sha256_bytes(bytes(o)), "tamanho": len(o)}
        return super().default(o)


def _decodificar(d: dict):
    if "__decimal__" in d:
        return Decimal(d["__decimal__"])
    if "__datetime__" in d:
        return datetime.fromisoformat(d["__datetime__"])
    if "__date__" in d:
        return date.fromisoformat(d["__date__"])
    return d


def dumps(obj) -> str:
    return json.dumps(obj, cls=CodificadorJSON, ensure_ascii=False, sort_keys=True)


def loads(texto_json: str):
    return json.loads(texto_json, object_hook=_decodificar)
