"""Leitura, classificação e validação de XMLs fiscais (NF-e/NFC-e 4.00, eventos, inutilização).

Princípios:
- O XML original é tratado como bytes imutáveis: nada aqui reescreve o conteúdo.
- Classificação distingue XML autorizado, sem protocolo, evento, inutilização,
  resumo (DistDFe), inválido e incompleto.
- Uma consulta de situação NUNCA é classificada como XML integral.
"""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from lxml import etree

from . import chave as chv

NS = "http://www.portalfiscal.inf.br/nfe"
NS_DS = "http://www.w3.org/2000/09/xmldsig#"
N = {"n": NS, "ds": NS_DS}

CSTAT_AUTORIZADA = {"100", "150"}  # 150 = autorizado fora de prazo
CSTAT_DENEGADA = {"110", "301", "302", "303"}
CSTAT_EVENTO_OK = {"135", "136", "155"}
CSTAT_CANCELADA_CONSULTA = {"101", "151", "155"}

TP_EVENTO_DESCRICAO = {
    "110110": "Carta de Correção",
    "110111": "Cancelamento",
    "110112": "Cancelamento por substituição",
    "110140": "EPEC",
    "210200": "Confirmação da Operação",
    "210210": "Ciência da Operação",
    "210220": "Desconhecimento da Operação",
    "210240": "Operação não Realizada",
}
TP_EVENTO_CANCELAMENTO = {"110111", "110112"}


class TipoXML(StrEnum):
    NFE_AUTORIZADA = "NFE_AUTORIZADA"
    NFE_DENEGADA = "NFE_DENEGADA"
    NFE_SEM_PROTOCOLO = "NFE_SEM_PROTOCOLO"
    EVENTO = "EVENTO"
    EVENTO_SEM_PROTOCOLO = "EVENTO_SEM_PROTOCOLO"
    INUTILIZACAO = "INUTILIZACAO"
    RESUMO_NFE = "RESUMO_NFE"
    RESUMO_EVENTO = "RESUMO_EVENTO"
    INVALIDO = "INVALIDO"
    INCOMPLETO = "INCOMPLETO"


@dataclass
class Problema:
    codigo: str
    mensagem: str
    grave: bool = True


@dataclass
class DocumentoXML:
    tipo: TipoXML
    conteudo: bytes
    sha256: str
    problemas: list[Problema] = field(default_factory=list)
    # NF-e / NFC-e
    chave: str | None = None
    uf: str | None = None
    modelo: str | None = None
    serie: int | None = None
    numero: int | None = None
    data_emissao: datetime | None = None
    ambiente: int | None = None  # 1 produção, 2 homologação
    tp_nf: int | None = None  # 0 entrada, 1 saída
    fin_nfe: int | None = None
    cnpj_emitente: str | None = None
    nome_emitente: str | None = None
    doc_destinatario: str | None = None
    valor: Decimal | None = None
    protocolo: str | None = None
    cstat: str | None = None
    data_autorizacao: datetime | None = None
    ver_aplic: str | None = None
    aut_xml: list[str] = field(default_factory=list)
    assinatura_ok: bool | None = None
    # Evento
    tp_evento: str | None = None
    seq_evento: int | None = None
    data_evento: datetime | None = None
    descricao_evento: str | None = None
    justificativa: str | None = None
    # Inutilização
    ano_inut: int | None = None
    numero_final: int | None = None
    # Resumo (DistDFe)
    situacao_resumo: str | None = None  # cSitNFe 1=autorizada 2=denegada 3=cancelada

    @property
    def valido(self) -> bool:
        return self.tipo not in (TipoXML.INVALIDO, TipoXML.INCOMPLETO) and not any(p.grave for p in self.problemas)

    @property
    def e_xml_integral(self) -> bool:
        """True somente para o XML completo da nota com protocolo de autorização/denegação."""
        return self.tipo in (TipoXML.NFE_AUTORIZADA, TipoXML.NFE_DENEGADA) and self.valido


def _dt(txt: str | None) -> datetime | None:
    if not txt:
        return None
    try:
        return datetime.fromisoformat(txt.strip())
    except ValueError:
        return None


def _t(el: etree._Element | None, xp: str) -> str | None:
    if el is None:
        return None
    r = el.xpath(xp, namespaces=N)
    if not r:
        return None
    v = r[0] if isinstance(r[0], str) else r[0].text
    return v.strip() if v else None


