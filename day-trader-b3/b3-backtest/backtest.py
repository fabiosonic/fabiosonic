#!/usr/bin/env python3
"""Backtest e treino do swing trade (comprado e vendido) para b3-backtest.
Só biblioteca padrão.

    python3 backtest.py baixar                       # histórico diário desde 2000 do universo (IBRA) + Ibovespa
    python3 backtest.py baixar --symbols PETR4,VALE3 --desde 2005-01-01
    python3 backtest.py testar --setup sobrevendido  # parâmetros atuais da skill, ano a ano
    python3 backtest.py testar --setup perdeu_20d --entrada abertura --stop atr:2 --alvo 3 --prazo 10 --filtro ambos
    python3 backtest.py otimizar                     # walk-forward + parâmetros treinados (sem gravar)
    python3 backtest.py otimizar --write             # grava b3-swing/parametros.json e o relatório

Treino (otimizar):
  1. Para cada setup (5 de compra, 5 de venda) testa a grade inteira:
     entrada (gatilho, abertura) x stop (swing:3/5/10, atr:1.5/2/3) x alvo
     (1R, 1.5R, 2R, 3R, sem alvo) x prazo (5, 10, 15, 20, 30 pregões) x filtro
     (nenhum; tendência = ativo do lado certo da MM200; regime = Ibovespa do
     lado certo da MM200; ambos) = 1.200 combinações, com custos (0,03% por
     perna), escorregamento (0,05% nas ordens stop) e aluguel de 2% a.a. no
     vendido.
  2. Walk-forward: treina 8 anos, escolhe a combinação de maior t (média de R
     / erro padrão) entre as que têm 100+ operações, R médio >= 0,05 e t >= 2,
     e mede nos 2 anos seguintes, que o treino não viu. Repete a janela de 2
     em 2 anos. O resultado fora da amostra é a estimativa honesta.
  3. Parâmetros finais: a mesma regra nos 10 anos mais recentes. Um setup só
     fica ATIVO se o processo deu R médio > 0 e t >= 1,5 fora da amostra.

Limites: o universo é a carteira atual do índice (viés de sobrevivência:
empresas que quebraram ou saíram não estão nos dados); operações por ativo
sem limite de carteira; dados gratuitos do Yahoo. Resultado passado não
garante resultado futuro.
"""

import argparse
import datetime
import json
import math
import os
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(AQUI, "..", "b3-comum"))
import b3lib  # noqa: E402
import carteira  # noqa: E402
import dados  # noqa: E402
import motor  # noqa: E402

PARAMETROS = os.path.join(AQUI, "..", "b3-swing", "parametros.json")
TREINO_ANOS, TESTE_ANOS = 8, 2
MIN_N, MIN_R, MIN_T = 100, 0.05, 2.0
OOS_MIN_T = 1.5
FINAL_ANOS = 10
ORDEM_CARTEIRA = "baixa_vol"   # menor ATR % primeiro: melhor nas duas metades fora da amostra
CENARIOS = ((0.005, 5), (0.01, 5))


# ---------------------------------------------------------------- texto dos combos

def combo_txt(c):
    entrada, (tipo, p), A, P, filtro = c
    return "%s, stop %s:%s, %s, %d pregões, filtro %s" % (
        entrada, tipo, ("%g" % p), ("alvo %gR" % A) if A else "sem alvo", P, filtro)


def combo_json(c):
    entrada, (tipo, p), A, P, filtro = c
    return {"entrada": entrada, "stop": "%s:%g" % (tipo, p), "alvo_r": A, "prazo": P, "filtro": filtro}


def ler_combo(a):
    tipo, p = a.stop.split(":")
    return (a.entrada, (tipo, float(p) if tipo == "atr" else int(p)), (float(a.alvo) if a.alvo not in ("0", "nenhum") else None),
            int(a.prazo), a.filtro)


# ---------------------------------------------------------------- seleção

