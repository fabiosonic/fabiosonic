"""Leitura dos dados fiscais das NFS-e já emitidas (XML nacional ou retorno do webservice de Itaboraí).

Cada nota rende dois conjuntos de fatos:
- do prestador → sugerem a regra geral da empresa (regime, apuração, carga aproximada, PIS/COFINS, IBS/CBS);
- do tomador → sugerem a regra específica dele (ISS retido, retenções, imunidade, exportação, IBS/CBS...).

A aplicação nunca sobrescreve o que o usuário já definiu: a regra geral só recebe o que ainda está vazio (uma vez,
na primeira importação), e o tomador só ganha regra específica se ainda não tiver regra gravada e se as notas
dele forem diferentes da regra geral.
"""

from __future__ import annotations

from collections import Counter
from decimal import ROUND_HALF_UP, Decimal

from .clientes import _achar, _digitos, _local, _texto

PADRAO_PCC = {"pis": Decimal("0.65"), "cofins": Decimal("3.00"), "csll": Decimal("1.00")}
# tpRetPisCofins (NT 007/2026) -> quais de (PIS, COFINS, CSLL) foram retidos
RETIDOS = {"0": (0, 0, 0), "1": (1, 1, 0), "2": (0, 0, 0), "3": (1, 1, 1), "4": (1, 1, 0), "5": (1, 0, 0),
           "6": (0, 1, 0), "7": (0, 1, 1), "8": (0, 0, 1), "9": (1, 0, 1)}


def _n(v) -> Decimal:
    try:
        return Decimal(str(v or "0").replace(",", ".").strip() or "0")
    except Exception:  # noqa: BLE001
        return Decimal(0)


def _pct(valor: Decimal, base: Decimal) -> str:
    if not valor or not base:
        return ""
    return str((valor / base * 100).quantize(Decimal("0.01"), ROUND_HALF_UP).normalize())


def _regime(op: str, p_pis: Decimal) -> str:
    if op == "2":
        return "mei"
    if op == "3":
        return "simples"
    if op == "1":
        return "real" if p_pis == Decimal("1.65") else "presumido" if p_pis == Decimal("0.65") else ""
    return ""


