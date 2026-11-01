#!/usr/bin/env python3
"""Extrai os campos fiscais relevantes dos XMLs de NFS-e (padrao nacional),
NF-e e DPS e grava um JSON consolidado por documento.

Uso: python3 tools/extrair_notas.py <pasta_xml> <saida.json>
"""
import json
import re
import sys
from pathlib import Path


def tag(xml, name, scope=None):
    src = scope if scope is not None else xml
    m = re.search(rf"<(?:\w+:)?{name}(?:\s[^>]*)?>(.*?)</(?:\w+:)?{name}>", src, re.S)
    return m.group(1).strip() if m else None


def bloco(xml, name):
    m = re.search(rf"<(?:\w+:)?{name}(?:\s[^>]*)?>(.*?)</(?:\w+:)?{name}>", xml, re.S)
    return m.group(1) if m else ""


def nfse_nacional(xml):
    emit = bloco(xml, "emit")
    prest = bloco(xml, "prest")
    toma = bloco(xml, "toma")
    serv = bloco(xml, "cServ")
    trib_mun = bloco(xml, "tribMun")
    pis = bloco(xml, "piscofins")
    # Reforma (RTC): o 1o grupo IBSCBS (infNFSe) traz valores calculados; o da DPS traz CST/cClassTrib
    grupos = re.findall(r"<IBSCBS>(.*?)</IBSCBS>", xml, re.S)
    ib_dps = next((g for g in grupos if "<cClassTrib>" in g), "")
    ib_val = next((g for g in grupos if "<totCIBS>" in g or "<pCBS>" in g), "")
    return {
        "tipo": "NFS-e Nacional",
        "numero": tag(xml, "nNFSe"),
        "emissao": tag(xml, "dhEmi") or tag(xml, "dhProc"),
        "competencia": tag(xml, "dCompet"),
        "situacao": tag(xml, "cStat"),
        "municipio_emissor": tag(xml, "xLocEmi"),
        "municipio_incidencia": tag(xml, "xLocIncid"),
        "emitente_cnpj": tag(emit, "CNPJ", emit) or tag(prest, "CNPJ", prest) or tag(emit, "CPF", emit),
        "emitente_nome": tag(emit, "xNome", emit),
        "emitente_uf": tag(emit, "UF", emit),
        "op_simples": tag(prest, "opSimpNac", prest),
        "reg_ap_trib_sn": tag(prest, "regApTribSN", prest),
        "reg_esp_trib": tag(prest, "regEspTrib", prest),
        "tomador_doc": tag(toma, "CNPJ", toma) or tag(toma, "CPF", toma),
        "tomador_nome": tag(toma, "xNome", toma),
        "cTribNac": tag(serv, "cTribNac", serv),
        "xTribNac": tag(xml, "xTribNac"),
        "cTribMun": tag(serv, "cTribMun", serv),
        "xTribMun": tag(xml, "xTribMun"),
        "cNBS": tag(serv, "cNBS", serv),
        "xNBS": tag(xml, "xNBS"),
        "descricao": tag(serv, "xDescServ", serv),
        "valor_servico": tag(xml, "vServ"),
        "valor_liquido": tag(xml, "vLiq"),
        "trib_issqn": tag(trib_mun, "tribISSQN", trib_mun),
        "ret_issqn": tag(trib_mun, "tpRetISSQN", trib_mun),
        "aliq_iss": tag(trib_mun, "pAliq", trib_mun) or tag(xml, "pAliqAplic"),
        "cst_pis_cofins": tag(pis, "CST", pis),
        "ret_pis_cofins": tag(pis, "tpRetPisCofins", pis),
        "p_tot_trib_sn": tag(xml, "pTotTribSN"),
        "ibscbs_cst": tag(ib_dps, "CST", ib_dps) if ib_dps else None,
        "ibscbs_cclasstrib": tag(ib_dps, "cClassTrib", ib_dps) if ib_dps else None,
        "ibscbs_ind_final": tag(ib_dps, "indFinal", ib_dps) if ib_dps else None,
        "ibscbs_p_red_cbs": tag(ib_val, "pRedAliqCBS", ib_val) if ib_val else None,
        "ibscbs_p_cbs": tag(ib_val, "pCBS", ib_val) if ib_val else None,
        "ibscbs_v_cbs": tag(ib_val, "vCBS", ib_val) if ib_val else None,
        "ibscbs_v_ibs": tag(ib_val, "vIBSTot", ib_val) if ib_val else None,
        "ind_op": tag(ib_dps, "cIndOp", ib_dps) if ib_dps else tag(xml, "cIndOp"),
        "ver_aplic": tag(xml, "verAplic"),
    }


