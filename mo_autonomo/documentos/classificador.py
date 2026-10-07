"""Classificação determinística por conteúdo (não pelo nome do arquivo)."""
from __future__ import annotations

from .ofx import OFXInvalido, ler_ofx
from .xml_fiscal import DocumentoNaoReconhecido, ler_xml
from ..util.arquivos import XMLInseguro

ASSINATURAS = (
    (b"%PDF", "PDF"), (b"\x89PNG", "IMAGEM"), (b"\xff\xd8\xff", "IMAGEM"), (b"GIF8", "IMAGEM"),
    (b"II*\x00", "IMAGEM"), (b"MM\x00*", "IMAGEM"), (b"PK\x03\x04", "ZIP"),
)


def tipo_bruto(dados: bytes) -> str:
    for assinatura, tipo in ASSINATURAS:
        if dados.startswith(assinatura):
            return tipo
    inicio = dados[:2048].lstrip(b"\xef\xbb\xbf \r\n\t")
    if inicio.startswith(b"<?xml") or inicio.startswith(b"<"):
        if b"<OFX>" in dados[:4096].upper():
            return "OFX"
        return "XML"
    if b"OFXHEADER" in dados[:512].upper() or b"<OFX>" in dados[:4096].upper():
        return "OFX"
    return "DESCONHECIDO"


def classificar(dados: bytes) -> dict:
    """Devolve {'classe': ..., 'doc': dict|None, 'erro': str|None}."""
    bruto = tipo_bruto(dados)
    if bruto == "XML":
        try:
            doc = ler_xml(dados)
            return {"classe": doc["tipo"], "doc": doc, "erro": None}
        except (DocumentoNaoReconhecido, XMLInseguro) as exc:
            return {"classe": "XML_DESCONHECIDO", "doc": None, "erro": str(exc)}
        except Exception as exc:  # noqa: BLE001 — XML malformado
            return {"classe": "XML_INVALIDO", "doc": None, "erro": f"{type(exc).__name__}: {exc}"}
    if bruto == "OFX":
        try:
            return {"classe": "OFX", "doc": ler_ofx(dados), "erro": None}
        except (OFXInvalido, ValueError) as exc:
            return {"classe": "OFX_INVALIDO", "doc": None, "erro": str(exc)}
    return {"classe": bruto, "doc": None, "erro": None}