def _nacional(raiz) -> dict:
    dps = _achar(raiz, "infDPS")
    if dps is None:
        return {}
    vserv = _n(_texto(dps, "vServ"))
    op = _texto(dps, "regTrib/opSimpNac")
    pc = _achar(dps, "piscofins")
    p_pis, p_cof = _n(_texto(pc, "pAliqPis")), _n(_texto(pc, "pAliqCofins"))
    cst = _texto(pc, "CST")
    g = {"op_simp_nac": op, "regime": _regime(op, p_pis), "reg_ap_trib_sn": _texto(dps, "regTrib/regApTribSN"),
         "reg_esp_trib": _texto(dps, "regTrib/regEspTrib"), "pis_cofins_cst": cst,
         "p_pis": str(p_pis.normalize()) if p_pis else "", "p_cofins": str(p_cof.normalize()) if p_cof else ""}
    tot = _achar(dps, "totTrib")
    if _achar(tot, "pTotTribSN") is not None:
        g["tot_trib_modo"] = "simples"
    elif _achar(tot, "pTotTrib") is not None:
        g |= {"tot_trib_modo": "percentual", "p_tot_fed": _texto(tot, "pTotTribFed"),
              "p_tot_est": _texto(tot, "pTotTribEst"), "p_tot_mun": _texto(tot, "pTotTribMun")}
    elif _achar(tot, "indTotTrib") is not None:
        g["tot_trib_modo"] = "nao"
    elif _achar(tot, "vTotTrib") is not None:
        g["tot_trib_modo"] = "valor"
    ibs = _achar(dps, "IBSCBS")
    g["tem_ibscbs"] = "1" if ibs is not None else ""
    if ibs is not None:
        g |= {"cst_reg": _texto(ibs, "gTribRegular/CSTReg"), "class_trib_reg": _texto(ibs, "gTribRegular/cClassTribReg"),
              "p_dif_uf": _texto(ibs, "gDif/pDifUF"), "p_dif_mun": _texto(ibs, "gDif/pDifMun"),
              "p_dif_cbs": _texto(ibs, "gDif/pDifCBS"), "c_cred_pres": _texto(ibs, "cCredPres")}

    tm = _achar(dps, "tribMun")
    tp_ret = _texto(tm, "tpRetISSQN")
    t = {"iss_retido": tp_ret in ("2", "3"), "ret_iss_por": "intermediario" if tp_ret == "3" else "tomador",
         "aliquota_iss_retido": _texto(tm, "pAliq") if tp_ret in ("2", "3") else "",
         "trib_issqn": _texto(tm, "tribISSQN") or "1", "tp_imunidade": _texto(tm, "tpImunidade"),
         "pais_result": _texto(tm, "cPaisResult"), "exig_susp_tp": _texto(tm, "exigSusp/tpSusp"),
         "exig_susp_proc": _texto(tm, "exigSusp/nProcesso"), "n_bm": _texto(tm, "BM/nBM"),
         "p_red_bm": _texto(tm, "BM/pRedBCBM"), "pis_cofins_cst": cst}
    # retenções federais em % do valor do serviço
    tf = _achar(dps, "tribFed")
    t["ret_irrf_pct"] = _pct(_n(_texto(tf, "vRetIRRF")), vserv)
    t["ret_inss_pct"] = _pct(_n(_texto(tf, "vRetCP")), vserv)
    tp_pcc = _texto(pc, "tpRetPisCofins")
    v_csll = _n(_texto(tf, "vRetCSLL"))
    if tp_pcc == "1" and (_texto(pc, "vPis") or _texto(pc, "vCofins")) and cst in ("", "00"):
        # leiaute anterior: vPis/vCofins eram os valores retidos e vRetCSLL só a CSLL
        t["ret_pis_pct"] = _pct(_n(_texto(pc, "vPis")), vserv)
        t["ret_cofins_pct"] = _pct(_n(_texto(pc, "vCofins")), vserv)
        t["ret_csll_pct"] = _pct(v_csll, vserv)
    elif v_csll:
        # NT 007/2026: vRetCSLL = PIS + COFINS + CSLL retidos; tpRetPisCofins diz quais
        ret = RETIDOS.get(tp_pcc, (0, 0, 1))
        padrao = sum(p for p, r in zip(PADRAO_PCC.values(), ret) if r)
        total = v_csll / vserv * 100 if vserv else Decimal(0)
        if padrao and abs(total - padrao) <= Decimal("0.02"):
            for (k, p), r in zip(PADRAO_PCC.items(), ret):
                t[f"ret_{k}_pct"] = str(p.normalize()) if r else ""
        else:
            t["ret_csll_pct"] = _pct(v_csll, vserv)
    if ibs is not None:
        t |= {"ind_final": _texto(ibs, "indFinal"), "class_trib": _digitos(_texto(ibs, "gIBSCBS/cClassTrib")),
              "tp_ente_gov": _texto(ibs, "tpEnteGov"), "tp_oper": _texto(ibs, "tpOper"),
              "dest_doc": _digitos(_texto(ibs, "dest/CNPJ") or _texto(ibs, "dest/CPF")),
              "dest_nome": _texto(ibs, "dest/xNome")}
    toma = _achar(dps, "toma")
    return {"geral": g, "tomador": t, "doc": _digitos(_texto(toma, "CNPJ") or _texto(toma, "CPF")),
            "data": _texto(dps, "dhEmi")[:10]}


