"""
Leitura de documentos fiscais eletrônicos (XML soltos ou dentro de .zip). Só biblioteca padrão.

Reconhece: NF-e (mod. 55), NFC-e (mod. 65), CT-e / CT-e OS (57/67), NFS-e Padrão Nacional, NFS-e ABRASF,
eventos de cancelamento (NF-e/CT-e/NFS-e Nacional).

Cada documento vira um dict com, no mínimo:
  tipo, chave, modelo, numero, data_emissao (AAAA-MM-DD), competencia (MMAAAA), emitente, destinatario,
  valor_total, situacao, itens (lista de dicts com as chaves de regra: cfop, cst, orig, cst_pis, cst_cofins...)
e campos específicos por tipo (ver funções abaixo). Nada é arredondado; valores em Decimal.

`iter_xml(raiz, ignorar=[...])` percorre pastas recursivamente e entra em .zip (inclusive zip dentro de zip),
devolvendo (origem_legivel, bytes) para cada .xml encontrado.
"""
import io
import os
import re
import zipfile
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation

D0 = Decimal("0")


def dec(x):
    if x is None:
        return D0
    x = str(x).strip().replace(",", ".")
    try:
        return Decimal(x)
    except InvalidOperation:
        return D0


def digits(s):
    return re.sub(r"\D", "", s or "")


def strip_ns(tag):
    return tag.split("}", 1)[1] if "}" in tag else tag


def walk(el):
    yield el
    for c in el:
        yield from walk(c)


def first(root, name):
    if root is None:
        return None
    for el in walk(root):
        if strip_ns(el.tag) == name:
            return el
    return None


def allof(root, name):
    return [el for el in walk(root) if strip_ns(el.tag) == name] if root is not None else []


def first_of(root, *names):
    """Primeiro elemento encontrado entre os nomes, na ordem dada (não usa `or`: Element sem filhos é falso)."""
    for n in names:
        el = first(root, n)
        if el is not None:
            return el
    return None


def text(root, name, default=""):
    el = first(root, name)
    return (el.text or "").strip() if el is not None and el.text else default


def child(el, name, default=""):
    if el is None:
        return default
    for c in el:
        if strip_ns(c.tag) == name:
            return (c.text or "").strip()
    return default


def competencia_de(data_iso):
    """'2026-08-14...' -> '082026' (formato de pasta que a rotina automática do Domínio espera)."""
    if not data_iso or len(data_iso) < 7:
        return ""
    return data_iso[5:7] + data_iso[0:4]


# --------------------------------------------------------------------------------------------------
# Percurso de pastas e zips
# --------------------------------------------------------------------------------------------------

def _iter_zip(zf, prefixo):
    for info in zf.infolist():
        if info.is_dir():
            continue
        nome = info.filename
        low = nome.lower()
        if low.endswith(".xml"):
            try:
                yield f"{prefixo}!{nome}", zf.read(info)
            except Exception as e:  # zip corrompido / senha
                yield f"{prefixo}!{nome}", ("ERRO_ZIP:" + str(e)).encode()
        elif low.endswith(".zip"):
            try:
                inner = zipfile.ZipFile(io.BytesIO(zf.read(info)))
                yield from _iter_zip(inner, f"{prefixo}!{nome}")
            except Exception as e:
                yield f"{prefixo}!{nome}", ("ERRO_ZIP:" + str(e)).encode()


def iter_xml(raiz, ignorar=()):
    """Gera (origem, bytes) para cada XML em `raiz` (recursivo), abrindo .zip. `ignorar`: pastas a pular."""
    ignorar = [os.path.normcase(os.path.abspath(p)) for p in ignorar]
    if os.path.isfile(raiz):
        pastas = [(os.path.dirname(raiz), [], [os.path.basename(raiz)])]
    else:
        pastas = os.walk(raiz)
    for base, dirs, files in pastas:
        nb = os.path.normcase(os.path.abspath(base))
        if any(nb == p or nb.startswith(p + os.sep) for p in ignorar):
            dirs[:] = []
            continue
        for f in sorted(files):
            caminho = os.path.join(base, f)
            low = f.lower()
            if low.endswith(".xml"):
                try:
                    with open(caminho, "rb") as fh:
                        yield caminho, fh.read()
                except OSError as e:
                    yield caminho, ("ERRO_LEITURA:" + str(e)).encode()
            elif low.endswith(".zip"):
                try:
                    with zipfile.ZipFile(caminho) as zf:
                        yield from _iter_zip(zf, caminho)
                except Exception as e:
                    yield caminho, ("ERRO_ZIP:" + str(e)).encode()