def escolher(stats_setup, anos):
    melhor, mm = None, None
    for combo, por_ano in stats_setup.items():
        m = motor.metricas(motor.somar(por_ano, anos))
        if m["n"] < MIN_N or m["R_medio"] < MIN_R or (m["t"] or 0) < MIN_T:
            continue
        chave = (m["t"], m["R_medio"])
        if melhor is None or chave > (mm["t"], mm["R_medio"]):
            melhor, mm = combo, m
    return melhor, mm


def walk_forward(stats_setup, primeiro, ultimo):
    janelas, total = [], motor._vazio()
    ini = primeiro + TREINO_ANOS
    while ini <= ultimo:
        treino = range(ini - TREINO_ANOS, ini)
        teste = range(ini, min(ini + TESTE_ANOS, ultimo + 1))
        combo, mt = escolher(stats_setup, treino)
        x = motor.somar(stats_setup[combo], teste) if combo else motor._vazio()
        for j in range(7):
            total[j] += x[j]
        janelas.append({"treino": "%d-%d" % (treino[0], treino[-1]), "teste": "%d-%d" % (teste[0], teste[-1]),
                        "combo": combo, "treino_m": mt, "teste_m": motor.metricas(x)})
        ini += TESTE_ANOS
    return janelas, total


def anos_de(stats):
    anos = set()
    for st in stats.values():
        for por_ano in st.values():
            anos.update(por_ano)
    return min(anos), max(anos)


def treinar(stats, hoje_ano):
    primeiro, ultimo = anos_de(stats)
    primeiro = max(primeiro, 2001)             # 2000 só aquece os indicadores
    res = {}
    for setup, st in stats.items():
        janelas, oos = walk_forward(st, primeiro, ultimo)
        anos_oos = range(primeiro + TREINO_ANOS, ultimo + 1)
        base = motor.metricas(motor.somar(st.get(motor.PADRAO, {}), anos_oos))
        final, mf = escolher(st, range(ultimo - FINAL_ANOS + 1, ultimo + 1))
        m_oos = motor.metricas(oos)
        ativo = bool(final) and m_oos.get("n", 0) >= MIN_N and m_oos["R_medio"] > 0 and (m_oos["t"] or 0) >= OOS_MIN_T
        # retrospecto (escolher olhando tudo): mostra o tamanho do excesso de ajuste
        retro, mr = escolher(st, range(primeiro, ultimo + 1))
        res[setup] = {"lado": "compra" if motor.SETUPS[setup] > 0 else "venda", "ativo": ativo,
                      "final": final, "final_treino": mf, "oos": m_oos, "padrao_oos": base, "janelas": janelas,
                      "retrospecto": retro, "retrospecto_m": mr,
                      "retrospecto_oos_da_skill": None}
    return res, (primeiro, ultimo)


# ---------------------------------------------------------------- carteira fora da amostra

def carteira_oos(res):
    """Junta as operações fora da amostra dos setups ativos, com o combo de cada janela."""
    ops = []
    for setup, r in res.items():
        if not r["ativo"]:
            continue
        for j in r["janelas"]:
            if not j["combo"]:
                continue
            a0, a1 = (int(x) for x in j["teste"].split("-"))
            for op in motor.operacoes(setup, j["combo"]):
                if a0 <= motor._ano(op["entrada"]) <= a1:
                    ops.append((op["saida"], op["entrada"], setup, op["symbol"], op["R"], op["dias"]))
    ops.sort()
    por_ano, acum, pico, dd = {}, 0.0, 0.0, 0.0
    for saida, entrada, setup, sym, R, dias in ops:
        a = motor._ano(saida)
        x = por_ano.setdefault(a, [0, 0.0, 0])
        x[0] += 1
        x[1] += R
        x[2] += 1 if R > 0 else 0
        acum += R
        pico = max(pico, acum)
        dd = max(dd, pico - acum)
    return {"operacoes": len(ops), "R_total": round(acum, 1), "max_drawdown_R": round(dd, 1),
            "por_ano": {a: {"n": x[0], "R": round(x[1], 1), "acerto": round(x[2] / x[0], 3)} for a, x in sorted(por_ano.items())},
            "anos_positivos": sum(1 for x in por_ano.values() if x[1] > 0), "anos": len(por_ano)}


