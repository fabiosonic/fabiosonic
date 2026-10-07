"""Leitura determinística de XML fiscais (NF-e/NFC-e, CT-e, NFS-e Nacional/ABRASF, eventos).

Saída: dict normalizado. Nada é inferido: campo ausente fica None.
"""
from __future__ import annotations

from datetime import date, datetime

from ..util.arquivos import filho, nome_local, nome_seguro, parse_xml_seguro, primeiro, texto, todos
from ..util.dinheiro import ValorInvalido, dinheiro
from ..util.documentos_id import so_digitos


class DocumentoNaoReconhecido(ValueError):
    pass


def _data(valor: str | None) -> date | None:
    if not valor:
        return None
    v = valor.strip()
    try:
        if "T" in v:
            return datetime.fromisoformat(v.replace("Z", "+00:00")).date()
        return date.fromisoformat(v[:10])
    except ValueError:
        return None


def _valor(v: str | None):
    if v is None:
        return None
    try:
        return dinheiro(v)
    except ValorInvalido:
        return None


def _doc_id(el) -> str | None:
    if el is None:
        return None
    return so_digitos(texto(el, "CNPJ") or texto(el, "CPF")) or None


def competencia(d: date | None) -> str | None:
    return f"{d.year:04d}-{d.month:02d}" if d else None


def _base(tipo: str) -> dict:
    return {"tipo": tipo, "chave": None, "modelo": None, "serie": None, "numero": None, "emissao": None,
            "competencia": None, "emitente_cnpj": None, "destinatario_cnpj": None, "participantes": [],
            "itens": [], "totais": {}, "autorizacao_cstat": None}


def _nfe(raiz) -> dict:
    inf = primeiro(raiz, "infNFe")
    ide = filho(inf, "ide")
    modelo = texto(ide, "mod")
    d = _base("NFE")  # NFC-e é decidida depois, com o parâmetro de leiaute conferido (aplicar_leiaute)
    d["chave"] = so_digitos(inf.get("Id")) or None
    d["modelo"], d["serie"], d["numero"] = modelo, texto(ide, "serie"), texto(ide, "nNF")
    d["emissao"] = _data(texto(ide, "dhEmi") or texto(ide, "dEmi"))
    d["competencia"] = competencia(d["emissao"])
    d["tp_nf"], d["id_dest"], d["fin_nfe"] = texto(ide, "tpNF"), texto(ide, "idDest"), texto(ide, "finNFe")
    d["refs"] = [so_digitos(texto(r, "refNFe")) for r in todos(ide, "NFref") if texto(r, "refNFe")]
    emit, dest = filho(inf, "emit"), filho(inf, "dest")
    d["emitente_cnpj"], d["destinatario_cnpj"] = _doc_id(emit), _doc_id(dest)
    d["crt"] = texto(emit, "CRT")
    d["uf_emit"], d["uf_dest"] = texto(emit, "enderEmit", "UF"), texto(dest, "enderDest", "UF")
    for det in todos(inf, "det"):
        prod = filho(det, "prod")
        icms = filho(det, "imposto", "ICMS")
        grupo = icms[0] if icms is not None and len(icms) else None
        d["itens"].append({
            "n": det.get("nItem"), "codigo": texto(prod, "cProd"), "descricao": texto(prod, "xProd"),
            "ncm": texto(prod, "NCM"), "cfop": texto(prod, "CFOP"), "v_prod": _valor(texto(prod, "vProd")),
            "ind_tot": texto(prod, "indTot"),
            "cst_icms": texto(grupo, "CST") if grupo is not None else None,
            "csosn": texto(grupo, "CSOSN") if grupo is not None else None,
        })
    tot = primeiro(inf, "ICMSTot")
    d["totais"] = {k: _valor(texto(tot, k)) for k in ("vProd", "vNF", "vDesc", "vFrete", "vICMS", "vST", "vIPI")}
    d["participantes"] = [x for x in (d["emitente_cnpj"], d["destinatario_cnpj"]) if x]
    prot = primeiro(raiz, "infProt")
    d["autorizacao_cstat"] = texto(prot, "cStat") if prot is not None else None
    return d


