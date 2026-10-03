"""Emissão pelo Emissor Nacional da NFS-e (Sefin Nacional / ADN — nfse.gov.br), alternativa ao webservice municipal.

Fluxo (Manual de Integração do Sistema Nacional NFS-e, leiaute v1.01):
- monta a DPS (Declaração de Prestação de Serviço) a partir do mesmo RPS usado no canal municipal;
- assina o elemento infDPS (XMLDSig envelopada, RSA-SHA256, C14N) com o certificado A1 (.pfx) do prestador;
- envia por HTTPS com autenticação mútua (o mesmo certificado) em POST /nfse, corpo JSON
  {"dpsXmlGZipB64": base64(gzip(xml))}; a resposta traz chaveAcesso e nfseXmlGZipB64 (ou "erros");
- cancelamento: evento 101101 em POST /nfse/{chave}/eventos, {"pedidoRegistroEventoXmlGZipB64": ...}.
"""

from __future__ import annotations

import base64
import gzip
import hashlib
import json
import os
import re
import ssl
import tempfile
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from xml.sax.saxutils import escape

from lxml import etree

from . import cliente, emissor
from .cliente import NotaEmitida, Resposta
from .modelos import ISS_RETIDO_SIM, Prestador, Rps, dinheiro
from .validacao import validar
from .xml_rps import so_digitos

NS = "http://www.sped.fazenda.gov.br/nfse"
DS = "http://www.w3.org/2000/09/xmldsig#"
VERSAO = "1.01"
VER_APLIC = "EmissorItaborai-1.0"

URLS = {  # (Sefin – emissão/eventos, ADN – DANFSe/parâmetros)
    True: ("https://sefin.nfse.gov.br/sefinnacional", "https://adn.nfse.gov.br"),
    False: ("https://sefin.producaorestrita.nfse.gov.br/SefinNacional", "https://adn.producaorestrita.nfse.gov.br"),
}
CONSULTA_PUBLICA = "https://www.nfse.gov.br/ConsultaPublica/?tpc=1&chave="
SCHEMAS = Path(__file__).resolve().parent.parent / "schemas" / "nacional"

MOTIVOS_CANCELAMENTO = {"1": "Erro na emissão", "2": "Serviço não prestado", "9": "Outros"}


class ErroCertificado(emissor.ErroConfiguracao):
    pass


# ---------------------------------------------------------------- configuração

def configuracao(cfg: dict | None = None) -> dict:
    from . import config
    return (cfg or config.carregar())["emissao"]


def canal(cfg: dict | None = None) -> str:
    return configuracao(cfg).get("canal", "municipal")


# ---------------------------------------------------------------- certificado A1

@dataclass
class Certificado:
    chave: object          # cryptography RSAPrivateKey
    cert: object           # cryptography x509.Certificate
    cadeia: list
    caminho: str
    senha: bytes

    @property
    def der_b64(self) -> str:
        from cryptography.hazmat.primitives.serialization import Encoding
        return base64.b64encode(self.cert.public_bytes(Encoding.DER)).decode()

    @property
    def titular(self) -> str:
        from cryptography.x509.oid import NameOID
        nomes = self.cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        return nomes[0].value if nomes else self.cert.subject.rfc4514_string()

    @property
    def validade(self) -> datetime:
        return getattr(self.cert, "not_valid_after_utc", None) or self.cert.not_valid_after

    @property
    def cnpj(self) -> str:
        """ICP-Brasil e-CNPJ: o CN termina em ':CNPJ'."""
        m = re.search(r":(\d{14})\b", self.titular)
        return m.group(1) if m else ""


def carregar_certificado(cfg: dict | None = None) -> Certificado:
    try:
        from cryptography.hazmat.primitives.serialization import pkcs12
    except ImportError as ex:  # pragma: no cover
        raise ErroCertificado("Instale o pacote 'cryptography' (pip install cryptography).") from ex
    c = configuracao(cfg)
    try:
        arq = emissor.arquivo_da_empresa(c.get("certificado_pfx", ""), "certificado A1 (.pfx)")
    except emissor.ErroConfiguracao as ex:
        raise ErroCertificado(str(ex)) from ex
    senha = (c.get("certificado_senha") or "").encode()
    try:
        chave, cert, cadeia = pkcs12.load_key_and_certificates(arq.read_bytes(), senha or None)
    except ValueError as ex:
        raise ErroCertificado("Não foi possível abrir o certificado: senha incorreta ou arquivo inválido.") from ex
    if not chave or not cert:
        raise ErroCertificado("O arquivo .pfx não contém chave privada e certificado.")
    return Certificado(chave, cert, list(cadeia or []), str(arq), senha)


def info_certificado(cfg: dict | None = None) -> dict:
    cert = carregar_certificado(cfg)
    validade = cert.validade
    dias = (validade.replace(tzinfo=None) - datetime.utcnow()).days
    return {"titular": cert.titular, "cnpj": cert.cnpj, "validade": validade.strftime("%d/%m/%Y"),
            "dias_restantes": dias, "vencido": dias < 0}


# ---------------------------------------------------------------- assinatura XMLDSig

def _c14n(el) -> bytes:
    """Canonicalização do elemento (com os namespaces herdados). Não usa o c14n do lxml: no libxml2 recente
    ele emite xmlns="" nos netos de um subelemento, o que invalida digest e assinatura."""
    return ET.canonicalize(etree.tostring(el, encoding="unicode")).encode("utf-8")