_XSD_DIR = __import__("pathlib").Path(__file__).resolve().parent.parent / "sefaz" / "schemas" / "nfe"
_XSD_RAIZ = {"nfeProc": "procNFe_v4.00.xsd", "NFe": "nfe_v4.00.xsd", "procEventoNFe": "procEventoNFe_v1.00.xsd",
             "procInutNFe": "procInutNFe_v4.00.xsd"}
_XSD_CACHE: dict[str, etree.XMLSchema] = {}


def validar_xsd(raiz: etree._Element) -> list[str]:
    """Valida contra o pacote oficial de schemas (PL_010g). Erros de XSD são registrados como
    AVISO (não rejeitam): um XML autorizado pela SEFAZ pode ter sido validado por pacote de outra
    versão (ex.: grupos da Reforma Tributária). A integridade é garantida pela assinatura."""
    nome = etree.QName(raiz).localname
    arq = _XSD_RAIZ.get(nome)
    if not arq or not (_XSD_DIR / arq).exists():
        return []
    try:
        if arq not in _XSD_CACHE:
            _XSD_CACHE[arq] = etree.XMLSchema(etree.parse(str(_XSD_DIR / arq)))
        esquema = _XSD_CACHE[arq]
    except (etree.XMLSchemaParseError, OSError) as e:
        return [f"schema {arq} indisponível: {e}"]
    if esquema.validate(raiz):
        return []
    return [f"{arq}: {err.message} (linha {err.line})" for err in list(esquema.error_log)[:5]]


def sha256(conteudo: bytes) -> str:
    return hashlib.sha256(conteudo).hexdigest()


_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, remove_blank_text=False, huge_tree=False)


def ler(conteudo: bytes | str, verificar_assinatura: bool = True, validar_esquema: bool = True) -> DocumentoXML:
    if isinstance(conteudo, str):
        conteudo = conteudo.encode("utf-8")
    h = sha256(conteudo)
    try:
        raiz = etree.fromstring(conteudo, _PARSER)
    except etree.XMLSyntaxError as e:
        texto = conteudo.strip()
        incompleto = len(texto) == 0 or not texto.endswith(b">") or "Premature end" in str(e) or "EndTag" in str(e)
        return DocumentoXML(
            tipo=TipoXML.INCOMPLETO if incompleto else TipoXML.INVALIDO,
            conteudo=conteudo, sha256=h,
            problemas=[Problema("XML_MALFORMADO", f"XML mal formado: {e}")],
        )
    nome = etree.QName(raiz).localname
    ns = etree.QName(raiz).namespace
    if ns != NS:
        return DocumentoXML(TipoXML.INVALIDO, conteudo, h,
                            [Problema("NAMESPACE", f"namespace inesperado: {ns!r} (esperado {NS})")])
    if nome in ("nfeProc", "NFe"):
        d = _ler_nfe(raiz, conteudo, h, verificar_assinatura)
        if validar_esquema:
            d.problemas += [Problema("XSD", m, grave=False) for m in validar_xsd(raiz)]
        return d
    if nome in ("procEventoNFe", "evento"):
        return _ler_evento(raiz, conteudo, h)
    if nome in ("procInutNFe", "inutNFe"):
        return _ler_inut(raiz, conteudo, h)
    if nome == "resNFe":
        return _ler_resnfe(raiz, conteudo, h)
    if nome == "resEvento":
        d = DocumentoXML(TipoXML.RESUMO_EVENTO, conteudo, h)
        d.chave = _t(raiz, "n:chNFe")
        d.tp_evento = _t(raiz, "n:tpEvento")
        d.seq_evento = int(_t(raiz, "n:nSeqEvento") or 0) or None
        d.protocolo = _t(raiz, "n:nProt")
        d.data_evento = _dt(_t(raiz, "n:dhEvento"))
        return d
    return DocumentoXML(TipoXML.INVALIDO, conteudo, h, [Problema("RAIZ", f"elemento raiz não suportado: {nome}")])


