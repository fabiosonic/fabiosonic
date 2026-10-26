#!/usr/bin/env python3
"""Máquina do tempo para b3-maquina-do-tempo. Só biblioteca padrão.

Reproduz um day trade planejado antes de você arriscar um real: 10.000
simulações do resto do pregão a partir da entrada, mais a mesma regra aplicada
em cada pregão passado dos dados.

    python3 timemachine.py run                         # trader-b3/plano.json, 10.000 simulações, semente 19
    python3 timemachine.py run --write                 # também grava trader-b3/maquina.json
    python3 timemachine.py run --ate 16:30 --seed 7 --replays 20000
    python3 timemachine.py run --symbol PETR4 --date 2026-10-23 --entry 58.57 \\
        --stop 58.27 --target 59.17 --entry-time 10:25

Como funciona (mesmo algoritmo do day-trader-skill):
  1. Lê 60 dias de candles de 5 min do Yahoo (sufixo .SA) e guarda só os
     pregões COMPLETOS antes da data do plano.
  2. Pool: para cada posição de candle do dia, cada candle passado vira
     razões (abertura, máxima, mínima, fechamento) / fechamento anterior.
  3. Cada simulação parte do preço de entrada e anda pelo resto do pregão:
     para o candle i sorteia uma posição j = i ± janela (padrão 2) e um
     candle passado dessa posição, escalado ao preço atual. O stop é testado
     antes do alvo em cada candle: um candle que toca os dois conta como stop.
  4. Resultados: "alvo", "stop" ou "nenhum" (ainda aberta no horário --ate,
     padrão o horário de zerar do plano). R = R do alvo, -1 no stop, ou
     (preço no --ate - entrada) / risco.
  5. Histórico: a regra do plano (rompimento da faixa, mesmo stop e mesmo R)
     reaplicada em cada pregão passado.

B3: o pregão muda de duração com o horário de verão americano (até 16h55 ou
até 17h55). Quando há menos de 20 pregões com a mesma duração do dia do
plano, os de outra duração entram com posição proporcional e a saída avisa.

Veredito: compara a fatia do alvo entre as simulações que tocaram um lado,
alvo / (alvo + stop), com a fatia de empate 1 / (1 + R): diferença menor que 5
pontos = "perto do empate"; 5 a 15 = "pende para o alvo/stop"; 15 ou mais =
"forte para o alvo/stop".

Uma simulação feita com os últimos 60 dias do próprio ativo não é previsão:
resultados, notícias e leilões podem fazer o que os últimos 60 dias não fizeram.
"""

import argparse
import datetime
import json
import math
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "b3-comum"))
import b3lib  # noqa: E402

PASSO = 300
MIN_PREGOES = 20
EMPATE = 0.05
FORTE = 0.15
MUITOS_NENHUM = 0.40


def sessoes_completas(chart, antes, cfg):
    """[(data, [candles])] completos antes de `antes`, e os incompletos deixados de fora."""
    completas, curtas = [], []
    for d, cs in sorted(b3lib.candles_por_sessao(chart, cfg, PASSO).items()):
        if d >= antes:
            continue
        n = b3lib.n_candles(d, PASSO, cfg)
        if len(cs) == n and [b["slot"] for b in cs] == list(range(n)):
            completas.append((d, cs))
        else:
            curtas.append({"dia": d.isoformat(), "candles": len(cs), "esperado": n})
    return completas, curtas


def montar_pool(sessoes, n):
    """pool[i] = candles passados da posição i como razões ao fechamento anterior.
    Sessões de outra duração entram na posição proporcional."""
    pool = [[] for _ in range(n)]
    for _, D in sessoes:
        L = len(D)
        for i in range(1, n):
            j = i if L == n else max(1, min(L - 1, int(round(i * (L - 1) / float(n - 1)))))
            pc = D[j - 1]["c"]
            pool[i].append((D[j]["o"] / pc, D[j]["h"] / pc, D[j]["l"] / pc, D[j]["c"] / pc))
    return pool