def assinar(xml: str, elemento: str, cert: Certificado) -> str:
    """Assina o elemento `elemento` (atributo Id) e insere <Signature> como seu irmão seguinte."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding

    raiz = etree.fromstring(xml.encode("utf-8"))
    alvo = raiz.find(f"{{{NS}}}{elemento}")
    ref = alvo.get("Id")
    digest = base64.b64encode(hashlib.sha256(_c14n(alvo)).digest()).decode()
    # Montada como texto e reparseada: a canonicalização de elementos criados via API do lxml
    # sob outro namespace padrão sai com xmlns="" nos filhos (assinatura inválida no Sefin).
    sig = etree.fromstring(
        f'<Signature xmlns="{DS}"><SignedInfo>'
        '<CanonicalizationMethod Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"/>'
        '<SignatureMethod Algorithm="http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"/>'
        f'<Reference URI="#{ref}"><Transforms>'
        '<Transform Algorithm="http://www.w3.org/2000/09/xmldsig#enveloped-signature"/>'
        '<Transform Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"/></Transforms>'
        '<DigestMethod Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"/>'
        f'<DigestValue>{digest}</DigestValue></Reference></SignedInfo>'
        f'<SignatureValue></SignatureValue><KeyInfo><X509Data><X509Certificate>{cert.der_b64}'
        '</X509Certificate></X509Data></KeyInfo></Signature>')
    raiz.append(sig)
    raiz = etree.fromstring(etree.tostring(raiz))
    sig = raiz.find(f"{{{DS}}}Signature")
    valor = cert.chave.sign(_c14n(sig.find(f"{{{DS}}}SignedInfo")), padding.PKCS1v15(), hashes.SHA256())
    sig.find(f"{{{DS}}}SignatureValue").text = base64.b64encode(valor).decode()
    return etree.tostring(raiz, encoding="unicode")


def verificar_assinatura(xml: str) -> bool:
    """Confere digest e assinatura (usado nos testes e antes do envio)."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding

    raiz = etree.fromstring(xml.encode("utf-8"))
    sig = raiz.find(f"{{{DS}}}Signature")
    ref = sig.find(f".//{{{DS}}}Reference").get("URI")[1:]
    alvo = next(e for e in raiz if e.get("Id") == ref)
    digest = base64.b64encode(hashlib.sha256(_c14n(alvo)).digest()).decode()
    if digest != sig.findtext(f".//{{{DS}}}DigestValue"):
        return False
    cert = x509.load_der_x509_certificate(base64.b64decode(sig.findtext(f".//{{{DS}}}X509Certificate")))
    try:
        cert.public_key().verify(base64.b64decode(sig.findtext(f"{{{DS}}}SignatureValue")),
                                 _c14n(sig.find(f"{{{DS}}}SignedInfo")), padding.PKCS1v15(), hashes.SHA256())
    except Exception:
        return False
    return True


# ---------------------------------------------------------------- DPS

def _t(tag: str, valor) -> str:
    valor = "" if valor is None else str(valor)
    return f"<{tag}>{escape(valor)}</{tag}>" if valor != "" else ""


def _txt(s: str, limite: int) -> str:
    return " ".join(str(s or "").split())[:limite]


def _v(d) -> str:
    return f"{dinheiro(d):.2f}"


def id_dps(cmun: str, cnpj: str, serie: str, numero: str) -> str:
    """'DPS' + cMun(7) + tipo inscrição (1 CPF / 2 CNPJ) + inscrição(14) + série(5) + nDPS(15)."""
    tipo = "2" if len(cnpj) == 14 else "1"
    return f"DPS{cmun}{tipo}{cnpj.zfill(14)}{serie.zfill(5)}{numero.zfill(15)}"


def _aliquota_sn(cfg: dict) -> Decimal:
    """Percentual aproximado dos tributos do Simples (pTotTribSN): alíquota efetiva do Anexo III pelo RBT12."""
    try:
        from . import relatorios
        hoje = datetime.now(emissor.FUSO).date()
        r = relatorios.rbt12(hoje)
        if r > 0:
            return Decimal(str(relatorios.aliquota_efetiva_anexo3(r))).quantize(Decimal("0.01"))
    except Exception:
        pass
    return Decimal(str(cfg["financeiro"].get("aliquota_simples_pct", 6))).quantize(Decimal("0.01"))


# tpRetPisCofins (NT 007/2026) pela combinação retida de (PIS, COFINS, CSLL)
TP_RET_PCC = {(0, 0, 0): "0", (1, 1, 1): "3", (1, 1, 0): "4", (1, 0, 0): "5", (0, 1, 0): "6",
              (0, 1, 1): "7", (0, 0, 1): "8", (1, 0, 1): "9"}


def _trib_federal(rps: Rps, regime: str) -> str:
    """Grupo tribFed conforme o regime: PIS/COFINS próprio (Real/Presumido) e retenções na fonte."""
    from . import fiscal
    r = rps.retencoes
    if regime == "mei":
        return ""                # tributos federais do MEI são fixos no DAS-MEI
    pcc = (int(bool(r.valor_pis)), int(bool(r.valor_cofins)), int(bool(r.valor_csll)))
    if regime == "simples" and any(pcc[:2]):
        raise ValueError("Optante do Simples Nacional não sofre retenção de PIS/COFINS (Lei 10.833/2003, art. 32, "
                         "II): ajuste a regra fiscal deste tomador.")
    pis_cofins = ""
    x = rps.extras or {}
    if regime in fiscal.PIS_COFINS:
        cst = so_digitos(x.get("pis_cofins_cst")) or "01"
        if cst in ("01", "02", "03", "05"):        # tributável: base, alíquotas e valores
            p_pis = _d(x.get("p_pis") or fiscal.PIS_COFINS[regime][0])
            p_cof = _d(x.get("p_cofins") or fiscal.PIS_COFINS[regime][1])
            base = rps.base_calculo
            valores = (_t("vBCPisCofins", _v(base)) + _t("pAliqPis", _v(p_pis)) + _t("pAliqCofins", _v(p_cof))
                       + _t("vPis", _v(dinheiro(base * p_pis / 100))) + _t("vCofins", _v(dinheiro(base * p_cof / 100))))
        else:                                       # alíquota zero, isenção, sem incidência, suspensão, outras
            valores = ""
        pis_cofins = ("<piscofins>" + _t("CST", cst) + valores + _t("tpRetPisCofins", TP_RET_PCC[pcc]) + "</piscofins>")
    # NT 007/2026: vRetCSLL leva a soma de PIS + COFINS + CSLL retidos
    soma_pcc = dinheiro(r.valor_pis + r.valor_cofins + r.valor_csll)
    corpo = (pis_cofins + (_t("vRetCP", _v(r.valor_inss)) if r.valor_inss else "")
             + (_t("vRetIRRF", _v(r.valor_ir)) if r.valor_ir else "")
             + (_t("vRetCSLL", _v(soma_pcc)) if soma_pcc else ""))
    return f"<tribFed>{corpo}</tribFed>" if corpo else ""