def _cte(raiz) -> dict:
    inf = primeiro(raiz, "infCte")
    ide = filho(inf, "ide")
    d = _base("CTE")
    d["chave"] = so_digitos(inf.get("Id")) or None
    d["modelo"], d["serie"], d["numero"] = texto(ide, "mod"), texto(ide, "serie"), texto(ide, "nCT")
    d["emissao"] = _data(texto(ide, "dhEmi"))
    d["competencia"] = competencia(d["emissao"])
    d["emitente_cnpj"] = _doc_id(filho(inf, "emit"))
    outros, papeis = [], {}
    for papel in ("rem", "exped", "receb", "dest"):
        x = _doc_id(filho(inf, papel))
        papeis[papel] = x
        if x:
            outros.append(x)
    toma3 = _um(primeiro(ide, "toma3"), primeiro(ide, "toma03"))
    d["tomador_codigo"] = texto(toma3, "toma") if toma3 is not None else None
    toma4 = primeiro(ide, "toma4")
    d["tomador_cnpj"] = _doc_id(toma4) if toma4 is not None else None
    if d["tomador_cnpj"]:
        outros.append(d["tomador_cnpj"])
    d["papeis"] = papeis
    d["destinatario_cnpj"] = _doc_id(filho(inf, "dest"))
    d["participantes"] = list(dict.fromkeys([x for x in [d["emitente_cnpj"], *outros] if x]))
    vprest = filho(inf, "vPrest")
    d["totais"] = {"vTPrest": _valor(texto(vprest, "vTPrest"))}
    prot = primeiro(raiz, "infProt")
    d["autorizacao_cstat"] = texto(prot, "cStat") if prot is not None else None
    return d


def _evento(raiz, familia: str) -> dict:
    inf = primeiro(raiz, "infEvento")
    d = _base(f"EVENTO_{familia}")
    d["chave_ref"] = so_digitos(texto(inf, "chNFe") or texto(inf, "chCTe") or "") or None
    d["tp_evento"] = texto(inf, "tpEvento")
    d["emissao"] = _data(texto(inf, "dhEvento"))
    d["competencia"] = competencia(d["emissao"])
    d["emitente_cnpj"] = so_digitos(texto(inf, "CNPJ")) or None
    d["participantes"] = [d["emitente_cnpj"]] if d["emitente_cnpj"] else []
    ret = primeiro(raiz, "retEvento")
    d["autorizacao_cstat"] = texto(primeiro(ret, "infEvento"), "cStat") if ret is not None else None
    return d


def _nfse_nacional(raiz) -> dict:
    inf = primeiro(raiz, "infNFSe")
    dps = primeiro(inf, "infDPS")
    d = _base("NFSE")
    d["padrao"] = "NACIONAL"
    d["chave"] = so_digitos(inf.get("Id")) or None
    d["numero"] = texto(inf, "nNFSe")
    d["emissao"] = _data(texto(dps, "dhEmi") or texto(inf, "dhProc"))
    comp = _data(texto(dps, "dCompet"))
    d["competencia"] = competencia(comp or d["emissao"])
    d["prestador_cnpj"] = _doc_id(filho(dps, "prest"))
    d["tomador_cnpj"] = _doc_id(filho(dps, "toma"))
    d["emitente_cnpj"], d["destinatario_cnpj"] = d["prestador_cnpj"], d["tomador_cnpj"]
    serv = filho(dps, "serv")
    d["c_trib_nac"] = texto(primeiro(serv, "cServ"), "cTribNac") if serv is not None else None
    d["municipio_incidencia"] = texto(inf, "cLocIncid")
    vs = primeiro(dps, "vServPrest")
    d["totais"] = {"vServ": _valor(texto(vs, "vServ"))}
    trib = primeiro(dps, "tribMun")
    d["iss_retencao_codigo"] = texto(trib, "tpRetISSQN")
    fed = primeiro(dps, "tribFed")
    pc = primeiro(fed, "piscofins") if fed is not None else None
    d["retencoes_federais"] = {
        "csll": _valor(texto(fed, "vRetCSLL")) if fed is not None else None,
        "irrf": _valor(texto(fed, "vRetIRRF")) if fed is not None else None,
        "inss": _valor(texto(fed, "vRetCP")) if fed is not None else None,
        "pis": _valor(texto(pc, "vPis")) if pc is not None else None,
        "cofins": _valor(texto(pc, "vCofins")) if pc is not None else None,
    }
    d["pis_cofins_retencao_codigo"] = texto(pc, "tpRetPisCofins") if pc is not None else None
    d["participantes"] = [x for x in (d["prestador_cnpj"], d["tomador_cnpj"]) if x]
    return d