def _ler_nfe(raiz, conteudo: bytes, h: str, verificar_assinatura: bool) -> DocumentoXML:
    nfe = raiz if etree.QName(raiz).localname == "NFe" else raiz.find(f"{{{NS}}}NFe")
    inf = nfe.find(f"{{{NS}}}infNFe") if nfe is not None else None
    d = DocumentoXML(TipoXML.NFE_SEM_PROTOCOLO, conteudo, h)
    if inf is None:
        d.tipo = TipoXML.INVALIDO
        d.problemas.append(Problema("SEM_INFNFE", "grupo infNFe ausente"))
        return d
    ide = inf.find(f"{{{NS}}}ide")
    emit = inf.find(f"{{{NS}}}emit")
    d.modelo = _t(ide, "n:mod")
    d.serie = int(_t(ide, "n:serie") or 0)
    d.numero = int(_t(ide, "n:nNF") or 0)
    d.data_emissao = _dt(_t(ide, "n:dhEmi"))
    d.ambiente = int(_t(ide, "n:tpAmb") or 0) or None
    d.tp_nf = int(_t(ide, "n:tpNF")) if _t(ide, "n:tpNF") else None
    d.fin_nfe = int(_t(ide, "n:finNFe")) if _t(ide, "n:finNFe") else None
    d.uf = chv.CODIGO_UF.get(_t(ide, "n:cUF") or "")
    d.cnpj_emitente = _t(emit, "n:CNPJ") or _t(emit, "n:CPF")
    d.nome_emitente = _t(emit, "n:xNome")
    dest = inf.find(f"{{{NS}}}dest")
    d.doc_destinatario = _t(dest, "n:CNPJ") or _t(dest, "n:CPF") or _t(dest, "n:idEstrangeiro")
    v = _t(inf, "n:total/n:ICMSTot/n:vNF")
    d.valor = Decimal(v) if v else None
    d.aut_xml = [x for x in (_t(a, "n:CNPJ") or _t(a, "n:CPF") for a in inf.findall(f"{{{NS}}}autXML")) if x]
    ident = (inf.get("Id") or "").removeprefix("NFe")
    d.chave = ident or None

    # Coerência da chave com os campos do XML
    if not ident:
        d.problemas.append(Problema("SEM_ID", "atributo Id de infNFe ausente"))
    else:
        try:
            ck = chv.analisar(ident)
            for campo, a, b in (("modelo", ck.modelo, d.modelo), ("série", ck.serie, d.serie),
                                ("número", ck.numero, d.numero), ("CNPJ", ck.cnpj, (d.cnpj_emitente or "").zfill(14)),
                                ("UF", ck.uf, d.uf)):
                if a != b:
                    d.problemas.append(Problema("CHAVE_DIVERGENTE", f"{campo} da chave ({a}) difere do XML ({b})"))
        except chv.ChaveInvalida as e:
            d.problemas.append(Problema("CHAVE_INVALIDA", str(e)))
    if d.modelo not in ("55", "65"):
        d.problemas.append(Problema("MODELO", f"modelo {d.modelo} não suportado"))
    if nfe.find(f"{{{NS_DS}}}Signature") is None:
        d.problemas.append(Problema("SEM_ASSINATURA", "NF-e sem assinatura digital"))
    elif verificar_assinatura:
        ok, msg = verificar_assinatura_xmldsig(nfe, inf)
        d.assinatura_ok = ok
        if not ok:
            d.problemas.append(Problema("ASSINATURA_INVALIDA", msg))

    prot = raiz.find(f"{{{NS}}}protNFe/{{{NS}}}infProt") if etree.QName(raiz).localname == "nfeProc" else None
    if prot is not None:
        d.cstat = _t(prot, "n:cStat")
        d.protocolo = _t(prot, "n:nProt")
        d.data_autorizacao = _dt(_t(prot, "n:dhRecbto"))
        d.ver_aplic = _t(prot, "n:verAplic")
        ch_prot = _t(prot, "n:chNFe")
        if ch_prot and d.chave and ch_prot != d.chave:
            d.problemas.append(Problema("PROTOCOLO_DIVERGENTE", "chave do protocolo difere da chave da NF-e"))
        tp_amb_prot = _t(prot, "n:tpAmb")
        if tp_amb_prot and d.ambiente and int(tp_amb_prot) != d.ambiente:
            d.problemas.append(Problema("AMBIENTE_DIVERGENTE", "tpAmb do protocolo difere do tpAmb da NF-e"))
        if d.cstat in CSTAT_AUTORIZADA and d.protocolo:
            d.tipo = TipoXML.NFE_AUTORIZADA
        elif d.cstat in CSTAT_DENEGADA:
            d.tipo = TipoXML.NFE_DENEGADA
        else:
            d.tipo = TipoXML.NFE_SEM_PROTOCOLO
            d.problemas.append(Problema("PROTOCOLO_NAO_AUTORIZADO", f"protocolo com cStat {d.cstat}", grave=False))
    return d