def q(a, x):
    return a[min(len(a) - 1, int(x * len(a)))]


def simular(pool, entrada, stop, alvo, k, ultimo, replays=10000, seed=19, janela=2):
    n = len(pool)
    risco = entrada - stop
    r_alvo = round((alvo - entrada) / risco, 4)
    rng = random.Random(seed)
    escolha = rng.choice

    def pos(i):
        return i if janela == 0 else min(n - 1, max(1, i + rng.randint(-janela, janela)))

    resultados, finais = [], []
    for _ in range(replays):
        p, res = entrada, None
        for i in range(k + 1, ultimo + 1):
            o, h, l, c = escolha(pool[pos(i)])
            if res is None:
                if p * l <= stop:
                    res = "stop"
                elif p * h >= alvo:
                    res = "alvo"
            p *= c
        resultados.append(res or "nenhum")
        finais.append(p)
    cont = {x: resultados.count(x) for x in ("alvo", "stop", "nenhum")}
    verde = sum(1 for r, p in zip(resultados, finais) if r == "alvo" or (r == "nenhum" and p > entrada))
    Rs = [r_alvo if r == "alvo" else -1.0 if r == "stop" else (p - entrada) / risco for r, p in zip(resultados, finais)]
    srt = sorted(finais)
    return {"replays": replays, "seed": seed, "janela": janela, "candles_restantes": ultimo - k,
            "p_alvo": round(cont["alvo"] / float(replays), 4), "p_stop": round(cont["stop"] / float(replays), 4),
            "p_nenhum": round(cont["nenhum"] / float(replays), 4), "p_verde": round(verde / float(replays), 4),
            "mediana": round(q(srt, 0.5), 2), "p5": round(q(srt, 0.05), 2), "p95": round(q(srt, 0.95), 2),
            "R_medio": round(statistics.mean(Rs), 3), "r_alvo": r_alvo}


def stop_da_regra(regra, oh, ol, e):
    if regra["stop"] == "or_mid":
        bruto = (oh + ol) / 2
    elif regra["stop"] == "or_low":
        bruto = ol
    elif regra["stop"] == "pct":
        bruto = e * (1 - regra["stop_param"] / 100.0)
    else:
        return None
    return math.floor(round(bruto * 100, 4)) / 100.0