def _d(v) -> Decimal:
    return Decimal(str(v).replace(",", "."))


def _pessoa(tag: str, doc, nome) -> str:
    doc = so_digitos(doc)
    if not doc:
        return ""
    return (f"<{tag}>" + _t("CNPJ" if len(doc) == 14 else "CPF", doc) + _t("xNome", _txt(nome, 150)) + f"</{tag}>")


def _end_ext(ext: dict, en) -> str:
    """Endereço no exterior (endExt) + logradouro; só sai quando há logradouro (o grupo end é opcional)."""
    if not getattr(en, "logradouro", ""):
        return ""
    return ("<end><endExt>" + _t("cPais", ext.get("pais_iso")) + _t("cEndPost", _txt(ext.get("cod_postal") or "0", 11))
            + _t("xCidade", _txt(ext.get("cidade"), 60)) + _t("xEstProvReg", _txt(ext.get("estado") or ext.get("cidade"), 60))
            + "</endExt>" + _t("xLgr", _txt(" ".join(x for x in (en.tipo_logradouro, en.logradouro) if x), 255))
            + _t("nro", _txt(en.numero or "S/N", 60)) + _t("xCpl", _txt(en.complemento, 156))
            + _t("xBairro", _txt(en.bairro or "-", 60)) + "</end>")


def _id_pessoa(doc: str, ext: dict) -> str:
    """CNPJ/CPF, ou NIF / motivo de não ter NIF (cliente do exterior)."""
    if ext:
        return _t("NIF", _txt(ext["nif"], 40)) if ext.get("nif") else _t("cNaoNIF", ext.get("sem_nif") or "0")
    return _t("CNPJ" if len(doc) == 14 else "CPF", doc)


def _end_nac(en) -> str:
    cep, cmun_t = so_digitos(en.cep), so_digitos(en.codigo_municipio)
    if not (len(cep) == 8 and len(cmun_t) == 7 and en.logradouro and en.bairro):
        return ""
    return (f"<end><endNac>{_t('cMun', cmun_t)}{_t('CEP', cep)}</endNac>"
            + _t("xLgr", _txt(" ".join(x for x in (en.tipo_logradouro, en.logradouro) if x), 255))
            + _t("nro", _txt(en.numero or "S/N", 60)) + _t("xCpl", _txt(en.complemento, 156))
            + _t("xBairro", _txt(en.bairro, 60)) + "</end>")


def _com_ext(x: dict) -> str:
    """Comércio exterior (exportação/importação de serviço): moeda e valor na moeda são obrigatórios."""
    if not (x.get("comext_moeda") and x.get("comext_valor")):
        return ""
    return ("<comExt>" + _t("mdPrestacao", x.get("comext_md") or "1") + _t("vincPrest", x.get("comext_vinc") or "0")
            + _t("tpMoeda", so_digitos(x["comext_moeda"]).zfill(3)) + _t("vServMoeda", _v(_d(x["comext_valor"])))
            + _t("mecAFComexP", (x.get("comext_mec_p") or "01").zfill(2)) + _t("mecAFComexT", (x.get("comext_mec_t") or "01").zfill(2))
            + _t("movTempBens", x.get("comext_mov") or "1") + _t("nDI", _txt(x.get("comext_di"), 12))
            + _t("nRE", _txt(x.get("comext_re"), 12)) + _t("mdic", x.get("comext_mdic") or "0") + "</comExt>")


TIPOS_DOC_DED = ("chNFSe", "chNFe", "NFSeMun", "NFNFS", "nDocFisc", "nDoc")


def _doc_ded(d: dict) -> str:
    tipo = d.get("tipo") if d.get("tipo") in TIPOS_DOC_DED else "nDoc"
    if tipo in ("chNFSe", "chNFe"):
        ident = _t(tipo, so_digitos(d.get("chave")))
    elif tipo == "NFSeMun":
        ident = ("<NFSeMun>" + _t("cMunNFSeMun", so_digitos(d.get("cmun"))) + _t("nNFSeMun", so_digitos(d.get("numero")))
                 + _t("cVerifNFSeMun", _txt(d.get("cod_verif"), 9)) + "</NFSeMun>")
    elif tipo == "NFNFS":
        ident = ("<NFNFS>" + _t("nNFS", so_digitos(d.get("numero"))) + _t("modNFS", so_digitos(d.get("modelo")) or "1")
                 + _t("serieNFS", _txt(d.get("serie") or "1", 15)) + "</NFNFS>")
    else:
        ident = _t(tipo, _txt(d.get("numero"), 255))
    fdoc = so_digitos(d.get("fornec_doc"))
    fornec = (f"<fornec>{_t('CNPJ' if len(fdoc) == 14 else 'CPF', fdoc)}{_t('xNome', _txt(d.get('fornec_nome'), 150))}</fornec>"
              if fdoc else "")
    tp = str(d.get("tp") or "99")
    return ("<docDedRed>" + ident + _t("tpDedRed", tp)
            + (_t("xDescOutDed", _txt(d.get("descricao") or "Outras deduções", 150)) if tp == "99" else "")
            + _t("dtEmiDoc", d.get("data")) + _t("vDedutivelRedutivel", _v(_d(d.get("valor_dedutivel") or d.get("valor_deducao"))))
            + _t("vDeducaoReducao", _v(_d(d.get("valor_deducao")))) + fornec + "</docDedRed>")


def _subst(x: dict) -> str:
    """Substituição de NFS-e (chave da nota substituída + motivo)."""
    ch = str(x.get("subst_chave") or "").strip()
    if not ch:
        return ""
    return ("<subst>" + _t("chSubstda", ch) + _t("cMotivo", x.get("subst_motivo") or "99")
            + _t("xMotivo", _txt(x.get("subst_xmotivo"), 255)) + "</subst>")


