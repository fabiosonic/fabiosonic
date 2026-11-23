"""Importador de NF-e (modelo 55), NFC-e (modelo 65) e eventos de cancelamento."""
from __future__ import annotations

from ..modelos import DocumentoFiscal, EventoFiscal, Item, Participante
from ..util import dec, parse_data, primeiro, texto

STATUS_AUTORIZADA = {"100", "150"}
STATUS_DENEGADA = {"110", "301", "302", "303"}
EVENTO_CANCELAMENTO = {"110111", "110112"}  # cancelamento e cancelamento por substituição


def _participante(el, endereco: str) -> Participante:
    if el is None:
        return Participante()
    return Participante(
        documento=texto(el, "CNPJ") or texto(el, "CPF") or texto(el, "idEstrangeiro"),
        nome=texto(el, "xNome"),
        uf=texto(el, f"{endereco}/UF"),
        municipio=texto(el, f"{endereco}/xMun"),
        crt=texto(el, "CRT"),
    )


def _grupo_filho(el):
    """ICMS/PIS/COFINS trazem um subgrupo variável (ICMS00, ICMSSN102, PISAliq...)."""
    if el is None:
        return None
    filhos = list(el)
    return filhos[0] if filhos else None


def _item(det) -> Item:
    prod = det.find("prod")
    imp = det.find("imposto")
    icms = _grupo_filho(imp.find("ICMS")) if imp is not None else None
    pis = _grupo_filho(imp.find("PIS")) if imp is not None else None
    cofins = _grupo_filho(imp.find("COFINS")) if imp is not None else None
    ipi = primeiro(imp, "IPI/IPITrib") if imp is not None else None
    return Item(
        numero=int(det.get("nItem", "0") or 0),
        codigo=texto(prod, "cProd"),
        descricao=texto(prod, "xProd"),
        ncm=texto(prod, "NCM"),
        cfop=texto(prod, "CFOP"),
        quantidade=dec(texto(prod, "qCom")),
        valor_unitario=dec(texto(prod, "vUnCom")),
        valor_produto=dec(texto(prod, "vProd")),
        desconto=dec(texto(prod, "vDesc")),
        cst_icms=texto(icms, "CST"),
        csosn=texto(icms, "CSOSN"),
        cst_pis=texto(pis, "CST"),
        cst_cofins=texto(cofins, "CST"),
        valor_icms=dec(texto(icms, "vICMS")),
        valor_icms_st=dec(texto(icms, "vICMSST")),
        valor_pis=dec(texto(pis, "vPIS")),
        valor_cofins=dec(texto(cofins, "vCOFINS")),
        valor_ipi=dec(texto(ipi, "vIPI")),
        tem_ibscbs=imp is not None and imp.find("IBSCBS") is not None,
    )


def ler_nfe(raiz, arquivo: str) -> DocumentoFiscal:
    inf = raiz.find(".//infNFe")
    if inf is None:
        raise ValueError("grupo infNFe não encontrado")
    ide = inf.find("ide")
    modelo = texto(ide, "mod")
    itens = [_item(det) for det in inf.findall("det")]
    tot_el = inf.find("total/ICMSTot")
    totais = {c.tag: dec(c.text) for c in tot_el} if tot_el is not None else {}

    prot = raiz.find(".//protNFe/infProt")
    cstat = texto(prot, "cStat")
    if prot is None:
        situacao = "sem_protocolo"
    elif cstat in STATUS_AUTORIZADA:
        situacao = "autorizada"
    elif cstat in STATUS_DENEGADA:
        situacao = "denegada"
    else:
        situacao = "sem_protocolo"

    chave = inf.get("Id", "").removeprefix("NFe") or texto(prot, "chNFe")
    return DocumentoFiscal(
        tipo="NFCE" if modelo == "65" else "NFE",
        chave=chave,
        numero=texto(ide, "nNF"),
        serie=texto(ide, "serie"),
        data_emissao=parse_data(texto(ide, "dhEmi") or texto(ide, "dEmi")),
        emitente=_participante(inf.find("emit"), "enderEmit"),
        destinatario=_participante(inf.find("dest"), "enderDest"),
        valor_total=totais.get("vNF", dec(texto(inf, "total/ICMSTot/vNF"))),
        arquivo=arquivo,
        tipo_operacao="saida" if texto(ide, "tpNF") == "1" else "entrada",
        situacao=situacao,
        protocolo=texto(prot, "nProt"),
        itens=itens,
        totais=totais,
        tem_ibscbs=any(i.tem_ibscbs for i in itens) or inf.find("total/IBSCBSTot") is not None,
        layout="nfe",
    )


def ler_evento(raiz, arquivo: str) -> EventoFiscal | None:
    inf = raiz.find(".//evento/infEvento")
    if inf is None:
        inf = raiz.find(".//infEvento")
    if inf is None or texto(inf, "tpEvento") not in EVENTO_CANCELAMENTO:
        return None
    ret = texto(raiz, ".//retEvento/infEvento/cStat")
    return EventoFiscal(
        chave=texto(inf, "chNFe"),
        tipo="cancelamento",
        data=parse_data(texto(inf, "dhEvento")),
        arquivo=arquivo,
        homologado=(ret in {"135", "155"}) if ret else True,
    )