def _municipal(raiz) -> dict:
    vserv = _n(_texto(raiz, "ValorTotalDosServicos") or _texto(raiz, "ValorServicos"))
    optante = _texto(raiz, "OptanteSimplesNacional")
    g = {"regime": "simples" if optante in ("1", "S", "s", "true") else ""}
    if g["regime"]:
        g["op_simp_nac"] = "3"
    retido = _texto(raiz, "IssRetido") == "1"
    t = {"iss_retido": retido, "aliquota_iss_retido": _texto(raiz, "Aliquota") if retido else "",
         "ret_irrf_pct": _pct(_n(_texto(raiz, "ValorIR")), vserv), "ret_pis_pct": _pct(_n(_texto(raiz, "ValorPIS")), vserv),
         "ret_cofins_pct": _pct(_n(_texto(raiz, "ValorCOFINS")), vserv),
         "ret_csll_pct": _pct(_n(_texto(raiz, "ValorCSLL")), vserv),
         "ret_inss_pct": _pct(_n(_texto(raiz, "ValorINSS")), vserv)}
    tom = _achar(raiz, "TomadorServico")
    return {"geral": g, "tomador": t, "doc": _digitos(_texto(tom, "CpfCnpj")),
            "data": _texto(raiz, "DataEmissaoNFSe")[:10]}


def fatos(raiz) -> dict:
    """Fatos fiscais de uma nota ({} se não for NFS-e reconhecida)."""
    if raiz is None:
        return {}
    if _local(raiz.tag) == "RetornoNfse" or _achar(raiz, "TomadorServico") is not None:
        return _municipal(raiz)
    return _nacional(raiz)


def _mais_frequente(valores: list) -> str:
    c = Counter(v for v in valores if v not in ("", None))
    return c.most_common(1)[0][0] if c else ""


def regra_geral(notas: list[dict]) -> dict:
    """Valor mais frequente de cada fato do prestador."""
    chaves = {k for n in notas for k in n.get("geral", {})}
    return {k: _mais_frequente([n["geral"].get(k) for n in notas]) for k in chaves}


PADRAO_TOT = {"simples": "simples", "mei": "nao", "presumido": "valor", "real": "valor"}
REGIME_PIS = {"presumido": ("0.65", "3"), "real": ("1.65", "7.6")}


def aplicar_geral(notas: list[dict]) -> list[str]:
    """Preenche a regra geral da empresa em uso com o que as notas mostram (só o que ainda não foi definido)."""
    from . import config
    cfg = config.carregar()
    f = cfg.get("fiscal") or {}
    if f.get("lido_dos_xml") or not notas:
        return []
    g = regra_geral(notas)
    novo_f: dict = {}
    novo_e: dict = {}
    if g.get("regime") and not f.get("regime"):
        novo_f["regime"] = g["regime"]
    regime = novo_f.get("regime") or f.get("regime") or ""
    if g.get("op_simp_nac"):
        novo_e["op_simp_nac"] = g["op_simp_nac"]
    for k in ("reg_ap_trib_sn", "reg_esp_trib"):
        if g.get(k):
            novo_e[k] = g[k]
    modo = g.get("tot_trib_modo")
    if modo and modo != PADRAO_TOT.get(regime) and f.get("tot_trib_modo", "auto") == "auto":
        novo_f["tot_trib_modo"] = modo
        if modo == "percentual":
            novo_f |= {k: g.get(k, "") for k in ("p_tot_fed", "p_tot_est", "p_tot_mun")}
    if g.get("pis_cofins_cst") and g["pis_cofins_cst"] not in ("01", "00") and not f.get("pis_cofins_cst"):
        novo_f["pis_cofins_cst"] = g["pis_cofins_cst"]
    padrao_pis = REGIME_PIS.get(regime)
    if g.get("p_pis") and padrao_pis and (g["p_pis"], g.get("p_cofins")) != padrao_pis and not f.get("p_pis"):
        novo_f |= {"p_pis": g["p_pis"], "p_cofins": g.get("p_cofins", "")}
    for k in ("cst_reg", "class_trib_reg", "p_dif_uf", "p_dif_mun", "p_dif_cbs", "c_cred_pres"):
        if g.get(k) and not f.get(k):
            novo_f[k] = g[k]
    if g.get("tem_ibscbs") and regime in ("simples", "mei") and f.get("ibscbs", "auto") == "auto":
        novo_f["ibscbs"] = "sempre"            # a empresa já informava IBS/CBS antes de ser obrigatório
    novo_f["lido_dos_xml"] = True
    config.salvar({"fiscal": novo_f, "emissao": novo_e} if novo_e else {"fiscal": novo_f})
    return [k for k in list(novo_f) + list(novo_e) if k != "lido_dos_xml"]