def ops_walk_forward(res, setups, usar_padrao=False):
    out = []
    for setup in setups:
        for j in res[setup]["janelas"]:
            combo = motor.PADRAO if usar_padrao else j["combo"]
            if not combo:
                continue
            a0, a1 = (int(x) for x in j["teste"].split("-"))
            for op in motor.operacoes(setup, combo):
                if a0 <= motor._ano(op["entrada"]) <= a1:
                    op["setup_lado"] = motor.SETUPS[setup]
                    out.append(op)
    return out


def referencias(ibov, cdi, inicio, fim):
    d0, d1 = datetime.date.fromisoformat(inicio).toordinal(), datetime.date.fromisoformat(fim).toordinal()
    anos = max((d1 - d0) / 365.25, 0.1)
    out = {}
    i0 = next((i for i, d in enumerate(ibov["d"]) if d >= d0), None)
    i1 = max((i for i, d in enumerate(ibov["d"]) if d <= d1), default=None)
    if i0 is not None and i1:
        pico, dd = 0.0, 0.0
        for c in ibov["c"][i0:i1 + 1]:
            pico = max(pico, c)
            dd = max(dd, (pico - c) / pico)
        out["ibovespa"] = {"cagr": round((ibov["c"][i1] / ibov["c"][i0]) ** (1 / anos) - 1, 4), "max_drawdown": round(dd, 4)}
    if cdi:
        f, d = 1.0, d0
        while d < d1:
            f *= 1 + carteira.taxa_cdi(cdi, d)
            d += 1
        out["cdi"] = {"cagr": round(f ** (1 / anos) - 1, 4), "max_drawdown": 0.0}
    return out


def avaliar_carteiras(res, ibov, cdi):
    ativos = [s for s, r in res.items() if r["ativo"]]
    antes = ops_walk_forward(res, list(res), usar_padrao=True)
    depois = ops_walk_forward(res, ativos)
    cen = {"skill_anterior": carteira.simular(antes, 5, 0.01, "aleatorio", cdi=cdi)}
    for risco, mp in CENARIOS:
        cen["treinada_%g%%_%d" % (100 * risco, mp)] = carteira.simular(depois, mp, risco, ORDEM_CARTEIRA, cdi=cdi)
    ref = cen["treinada_%g%%_%d" % (100 * CENARIOS[0][0], CENARIOS[0][1])]
    return cen, (referencias(ibov, cdi, ref["inicio"], ref["fim"]) if ref.get("operacoes") else {})


# ---------------------------------------------------------------- relatório

def fm(m, k, casas=2, pct=False):
    v = m.get(k) if m else None
    if v is None:
        return "-"
    return (b3lib.num(100 * v, 1) + "%") if pct else b3lib.num(v, casas)