def _obra(x: dict) -> str:
    cno, cib = so_digitos(x.get("obra_cno")), str(x.get("obra_cib") or "").strip()
    if not (cno or cib):
        return ""
    return ("<obra>" + _t("inscImobFisc", _txt(x.get("obra_insc_imob"), 30))
            + (_t("cObra", cno[:30]) if cno else _t("cCIB", cib[:8])) + "</obra>")


def _evento(x: dict) -> str:
    if not x.get("evento_nome"):
        return ""
    if x.get("evento_id"):
        local = _t("idAtvEvt", _txt(x["evento_id"], 30))
    else:
        local = ("<end>" + _t("CEP", so_digitos(x.get("evento_cep"))) + _t("xLgr", _txt(x.get("evento_lgr"), 255))
                 + _t("nro", _txt(x.get("evento_nro") or "S/N", 60)) + _t("xBairro", _txt(x.get("evento_bairro"), 60))
                 + "</end>")
    return ("<atvEvento>" + _t("xNome", _txt(x["evento_nome"], 255)) + _t("dtIni", x.get("evento_ini"))
            + _t("dtFim", x.get("evento_fim") or x.get("evento_ini")) + local + "</atvEvento>")


def _info_compl(x: dict, obs: str) -> str:
    corpo = (_t("idDocTec", _txt(x.get("doc_tec"), 40)) + _t("docRef", _txt(x.get("doc_ref"), 255))
             + _t("xPed", _txt(x.get("pedido"), 15)) + _t("xInfComp", obs))
    return f"<infoCompl>{corpo}</infoCompl>" if corpo else ""


def _tot_trib(rps: Rps, regime: str, op_sn: str, x: dict, cfg: dict) -> str:
    """Carga aproximada (Lei 12.741/2012): uma das formas do leiaute, conforme a regra geral e o regime."""
    modo = x.get("tot_trib_modo") or "auto"
    if modo == "nao" or (modo == "auto" and regime == "mei"):
        return _t("indTotTrib", "0")
    if modo == "percentual":
        return ("<pTotTrib>" + "".join(_t(t, _v(_d(x.get(k) or 0))) for t, k in
                (("pTotTribFed", "p_tot_fed"), ("pTotTribEst", "p_tot_est"), ("pTotTribMun", "p_tot_mun"))) + "</pTotTrib>")
    if modo == "simples" or (modo == "auto" and op_sn == "3"):
        return _t("pTotTribSN", f"{_aliquota_sn(cfg):.2f}")
    return ("<vTotTrib>" + _t("vTotTribFed", _v(rps.valor_total_tributos))
            + _t("vTotTribEst", "0.00") + _t("vTotTribMun", "0.00") + "</vTotTrib>")


def _ibscbs(rps: Rps, x: dict, ctrib: str) -> str:
    refs = [so_digitos(c) for c in str(x.get("ref_nfse") or "").replace(";", ",").split(",") if so_digitos(c)]
    dest = ""
    if so_digitos(x.get("dest_doc")):
        d = so_digitos(x["dest_doc"])
        dest = "<dest>" + _t("CNPJ" if len(d) == 14 else "CPF", d) + _t("xNome", _txt(x.get("dest_nome"), 150)) + "</dest>"
    imovel = ""
    if x.get("imovel_cib"):
        imovel = ("<imovel>" + _t("inscImobFisc", _txt(x.get("imovel_insc_imob"), 30))
                  + _t("cCIB", str(x["imovel_cib"])[:8]) + "</imovel>")
    ree = ""
    if x.get("ree_valor"):
        chave = so_digitos(x.get("ree_chave"))
        doc = (f"<dFeNacional>{_t('tipoChaveDFe', x.get('ree_tipo_chave') or '1')}{_t('chaveDFe', chave)}</dFeNacional>"
               if chave else f"<docOutro>{_t('nDoc', _txt(x.get('ree_ndoc'), 255))}{_t('xDoc', _txt(x.get('ree_xdoc'), 255))}</docOutro>")
        fdoc = so_digitos(x.get("ree_fornec_doc"))
        fornec = (f"<fornec>{_t('CNPJ' if len(fdoc) == 14 else 'CPF', fdoc)}{_t('xNome', _txt(x.get('ree_fornec_nome'), 150))}</fornec>"
                  if fdoc else "")
        ree = ("<gReeRepRes><documentos>" + doc + fornec + _t("dtEmiDoc", x.get("ree_dt_emi")) + _t("dtCompDoc", x.get("ree_dt_comp") or x.get("ree_dt_emi"))
               + _t("tpReeRepRes", x.get("ree_tipo") or "99")
               + (_t("xTpReeRepRes", _txt(x.get("ree_xtipo") or "Reembolso de despesa", 150)) if (x.get("ree_tipo") or "99") == "99" else "")
               + _t("vlrReeRepRes", _v(_d(x["ree_valor"]))) + "</documentos></gReeRepRes>")
    reg = (f"<gTribRegular>{_t('CSTReg', so_digitos(x['cst_reg']))}{_t('cClassTribReg', so_digitos(x.get('class_trib_reg')))}</gTribRegular>"
           if x.get("cst_reg") and x.get("class_trib_reg") else "")
    dif = ""
    if any(x.get(k) for k in ("p_dif_uf", "p_dif_mun", "p_dif_cbs")):
        dif = ("<gDif>" + "".join(_t(t, _v(_d(x.get(k) or 0))) for t, k in
               (("pDifUF", "p_dif_uf"), ("pDifMun", "p_dif_mun"), ("pDifCBS", "p_dif_cbs"))) + "</gDif>")
    return ("<IBSCBS>" + _t("finNFSe", "0") + _t("indFinal", "1" if rps.ind_final == "1" else "0")
            + _t("cIndOp", so_digitos(rps.indicador_operacao)) + _t("tpOper", x.get("tp_oper"))
            + ("<gRefNFSe>" + "".join(_t("refNFSe", c) for c in refs[:99]) + "</gRefNFSe>" if refs else "")
            + _t("tpEnteGov", x.get("tp_ente_gov")) + _t("indDest", "1" if dest else "0") + dest + imovel
            + "<valores>" + ree + "<trib><gIBSCBS>" + _t("CST", ctrib[:3]) + _t("cClassTrib", ctrib)
            + _t("cCredPres", so_digitos(x.get("c_cred_pres"))[:2]) + reg + dif
            + "</gIBSCBS></trib></valores></IBSCBS>")