def _nfse_abrasf(raiz) -> dict:
    inf = primeiro(raiz, "InfNfse")
    d = _base("NFSE")
    d["padrao"] = "ABRASF"
    d["numero"] = texto(inf, "Numero")
    d["chave"] = None
    cod_ver = texto(inf, "CodigoVerificacao")
    d["emissao"] = _data(texto(inf, "DataEmissao"))
    # ABRASF 2.x: Competencia fica em DeclaracaoPrestacaoServico/InfDeclaracaoPrestacaoServico
    d["competencia"] = competencia(_data(texto(primeiro(inf, "Competencia"))) or d["emissao"])
    prest = _um(primeiro(inf, "PrestadorServico"), primeiro(inf, "Prestador"))
    toma = _um(primeiro(inf, "TomadorServico"), primeiro(inf, "Tomador"))
    d["prestador_cnpj"] = so_digitos(texto(primeiro(prest, "CpfCnpj"), "Cnpj") or texto(prest, "Cnpj") or
                                     texto(primeiro(prest, "IdentificacaoPrestador"), "Cnpj") or "") or None
    d["tomador_cnpj"] = so_digitos(texto(primeiro(toma, "CpfCnpj"), "Cnpj") or
                                   texto(primeiro(toma, "CpfCnpj"), "Cpf") or "") or None
    d["emitente_cnpj"], d["destinatario_cnpj"] = d["prestador_cnpj"], d["tomador_cnpj"]
    if d["prestador_cnpj"] and d["numero"]:
        d["chave"] = nome_seguro(f"ABRASF-{d['prestador_cnpj']}-{d['numero']}-{cod_ver or ''}")
    valores = primeiro(inf, "Valores")
    d["totais"] = {"vServ": _valor(texto(valores, "ValorServicos"))}
    d["retencoes_federais"] = {k: _valor(texto(valores, campo)) for k, campo in
                               (("pis", "ValorPis"), ("cofins", "ValorCofins"), ("csll", "ValorCsll"),
                                ("irrf", "ValorIr"), ("inss", "ValorInss"))}
    d["cancelada"] = primeiro(raiz, "NfseCancelamento") is not None
    d["iss_retencao_codigo"] = texto(primeiro(inf, "Servico"), "IssRetido") or texto(valores, "IssRetido")
    d["c_trib_nac"] = texto(primeiro(inf, "Servico"), "ItemListaServico")
    d["participantes"] = [x for x in (d["prestador_cnpj"], d["tomador_cnpj"]) if x]
    return d


def _um(*elementos):
    """Primeiro elemento não-None (Element vazio é 'falsy', não usar `or`)."""
    for e in elementos:
        if e is not None:
            return e
    return None


def ler_xml(dados: bytes) -> dict:
    raiz = parse_xml_seguro(dados)
    nome = nome_local(raiz.tag)
    if primeiro(raiz, "infNFe") is not None and nome in ("nfeProc", "NFe"):
        return _nfe(raiz)
    if primeiro(raiz, "infCte") is not None and nome in ("cteProc", "CTe"):
        return _cte(raiz)
    if nome in ("procEventoNFe", "evento", "envEvento") and primeiro(raiz, "chNFe") is not None:
        return _evento(raiz, "NFE")
    if nome in ("procEventoCTe", "eventoCTe") and primeiro(raiz, "chCTe") is not None:
        return _evento(raiz, "CTE")
    if primeiro(raiz, "infNFSe") is not None:
        return _nfse_nacional(raiz)
    if primeiro(raiz, "InfNfse") is not None:
        n = len(todos(raiz, "InfNfse"))
        if n > 1:  # lista/consulta com várias notas: ler só a 1ª perderia as outras (e o cancelamento se mistura)
            raise DocumentoNaoReconhecido(f"XML com {n} NFS-e (lista/consulta da prefeitura): "
                                          "baixar uma nota por arquivo ou separar antes de importar")
        return _nfse_abrasf(raiz)
    if nome.lower().startswith("procevento") or primeiro(raiz, "infEvento") is not None:
        d = _base("EVENTO_OUTRO")
        return d
    raise DocumentoNaoReconhecido(f"XML não reconhecido (raiz {nome})")


def aplicar_leiaute(doc: dict, catalogo) -> dict:
    """Ajustes que dependem de códigos de leiaute (regra 3): só com parâmetros conferidos do MOC_NFE.

    - NF-e com `mod` igual a `modelo_nfce` vira NFCE;
    - evento cuja chave tem esse modelo (posição `chave_pos_modelo`) vira EVENTO_NFCE.
    Sem os parâmetros, o documento fica como NFE/EVENTO_NFE (e a rota depende do mesmo MOC).
    """
    if catalogo is None or doc is None:
        return doc
    mod = catalogo.parametro("MOC_NFE", "modelo_nfce")
    pos = catalogo.parametro("MOC_NFE", "chave_pos_modelo")
    if mod is None:
        return doc
    if doc["tipo"] == "NFE" and str(doc.get("modelo")) == str(mod):
        doc["tipo"] = "NFCE"
    elif doc["tipo"] == "EVENTO_NFE" and pos is not None:
        ch = doc.get("chave_ref") or ""
        if len(ch) == 44 and ch[int(pos[0]):int(pos[1])] == str(mod):
            doc["tipo"] = "EVENTO_NFCE"
    return doc