def relatorio(res, periodo, cart, n_ativos, gerado, cenarios=None, refs=None):
    L = ["# Treino do swing trade — walk-forward", "",
         "Gerado em %s com %d ativos do IBRA, pregões de %d a %d (preços ajustados por proventos)." % (
             gerado, n_ativos, periodo[0], periodo[1]),
         "Treino de %d anos, teste nos %d seguintes, de %d em %d anos. Custos de 0,03%% por perna, 0,05%% de "
         "escorregamento nas ordens stop, aluguel de 2%% a.a. no vendido." % (TREINO_ANOS, TESTE_ANOS, TESTE_ANOS, TESTE_ANOS),
         "", "## Fora da amostra: padrão atual × treinado", "",
         "| setup | lado | padrão: n | padrão: acerto | padrão: R médio | treinado: n | treinado: acerto | treinado: R médio | treinado: t | fator de lucro | status |",
         "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for setup, r in sorted(res.items(), key=lambda kv: (kv[1]["lado"], -(kv[1]["oos"].get("R_medio") or -9))):
        b, o = r["padrao_oos"], r["oos"]
        L.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            setup, r["lado"], b.get("n", 0), fm(b, "acerto", pct=True), fm(b, "R_medio", 3), o.get("n", 0),
            fm(o, "acerto", pct=True), fm(o, "R_medio", 3), fm(o, "t"), fm(o, "fator_lucro"),
            "**ATIVO**" if r["ativo"] else "desativado"))
    L += ["", "## Parâmetros adotados (treino nos %d anos mais recentes)" % FINAL_ANOS, "",
          "| setup | parâmetros | n treino | acerto | R médio | t | pregões |", "|---|---|---:|---:|---:|---:|---:|"]
    for setup, r in sorted(res.items()):
        if r["ativo"]:
            m = r["final_treino"]
            L.append("| %s | %s | %s | %s | %s | %s | %s |" % (setup, combo_txt(r["final"]), m["n"], fm(m, "acerto", pct=True),
                                                               fm(m, "R_medio", 3), fm(m, "t"), fm(m, "pregoes_medios", 1)))
    L += ["", "## Carteira fora da amostra (setups ativos, combo escolhido em cada janela)", "",
          "%d operações, %s R no total, maior queda acumulada de %s R, %d de %d anos positivos." % (
              cart["operacoes"], b3lib.num(cart["R_total"], 1), b3lib.num(cart["max_drawdown_R"], 1),
              cart["anos_positivos"], cart["anos"]), "",
          "| ano | operações | acerto | R |", "|---|---:|---:|---:|"]
    for a, x in cart["por_ano"].items():
        L.append("| %s | %d | %s | %s |" % (a, x["n"], b3lib.num(100 * x["acerto"], 1) + "%", b3lib.num(x["R"], 1)))
    if cenarios:
        L += ["", "## Carteira realista fora da amostra", "",
              "Até 5 posições, um ativo por vez, sem alavancagem, risco fixo por operação sobre o patrimônio, "
              "sinais do mesmo pregão em ordem de %s%s." % (
                  "menor volatilidade (ATR %)" if ORDEM_CARTEIRA == "baixa_vol" else ORDEM_CARTEIRA,
                  "; o caixa livre rende CDI" if any(c.get("cdi_no_caixa") for c in cenarios.values()) else ""), "",
              "| cenário | operações | acerto | R médio | retorno ao ano | maior queda | anos positivos |",
              "|---|---:|---:|---:|---:|---:|---:|"]
        nomes = {"skill_anterior": "skill antes do treino (padrão, 10 setups, 1% de risco)"}
        for k, m in cenarios.items():
            if not m.get("operacoes"):
                continue
            L.append("| %s | %d | %s | %s | %s | %s | %d de %d |" % (
                nomes.get(k, k.replace("treinada_", "treinada, risco ").replace("_", ", máx. ") + " posições"),
                m["operacoes"], fm(m, "acerto", pct=True), fm(m, "R_medio", 3), fm(m, "cagr", pct=True),
                fm(m, "max_drawdown", pct=True), m["anos_positivos"], m["anos"]))
        for nome, r in (refs or {}).items():
            L.append("| %s | - | - | - | %s | %s | - |" % ("CDI" if nome == "cdi" else "Ibovespa (retorno total, com proventos)",
                                                         fm(r, "cagr", pct=True), fm(r, "max_drawdown", pct=True)))
    L += ["", "## Excesso de ajuste", "",
          "Escolhendo a melhor combinação olhando o período inteiro (retrospecto) o resultado parece melhor do que o "
          "walk-forward entrega. A diferença é o quanto a otimização se engana sozinha:", "",
          "| setup | retrospecto: R médio | fora da amostra: R médio |", "|---|---:|---:|"]
    for setup, r in sorted(res.items()):
        L.append("| %s | %s | %s |" % (setup, fm(r["retrospecto_m"], "R_medio", 3), fm(r["oos"], "R_medio", 3)))
    L += ["", "## Janelas do walk-forward", ""]
    for setup, r in sorted(res.items()):
        L.append("**%s** (%s)" % (setup, r["lado"]))
        L.append("")
        L.append("| treino | teste | combinação escolhida | teste: n | teste: R médio |")
        L.append("|---|---|---|---:|---:|")
        for j in r["janelas"]:
            L.append("| %s | %s | %s | %s | %s |" % (j["treino"], j["teste"], combo_txt(j["combo"]) if j["combo"] else "nenhuma passou",
                                                     j["teste_m"].get("n", 0), fm(j["teste_m"], "R_medio", 3)))
        L.append("")
    L += ["## Limites", "",
          "- Viés de sobrevivência: o universo é a carteira atual do IBRA; empresas que quebraram ou saíram do índice "
          "não estão nos dados, o que favorece o comprado.",
          "- R por operação, sem limite de posições simultâneas nem de caixa.",
          "- Dados gratuitos do Yahoo; o gatilho e o stop usam 0,05% além da máxima/mínima.",
          "- Resultado passado não garante resultado futuro. Não é recomendação de investimento.", ""]
    return "\n".join(L)