def _ler_evento(raiz, conteudo: bytes, h: str) -> DocumentoXML:
    ev = raiz if etree.QName(raiz).localname == "evento" else raiz.find(f"{{{NS}}}evento")
    inf = ev.find(f"{{{NS}}}infEvento") if ev is not None else None
    d = DocumentoXML(TipoXML.EVENTO_SEM_PROTOCOLO, conteudo, h)
    if inf is None:
        d.tipo = TipoXML.INVALIDO
        d.problemas.append(Problema("SEM_INFEVENTO", "grupo infEvento ausente"))
        return d
    d.chave = _t(inf, "n:chNFe")
    d.tp_evento = _t(inf, "n:tpEvento")
    d.seq_evento = int(_t(inf, "n:nSeqEvento") or 1)
    d.data_evento = _dt(_t(inf, "n:dhEvento"))
    d.ambiente = int(_t(inf, "n:tpAmb") or 0) or None
    d.cnpj_emitente = _t(inf, "n:CNPJ") or _t(inf, "n:CPF")
    d.descricao_evento = _t(inf, "n:detEvento/n:descEvento") or TP_EVENTO_DESCRICAO.get(d.tp_evento or "")
    d.justificativa = _t(inf, "n:detEvento/n:xJust") or _t(inf, "n:detEvento/n:xCorrecao")
    if d.chave:
        try:
            ck = chv.analisar(d.chave)
            d.modelo, d.serie, d.numero, d.uf = ck.modelo, ck.serie, ck.numero, ck.uf
        except chv.ChaveInvalida as e:
            d.problemas.append(Problema("CHAVE_INVALIDA", str(e)))
    ret = raiz.find(f"{{{NS}}}retEvento/{{{NS}}}infEvento")
    if ret is not None:
        d.cstat = _t(ret, "n:cStat")
        d.protocolo = _t(ret, "n:nProt")
        d.data_autorizacao = _dt(_t(ret, "n:dhRegEvento"))
        if d.cstat in CSTAT_EVENTO_OK and d.protocolo:
            d.tipo = TipoXML.EVENTO
        else:
            d.problemas.append(Problema("EVENTO_NAO_REGISTRADO", f"retEvento com cStat {d.cstat}", grave=False))
    return d


def _ler_inut(raiz, conteudo: bytes, h: str) -> DocumentoXML:
    inf = raiz.find(f"{{{NS}}}inutNFe/{{{NS}}}infInut") if etree.QName(raiz).localname == "procInutNFe" \
        else raiz.find(f"{{{NS}}}infInut")
    d = DocumentoXML(TipoXML.INUTILIZACAO, conteudo, h)
    if inf is None:
        d.tipo = TipoXML.INVALIDO
        d.problemas.append(Problema("SEM_INFINUT", "grupo infInut ausente"))
        return d
    d.ambiente = int(_t(inf, "n:tpAmb") or 0) or None
    d.uf = chv.CODIGO_UF.get(_t(inf, "n:cUF") or "")
    d.ano_inut = 2000 + int(_t(inf, "n:ano") or 0)
    d.cnpj_emitente = _t(inf, "n:CNPJ") or _t(inf, "n:CPF")
    d.modelo = _t(inf, "n:mod")
    d.serie = int(_t(inf, "n:serie") or 0)
    d.numero = int(_t(inf, "n:nNFIni") or 0)
    d.numero_final = int(_t(inf, "n:nNFFin") or 0)
    d.justificativa = _t(inf, "n:xJust")
    ret = raiz.find(f"{{{NS}}}retInutNFe/{{{NS}}}infInut")
    if ret is not None:
        d.cstat = _t(ret, "n:cStat")
        d.protocolo = _t(ret, "n:nProt")
        d.data_autorizacao = _dt(_t(ret, "n:dhRecbto"))
    if d.cstat != "102" or not d.protocolo:
        d.problemas.append(Problema("INUT_SEM_HOMOLOGACAO", "inutilização sem retorno cStat 102", grave=False))
    return d