# --------------------------------------------------------------------------------------------------
# Parser
# --------------------------------------------------------------------------------------------------

def _icms_item(det):
    icms = first(det, "ICMS")
    cst = orig = ""
    tipo = ""
    if icms is not None and len(icms):
        grp = icms[0]
        orig = child(grp, "orig", "")
        if child(grp, "CSOSN"):
            tipo, cst = "CSOSN", child(grp, "CSOSN")
        else:
            tipo, cst = "CST", child(grp, "CST")
    return tipo, cst, orig


def _pis_cofins_item(det):
    pis = first(det, "PIS")
    cof = first(det, "COFINS")
    cst_pis = child(pis[0], "CST") if pis is not None and len(pis) else ""
    cst_cof = child(cof[0], "CST") if cof is not None and len(cof) else ""
    return cst_pis, cst_cof


def parse_bytes(data, origem=""):
    if data[:9] in (b"ERRO_ZIP:", b"ERRO_LEIT"):
        return {"origem": origem, "tipo": "NAO_RECONHECIDO", "erro": data.decode(errors="replace")}
    try:
        root = ET.fromstring(data)
    except ET.ParseError as e:
        return {"origem": origem, "tipo": "NAO_RECONHECIDO", "erro": f"XML inválido: {e}"}
    tags = {strip_ns(el.tag) for el in walk(root)}

    # ---- eventos ---------------------------------------------------------------------------------
    if "infEvento" in tags:
        tp = text(root, "tpEvento")
        desc = text(root, "descEvento") or text(root, "xEvento")
        ch = text(root, "chNFe") or text(root, "chCTe")
        kind = "EVENTO_CANCELAMENTO" if tp in ("110111", "110112") or "ancel" in desc else "EVENTO_OUTRO"
        modelo = ch[20:22] if len(ch) == 44 else ""
        return {"origem": origem, "tipo": kind, "chave": ch, "modelo": modelo, "descricao": desc or tp,
                "emitente": ch[6:20] if len(ch) == 44 else "", "data_emissao": text(root, "dhEvento")[:10],
                "competencia": competencia_de(text(root, "dhEvento")[:10])}
    if "infNFSe" not in tags and "infDPS" not in tags and "chNFSe" in tags and ("xDesc" in tags or "infEvento" in tags or "infPedReg" in tags):
        ch = digits(text(root, "chNFSe"))
        # chave NFS-e Nacional (50): cLocEmi(7) ambGer(1) tpInsc(1) nInsc(14) ... → CNPJ/CPF do emitente em [9:23]
        emit = (ch[9:23] if ch[8] == "2" else ch[12:23]) if len(ch) == 50 else ""
        return {"origem": origem, "tipo": "EVENTO_CANCELAMENTO", "chave": ch, "modelo": "NFSe",
                "descricao": text(root, "xDesc") or "evento NFS-e", "emitente": emit, "data_emissao": text(root, "dhEvento")[:10],
                "competencia": competencia_de(text(root, "dhEvento")[:10])}

    # ---- NF-e / NFC-e ----------------------------------------------------------------------------
    if "infNFe" in tags:
        inf = first(root, "infNFe")
        ide, emit, dest, tot = first(inf, "ide"), first(inf, "emit"), first(inf, "dest"), first(inf, "ICMSTot")
        mod = child(ide, "mod")
        chave = (inf.get("Id") or "").replace("NFe", "")
        emit_doc = child(emit, "CNPJ") or child(emit, "CPF")
        dest_doc = child(dest, "CNPJ") or child(dest, "CPF") or child(dest, "idEstrangeiro")
        pag = first(inf, "pag")
        tpags = sorted({child(d, "tPag") for d in allof(pag, "detPag")} - {""}) if pag is not None else []
        itens = []
        for det in allof(inf, "det"):
            prod = first(det, "prod")
            tipo_cst, cst, orig = _icms_item(det)
            cst_pis, cst_cof = _pis_cofins_item(det)
            itens.append({"cfop": child(prod, "CFOP"), "ncm": child(prod, "NCM"), "tipo_cst": tipo_cst, "cst": cst, "orig": orig,
                          "cst_pis": cst_pis, "cst_cofins": cst_cof, "valor": dec(child(prod, "vProd")),
                          "icms_st": dec(text(det, "vICMSST")) > 0, "ipi": dec(text(det, "vIPI")) > 0})
        cstat = text(root, "cStat")
        situacao = "autorizada" if cstat in ("", "100", "150") else ("cancelada" if cstat in ("101", "151", "135") else f"cStat_{cstat}")
        data = (child(ide, "dhEmi") or child(ide, "dEmi"))[:10]
        return {"origem": origem, "tipo": "NFC-e" if mod == "65" else "NF-e", "modelo": mod, "chave": chave,
                "numero": child(ide, "nNF"), "serie": child(ide, "serie"), "data_emissao": data, "competencia": competencia_de(data),
                "data_saida": (child(ide, "dhSaiEnt") or child(ide, "dSaiEnt"))[:10],
                "emitente": emit_doc, "emitente_nome": child(emit, "xNome"), "emitente_uf": text(emit, "UF"), "emitente_crt": child(emit, "CRT"),
                "destinatario": dest_doc, "destinatario_nome": child(dest, "xNome"), "destinatario_uf": text(dest, "UF"),
                "dest_tipo": "CNPJ" if child(dest, "CNPJ") else ("CPF" if child(dest, "CPF") else ("ESTRANGEIRO" if child(dest, "idEstrangeiro") else "SEM_DEST")),
                "valor_total": dec(child(tot, "vNF")), "icms": dec(child(tot, "vICMS")), "icms_st": dec(child(tot, "vST")),
                "ipi": dec(child(tot, "vIPI")), "pis": dec(child(tot, "vPIS")), "cofins": dec(child(tot, "vCOFINS")),
                "finalidade": child(ide, "finNFe"), "tp_nf": child(ide, "tpNF"), "ind_pres": child(ide, "indPres"),
                "formas_pagamento": tpags, "situacao": situacao, "itens": itens}

    # ---- CT-e / CT-e OS --------------------------------------------------------------------------
    if "infCte" in tags:
        inf = first(root, "infCte")
        ide, emit = first(inf, "ide"), first(inf, "emit")
        chave = (inf.get("Id") or "").replace("CTe", "")
        papeis = {}
        for tag in ("rem", "exped", "receb", "dest"):
            el = first(inf, tag)
            if el is not None:
                papeis[tag] = digits(child(el, "CNPJ") or child(el, "CPF"))
        toma_el = first_of(inf, "toma3", "toma4")
        toma_code = child(toma_el, "toma") if toma_el is not None else ""
        toma_map = {"0": "rem", "1": "exped", "2": "receb", "3": "dest", "4": "toma"}
        if toma_code == "4":  # toma4: o tomador ("outros") vem identificado dentro do próprio grupo
            papeis["toma"] = digits(child(toma_el, "CNPJ") or child(toma_el, "CPF"))
        tomador = papeis.get("toma") or papeis.get(toma_map.get(toma_code, ""), "")
        icms = first(first(inf, "imp"), "ICMS")
        cst = ""
        if icms is not None and len(icms):
            cst = child(icms[0], "CST")
        data = child(ide, "dhEmi")[:10]
        return {"origem": origem, "tipo": "CT-e", "modelo": child(ide, "mod"), "chave": chave, "numero": child(ide, "nCT"),
                "serie": child(ide, "serie"), "data_emissao": data, "competencia": competencia_de(data),
                "emitente": child(emit, "CNPJ"), "emitente_nome": child(emit, "xNome"), "emitente_uf": text(emit, "UF"),
                "destinatario": tomador, "papeis": papeis, "tomador_codigo": toma_code,
                "valor_total": dec(text(inf, "vTPrest")), "icms": dec(text(icms, "vICMS")) if icms is not None else D0,
                "situacao": "autorizada", "modal": child(ide, "modal"), "tp_cte": child(ide, "tpCTe"),
                "itens": [{"cfop": child(ide, "CFOP"), "tipo_cst": "CST", "cst": cst, "orig": "", "cst_pis": "", "cst_cofins": "",
                           "valor": dec(text(inf, "vTPrest")), "icms_st": False, "ipi": False}]}

    # ---- NFS-e Padrão Nacional -------------------------------------------------------------------
    if "infNFSe" in tags or "infDPS" in tags:
        inf = first_of(root, "infNFSe", "infDPS")
        prest, toma = first(root, "prest"), first(root, "toma")
        emit = first(root, "emit")
        prest_doc = digits(child(prest, "CNPJ") or child(prest, "CPF")) or digits(child(emit, "CNPJ"))
        toma_doc = digits(child(toma, "CNPJ") or child(toma, "CPF"))
        data = (text(root, "dhProc") or text(root, "dhEmi"))[:10]
        dcompet = text(root, "dCompet")[:10]
        return {"origem": origem, "tipo": "NFS-e Nacional", "modelo": "NFSe", "chave": text(root, "chNFSe") or (inf.get("Id") or ""),
                "numero": text(root, "nNFSe") or text(root, "nDPS"), "serie": text(root, "serie"),
                "data_emissao": data, "data_competencia": dcompet, "competencia": competencia_de(dcompet or data),
                "emitente": prest_doc, "emitente_nome": child(prest, "xNome") or child(emit, "xNome"),
                "destinatario": toma_doc, "destinatario_nome": child(toma, "xNome"),
                "valor_total": dec(text(root, "vServ")), "iss": dec(text(root, "vISSQN")) or dec(text(root, "vISS")),
                "trib_issqn": text(root, "tribISSQN"), "tp_ret_issqn": text(root, "tpRetISSQN"), "c_trib_nac": text(root, "cTribNac"),
                "c_trib_mun": text(root, "cTribMun"), "op_simp_nac": text(root, "opSimpNac"), "reg_esp_trib": text(root, "regEspTrib"),
                "mun_emissor": text(root, "cLocEmi"), "mun_incidencia": text(root, "cLocIncid") or text(root, "cLocPrestacao"),
                "mun_tomador": child(first(toma, "end"), "cMun") if toma is not None else "",
                "ret_irrf": dec(text(root, "vRetIRRF")), "tp_ret_pis_cofins": text(root, "tpRetPisCofins"),
                "ret_csll": dec(text(root, "vRetCSLL")), "ret_pis": dec(text(root, "vRetPIS")), "ret_cofins": dec(text(root, "vRetCOFINS")),
                "situacao": "autorizada", "itens": []}

    # ---- NFS-e ABRASF -----------------------------------------------------------------------------
    if "InfNfse" in tags or "InfDeclaracaoPrestacaoServico" in tags or "Nfse" in tags:
        prest = first_of(root, "PrestadorServico", "Prestador")
        toma = first_of(root, "TomadorServico", "Tomador")
        prest_doc = digits(text(prest, "Cnpj")) if prest is not None else ""
        toma_doc = digits(text(toma, "Cnpj") or text(toma, "Cpf")) if toma is not None else ""
        cancel = first(root, "NfseCancelamento") is not None or first(root, "Cancelamento") is not None
        data = text(root, "DataEmissao")[:10]
        comp = text(root, "Competencia")[:10]
        iss = dec(text(root, "ValorIss"))
        return {"origem": origem, "tipo": "NFS-e ABRASF", "modelo": "NFSe", "chave": text(root, "CodigoVerificacao") or text(root, "Numero"),
                "numero": text(root, "Numero"), "serie": "", "data_emissao": data, "data_competencia": comp, "competencia": competencia_de(comp or data),
                "emitente": prest_doc, "emitente_nome": text(prest, "RazaoSocial") if prest is not None else "",
                "destinatario": toma_doc, "destinatario_nome": text(toma, "RazaoSocial") if toma is not None else "",
                "valor_total": dec(text(root, "ValorServicos")), "iss": iss,
                "natureza_operacao": text(root, "NaturezaOperacao") or text(root, "ExigibilidadeISS"),
                "item_lista": digits(text(root, "ItemListaServico")), "iss_retido_flag": text(root, "IssRetido"),
                "iss_retido": dec(text(root, "ValorIssRetido")) or (iss if text(root, "IssRetido") == "1" else D0),
                "mun_prestacao": text(root, "CodigoMunicipio") or text(root, "MunicipioPrestacaoServico"),
                "op_simp_nac": text(root, "OptanteSimplesNacional"), "reg_esp_trib": text(root, "RegimeEspecialTributacao"),
                "ret_irrf": dec(text(root, "ValorIr")), "ret_csll": dec(text(root, "ValorCsll")), "ret_pis": dec(text(root, "ValorPis")),
                "ret_cofins": dec(text(root, "ValorCofins")), "situacao": "cancelada" if cancel else "autorizada", "itens": []}

    return {"origem": origem, "tipo": "NAO_RECONHECIDO", "erro": "leiaute não identificado: " + ",".join(sorted(tags))[:150]}


def direcao_para(doc, cnpj):
    """Direção do documento do ponto de vista da empresa `cnpj` (só dígitos)."""
    t = doc["tipo"]
    emit, dest = digits(doc.get("emitente")), digits(doc.get("destinatario"))
    if t in ("NF-e", "NFC-e"):
        if emit == cnpj:
            return "saida"
        if dest == cnpj:
            return "entrada"
        return "terceiro"
    if t == "CT-e":
        if emit == cnpj:
            return "saida"  # a empresa é transportadora
        if dest == cnpj or cnpj in doc.get("papeis", {}).values():
            return "entrada"  # frete tomado / participante
        return "terceiro"
    if t.startswith("NFS-e"):
        if emit == cnpj:
            return "prestado"
        if dest == cnpj:
            return "tomado"
        return "terceiro"
    if t.startswith("EVENTO"):
        return "evento"
    return "ignorado"