def gerar_dps(rps: Rps, prestador: Prestador, producao: bool, serie: str, numero: str,
              cfg: dict | None = None, agora: datetime | None = None) -> str:
    from . import config
    cfg = cfg or config.carregar()
    e = cfg["emissao"]
    agora = agora or datetime.now(emissor.FUSO).replace(microsecond=0)
    # Sefin recusa dhEmi no futuro; um minuto de folga para diferença de relógio
    dh = (agora - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%S") + "-03:00"
    compet = rps.competencia or agora.date()
    if compet > agora.date():
        compet = agora.date()
    cnpj = so_digitos(prestador.cnpj)
    cmun = e.get("municipio_emissor") or "3301900"
    ident = id_dps(cmun, cnpj, serie, numero)

    from . import fiscal
    f = fiscal.geral(cfg)
    regime = f["regime"]
    op_sn = fiscal.OP_SIMP_NAC[regime]
    reg = (_t("opSimpNac", op_sn)
           + (_t("regApTribSN", e.get("reg_ap_trib_sn", "2")) if op_sn == "3" else "")
           + _t("regEspTrib", "0" if regime == "mei" else e.get("reg_esp_trib", "0")))
    prest = (f"<prest>{_t('CNPJ', cnpj)}"
             + (_t("IM", so_digitos(prestador.inscricao_municipal)) if e.get("informar_im") else "")
             + f"<regTrib>{reg}</regTrib></prest>")

    tom = rps.tomador
    ext = tom.estrangeiro or {}
    doc = "" if ext else so_digitos(tom.cpf_cnpj)
    contraparte = ""
    if doc or ext:
        end = _end_ext(ext, tom.endereco) if ext else _end_nac(tom.endereco)
        fone = so_digitos(tom.telefone)
        email = (tom.email or "").split(";")[0].split(",")[0].strip()
        im_t = so_digitos(tom.inscricao_municipal).lstrip("0")
        contraparte = (_id_pessoa(doc, ext)
                       + (_t("IM", im_t) if im_t and e.get("informar_im") and not ext else "")
                       + _t("xNome", _txt(tom.razao_social, 300)) + end
                       + (_t("fone", fone) if 6 <= len(fone) <= 20 else "")
                       + (_t("email", email[:80]) if "@" in email else ""))
    toma = f"<toma>{contraparte}</toma>" if contraparte else ""

    x = rps.extras or {}
    # Emissão pelo tomador (2) ou pelo intermediário (3): o cliente escolhido na tela é o PRESTADOR do serviço
    # (ex.: importação de serviço) e esta empresa entra como tomador ou intermediário.
    tp_emit = str(x.get("tp_emit") or "1")
    if tp_emit in ("2", "3") and contraparte:
        op_p = x.get("prest_op_simp_nac") or "1"
        reg_p = (_t("opSimpNac", op_p) + (_t("regApTribSN", "1") if op_p == "3" else "") + _t("regEspTrib", "0"))
        prest = f"<prest>{contraparte}<regTrib>{reg_p}</regTrib></prest>"
        nome_emp = _txt(cfg.get("empresa", {}).get("nome") or "EMPRESA", 300)
        eu = _t("CNPJ", cnpj) + _t("xNome", nome_emp)
        if tp_emit == "2":
            toma = f"<toma>{eu}</toma>"
        else:
            toma = _pessoa("toma", x.get("toma_doc"), x.get("toma_nome"))
            x = {**x, "interm_doc": cnpj, "interm_nome": nome_emp}
    desc = _txt("; ".join(i.descricao for i in rps.itens), 2000)
    obs = _txt(rps.observacoes, 2000)
    loc = (_t("cPaisPrestacao", str(x["local_prestacao_pais"]).upper()) if x.get("local_prestacao_pais")
           else _t("cLocPrestacao", so_digitos(rps.local_prestacao) or "3301900"))
    serv = ("<serv><locPrest>" + loc + "</locPrest>"
            + "<cServ>" + _t("cTribNac", so_digitos(rps.codigo_desdobro)[:6])
            + _t("cTribMun", so_digitos(rps.codigo_tributacao_municipio)[:3] if len(so_digitos(rps.codigo_tributacao_municipio)) == 3 else "")
            + _t("xDescServ", desc) + _t("cNBS", so_digitos(rps.codigo_nbs)) + "</cServ>"
            + _com_ext(x) + _obra(x) + _evento(x) + _info_compl(x, obs) + "</serv>")

    retido = rps.iss_retido == ISS_RETIDO_SIM
    trib_issqn = str(x.get("trib_issqn") or "1")
    if regime == "mei" or trib_issqn != "1":
        retido = False          # MEI: ISS no DAS-MEI (E1302); imune/exportação/não incidência: nada a reter
    desc_cond, desc_inc = dinheiro(rps.desconto_condicionado), dinheiro(rps.desconto_incondicionado)
    descontos = ""
    if desc_cond or desc_inc:
        descontos = ("<vDescCondIncond>" + (_t("vDescIncond", _v(desc_inc)) if desc_inc else "")
                     + (_t("vDescCond", _v(desc_cond)) if desc_cond else "") + "</vDescCondIncond>")
    ded = ""
    if x.get("ded_docs"):
        ded = "<vDedRed><documentos>" + "".join(_doc_ded(d) for d in x["ded_docs"][:1000]) + "</documentos></vDedRed>"
    elif x.get("ded_pct"):
        ded = f"<vDedRed>{_t('pDR', _v(Decimal(str(x['ded_pct']))))}</vDedRed>"
    elif rps.valor_deducoes:
        ded = f"<vDedRed>{_t('vDR', _v(rps.valor_deducoes))}</vDedRed>"
    susp = (f"<exigSusp>{_t('tpSusp', x['exig_susp_tp'])}{_t('nProcesso', x.get('exig_susp_proc'))}</exigSusp>"
            if x.get("exig_susp_tp") else "")
    bm = (f"<BM>{_t('nBM', x['n_bm'])}{_t('pRedBCBM', _v(Decimal(str(x['p_red_bm']))) if x.get('p_red_bm') else '')}</BM>"
          if x.get("n_bm") else "")
    tp_ret = ("3" if x.get("ret_iss_por") == "intermediario" else "2") if retido else "1"
    # alíquota só para ME/EPP com retenção (E0625); não optante em município conveniado usa a parametrizada (E0617)
    trib_mun = ("<tribMun>" + _t("tribISSQN", trib_issqn)
                + (_t("cPaisResult", x.get("pais_result")) if trib_issqn == "3" else "")
                + (_t("tpImunidade", x.get("tp_imunidade") or "0") if trib_issqn == "2" else "")
                + susp + bm + _t("tpRetISSQN", tp_ret)
                + (_t("pAliq", _v(rps.aliquota_iss)) if retido and op_sn == "3" and rps.aliquota_iss else "")
                + "</tribMun>")
    trib_fed = _trib_federal(rps, regime)
    tot = _tot_trib(rps, regime, op_sn, x, cfg)
    vreceb = _t("vReceb", _v(Decimal(str(x["v_receb"])))) if x.get("v_receb") and x.get("interm_doc") else ""
    valores = ("<valores><vServPrest>" + vreceb + _t("vServ", _v(rps.valor_servicos)) + "</vServPrest>" + descontos
               + ded + "<trib>" + trib_mun + trib_fed + f"<totTrib>{tot}</totTrib></trib></valores>")

    ibscbs = ""
    ctrib = so_digitos(rps.classificacao_tributaria)
    if fiscal.informar_ibscbs(f, compet) and ctrib and so_digitos(rps.indicador_operacao):
        ibscbs = _ibscbs(rps, x, ctrib)
    interm = _pessoa("interm", x.get("interm_doc"), x.get("interm_nome"))

    return (f'<DPS xmlns="{NS}" versao="{VERSAO}"><infDPS Id="{ident}">'
            + _t("tpAmb", "1" if producao else "2") + _t("dhEmi", dh) + _t("verAplic", VER_APLIC)
            + _t("serie", serie) + _t("nDPS", numero) + _t("dCompet", compet.isoformat())
            + _t("tpEmit", tp_emit if tp_emit in ("2", "3") else "1")
            + (_t("cMotivoEmisTI", x.get("motivo_emis_ti") or "1") if tp_emit in ("2", "3") else "")
            + _t("cLocEmi", cmun)
            + _subst(x) + prest + toma + interm + serv + valores + ibscbs + "</infDPS></DPS>")


def gerar_cancelamento(chave: str, cnpj: str, motivo: str, justificativa: str, producao: bool,
                       agora: datetime | None = None) -> str:
    agora = agora or datetime.now(emissor.FUSO).replace(microsecond=0)
    dh = (agora - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%S") + "-03:00"
    return (f'<pedRegEvento xmlns="{NS}" versao="{VERSAO}"><infPedReg Id="PRE{chave}101101">'
            + _t("tpAmb", "1" if producao else "2") + _t("verAplic", VER_APLIC) + _t("dhEvento", dh)
            + _t("CNPJAutor", so_digitos(cnpj)) + _t("chNFSe", chave)
            + "<e101101>" + _t("xDesc", "Cancelamento de NFS-e") + _t("cMotivo", motivo)
            + _t("xMotivo", _txt(justificativa, 255)) + "</e101101></infPedReg></pedRegEvento>")


_SCHEMAS: dict = {}


def validar_xsd(xml: str, arquivo: str = "DPS_v1.01.xsd") -> None:
    from .validacao import ErroValidacao
    if arquivo not in _SCHEMAS:
        _SCHEMAS[arquivo] = etree.XMLSchema(etree.parse(str(SCHEMAS / arquivo)))
    esquema = _SCHEMAS[arquivo]
    doc = etree.fromstring(xml.encode("utf-8"))
    if not esquema.validate(doc):
        raise ErroValidacao([f"Leiaute nacional: {e.message}" for e in esquema.error_log][:10])


# ---------------------------------------------------------------- comunicação (mTLS)

def _contexto_ssl(cert: Certificado) -> ssl.SSLContext:
    """Contexto TLS com o certificado do cliente. A chave vai para um arquivo temporário cifrado
    com senha aleatória (o ssl do Python só lê de arquivo) e é apagada logo após o carregamento."""
    import secrets
    from cryptography.hazmat.primitives.serialization import BestAvailableEncryption, Encoding, PrivateFormat
    ctx = ssl.create_default_context()
    senha = secrets.token_hex(16).encode()
    pem = cert.chave.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, BestAvailableEncryption(senha))
    pem += cert.cert.public_bytes(Encoding.PEM) + b"".join(c.public_bytes(Encoding.PEM) for c in cert.cadeia)
    fd, caminho = tempfile.mkstemp(suffix=".pem")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(pem)
        ctx.load_cert_chain(caminho, password=senha)
    finally:
        os.unlink(caminho)
    return ctx


def _requisicao(metodo: str, url: str, cert: Certificado, corpo: dict | None = None,
                contexto: ssl.SSLContext | None = None) -> tuple[int, bytes]:
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(url, data=dados, method=metodo,
                                 headers={"Content-Type": "application/json", "Accept": "application/json"})
    ctx = contexto or _contexto_ssl(cert)
    try:
        with urllib.request.urlopen(req, timeout=cliente.TIMEOUT, context=ctx) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as ex:
        return ex.code, ex.read()


def _gz64(xml: str) -> str:
    return base64.b64encode(gzip.compress(xml.encode("utf-8"))).decode()


def _de_gz64(s: str) -> str:
    return gzip.decompress(base64.b64decode(s)).decode("utf-8")


def _mensagens(js: dict, chave: str) -> list[str]:
    itens = js.get(chave) or js.get(chave.capitalize()) or []
    if isinstance(itens, dict):
        itens = [itens]
    out = []
    for i in itens:
        if isinstance(i, str):
            out.append(i)
            continue
        cod = i.get("Codigo") or i.get("codigo") or ""
        desc = i.get("Descricao") or i.get("descricao") or i.get("mensagem") or ""
        comp = i.get("Complemento") or i.get("complemento") or ""
        out.append(" - ".join(x for x in (str(cod), desc, comp) if x))
    return out


def interpretar(status: int, bruto: bytes, xml_enviado: str) -> Resposta:
    texto = bruto.decode("utf-8", "replace")
    try:
        js = json.loads(texto) if texto.strip() else {}
    except ValueError:
        js = {}
    erros = _mensagens(js, "erros") if isinstance(js, dict) else []
    resp = Resposta(sucesso=False, xml_enviado=xml_enviado, xml_retorno=texto, status_http=status, erros=erros,
                    alertas=_mensagens(js, "alertas") if isinstance(js, dict) else [])
    if status in (200, 201) and isinstance(js, dict) and js.get("chaveAcesso") and not erros:
        xml_nfse = _de_gz64(js["nfseXmlGZipB64"]) if js.get("nfseXmlGZipB64") else ""
        numero = ""
        if xml_nfse:
            try:
                numero = etree.fromstring(xml_nfse.encode()).findtext(f".//{{{NS}}}nNFSe") or ""
            except etree.XMLSyntaxError:
                pass
        chave = js["chaveAcesso"]
        resp.sucesso = True
        resp.notas = [NotaEmitida(numero_nfse=numero or chave[-13:].lstrip("0"), codigo_verificacao=chave,
                                  data_emissao=js.get("dataHoraProcessamento", ""), link=CONSULTA_PUBLICA + chave,
                                  numero_rps=js.get("idDps", ""), xml=xml_nfse)]
    elif not erros:
        resp.erros = [f"Sefin Nacional respondeu HTTP {status}: {texto[:300] or 'sem conteúdo'}"]
    return resp


# ---------------------------------------------------------------- numeração da DPS

def _proximo_dps() -> int:
    from . import config
    arq = emissor._arquivo_sequencia()
    salvo = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else {}
    return max(int(salvo.get("proximo_dps", 0) or 0), int(config.carregar()["emissao"].get("proximo_dps", 1) or 1))


def _avancar_dps(numero: int) -> None:
    arq = emissor._arquivo_sequencia()
    salvo = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else {}
    salvo["proximo_dps"] = max(int(salvo.get("proximo_dps", 0) or 0), numero + 1)
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps(salvo, indent=2), encoding="utf-8")