def nfe(xml):
    emit = bloco(xml, "emit")
    dest = bloco(xml, "dest")
    itens = []
    for det in re.findall(r"<det\b[^>]*>(.*?)</det>", xml, re.S):
        prod = bloco(det, "prod")
        imp = bloco(det, "imposto")
        itens.append({
            "xProd": tag(prod, "xProd", prod),
            "NCM": tag(prod, "NCM", prod),
            "CFOP": tag(prod, "CFOP", prod),
            "CEST": tag(prod, "CEST", prod),
            "cst_icms": tag(imp, "CST", imp) or tag(imp, "CSOSN", imp),
            "cBenef": tag(prod, "cBenef", prod),
            "ibscbs_cst": tag(bloco(imp, "IBSCBS"), "CST") if "IBSCBS" in imp else None,
            "ibscbs_cclasstrib": tag(imp, "cClassTrib"),
        })
    return {
        "tipo": "NF-e" if tag(xml, "mod") != "65" else "NFC-e",
        "numero": tag(xml, "nNF"),
        "emissao": tag(xml, "dhEmi"),
        "natureza": tag(xml, "natOp"),
        "emitente_cnpj": tag(emit, "CNPJ", emit),
        "emitente_nome": tag(emit, "xNome", emit),
        "emitente_uf": tag(emit, "UF", emit),
        "crt": tag(emit, "CRT", emit),
        "destinatario_doc": tag(dest, "CNPJ", dest) or tag(dest, "CPF", dest),
        "destinatario_nome": tag(dest, "xNome", dest),
        "destinatario_uf": tag(dest, "UF", dest),
        "valor_total": tag(xml, "vNF"),
        "itens": itens,
    }


def processar(path):
    xml = path.read_text(encoding="utf-8", errors="ignore")
    if "<infNFe" in xml:
        d = nfe(xml)
    elif "<infNFSe" in xml or "<infDPS" in xml:
        d = nfse_nacional(xml)
        if "<infNFSe" not in xml:
            d["tipo"] = "DPS"
    else:
        # layouts municipais (ABRASF/RPS): captura generica
        d = {
            "tipo": "NFS-e municipal/RPS",
            "numero": tag(xml, "Numero"),
            "emitente_cnpj": tag(bloco(xml, "Prestador") or bloco(xml, "PrestadorServico"), "Cnpj"),
            "emitente_nome": tag(xml, "RazaoSocial"),
            "item_lista": tag(xml, "ItemListaServico"),
            "cod_trib_mun": tag(xml, "CodigoTributacaoMunicipio"),
            "cnae": tag(xml, "CodigoCnae"),
            "descricao": tag(xml, "Discriminacao"),
            "valor_servico": tag(xml, "ValorServicos"),
            "aliq_iss": tag(xml, "Aliquota"),
            "iss_retido": tag(xml, "IssRetido"),
            "simples": tag(xml, "OptanteSimplesNacional"),
            "tomador_doc": tag(bloco(xml, "Tomador") or bloco(xml, "TomadorServico"), "Cnpj"),
        }
    d["arquivo"] = path.name
    return d


def main():
    pasta, saida = Path(sys.argv[1]), Path(sys.argv[2])
    docs = [processar(p) for p in sorted(pasta.glob("*.xml"))]
    saida.write_text(json.dumps(docs, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(docs)} documentos extraidos -> {saida}")


if __name__ == "__main__":
    main()
