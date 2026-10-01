"""Validação contra o XSD oficial da prefeitura (schemas/webserviceNFSe.xsd).

Usa lxml quando instalado; sem lxml a validação é pulada (as críticas de validacao.py
continuam valendo) — instale com `pip install lxml` para validar antes de cada envio.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from .validacao import ErroValidacao

ARQUIVO_XSD = Path(__file__).resolve().parent.parent / "schemas" / "webserviceNFSe.xsd"


@lru_cache(maxsize=1)
def _schema():
    try:
        from lxml import etree
    except ImportError:
        return None
    return etree.XMLSchema(etree.parse(str(ARQUIVO_XSD)))


def disponivel() -> bool:
    return _schema() is not None


def validar_xsd(xml: str) -> bool:
    """Levanta ErroValidacao com as mensagens do XSD. Devolve False se lxml não estiver instalado."""
    schema = _schema()
    if schema is None:
        return False
    from lxml import etree
    doc = etree.fromstring(xml.encode("utf-8"))
    if not schema.validate(doc):
        raise ErroValidacao([f"XSD da prefeitura: {e.message}" for e in schema.error_log])
    return True
