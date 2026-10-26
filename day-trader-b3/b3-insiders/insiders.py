#!/usr/bin/env python3
"""Negociações de administradores e controladores para b3-insiders. Só
biblioteca padrão. Substitui o "Pelosi tracker" do day-trader-skill: no
Brasil a informação pública equivalente é o formulário de Valores Mobiliários
Negociados e Detidos (Resolução CVM 44, art. 11), que cada companhia entrega
todo mês com as compras e vendas de diretores, conselheiros, membros de órgãos
estatutários e controladores (e pessoas ligadas), consolidado por cargo.

    python3 insiders.py PETR4,VALE3                 # últimos 3 meses
    python3 insiders.py WEGE3 --meses 6 --detalhe   # cada negócio
    python3 insiders.py --ranking                   # maiores compras líquidas do último mês
    python3 insiders.py --ranking --vendas          # maiores vendas líquidas
    python3 insiders.py --novos                     # só meses ainda não vistos

Conta só compras e vendas À VISTA de ações da própria companhia. Planos de
remuneração, subscrição, doação, empréstimo e bonificação ficam de fora.
Negócio informado com preço zero entra na quantidade e não no volume.

Atraso: o formulário vence 10 dias depois do fim do mês, e o arquivo da CVM é
atualizado uma vez por dia. Mostra o passado, não intenção: administrador
vende por motivos pessoais, fiscais ou de diversificação. Não é informação
privilegiada e não é sinal de compra ou venda.
"""

import argparse
import datetime
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "b3-comum"))
import b3lib  # noqa: E402
import cvm  # noqa: E402

MOVS = {"Compra à vista": "compra", "Venda à vista": "venda"}
CLASSE_POR_FINAL = {3: "ON", 4: "PN", 5: "PNA", 6: "PNB", 7: "PNC", 8: "PND"}


def classe(sym):
    m = b3lib.TICKER.match(b3lib.sem_fracionario(sym))
    return CLASSE_POR_FINAL.get(int(m.group(2))) if m else None


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def ler_negocios(anos, desde, offline=None, cnpjs=None):
    """Negócios à vista de ações da própria companhia, versão mais recente de cada mês."""
    brutos, versao = [], {}
    for ano in anos:
        try:
            z = cvm.zip_ano("VLMO", ano, offline=offline)
        except b3lib.B3Erro:
            continue
        for r in cvm.linhas(z, "vlmo_cia_aberta_con",
                            lambda r: r["Tipo_Movimentacao"] in MOVS and r["Tipo_Empresa"] == "Companhia"
                            and r["Tipo_Ativo"] == "Ações" and (cnpjs is None or r["CNPJ_Companhia"] in cnpjs)):
            if r["Data_Referencia"] < desde:
                continue
            k = (r["CNPJ_Companhia"], r["Data_Referencia"])
            v = int(r["Versao"] or 1)
            versao[k] = max(versao.get(k, 0), v)
            brutos.append((k, v, r))
    out = []
    for k, v, r in brutos:
        if v != versao[k]:
            continue
        out.append({"cnpj": r["CNPJ_Companhia"], "empresa": r["Nome_Companhia"].strip(), "mes": r["Data_Referencia"][:7],
                    "cargo": r["Tipo_Cargo"] or "Não informado", "lado": MOVS[r["Tipo_Movimentacao"]],
                    "classe": (r["Caracteristica_Valor_Mobiliario"] or "").strip().upper(), "data": r["Data_Movimentacao"],
                    "qtd": f(r["Quantidade"]), "preco": f(r["Preco_Unitario"]), "volume": f(r["Volume"]),
                    "corretora": r["Intermediario"]})
    return out


def resumir(negocios):
    """{(cnpj, classe): {"empresa", "meses": {mes: {cargo: {compra, venda, ...}}}, totais}}."""
    res = {}
    for n in negocios:
        k = (n["cnpj"], n["classe"])
        r = res.setdefault(k, {"empresa": n["empresa"], "classe": n["classe"], "meses": defaultdict(dict),
                               "compra_qtd": 0.0, "venda_qtd": 0.0, "compra_vol": 0.0, "venda_vol": 0.0})
        c = r["meses"][n["mes"]].setdefault(n["cargo"], {"compra_qtd": 0.0, "venda_qtd": 0.0, "compra_vol": 0.0, "venda_vol": 0.0})
        c[n["lado"] + "_qtd"] += n["qtd"]
        c[n["lado"] + "_vol"] += n["volume"]
        r[n["lado"] + "_qtd"] += n["qtd"]
        r[n["lado"] + "_vol"] += n["volume"]
    for r in res.values():
        r["liquido_vol"] = r["compra_vol"] - r["venda_vol"]
        r["liquido_qtd"] = r["compra_qtd"] - r["venda_qtd"]
        r["meses"] = {m: r["meses"][m] for m in sorted(r["meses"])}
    return res


