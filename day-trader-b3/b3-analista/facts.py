#!/usr/bin/env python3
"""Analista de resultados para b3-analista. Só biblioteca padrão.

Lê as demonstrações que as companhias entregam à CVM (ITR trimestral e DFP
anual, Portal de Dados Abertos) e monta, por trimestre: receita, resultado
antes do resultado financeiro (EBIT), lucro líquido, margens e crescimento
contra o mesmo trimestre do ano anterior.

    python3 facts.py PETR4
    python3 facts.py ITUB4 --trimestres 8 --individual
    python3 facts.py PETR4,VALE3 --json --write      # grava trader-b3/analista.json

De onde vem cada número (DRE consolidada; --individual usa a individual):
  receita  conta 3.01 (em bancos: Receitas da Intermediação Financeira)
  EBIT     "Resultado Antes do Resultado Financeiro e dos Tributos"
           (não existe em bancos e seguradoras: fica "-")
  lucro    "Lucro/Prejuízo Consolidado do Período" (ou "do Período")
  4º tri   não há ITR do 4º trimestre: 4T = DFP anual - 9 meses do ITR do 3T

Valores em R$ convertidos da escala informada (MIL/UNIDADE). A versão mais
recente de cada documento vale (reapresentações substituem a original).
Primeira execução baixa ~65 MB da CVM (ITR do ano, ITR e DFP do ano anterior);
depois usa o cache por 24 h. Dado contábil não é recomendação.
"""

import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "b3-comum"))
import b3lib  # noqa: E402
import cvm  # noqa: E402

ESCALA = {"MIL": 1000.0, "UNIDADE": 1.0}


def conta(cd, ds):
    """Classifica a linha da DRE em receita, ebit, lucro ou None."""
    ds = (ds or "").strip()
    if cd == "3.01":
        return "receita"
    if cd.count(".") != 1:
        return None
    if ds.startswith("Resultado Antes do Resultado Financeiro"):
        return "ebit"
    if ds.startswith("Lucro/Prejuízo Consolidado do Período") or ds.startswith("Lucro/Prejuízo do Período"):
        return "lucro"
    return None


def ler_dre(path_zip, cnpj, tipo, individual=False):
    """{(ini, fim): {"receita", "ebit", "lucro", "versao", "ref"}} de um ITR/DFP."""
    membro = "_DRE_%s" % ("ind" if individual else "con")
    periodos = {}
    for r in cvm.linhas(path_zip, membro, lambda r: r["CNPJ_CIA"] == cnpj):
        k = conta(r["CD_CONTA"], r["DS_CONTA"])
        if not k:
            continue
        chave = (r["DT_INI_EXERC"], r["DT_FIM_EXERC"])
        versao = int(r["VERSAO"] or 1)
        p = periodos.setdefault(chave, {"versao": versao, "ref": r["DT_REFER"]})
        if versao < p["versao"]:
            continue
        if versao > p["versao"]:
            periodos[chave] = p = {"versao": versao, "ref": r["DT_REFER"]}
        try:
            p[k] = float(r["VL_CONTA"]) * ESCALA.get(r["ESCALA_MOEDA"], 1.0)
        except ValueError:
            pass
    return periodos


def meses(ini, fim):
    a, b = datetime.date.fromisoformat(ini), datetime.date.fromisoformat(fim)
    return (b.year - a.year) * 12 + b.month - a.month + 1


def trimestres(*fontes):
    """Junta períodos e devolve {fim_do_tri: valores} de trimestres de 3 meses,
    derivando o 4º tri de anual - 9 meses."""
    todos = {}
    for f in fontes:
        for k, v in f.items():
            if k not in todos or v["versao"] >= todos[k]["versao"]:
                todos[k] = v
    tri = {fim: v for (ini, fim), v in todos.items() if meses(ini, fim) == 3}
    for (ini, fim), anual in todos.items():
        if meses(ini, fim) == 12 and fim.endswith("-12-31") and fim not in tri:
            nove = todos.get((ini, fim[:4] + "-09-30"))
            if nove:
                tri[fim] = {k: anual[k] - nove[k] for k in ("receita", "ebit", "lucro") if k in anual and k in nove}
                tri[fim]["derivado"] = True
    return tri


def var(a, b):
    return None if a is None or b in (None, 0) else (a / abs(b) - 1) * 100