def historico(sessoes, regra, ultimo_hhmm, cfg):
    """A regra do plano em cada pregão passado: entrada no primeiro fechamento
    acima da faixa, stop antes do alvo, senão o fechamento no horário --ate."""
    n_or = int(regra.get("or_minutes") or 15) // 5
    ops = []
    for d, D in sessoes:
        abre = b3lib.sessao(d, cfg)[0]
        ult = min(len(D) - 1, int((datetime.datetime.combine(d, ultimo_hhmm) -
                                   datetime.datetime.combine(d, abre)).total_seconds()) // PASSO - 1)
        oh, ol = max(b["h"] for b in D[:n_or]), min(b["l"] for b in D[:n_or])
        k = next((i for i in range(n_or, ult + 1) if D[i]["c"] > oh), None)
        if k is None:
            continue
        e = round(D[k]["c"], 2)
        s = stop_da_regra(regra, oh, ol, e)
        if s is None or e - s <= 0:
            continue
        t = round(e + regra["alvo_r"] * (e - s), 2)
        res = None
        for b in D[k + 1:ult + 1]:
            if b["l"] <= s:
                res = "stop"
                break
            if b["h"] >= t:
                res = "alvo"
                break
        R = regra["alvo_r"] if res == "alvo" else -1.0 if res == "stop" else (D[ult]["c"] - e) / (e - s)
        ops.append({"dia": d.isoformat(), "hora": D[k]["fim"].strftime("%H:%M"), "entrada": e, "stop": s,
                    "alvo": t, "resultado": res or "nenhum", "R": round(R, 2)})
    return {"pregoes": len(sessoes), "disparos": len(ops),
            "alvo": sum(1 for x in ops if x["resultado"] == "alvo"),
            "stop": sum(1 for x in ops if x["resultado"] == "stop"),
            "nenhum": sum(1 for x in ops if x["resultado"] == "nenhum"),
            "R_medio": round(statistics.mean(x["R"] for x in ops), 3) if ops else None, "operacoes": ops}


def veredito(mc):
    pa, ps = mc["p_alvo"], mc["p_stop"]
    if pa + ps <= 0:
        return "Nenhuma simulação tocou alvo ou stop: o preço no horário final decide todas."
    r = mc["r_alvo"] or 1.0
    fatia, empate = pa / (pa + ps), 1.0 / (1.0 + r)
    d = fatia - empate
    if abs(d) < EMPATE:
        cab = "Perto do empate"
    elif abs(d) < FORTE:
        cab = "Pende para o alvo" if d > 0 else "Pende para o stop"
    else:
        cab = "Forte para o alvo" if d > 0 else "Forte para o stop"
    return ("%s: com alvo de %sR o alvo precisa vir primeiro em %s das simulações que tocaram um lado; "
            "veio em %s (alvo %s, stop %s)." % (cab, b3lib.num(r), b3lib.pct(100 * empate, 0),
                                                 b3lib.pct(100 * fatia, 0), b3lib.pct(100 * pa, 1),
                                                 b3lib.pct(100 * ps, 1)))


def carregar_plano(a):
    if a.entry:
        if not (a.symbol and a.stop and a.target and a.entry_time and a.date):
            raise b3lib.B3Erro("sem plano.json informe --symbol, --date, --entry, --stop, --target e --entry-time")
        e, s, t = a.entry, a.stop, a.target
        return {"symbol": b3lib.normalizar(a.symbol), "dia": a.date, "entrada": e, "stop": s, "alvo": t,
                "hora_entrada": a.entry_time, "zerar_ate": None,
                "regra": {"stop": "or_mid", "stop_param": 0, "alvo_r": round((t - e) / (e - s), 2), "or_minutes": 15}}
    return b3lib.ler_json(b3lib.caminho("plano.json"), obrigatorio=True, o_que="o plano (rode /b3-saida)")


def rodar(chart, plano, cfg, replays=10000, seed=19, janela=2, ate=None):
    dia = datetime.date.fromisoformat(plano["dia"])
    s = b3lib.sessao(dia, cfg)
    if s is None:
        raise b3lib.B3Erro("não há pregão em %s" % plano["dia"])
    abre, fecha = s
    n = b3lib.n_candles(dia, PASSO, cfg)
    hora = b3lib.ler_hhmm(plano.get("hora_entrada") or "", "hora da entrada")
    minutos = lambda t: int((datetime.datetime.combine(dia, t) - datetime.datetime.combine(dia, abre)).total_seconds()) // 60
    k = minutos(hora) // 5 - 1          # o candle cujo fechamento é a entrada
    ate_t = b3lib.ler_hhmm(ate, "--ate") if ate else (b3lib.ler_hhmm(plano["zerar_ate"]) if plano.get("zerar_ate") else fecha)
    ultimo = min(n - 1, minutos(ate_t) // 5 - 1)
    if not 0 <= k < ultimo:
        raise b3lib.B3Erro("a entrada às %s não deixa candles até %s" % (b3lib.hm(hora), b3lib.hm(ate_t)))
    todas, curtas = sessoes_completas(chart, dia, cfg)
    mesmas = [x for x in todas if len(x[1]) == n]
    usadas = mesmas if len(mesmas) >= MIN_PREGOES else todas
    if len(usadas) < MIN_PREGOES:
        raise b3lib.B3Erro("só há %d pregões completos antes de %s; preciso de %d" % (len(usadas), plano["dia"], MIN_PREGOES))
    pool = montar_pool(usadas, n)
    mc = simular(pool, plano["entrada"], plano["stop"], plano["alvo"], k, ultimo, replays, seed, janela)
    doc = {"plano": plano, "ate": b3lib.hm(ate_t), "pregoes_usados": len(usadas), "pregoes_fora": curtas,
           "proporcional": usadas is todas and len(mesmas) != len(todas),
           "simulacao": mc, "veredito": veredito(mc),
           "historico": historico(usadas, plano["regra"], ate_t, cfg) if plano.get("regra") else None,
           "aviso": "Simulação com os últimos pregões do próprio ativo; não é previsão."}
    notas = []
    if mc["p_nenhum"] > MUITOS_NENHUM:
        notas.append("%s das simulações não tocaram nenhum lado até %s." % (b3lib.pct(100 * mc["p_nenhum"], 1),
                                                                          b3lib.hm(ate_t)))
    if doc["proporcional"]:
        notas.append("menos de %d pregões com a mesma duração de hoje (%d candles): usei pregões de outra "
                     "duração com posição proporcional" % (MIN_PREGOES, n))
    doc["notas"] = notas
    return doc


def sinal(x):
    return ("+" if x >= 0 else "") + b3lib.num(x, 3)


def relatorio(doc):
    p, mc, h = doc["plano"], doc["simulacao"], doc["historico"]
    linhas = ["Máquina do tempo — %s em %s: entrada %s às %s, stop %s, alvo %s, até %s" % (
        p["symbol"], p["dia"], b3lib.reais(p["entrada"]), p["hora_entrada"], b3lib.reais(p["stop"]),
        b3lib.reais(p["alvo"]), doc["ate"]),
        "  %d simulações (semente %d) com %d pregões completos" % (mc["replays"], mc["seed"], doc["pregoes_usados"]),
        "  alvo primeiro %s | stop primeiro %s | nenhum %s | terminou no verde %s" % (
            b3lib.pct(100 * mc["p_alvo"], 1), b3lib.pct(100 * mc["p_stop"], 1), b3lib.pct(100 * mc["p_nenhum"], 1),
            b3lib.pct(100 * mc["p_verde"], 1)),
        "  preço no fim: mediana %s (5%% a 95%%: %s a %s) | R médio %s" % (
            b3lib.reais(mc["mediana"]), b3lib.reais(mc["p5"]), b3lib.reais(mc["p95"]), sinal(mc["R_medio"])),
        "  " + doc["veredito"]]
    for n_ in doc["notas"]:
        linhas.append("  nota: " + n_)
    if h:
        linhas.append("  Histórico da regra: %d disparos em %d pregões — alvo %d, stop %d, nenhum %d, R médio %s" % (
            h["disparos"], h["pregoes"], h["alvo"], h["stop"], h["nenhum"],
            "-" if h["R_medio"] is None else sinal(h["R_medio"])))
    linhas.append("  " + doc["aviso"])
    return "\n".join(linhas)


def main(argv=None):
    pa = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    pa.add_argument("cmd", choices=["run"])
    pa.add_argument("--symbol")
    pa.add_argument("--date")
    pa.add_argument("--entry", type=float)
    pa.add_argument("--stop", type=float)
    pa.add_argument("--target", type=float)
    pa.add_argument("--entry-time")
    pa.add_argument("--ate")
    pa.add_argument("--replays", type=int, default=10000)
    pa.add_argument("--seed", type=int, default=19)
    pa.add_argument("--janela", type=int, default=2)
    pa.add_argument("--offline")
    pa.add_argument("--config")
    pa.add_argument("--write", action="store_true")
    pa.add_argument("--json", action="store_true")
    a = pa.parse_args(argv)
    try:
        cfg = b3lib.ler_config(a.config)
        plano = carregar_plano(a)
        chart = b3lib.obter_chart(plano["symbol"], "60d", "5m", a.offline)
        doc = rodar(chart, plano, cfg, a.replays, a.seed, a.janela, a.ate)
        if a.write:
            b3lib.gravar_json(b3lib.caminho("maquina.json"), doc)
        print(json.dumps(doc, ensure_ascii=False, indent=2) if a.json else relatorio(doc))
        return 0
    except b3lib.B3Erro as e:
        print("maquina-do-tempo: %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
