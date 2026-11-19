"""Gera certificados A1 de TESTE (autoassinados, NÃO ICP-Brasil) e XMLs fiscais assinados."""

from __future__ import annotations

import base64
import hashlib
import random
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from lxml import etree

from moxml.fiscal import chave as chv

NS = "http://www.portalfiscal.inf.br/nfe"
NS_DS = "http://www.w3.org/2000/09/xmldsig#"


def _der_printable(txt: str) -> bytes:
    b = txt.encode("ascii")
    return bytes([0x13, len(b)]) + b


def gerar_certificado_teste(cnpj: str, razao: str, dias_validade: int = 365, senha: str = "teste",
                            inicio: datetime | None = None) -> tuple[bytes, object, x509.Certificate]:
    """PFX com otherName ICP-Brasil 2.16.76.1.3.3 (CNPJ) — apenas para laboratório."""
    chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    inicio = inicio or datetime.now(UTC) - timedelta(days=1)
    nome = x509.Name([x509.NameAttribute(NameOID.COUNTRY_NAME, "BR"),
                      x509.NameAttribute(NameOID.ORGANIZATION_NAME, "LABORATORIO MOXML (NAO ICP-Brasil)"),
                      x509.NameAttribute(NameOID.COMMON_NAME, f"{razao}:{cnpj}")])
    emissor = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "AC TESTE MOXML")])
    san = x509.SubjectAlternativeName([
        x509.OtherName(x509.ObjectIdentifier("2.16.76.1.3.3"), _der_printable(cnpj)),
    ])
    cert = (x509.CertificateBuilder().subject_name(nome).issuer_name(emissor).public_key(chave.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(inicio)
            .not_valid_after(inicio + timedelta(days=dias_validade)).add_extension(san, critical=False)
            .sign(chave, hashes.SHA256()))
    pfx = pkcs12.serialize_key_and_certificates(b"teste", chave, cert, None,
                                               serialization.BestAvailableEncryption(senha.encode()))
    return pfx, chave, cert


def assinar(el_pai: etree._Element, el_assinado: etree._Element, chave, cert: x509.Certificate) -> None:
    """XMLDSig enveloped, C14N 1.0, RSA-SHA1/SHA1 (padrão NF-e 4.00)."""
    ident = el_assinado.get("Id")
    digest = base64.b64encode(hashlib.sha1(etree.tostring(el_assinado, method="c14n")).digest()).decode()
    sig = etree.SubElement(el_pai, f"{{{NS_DS}}}Signature", nsmap={None: NS_DS})
    si = etree.SubElement(sig, f"{{{NS_DS}}}SignedInfo")
    etree.SubElement(si, f"{{{NS_DS}}}CanonicalizationMethod", Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315")
    etree.SubElement(si, f"{{{NS_DS}}}SignatureMethod", Algorithm="http://www.w3.org/2000/09/xmldsig#rsa-sha1")
    ref = etree.SubElement(si, f"{{{NS_DS}}}Reference", URI=f"#{ident}")
    tr = etree.SubElement(ref, f"{{{NS_DS}}}Transforms")
    etree.SubElement(tr, f"{{{NS_DS}}}Transform", Algorithm="http://www.w3.org/2000/09/xmldsig#enveloped-signature")
    etree.SubElement(tr, f"{{{NS_DS}}}Transform", Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315")
    etree.SubElement(ref, f"{{{NS_DS}}}DigestMethod", Algorithm="http://www.w3.org/2000/09/xmldsig#sha1")
    etree.SubElement(ref, f"{{{NS_DS}}}DigestValue").text = digest
    valor = chave.sign(etree.tostring(si, method="c14n"), padding.PKCS1v15(), hashes.SHA1())
    etree.SubElement(sig, f"{{{NS_DS}}}SignatureValue").text = base64.b64encode(valor).decode()
    ki = etree.SubElement(etree.SubElement(sig, f"{{{NS_DS}}}KeyInfo"), f"{{{NS_DS}}}X509Data")
    etree.SubElement(ki, f"{{{NS_DS}}}X509Certificate").text = base64.b64encode(
        cert.public_bytes(serialization.Encoding.DER)).decode()


def _sub(pai, tag, texto=None):
    e = etree.SubElement(pai, f"{{{NS}}}{tag}")
    if texto is not None:
        e.text = str(texto)
    return e


def gerar_nfe(cnpj: str, razao: str, uf: str, modelo: str, serie: int, numero: int, emissao: datetime,
              chave_priv, cert, valor: Decimal = Decimal("100.00"), tp_amb: int = 1, cnf: str | None = None,
              protocolo: bool = True, cstat: str = "100", tp_emis: int = 1) -> tuple[str, bytes, bytes]:
    """Retorna (chave, xml nfeProc|NFe, xml protNFe)."""
    cnf = cnf or f"{random.randint(10_000_000, 99_999_999)}"
    ch = chv.montar_chave(uf, emissao.year, emissao.month, cnpj, modelo, serie, numero, tp_emis, cnf)
    nfe = etree.Element(f"{{{NS}}}NFe", nsmap={None: NS})
    inf = _sub(nfe, "infNFe")
    inf.set("versao", "4.00")
    inf.set("Id", f"NFe{ch}")
    ide = _sub(inf, "ide")
    for tag, val in (("cUF", chv.UF_CODIGO[uf]), ("cNF", cnf), ("natOp", "VENDA"), ("mod", modelo), ("serie", serie),
                     ("nNF", numero), ("dhEmi", emissao.replace(microsecond=0).isoformat()), ("tpNF", 1), ("idDest", 1),
                     ("cMunFG", "3304557"), ("tpImp", 4 if modelo == "65" else 1), ("tpEmis", tp_emis),
                     ("cDV", ch[-1]), ("tpAmb", tp_amb), ("finNFe", 1), ("indFinal", 1), ("indPres", 1),
                     ("procEmi", 0), ("verProc", "LAB-MOXML")):
        _sub(ide, tag, val)
    emit = _sub(inf, "emit")
    _sub(emit, "CNPJ", cnpj)
    _sub(emit, "xNome", razao)
    _sub(emit, "CRT", 1)
    if modelo == "55":
        dest = _sub(inf, "dest")
        _sub(dest, "CNPJ", "11222333000181")
        _sub(dest, "xNome", "DESTINATARIO TESTE")
    tot = _sub(_sub(inf, "total"), "ICMSTot")
    _sub(tot, "vProd", f"{valor:.2f}")
    _sub(tot, "vNF", f"{valor:.2f}")
    assinar(nfe, inf, chave_priv, cert)
    prot = etree.Element(f"{{{NS}}}protNFe", nsmap={None: NS})
    prot.set("versao", "4.00")
    ip = _sub(prot, "infProt")
    nprot = f"333{emissao:%y}{numero:010d}"[:15]
    for tag, val in (("tpAmb", tp_amb), ("verAplic", "SVRS-LAB"), ("chNFe", ch),
                     ("dhRecbto", (emissao + timedelta(seconds=2)).isoformat()), ("nProt", nprot),
                     ("digVal", "AAAA"), ("cStat", cstat), ("xMotivo", "Autorizado o uso da NF-e")):
        _sub(ip, tag, val)
    prot_xml = etree.tostring(prot, encoding="utf-8")
    if not protocolo:
        return ch, etree.tostring(nfe, xml_declaration=True, encoding="UTF-8"), prot_xml
    proc = etree.Element(f"{{{NS}}}nfeProc", nsmap={None: NS})
    proc.set("versao", "4.00")
    proc.append(nfe)
    proc.append(etree.fromstring(prot_xml))
    return ch, etree.tostring(proc, xml_declaration=True, encoding="UTF-8"), prot_xml


def gerar_evento_cancelamento(ch: str, cnpj: str, quando: datetime, chave_priv, cert, tp_amb: int = 1,
                              tp_evento: str = "110111", seq: int = 1) -> bytes:
    ck = chv.analisar(ch)
    proc = etree.Element(f"{{{NS}}}procEventoNFe", nsmap={None: NS})
    proc.set("versao", "1.00")
    ev = _sub(proc, "evento")
    ev.set("versao", "1.00")
    inf = _sub(ev, "infEvento")
    inf.set("Id", f"ID{tp_evento}{ch}{seq:02d}")
    for tag, val in (("cOrgao", chv.UF_CODIGO[ck.uf]), ("tpAmb", tp_amb), ("CNPJ", cnpj), ("chNFe", ch),
                     ("dhEvento", quando.isoformat()), ("tpEvento", tp_evento), ("nSeqEvento", seq), ("verEvento", "1.00")):
        _sub(inf, tag, val)
    det = _sub(inf, "detEvento")
    det.set("versao", "1.00")
    _sub(det, "descEvento", "Cancelamento" if tp_evento == "110111" else "Carta de Correcao")
    if tp_evento == "110111":
        _sub(det, "nProt", "333000000000001")
        _sub(det, "xJust", "Cancelamento de teste do laboratorio")
    else:
        _sub(det, "xCorrecao", "Correcao de teste do laboratorio")
    assinar(ev, inf, chave_priv, cert)
    ret = _sub(proc, "retEvento")
    ret.set("versao", "1.00")
    ri = _sub(ret, "infEvento")
    for tag, val in (("tpAmb", tp_amb), ("verAplic", "SVRS-LAB"), ("cOrgao", chv.UF_CODIGO[ck.uf]), ("cStat", "135"),
                     ("xMotivo", "Evento registrado e vinculado a NF-e"), ("chNFe", ch), ("tpEvento", tp_evento),
                     ("nSeqEvento", seq), ("dhRegEvento", (quando + timedelta(seconds=3)).isoformat()),
                     ("nProt", f"1{quando:%y%m%d%H%M%S}{seq:02d}"[:15])):
        _sub(ri, tag, val)
    return etree.tostring(proc, xml_declaration=True, encoding="UTF-8")


def gerar_inutilizacao(cnpj: str, uf: str, modelo: str, serie: int, ini: int, fim: int, ano: int, tp_amb: int = 1) -> bytes:
    proc = etree.Element(f"{{{NS}}}procInutNFe", nsmap={None: NS})
    proc.set("versao", "4.00")
    inut = _sub(proc, "inutNFe")
    inut.set("versao", "4.00")
    inf = _sub(inut, "infInut")
    for tag, val in (("tpAmb", tp_amb), ("xServ", "INUTILIZAR"), ("cUF", chv.UF_CODIGO[uf]), ("ano", f"{ano % 100:02d}"),
                     ("CNPJ", cnpj), ("mod", modelo), ("serie", serie), ("nNFIni", ini), ("nNFFin", fim),
                     ("xJust", "Inutilizacao de teste do laboratorio")):
        _sub(inf, tag, val)
    ret = _sub(proc, "retInutNFe")
    ret.set("versao", "4.00")
    ri = _sub(ret, "infInut")
    for tag, val in (("tpAmb", tp_amb), ("cStat", "102"), ("xMotivo", "Inutilizacao de numero homologado"),
                     ("nProt", "333000000009999"), ("dhRecbto", datetime(2000 + ano % 100, 6, 1, tzinfo=UTC).isoformat())):
        _sub(ri, tag, val)
    return etree.tostring(proc, xml_declaration=True, encoding="UTF-8")