def linha_total(r):
    sinal = "COMPRA LÍQUIDA" if r["liquido_vol"] > 0 else "VENDA LÍQUIDA" if r["liquido_vol"] < 0 else "neutro"
    return "%s: compras %s ações (%s), vendas %s ações (%s) -> %s de %s" % (
        r["classe"] or "?", b3lib.num(r["compra_qtd"], 0), b3lib.reais(r["compra_vol"], 0), b3lib.num(r["venda_qtd"], 0),
        b3lib.reais(r["venda_vol"], 0), sinal, b3lib.reais(abs(r["liquido_vol"]), 0))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("symbols", nargs="?")
    p.add_argument("--meses", type=int, default=3)
    p.add_argument("--detalhe", action="store_true")
    p.add_argument("--ranking", action="store_true")
    p.add_argument("--vendas", action="store_true")
    p.add_argument("--top", type=int, default=15)
    p.add_argument("--novos", action="store_true")
    p.add_argument("--now")
    p.add_argument("--offline", help="pasta com os ZIPs da CVM")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    try:
        hoje = b3lib.para_brt(b3lib.ler_agora(a.now)).date()
        primeiro = datetime.date(hoje.year, hoje.month, 1)
        for _ in range(a.meses if not a.ranking else 1):
            primeiro = (primeiro - datetime.timedelta(days=1)).replace(day=1)
        desde = primeiro.isoformat()
        anos = sorted({primeiro.year, hoje.year})
        if a.ranking:
            negs = ler_negocios(anos, desde, a.offline)
            ultimo = max((n["mes"] for n in negs), default=None)
            negs = [n for n in negs if n["mes"] == ultimo]
            res = sorted(resumir(negs).values(), key=lambda r: r["liquido_vol"], reverse=not a.vendas)[:a.top]
            if a.json:
                print(json.dumps({"mes": ultimo, "ranking": res}, ensure_ascii=False, indent=2, default=dict))
                return 0
            print("Maiores %s líquidas de administradores e controladores em %s (CVM, art. 11 da Res. CVM 44):" % (
                "vendas" if a.vendas else "compras", ultimo))
            for i, r in enumerate(res, 1):
                print("  %2d. %-45s %s" % (i, r["empresa"][:45], linha_total(r)))
            return 0 if res else 1
        if not a.symbols:
            raise b3lib.B3Erro("informe os ativos (ex.: PETR4,VALE3) ou use --ranking")
        syms = [b3lib.sem_fracionario(s) for s in a.symbols.split(",") if s.strip()]
        cnpjs, faltou = cvm.cnpj_de(syms, hoje.year, a.offline)
        negs = ler_negocios(anos, desde, a.offline, {v["cnpj"] for v in cnpjs.values()})
        estado_p = b3lib.caminho("estado", "insiders.json")
        estado = b3lib.ler_json(estado_p, {"vistos": {}}) or {"vistos": {}}
        if a.novos:
            negs = [n for n in negs if n["mes"] > estado["vistos"].get(n["cnpj"], "")]
        for n in negs:
            estado["vistos"][n["cnpj"]] = max(estado["vistos"].get(n["cnpj"], ""), n["mes"])
        b3lib.gravar_json(estado_p, estado)
        res = resumir(negs)
        if a.json:
            print(json.dumps({"desde": desde, "resumo": {"%s %s" % k: v for k, v in res.items()},
                              "negocios": negs if a.detalhe else None, "sem_cadastro": faltou},
                             ensure_ascii=False, indent=2, default=dict))
            return 0 if res else 1
        for sym, info in cnpjs.items():
            print("%s — %s, negócios à vista de administradores e controladores desde %s:" % (sym, info["nome"], desde[:7]))
            grupos = [r for (cnpj, cl), r in sorted(res.items()) if cnpj == info["cnpj"]]
            alvo = classe(sym)
            grupos.sort(key=lambda r: r["classe"] != alvo)
            if not grupos:
                print("  nenhuma compra ou venda à vista informada no período")
            for r in grupos:
                print("  " + linha_total(r) + ("  <- classe do %s" % sym if r["classe"] == alvo else ""))
                for mes, cargos in r["meses"].items():
                    for cargo, c in cargos.items():
                        print("     %s %-40s compra %12s  venda %12s" % (mes, cargo[:40], b3lib.reais(c["compra_vol"], 0),
                                                                        b3lib.reais(c["venda_vol"], 0)))
            if a.detalhe:
                for n in sorted((n for n in negs if n["cnpj"] == info["cnpj"]), key=lambda n: n["data"]):
                    print("     %s %-6s %-4s %10s a %s (%s) — %s" % (n["data"], n["lado"], n["classe"], b3lib.num(n["qtd"], 0),
                                                                   b3lib.reais(n["preco"]), n["cargo"], n["corretora"]))
        if faltou:
            print("sem cadastro na CVM: %s" % ", ".join(faltou))
        print("Mostra o passado (formulário mensal, entregue até 10 dias após o mês). Não é sinal de compra ou venda.")
        return 0 if res else 1
    except b3lib.B3Erro as e:
        print("insiders: %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