# ---------------------------------------------------------------- operações

def prestador() -> Prestador:
    emissor.carregar_env()
    cnpj = so_digitos(emissor.env("ITABORAI_CNPJ"))
    if not cnpj:
        raise emissor.ErroConfiguracao("Configure ITABORAI_CNPJ no arquivo .env.")
    return Prestador(cnpj=cnpj, inscricao_municipal=so_digitos(emissor.env("ITABORAI_IM")),
                     chave_webservice="")


def preparar(rps: Rps, producao: bool, cert: Certificado | None = None, cfg: dict | None = None,
             numero: int | None = None) -> tuple[str, str, list[str]]:
    """Valida, gera, confere no XSD e assina a DPS. Devolve (xml assinado, nDPS, alertas)."""
    from . import config
    cfg = cfg or config.carregar()
    numero = numero or _proximo_dps()
    rps.numero = str(numero)
    rps.data_emissao = rps.data_emissao or datetime.now(emissor.FUSO).replace(tzinfo=None, microsecond=0)
    alertas = validar(rps)
    alertas += _regras_raras(rps)
    prest = prestador()
    serie = str(cfg["emissao"].get("serie_dps", "900"))
    xml = gerar_dps(rps, prest, producao, serie, str(numero), cfg)
    validar_xsd(xml)
    if cert is None:
        return xml, str(numero), alertas
    if cert.cnpj and cert.cnpj[:8] != prest.cnpj[:8]:
        raise ErroCertificado(f"O certificado é do CNPJ {cert.cnpj}, mas o prestador é {prest.cnpj}.")
    assinado = assinar(xml, "infDPS", cert)
    validar_xsd(assinado)
    return assinado, str(numero), alertas