CAMPOS_COMPARAR = ("iss_retido", "aliquota_iss_retido", "ret_iss_por", "ret_irrf_pct", "ret_pis_pct", "ret_cofins_pct",
                   "ret_csll_pct", "ret_inss_pct", "trib_issqn", "tp_imunidade", "pais_result", "exig_susp_tp",
                   "exig_susp_proc", "n_bm", "p_red_bm", "pis_cofins_cst", "ind_final", "class_trib", "tp_ente_gov",
                   "tp_oper", "dest_doc", "dest_nome")


def _norm(v) -> str:
    if isinstance(v, bool):
        return "1" if v else ""
    s = str(v or "").strip().replace(",", ".")
    try:
        return str(Decimal(s).normalize()) if s and s.replace(".", "", 1).isdigit() else s
    except Exception:  # noqa: BLE001
        return s


def _igual(a, b) -> bool:
    vazio = ("", "0")
    na, nb = _norm(a), _norm(b)
    return (na in vazio and nb in vazio) or na == nb


def aplicar_tomadores(notas: list[dict]) -> int:
    """Tomador sem regra gravada cujas notas diferem da regra geral ganha regra específica (da nota mais recente)."""
    from . import clientes, fiscal
    geral = fiscal.geral()
    cclass_comum = _mais_frequente([n["tomador"].get("class_trib") for n in notas])
    ind_auto = lambda doc: "1" if len(doc) == 11 else "0"  # noqa: E731
    ultima: dict[str, dict] = {}
    for n in sorted(notas, key=lambda x: x.get("data", "")):
        if n.get("doc"):
            ultima[n["doc"]] = n
    n_regras = 0
    for c in clientes.listar():
        nota = ultima.get(c["cpf_cnpj"])
        if not nota or "fiscal" in c:
            continue
        t = dict(nota["tomador"])
        if t.get("class_trib") == cclass_comum:
            t["class_trib"] = ""                    # é o do serviço, não uma particularidade do tomador
        if t.get("ind_final") == ind_auto(c["cpf_cnpj"]):
            t["ind_final"] = ""
        if t.get("pis_cofins_cst") in (geral.get("pis_cofins_cst") or "01", "00"):
            t["pis_cofins_cst"] = ""
        if t.get("trib_issqn") == "1":
            t["trib_issqn"] = ""
        if t.get("ret_iss_por") == "tomador" or not t.get("iss_retido"):
            t["ret_iss_por"] = ""                   # padrão: retido pelo tomador
        diferente = [k for k in CAMPOS_COMPARAR if t.get(k) not in ("", None, False)
                     and not _igual(t.get(k), geral.get(k))]
        if not diferente:
            continue
        regra = {"usar_geral": False, **{k: geral.get(k) for k in fiscal.CAMPOS_TOMADOR if k in geral},
                 **{k: v for k, v in t.items() if v not in ("", None)},
                 **{k: t.get(k) or "0" for k in fiscal.RETENCOES}, "iss_retido": bool(t.get("iss_retido"))}
        regra.setdefault("trib_issqn", "1")
        regra.setdefault("ind_final", "auto")
        try:
            clientes.salvar({**c, "fiscal": regra})
            n_regras += 1
        except ValueError:
            continue                                # dado incompleto na nota: fica na regra geral
    return n_regras