def gravar_parametros(res, periodo, n_ativos, gerado, cenarios=None, refs=None):
    doc = {"gerado_em": gerado, "periodo": "%d-%d" % periodo, "ativos": n_ativos,
           "metodo": "walk-forward %d+%d anos; final nos %d anos mais recentes" % (TREINO_ANOS, TESTE_ANOS, FINAL_ANOS),
           "custos": {"custo_por_perna": motor.CUSTO, "escorregamento_stop": motor.SLIP, "aluguel_aa": motor.ALUGUEL_AA},
           "carteira": {"ordem": ORDEM_CARTEIRA, "cenarios": {k: {kk: v for kk, v in m.items() if kk != "retorno_por_ano"}
                                                              for k, m in (cenarios or {}).items()},
                        "referencias": refs or {}},
           "setups": {}}
    for setup, r in sorted(res.items()):
        item = {"lado": r["lado"], "ativo": r["ativo"], "oos": r["oos"], "padrao_oos": r["padrao_oos"]}
        if r["final"]:
            item.update(combo_json(r["final"]))
            item["treino"] = r["final_treino"]
        doc["setups"][setup] = item
    b3lib.gravar_json(PARAMETROS, doc)
    return doc


# ---------------------------------------------------------------- comandos

def universo(a):
    if a.symbols:
        return [b3lib.sem_fracionario(s) for s in a.symbols.split(",") if s.strip()]
    path = a.universo or b3lib.caminho("universo.txt")
    if not os.path.exists(path):
        raise b3lib.B3Erro("não há %s: rode `scan.py universo` (b3-scanner) ou passe --symbols" % path)
    return [l.split("|")[0].strip() for l in open(path, encoding="utf-8") if l.strip() and not l.startswith("#")]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cmd", choices=["baixar", "testar", "otimizar"])
    p.add_argument("--symbols")
    p.add_argument("--universo")
    p.add_argument("--desde", default="2000-01-01")
    p.add_argument("--forcar", action="store_true")
    p.add_argument("--base", help="pasta com os históricos (padrão trader-b3/cache/historico)")
    p.add_argument("--setup")
    p.add_argument("--entrada", default="gatilho")
    p.add_argument("--stop", default="swing:5")
    p.add_argument("--alvo", default="2")
    p.add_argument("--prazo", default="15")
    p.add_argument("--filtro", default="nenhum", choices=motor.FILTROS)
    p.add_argument("--processos", type=int)
    p.add_argument("--write", action="store_true")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    try:
        syms = universo(a)
        if a.cmd == "baixar":
            ok, falhas = dados.baixar(syms + [dados.IBOV], datetime.date.fromisoformat(a.desde), a.forcar)
            try:
                dados.baixar_cdi(int(a.desde[:4]))
            except Exception as e:  # o CDI é só referência
                falhas["CDI"] = str(e)
            print("%d históricos em %s; falhas: %s" % (len(ok), dados.pasta(), ", ".join(falhas) or "nenhuma"))
            return 0 if ok else 1
        t0 = time.time()
        motor.DADOS, ibov = motor.carregar_universo(syms, a.base)
        if not motor.DADOS:
            raise b3lib.B3Erro("nenhum histórico carregado: rode `backtest.py baixar`")
        if a.cmd == "testar":
            if a.setup not in motor.SETUPS:
                raise b3lib.B3Erro("--setup é um de: %s" % ", ".join(motor.SETUPS))
            combo = ler_combo(a)
            if combo[1] not in motor.STOPS or combo[2] not in motor.ALVOS or combo[3] not in motor.PRAZOS:
                raise b3lib.B3Erro("combinação fora da grade (stops %s, alvos %s, prazos %s)" % (
                    motor.STOPS, motor.ALVOS, motor.PRAZOS))
            _, st = motor.rodar_setup(a.setup)
            por_ano = st.get(combo, {})
            anos = sorted(por_ano)
            tot = motor.metricas(motor.somar(por_ano, anos))
            if a.json:
                print(json.dumps({"combo": combo_json(combo), "total": tot,
                                  "por_ano": {y: motor.metricas(por_ano[y]) for y in anos}}, ensure_ascii=False, indent=2))
                return 0
            print("%s (%s) — %s" % (a.setup, "compra" if motor.SETUPS[a.setup] > 0 else "venda", combo_txt(combo)))
            print("  total: %d operações, acerto %s, R médio %s, fator de lucro %s, t %s, %s pregões em média" % (
                tot.get("n", 0), fm(tot, "acerto", pct=True), fm(tot, "R_medio", 3), fm(tot, "fator_lucro"), fm(tot, "t"),
                fm(tot, "pregoes_medios", 1)))
            for y in anos:
                m = motor.metricas(por_ano[y])
                print("  %d: %4d operações, acerto %6s, R médio %7s" % (y, m["n"], fm(m, "acerto", pct=True), fm(m, "R_medio", 3)))
            return 0
        stats = motor.rodar_todos(list(motor.SETUPS), a.processos)
        res, periodo = treinar(stats, datetime.date.today().year)
        cart = carteira_oos(res)
        try:
            cdi = dados.ler_cdi() if a.base else dados.baixar_cdi()
        except Exception:
            cdi = dados.ler_cdi()
        cenarios, refs = avaliar_carteiras(res, ibov, cdi)
        gerado = datetime.date.today().isoformat()
        texto = relatorio(res, periodo, cart, len(motor.DADOS), gerado, cenarios, refs)
        if a.write:
            gravar_parametros(res, periodo, len(motor.DADOS), gerado, cenarios, refs)
            os.makedirs(b3lib.caminho("backtest"), exist_ok=True)
            with open(b3lib.caminho("backtest", "relatorio.md"), "w", encoding="utf-8") as f:
                f.write(texto)
        if a.json:
            print(json.dumps({"setups": {k: {kk: (combo_json(vv) if kk in ("final", "retrospecto") and vv else vv)
                                              for kk, vv in v.items() if kk != "janelas"} for k, v in res.items()},
                              "carteira_oos": cart, "cenarios": cenarios, "referencias": refs},
                             ensure_ascii=False, indent=2, default=str))
        else:
            print(texto)
            print("(%.0f s)" % (time.time() - t0), file=sys.stderr)
        return 0
    except b3lib.B3Erro as e:
        print("backtest: %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