def _regras_raras(rps: Rps) -> list[str]:
    """Exportação/importação, emissão pelo tomador/intermediário e dedução por documentos."""
    from .validacao import ErroValidacao
    x, erros, alertas = rps.extras or {}, [], []
    tp = str(x.get("tp_emit") or "1")
    exterior = bool(rps.tomador.estrangeiro)
    comext = bool(x.get("comext_moeda") and x.get("comext_valor"))
    if str(x.get("trib_issqn") or "1") == "3" and not comext:
        erros.append("Exportação de serviço: preencha Comércio exterior (moeda e valor na moeda estrangeira).")
    if tp == "2" and exterior and not comext:
        erros.append("Importação de serviço (emitida pelo tomador): preencha Comércio exterior (moeda e valor).")
    if exterior and not comext and tp == "1":
        alertas.append("Tomador do exterior: se for exportação de serviço, marque Situação do ISS = Exportação e "
                       "preencha Comércio exterior.")
    if tp in ("2", "3") and not so_digitos(rps.tomador.cpf_cnpj) and not exterior:
        erros.append("Emissão pelo tomador/intermediário: escolha o PRESTADOR do serviço no campo Cliente.")
    if tp == "3" and len(so_digitos(x.get("toma_doc"))) not in (11, 14):
        erros.append("Emissão pelo intermediário: informe CPF/CNPJ e nome do tomador do serviço.")
    total_ded = sum(_d(d.get("valor_deducao") or 0) for d in x.get("ded_docs") or [])
    if total_ded > rps.valor_servicos:
        erros.append("Dedução por documentos maior que o valor do serviço.")
    if erros:
        raise ErroValidacao(erros)
    return alertas