def _ler_resnfe(raiz, conteudo: bytes, h: str) -> DocumentoXML:
    d = DocumentoXML(TipoXML.RESUMO_NFE, conteudo, h)
    d.chave = _t(raiz, "n:chNFe")
    d.cnpj_emitente = _t(raiz, "n:CNPJ") or _t(raiz, "n:CPF")
    d.nome_emitente = _t(raiz, "n:xNome")
    d.data_emissao = _dt(_t(raiz, "n:dhEmi"))
    v = _t(raiz, "n:vNF")
    d.valor = Decimal(v) if v else None
    d.protocolo = _t(raiz, "n:nProt")
    d.situacao_resumo = _t(raiz, "n:cSitNFe")
    if d.chave and chv.valida(d.chave):
        ck = chv.analisar(d.chave)
        d.modelo, d.serie, d.numero, d.uf = ck.modelo, ck.serie, ck.numero, ck.uf
    return d


def verificar_assinatura_xmldsig(nfe_el, inf_el) -> tuple[bool, str]:
    """Confere DigestValue (SHA-1, C14N inclusiva) e SignatureValue (RSA-SHA1/SHA256).

    Verifica integridade do conteúdo assinado pelo emitente. Não valida a cadeia
    ICP-Brasil do certificado do emitente (ver LIMITACOES.md)."""
    from cryptography import x509
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding

    sig = nfe_el.find(f"{{{NS_DS}}}Signature")
    si = sig.find(f"{{{NS_DS}}}SignedInfo")
    try:
        alg_dig = si.find(f"{{{NS_DS}}}Reference/{{{NS_DS}}}DigestMethod").get("Algorithm", "")
        dig_esperado = base64.b64decode(si.findtext(f"{{{NS_DS}}}Reference/{{{NS_DS}}}DigestValue").strip())
        alg_sig = si.find(f"{{{NS_DS}}}SignatureMethod").get("Algorithm", "")
        valor = base64.b64decode(sig.findtext(f"{{{NS_DS}}}SignatureValue").strip())
        cert_b64 = "".join(sig.findtext(f".//{{{NS_DS}}}X509Certificate").split())
        cert = x509.load_der_x509_certificate(base64.b64decode(cert_b64))
    except Exception as e:  # noqa: BLE001
        return False, f"assinatura incompleta: {e}"
    hdig = hashlib.sha256 if alg_dig.endswith("sha256") else hashlib.sha1
    c14n_inf = etree.tostring(inf_el, method="c14n")
    if hdig(c14n_inf).digest() != dig_esperado:
        return False, "DigestValue não confere: conteúdo de infNFe foi alterado após a assinatura"
    c14n_si = etree.tostring(si, method="c14n")
    halg = hashes.SHA256() if alg_sig.endswith("sha256") else hashes.SHA1()
    try:
        cert.public_key().verify(valor, c14n_si, padding.PKCS1v15(), halg)
    except InvalidSignature:
        return False, "SignatureValue inválido"
    except Exception as e:  # noqa: BLE001
        return False, f"falha ao verificar assinatura: {e}"
    return True, "assinatura íntegra"


def montar_nfeproc(nfe_xml: bytes, prot_nfe_xml: bytes) -> bytes:
    """Une NFe (assinada pelo emitente) e protNFe (retornado pela SEFAZ) em nfeProc.

    Usado quando o emissor guardou o XML sem protocolo e a SEFAZ confirmou a autorização
    pela consulta de situação. Os elementos são copiados byte a byte (sem reformatação)."""
    nfe = etree.fromstring(nfe_xml, _PARSER)
    if etree.QName(nfe).localname == "nfeProc":
        raise ValueError("XML já está no formato nfeProc")
    prot = etree.fromstring(prot_nfe_xml, _PARSER)
    versao = nfe.find(f"{{{NS}}}infNFe").get("versao", "4.00")
    nfe_txt = etree.tostring(nfe, encoding="unicode")
    prot_txt = etree.tostring(prot, encoding="unicode")
    for txt in (nfe_txt, prot_txt):
        if 'xmlns="' not in txt.split(">", 1)[0]:
            raise ValueError("elementos devem declarar o namespace padrão da NF-e")
    saida = f'<?xml version="1.0" encoding="UTF-8"?><nfeProc xmlns="{NS}" versao="{versao}">{nfe_txt}{prot_txt}</nfeProc>'
    return saida.encode("utf-8")
