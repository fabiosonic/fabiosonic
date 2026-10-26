#!/usr/bin/env python3
"""Ponte fiscal para b3-fiscal: transforma as execuções registradas pela
b3-boleta (trader-b3/execucoes.csv) no layout de apuração mensal de IR da
skill `traders` e, se ela estiver instalada, roda a apuração.

    python3 fiscal.py exportar                     # -> trader-b3/operacoes_ir.csv
    python3 fiscal.py apurar                       # exporta e roda apuracao_mensal.py
    python3 fiscal.py apurar --prejuizo-dt 350.20 --irrf-anterior 1.10

Day trade x operação comum (IN RFB 1.585/2015, art. 65, §1º): é day trade a
compra e a venda do mesmo ativo no mesmo dia, na mesma corretora. Por dia e por
ativo (lote e fracionário juntos), a quantidade casada = menor entre o total
comprado e o total vendido; o resto é operação comum (swing trade). Os custos
de cada execução são rateados pela quantidade.

Premissa: todas as execuções do arquivo são da MESMA corretora. Se você usa
mais de uma, registre-as em pastas separadas (variável B3_DIR) e apure juntas
depois: operações em corretoras diferentes no mesmo dia não são day trade.

Tipo do ativo: final 3 a 8 = ACAO; 31 a 35 e 39 = BDR; final 11 é ambíguo
(unit, ETF ou FII) e precisa estar em "tipos" no trader-b3/config.json,
ex.: {"tipos": {"BOVA11": "ETF", "HGLG11": "FII", "TAEE11": "ACAO"}}.

Onde procura a apuração: variável TRADERS_APURACAO, .claude/skills/traders/
scripts/apuracao_mensal.py no repositório e em ~/.claude/skills/traders/.
"""

import argparse
import csv
import os
import subprocess
import sys
from collections import OrderedDict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "b3-comum"))
import b3lib  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
CAMPOS_IR = ["data", "ativo", "tipo", "modalidade", "operacao", "quantidade", "preco", "custos"]


def ler_execucoes(path):
    if not os.path.exists(path):
        raise b3lib.B3Erro("não há %s: registre execuções com `ticket.py fill`" % path)
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def classificar(execs, cfg):
    """Execuções -> linhas no layout da skill traders, separando DT de ST."""
    grupos = OrderedDict()
    for e in sorted(execs, key=lambda r: (r["data"], r.get("hora", ""))):
        grupos.setdefault((e["data"], b3lib.sem_fracionario(e["codigo"])), []).append(e)
    linhas, faltando = [], set()
    for (data, sym), evs in grupos.items():
        tipo = b3lib.tipo_ativo(sym, cfg)
        if tipo == "UNIT":
            tipo = "ACAO"
        if tipo is None:
            faltando.add(sym)
            continue
        compras = sum(int(e["quantidade"]) for e in evs if e["lado"] == "compra")
        vendas = sum(int(e["quantidade"]) for e in evs if e["lado"] == "venda")
        dt = {"compra": min(compras, vendas), "venda": min(compras, vendas)}
        for e in evs:
            q = int(e["quantidade"])
            custo = float(e.get("custos") or 0)
            no_dt = min(q, dt[e["lado"]])
            dt[e["lado"]] -= no_dt
            for qtd, mod in ((no_dt, "DT"), (q - no_dt, "ST")):
                if qtd:
                    linhas.append({"data": data, "ativo": sym, "tipo": tipo, "modalidade": mod,
                                   "operacao": "C" if e["lado"] == "compra" else "V", "quantidade": qtd,
                                   "preco": e["preco"], "custos": "%.2f" % (custo * qtd / q)})
    if faltando:
        raise b3lib.B3Erro("defina o tipo (ACAO, ETF, FII ou BDR) em \"tipos\" no config para: %s"
                           % ", ".join(sorted(faltando)))
    return linhas


def gravar(linhas, path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS_IR)
        w.writeheader()
        w.writerows(linhas)


def achar_apuracao():
    candidatos = [os.environ.get("TRADERS_APURACAO"),
                  os.path.join(AQUI, "..", "..", ".claude", "skills", "traders", "scripts", "apuracao_mensal.py"),
                  os.path.join(os.getcwd(), ".claude", "skills", "traders", "scripts", "apuracao_mensal.py"),
                  os.path.expanduser("~/.claude/skills/traders/scripts/apuracao_mensal.py")]
    return next((os.path.abspath(c) for c in candidatos if c and os.path.exists(c)), None)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cmd", choices=["exportar", "apurar"])
    p.add_argument("--execucoes", default=b3lib.caminho("execucoes.csv"))
    p.add_argument("--saida", default=b3lib.caminho("operacoes_ir.csv"))
    p.add_argument("--prejuizo-comum", default="0")
    p.add_argument("--prejuizo-dt", default="0")
    p.add_argument("--prejuizo-fii", default="0")
    p.add_argument("--irrf-anterior", default="0")
    p.add_argument("--custo-inicial")
    p.add_argument("--config")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    try:
        cfg = b3lib.ler_config(a.config)
        linhas = classificar(ler_execucoes(a.execucoes), cfg)
        gravar(linhas, a.saida)
        n_dt = sum(1 for l in linhas if l["modalidade"] == "DT")
        print("%d linhas exportadas para %s (%d day trade, %d operação comum)." % (
            len(linhas), a.saida, n_dt, len(linhas) - n_dt), file=sys.stderr if a.json else sys.stdout)
        if a.cmd == "exportar":
            return 0
        script = achar_apuracao()
        if not script:
            print("Não achei a skill traders (apuracao_mensal.py). Use /traders com o arquivo %s "
                  "ou defina TRADERS_APURACAO." % a.saida)
            return 1
        cmd = [sys.executable, script, a.saida, "--prejuizo-comum", a.prejuizo_comum, "--prejuizo-dt",
               a.prejuizo_dt, "--prejuizo-fii", a.prejuizo_fii, "--irrf-anterior", a.irrf_anterior]
        if a.custo_inicial:
            cmd += ["--custo-inicial", a.custo_inicial]
        if a.json:
            cmd.append("--json")
        return subprocess.call(cmd)
    except b3lib.B3Erro as e:
        print("fiscal: %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