def emitir(rps: Rps, producao: bool = False, url: str | None = None, contexto: ssl.SSLContext | None = None,
           numero: int | None = None) -> Resposta:
    """`numero` fixo (assistente de validação) não usa nem avança o contador de DPS da empresa."""
    from . import config
    cfg = config.carregar()
    producao = emissor.producao_autorizada(producao)
    cert = carregar_certificado(cfg)
    base = url or URLS[producao][0]
    for tentativa in range(2):
        xml, n_dps, alertas = preparar(rps, producao, cert, cfg, numero=numero)
        pasta = emissor.RAIZ / "saida" / datetime.now(emissor.FUSO).strftime("%Y-%m") / f"DPS_{n_dps}"
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / "dps.xml").write_text(xml, encoding="utf-8")
        status, bruto = _requisicao("POST", base.rstrip("/") + "/nfse", cert, {"dpsXmlGZipB64": _gz64(xml)}, contexto)
        (pasta / "retorno.json").write_bytes(bruto)
        resp = interpretar(status, bruto, xml)
        # O nº da DPS é consumido mesmo com rejeição por duplicidade (E0014: DPS já existente): avança e repete.
        duplicada = any("E0014" in e or "já exist" in e.lower() for e in resp.erros)
        if (resp.sucesso or duplicada) and not numero:
            _avancar_dps(int(n_dps))
        for nota in resp.notas:
            if nota.xml:
                (pasta / f"NFSe_{nota.codigo_verificacao}.xml").write_text(nota.xml, encoding="utf-8")
        (pasta / "resumo.json").write_text(json.dumps({
            "canal": "nacional", "ambiente": "producao" if producao else "producao_restrita", "dps": n_dps,
            "sucesso": resp.sucesso, "erros": resp.erros, "chave": resp.notas[0].codigo_verificacao if resp.notas else "",
        }, indent=2, ensure_ascii=False), encoding="utf-8")
        resp.alertas = alertas + resp.alertas
        resp.pasta = str(pasta)
        if not duplicada or tentativa:
            if tentativa:
                resp.alertas.insert(0, "A DPS anterior já existia no Sefin; reenviada com o número seguinte.")
            return resp
        rps.numero = ""
        numero = numero + 1 if numero else None
    return resp  # pragma: no cover


def cancelar(chave: str, justificativa: str, producao: bool = False, motivo: str = "1", url: str | None = None,
             contexto: ssl.SSLContext | None = None) -> Resposta:
    chave = re.sub(r"\s", "", chave or "")
    if not re.fullmatch(r"[0-9A-Z]{50}", chave):
        raise ValueError("Informe a chave de acesso da NFS-e nacional (50 caracteres).")
    if len(justificativa.strip()) < 15:
        raise ValueError("Justificativa do cancelamento deve ter ao menos 15 caracteres.")
    if motivo not in MOTIVOS_CANCELAMENTO:
        motivo = "9"
    producao = emissor.producao_autorizada(producao)
    cert = carregar_certificado()
    xml = gerar_cancelamento(chave, prestador().cnpj, motivo, justificativa, producao)
    xml = assinar(xml, "infPedReg", cert)
    validar_xsd(xml, "pedRegEvento_v1.01.xsd")
    base = url or URLS[producao][0]
    pasta = emissor.RAIZ / "saida" / datetime.now(emissor.FUSO).strftime("%Y-%m") / f"CANCELAMENTO_{chave[-15:]}"
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "evento.xml").write_text(xml, encoding="utf-8")
    status, bruto = _requisicao("POST", f"{base.rstrip('/')}/nfse/{chave}/eventos", cert,
                                {"pedidoRegistroEventoXmlGZipB64": _gz64(xml)}, contexto)
    (pasta / "retorno.json").write_bytes(bruto)
    texto = bruto.decode("utf-8", "replace")
    try:
        js = json.loads(texto) if texto.strip() else {}
    except ValueError:
        js = {}
    erros = _mensagens(js, "erros") if isinstance(js, dict) else []
    ok = status in (200, 201) and not erros
    if not ok and not erros:
        erros = [f"Sefin Nacional respondeu HTTP {status}: {texto[:300]}"]
    if ok and isinstance(js, dict) and js.get("eventoXmlGZipB64"):
        (pasta / "evento_registrado.xml").write_text(_de_gz64(js["eventoXmlGZipB64"]), encoding="utf-8")
    return Resposta(sucesso=ok, xml_enviado=xml, xml_retorno=texto, status_http=status, erros=erros,
                    situacao="cancelada" if ok else "", pasta=str(pasta))


def testar_conexao(producao: bool | None = None) -> dict:
    """Abre o certificado e consulta os parâmetros do município no ADN (confirma mTLS e o convênio)."""
    from . import config
    cfg = config.carregar()
    info = info_certificado(cfg)
    producao = emissor.em_producao() if producao is None else producao
    cert = carregar_certificado(cfg)
    cmun = cfg["emissao"].get("municipio_emissor") or "3301900"
    try:
        status, bruto = _requisicao("GET", f"{URLS[producao][1]}/parametrizacao/{cmun}/convenio", cert)
    except OSError as ex:  # o certificado abriu; a rede/ADN não respondeu
        return info | {"conexao": False, "status_http": 0, "convenio": None,
                       "mensagem": f"Certificado OK, mas sem conexão com o ADN: {ex}"}
    texto = bruto.decode("utf-8", "replace")
    try:
        js = json.loads(texto)
    except ValueError:
        js = {}
    conv = js.get("parametrosConvenio") if isinstance(js, dict) else None
    return info | {"conexao": status == 200, "status_http": status, "convenio": conv,
                   "mensagem": ("Conexão com o ADN OK." if status == 200 else f"ADN respondeu HTTP {status}: {texto[:200]}")}
