"""Regras fiscais da emissão: regra geral da empresa (Configurações) e regra específica de cada tomador.

Regra geral (config["fiscal"] + regime em config["emissao"]):
- regime do prestador: mei | simples | presumido | real (define opSimpNac, PIS/COFINS próprio, carga aproximada);
- ISS retido pelo tomador e alíquota; retenções federais (IRRF, PIS, COFINS, CSLL, INSS) em %;
- IBS/CBS: quando informar o grupo e o indicador de consumo final.

Regra do tomador (cliente["fiscal"]): com "usar_geral" desligado, os campos do tomador substituem os da regra
geral só para aquele tomador e ficam guardados nele para as próximas notas.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

REGIMES = {"mei": "MEI", "simples": "Simples Nacional (ME/EPP)", "presumido": "Lucro Presumido",
           "real": "Lucro Real"}
OP_SIMP_NAC = {"mei": "2", "simples": "3", "presumido": "1", "real": "1"}
# PIS/COFINS de apuração própria do regime regular (CST 01 = alíquota básica)
PIS_COFINS = {"presumido": ("0.65", "3.00"), "real": ("1.65", "7.60")}
RETENCOES = ("ret_irrf_pct", "ret_pis_pct", "ret_cofins_pct", "ret_csll_pct", "ret_inss_pct")
# situação do ISS, exigibilidade suspensa, benefício municipal, PIS/COFINS, ente governamental e destinatário
TOMADOR_EXTRA = ("trib_issqn", "tp_imunidade", "pais_result", "exig_susp_tp", "exig_susp_proc", "n_bm", "p_red_bm",
                 "ret_iss_por", "pis_cofins_cst", "tp_ente_gov", "tp_oper", "dest_doc", "dest_nome")
# campos só da regra geral (prestador): carga aproximada, PIS/COFINS próprio e IBS/CBS avançado
GERAL_EXTRA = ("tot_trib_modo", "p_tot_fed", "p_tot_est", "p_tot_mun", "pis_cofins_cst", "p_pis", "p_cofins",
               "cst_reg", "class_trib_reg", "p_dif_uf", "p_dif_mun", "p_dif_cbs", "c_cred_pres")
# campos que o tomador pode ter diferentes da regra geral (o regime é sempre o da empresa)
CAMPOS_TOMADOR = ("iss_retido", "aliquota_iss_retido", *RETENCOES, "ind_final", "class_trib", *TOMADOR_EXTRA)
CST_PIS_COFINS = ("01", "02", "03", "04", "05", "06", "07", "08", "09", "49", "99")
TRIB_ISSQN = {"1": "Operação tributável", "2": "Imunidade", "3": "Exportação de serviço", "4": "Não incidência"}
LIMITE_DISPENSA = Decimal("10.00")   # IRRF (Lei 9.430/96, art. 67) e PIS/COFINS/CSLL (Lei 10.833/03, art. 31, §3º)


def _dec(v) -> Decimal:
    try:
        return Decimal(str(v or "0").replace(",", ".").strip() or "0")
    except Exception:  # noqa: BLE001 — valor inválido digitado vira zero (a tela valida antes)
        return Decimal(0)


def regime(cfg: dict) -> str:
    r = (cfg.get("fiscal") or {}).get("regime") or ""
    if r in REGIMES:
        return r
    return {"2": "mei", "1": "presumido"}.get(str(cfg["emissao"].get("op_simp_nac", "3")), "simples")


def geral(cfg: dict | None = None) -> dict:
    from . import config
    cfg = cfg or config.carregar()
    f = dict(cfg.get("fiscal") or {})
    f["regime"] = regime(cfg)
    if not cfg["emissao"].get("informar_ibscbs", True) and f.get("ibscbs", "auto") == "auto":
        f["ibscbs"] = "nunca"
    return f


def do_tomador(cli: dict | None, cfg: dict | None = None) -> dict:
    """Regra que vale para o tomador: a dele (se não usa a geral) por cima da geral."""
    g = geral(cfg)
    esp = (cli or {}).get("fiscal") or {}
    if esp and not esp.get("usar_geral", True):
        return g | {k: esp[k] for k in CAMPOS_TOMADOR if k in esp} | {"origem": "tomador"}
    return g | {"origem": "geral"}


def normalizar_tomador(d: dict | None) -> dict:
    """O que se guarda no cadastro do tomador."""
    d = d or {}
    usar = d.get("usar_geral", True) not in (False, 0, "0", "false", "nao")
    if usar:
        return {"usar_geral": True}
    out = {"usar_geral": False, "iss_retido": bool(d.get("iss_retido")) and d.get("iss_retido") not in ("0", "false"),
           "aliquota_iss_retido": str(d.get("aliquota_iss_retido") or "").replace(",", ".").strip(),
           "ind_final": str(d.get("ind_final") or "auto"),
           "class_trib": "".join(ch for ch in str(d.get("class_trib") or "") if ch.isdigit())[:6]}
    for k in RETENCOES:
        v = _dec(d.get(k))
        if v < 0 or v > 20:
            raise ValueError("Percentual de retenção fora do intervalo (0 a 20%).")
        out[k] = str(v.normalize()) if v else "0"
    if out["aliquota_iss_retido"] and not (0 <= _dec(out["aliquota_iss_retido"]) <= 5):
        raise ValueError("Alíquota do ISS retido deve estar entre 0 e 5% (LC 116/2003).")
    dig = lambda k, n=99: "".join(ch for ch in str(d.get(k) or "") if ch.isdigit())[:n]  # noqa: E731
    out |= {"trib_issqn": dig("trib_issqn", 1) or "1", "tp_imunidade": dig("tp_imunidade", 1),
            "pais_result": str(d.get("pais_result") or "").strip().upper()[:2],
            "exig_susp_tp": dig("exig_susp_tp", 1), "exig_susp_proc": dig("exig_susp_proc", 30),
            "n_bm": dig("n_bm", 14), "p_red_bm": str(_dec(d.get("p_red_bm")).normalize()) if _dec(d.get("p_red_bm")) else "",
            "ret_iss_por": "intermediario" if d.get("ret_iss_por") == "intermediario" else "tomador",
            "pis_cofins_cst": dig("pis_cofins_cst", 2), "tp_ente_gov": dig("tp_ente_gov", 1), "tp_oper": dig("tp_oper", 1),
            "dest_doc": dig("dest_doc", 14), "dest_nome": str(d.get("dest_nome") or "").strip()[:150]}
    if out["trib_issqn"] not in TRIB_ISSQN:
        raise ValueError("Situação do ISS inválida.")
    if out["trib_issqn"] == "2" and out["tp_imunidade"] not in ("0", "1", "2", "3", "4", "5"):
        raise ValueError("Imunidade: informe o tipo de imunidade (CF/88, art. 150, VI).")
    if out["trib_issqn"] == "3" and len(out["pais_result"]) != 2:
        raise ValueError("Exportação: informe o país onde se verificou o resultado do serviço (sigla ISO, ex.: US).")
    if out["exig_susp_tp"] and (out["exig_susp_tp"] not in ("1", "2") or len(out["exig_susp_proc"]) != 30):
        raise ValueError("Exigibilidade suspensa: escolha o tipo e informe o número do processo com 30 dígitos.")
    if out["n_bm"] and len(out["n_bm"]) != 14:
        raise ValueError("Benefício municipal: o identificador tem 14 dígitos.")
    if out["pis_cofins_cst"] and out["pis_cofins_cst"] not in CST_PIS_COFINS:
        raise ValueError("CST de PIS/COFINS inválido para serviço prestado.")
    if out["dest_doc"] and (len(out["dest_doc"]) not in (11, 14) or not out["dest_nome"]):
        raise ValueError("Destinatário diferente: informe CPF/CNPJ e nome.")
    return out


def _cent(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), ROUND_HALF_UP)


def aplicar(rps: dict, cli: dict | None, cfg: dict | None = None) -> dict:
    """Completa o dicionário do RPS com ISS retido, retenções federais e IBS/CBS conforme a regra do tomador."""
    from . import config
    cfg = cfg or config.carregar()
    r = do_tomador(cli, cfg)
    reg = r["regime"]
    valor = sum(_dec(i["valor_unitario"]) * _dec(i.get("quantidade", 1)) for i in rps["itens"])
    alertas = []
    # regra geral sem ISS retido não desfaz um serviço cadastrado como retido; a regra do tomador manda
    retido = bool(r.get("iss_retido")) or (r["origem"] == "geral" and str(rps.get("iss_retido")) == "1")
    rps["iss_retido"] = "1" if retido else "2"
    if retido and reg != "mei":
        aliq = _dec(r.get("aliquota_iss_retido")) or _dec(rps.get("aliquota_iss"))
        rps["aliquota_iss"] = str(aliq)
    if reg in ("simples", "mei"):
        rps["tipo_tributacao"] = "4"
    elif str(rps.get("tipo_tributacao", "4")) == "4":
        rps["tipo_tributacao"] = "0"                # não optante: tributado no município
    if reg == "mei":
        rps["aliquota_iss"] = "0"
    # retenções federais (valores com dispensa legal de até R$ 10)
    pct = {k: _dec(r.get(k)) for k in RETENCOES}
    vals = {k: _cent(valor * p / 100) for k, p in pct.items()}
    if vals["ret_irrf_pct"] and vals["ret_irrf_pct"] <= LIMITE_DISPENSA:
        vals["ret_irrf_pct"] = Decimal(0)
        alertas.append("IRRF de até R$ 10,00 dispensado (Lei 9.430/96, art. 67).")
    pcc = vals["ret_pis_pct"] + vals["ret_cofins_pct"] + vals["ret_csll_pct"]
    if pcc and pcc <= LIMITE_DISPENSA:
        for k in ("ret_pis_pct", "ret_cofins_pct", "ret_csll_pct"):
            vals[k] = Decimal(0)
        alertas.append("PIS/COFINS/CSLL retidos de até R$ 10,00 dispensados (Lei 10.833/03, art. 31, §3º).")
    if reg in ("simples", "mei") and (pcc or vals["ret_irrf_pct"]):
        alertas.append("Prestador do Simples Nacional em regra não sofre retenção de IRRF e de PIS/COFINS/CSLL; "
                       "confira a regra deste tomador.")
    rps["retencoes"] = {
        "aliquota_ir": str(pct["ret_irrf_pct"]) if vals["ret_irrf_pct"] else "0", "valor_ir": str(vals["ret_irrf_pct"]),
        "aliquota_pis": str(pct["ret_pis_pct"]) if vals["ret_pis_pct"] else "0", "valor_pis": str(vals["ret_pis_pct"]),
        "aliquota_cofins": str(pct["ret_cofins_pct"]) if vals["ret_cofins_pct"] else "0",
        "valor_cofins": str(vals["ret_cofins_pct"]),
        "aliquota_csll": str(pct["ret_csll_pct"]) if vals["ret_csll_pct"] else "0", "valor_csll": str(vals["ret_csll_pct"]),
        "aliquota_inss": str(pct["ret_inss_pct"]) if vals["ret_inss_pct"] else "0", "valor_inss": str(vals["ret_inss_pct"]),
    }
    if r.get("class_trib"):
        rps["classificacao_tributaria"] = r["class_trib"]
    doc = "".join(ch for ch in str((rps.get("tomador") or {}).get("cpf_cnpj", "")) if ch.isdigit())
    ind = str(r.get("ind_final") or "auto")
    rps["ind_final"] = ind if ind in ("0", "1") else ("1" if len(doc) == 11 else "0")
    # campos da DPS nacional que vêm da regra (tomador e geral); os da própria nota entram por cima
    extras = {k: cfg.get("fiscal", {}).get(k) for k in GERAL_EXTRA if cfg.get("fiscal", {}).get(k)}
    extras |= {k: r[k] for k in TOMADOR_EXTRA if r.get(k)}          # a regra do tomador vale primeiro
    if extras.get("trib_issqn", "1") != "1" and retido:
        alertas.append("Serviço imune/exportado/não incidente: o ISS não é retido.")
        rps["iss_retido"] = "2"
    rps["extras"] = extras | dict(rps.get("extras") or {})
    rps["_alertas_fiscais"] = alertas
    return rps


def informar_ibscbs(f: dict, competencia: date) -> bool:
    """auto: regime regular sempre (obrigatório em 2026); Simples/MEI a partir de 01/01/2027."""
    modo = f.get("ibscbs", "auto")
    if modo in ("sempre", "nunca"):
        return modo == "sempre"
    return f["regime"] in ("presumido", "real") or competencia >= date(2027, 1, 1)


def resumo(f: dict) -> str:
    """Texto curto da regra (tela de emissão)."""
    partes = [REGIMES[f["regime"]]]
    if f.get("iss_retido"):
        partes.append("ISS retido" + (f" {f['aliquota_iss_retido']}%" if f.get("aliquota_iss_retido") else ""))
    nomes = {"ret_irrf_pct": "IRRF", "ret_pis_pct": "PIS", "ret_cofins_pct": "COFINS", "ret_csll_pct": "CSLL",
             "ret_inss_pct": "INSS"}
    ret = [f"{nomes[k]} {str(_dec(f.get(k)).normalize()).replace('.', ',')}%" for k in RETENCOES if _dec(f.get(k))]
    partes.append("retenções: " + ", ".join(ret) if ret else "sem retenções federais")
    return " · ".join(partes)


# ---------------------------------------------------------------- campos da própria nota

CAMPOS_NOTA = {
    "local_prestacao": 7, "c_trib_mun": 3, "desc_incond": "v", "desc_cond": "v", "ded_valor": "v", "ded_pct": "p",
    "obra_cno": 30, "obra_cib": "a8", "obra_insc_imob": "t30", "evento_nome": "t255", "evento_ini": "d", "evento_fim": "d",
    "evento_id": "t30", "evento_cep": 8, "evento_lgr": "t255", "evento_nro": "t60", "evento_bairro": "t60",
    "pedido": "t15", "doc_tec": "t40", "doc_ref": "t255", "imovel_cib": "a8", "imovel_insc_imob": "t30",
    "ree_valor": "v", "ree_tipo": 2, "ree_xtipo": "t150", "ree_chave": 50, "ree_tipo_chave": 1, "ree_ndoc": "t255",
    "ree_xdoc": "t255", "ree_fornec_doc": 14, "ree_fornec_nome": "t150", "ree_dt_emi": "d", "ree_dt_comp": "d",
    "ref_nfse": "t1000", "interm_doc": 14, "interm_nome": "t150", "v_receb": "v",
    "subst_chave": 50, "subst_motivo": 2, "subst_xmotivo": "t255",
}


def normalizar_nota(d: dict | None) -> dict:
    """Campos opcionais da nota (tela 'Mais campos da nota'): limpa, valida e devolve só o que foi preenchido."""
    import re
    out = {}
    for k, regra in CAMPOS_NOTA.items():
        v = str((d or {}).get(k) or "").strip()
        if not v:
            continue
        if isinstance(regra, int):
            v = re.sub(r"\D", "", v)[:regra]
        elif regra in ("v", "p"):
            n = _dec(v)
            if n < 0 or (regra == "p" and n > 100):
                raise ValueError(f"Valor inválido em {k}.")
            v = str(n)
        elif regra == "a8":                        # CIB: 8 caracteres alfanuméricos
            v = re.sub(r"[^0-9A-Za-z]", "", v).upper()[:8]
        elif regra == "d":
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
                raise ValueError("Datas no formato AAAA-MM-DD.")
        else:
            v = " ".join(v.split())[:int(regra[1:])]
        if v and v != "0":
            out[k] = v
    if "local_prestacao" in out and len(out["local_prestacao"]) != 7:
        raise ValueError("Município da prestação: código IBGE com 7 dígitos.")
    if "obra_cib" in out and len(out["obra_cib"]) != 8 or "imovel_cib" in out and len(out["imovel_cib"]) != 8:
        raise ValueError("CIB (Cadastro Imobiliário Brasileiro) tem 8 caracteres.")
    if "evento_nome" in out and not out.get("evento_ini"):
        raise ValueError("Evento: informe a data de início.")
    if "evento_nome" in out and not (out.get("evento_id") or out.get("evento_cep")):
        raise ValueError("Evento: informe o código do evento (prefeitura) ou o CEP e endereço.")
    if "ree_valor" in out and not out.get("ree_dt_emi"):
        raise ValueError("Reembolso/repasse: informe a data de emissão do documento.")
    if "interm_doc" in out and len(out["interm_doc"]) not in (11, 14):
        raise ValueError("Intermediário: CPF ou CNPJ inválido.")
    if "subst_chave" in out and len(out["subst_chave"]) != 50:
        raise ValueError("Substituição: a chave da NFS-e substituída tem 50 dígitos.")
    if "ref_nfse" in out:
        chaves = [re.sub(r"\D", "", c) for c in re.split(r"[,;\s]+", out["ref_nfse"]) if c.strip()]
        if any(len(c) != 50 for c in chaves):
            raise ValueError("NFS-e referenciada: cada chave de acesso tem 50 dígitos.")
        out["ref_nfse"] = ",".join(chaves)
    if "ded_pct" in out and "ded_valor" in out:
        raise ValueError("Dedução/redução: informe percentual ou valor, não os dois.")
    return out