def analisar(tri, n=6):
    fins = sorted(tri)[-n:]
    out = []
    for fim in fins:
        v = tri[fim]
        ant = tri.get(str(int(fim[:4]) - 1) + fim[4:]) or {}
        rec = v.get("receita")
        out.append({"trimestre": "%dT%s" % ((int(fim[5:7]) + 2) // 3, fim[2:4]), "fim": fim,
                    "receita": rec, "ebit": v.get("ebit"), "lucro": v.get("lucro"),
                    "margem_ebit": (v["ebit"] / rec * 100) if v.get("ebit") is not None and rec else None,
                    "margem_liquida": (v["lucro"] / rec * 100) if v.get("lucro") is not None and rec else None,
                    "receita_aa": var(rec, ant.get("receita")), "lucro_aa": var(v.get("lucro"), ant.get("lucro")),
                    "derivado": bool(v.get("derivado"))})
    return out


def ultimo_documento(z, cnpj):
    docs = [r for r in cvm.linhas(z, "itr_cia_aberta_2", lambda r: r["CNPJ_CIA"] == cnpj)] if z else []
    if not docs:
        return None
    d = max(docs, key=lambda r: (r["DT_REFER"], int(r["VERSAO"] or 1)))
    return {"referencia": d["DT_REFER"], "entregue": d["DT_RECEB"], "link": d["LINK_DOC"], "versao": d["VERSAO"]}


def mi(x):
    return "-" if x is None else b3lib.num(x / 1e6, 0)


def render(sym, nome, linhas, doc):
    out = ["%s — %s (R$ milhões; fonte: CVM, ITR/DFP)" % (sym, nome),
           "  %-6s %12s %12s %12s %8s %8s %9s %9s" % ("tri", "receita", "EBIT", "lucro", "mg EBIT", "mg líq", "rec a/a", "luc a/a")]
    for l in linhas:
        out.append("  %-6s %12s %12s %12s %8s %8s %9s %9s%s" % (
            l["trimestre"], mi(l["receita"]), mi(l["ebit"]), mi(l["lucro"]), b3lib.pct(l["margem_ebit"], 1),
            b3lib.pct(l["margem_liquida"], 1), b3lib.pct(l["receita_aa"], 1), b3lib.pct(l["lucro_aa"], 1),
            "  (4T = anual - 9M)" if l["derivado"] else ""))
    if doc:
        out.append("  último ITR: referência %s, entregue em %s (versão %s)\n  %s" % (
            doc["referencia"], doc["entregue"], doc["versao"], doc["link"]))
    return "\n".join(out)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("symbols")
    p.add_argument("--trimestres", type=int, default=6)
    p.add_argument("--individual", action="store_true")
    p.add_argument("--ano", type=int)
    p.add_argument("--offline", help="pasta com os ZIPs da CVM")
    p.add_argument("--json", action="store_true")
    p.add_argument("--write", action="store_true")
    a = p.parse_args(argv)
    try:
        ano = a.ano or datetime.date.today().year
        syms = [b3lib.sem_fracionario(s) for s in a.symbols.split(",") if s.strip()]
        cnpjs, faltou = cvm.cnpj_de(syms, ano, a.offline)
        zips = {}
        for chave, (conj, an) in {"itr": ("ITR", ano), "itr_ant": ("ITR", ano - 1), "dfp_ant": ("DFP", ano - 1)}.items():
            try:
                zips[chave] = cvm.zip_ano(conj, an, horas=24, offline=a.offline)
            except b3lib.B3Erro:
                zips[chave] = None
        if not zips["itr"] and not zips["itr_ant"]:
            raise b3lib.B3Erro("não consegui os arquivos ITR da CVM")
        res = {}
        for sym, info in cnpjs.items():
            fontes = [ler_dre(zips[k], info["cnpj"], k[:3], a.individual) for k in ("itr_ant", "dfp_ant", "itr") if zips[k]]
            linhas = analisar(trimestres(*fontes), a.trimestres)
            res[sym] = {"empresa": info["nome"], "cnpj": info["cnpj"], "trimestres": linhas,
                        "ultimo_itr": ultimo_documento(zips["itr"], info["cnpj"])}
        if a.write:
            b3lib.gravar_json(b3lib.caminho("analista.json"), res)
        if a.json:
            print(json.dumps({"resultados": res, "sem_cadastro": faltou}, ensure_ascii=False, indent=2))
        else:
            for sym, r in res.items():
                print(render(sym, r["empresa"], r["trimestres"], r["ultimo_itr"]) if r["trimestres"] else
                      "%s — %s: nenhuma DRE %s encontrada" % (sym, r["empresa"], "individual" if a.individual else "consolidada (tente --individual)"))
            if faltou:
                print("sem cadastro na CVM (BDR, ETF ou FII não entregam ITR como companhia aberta): %s" % ", ".join(faltou))
        return 0 if res else 1
    except b3lib.B3Erro as e:
        print("analista: %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
