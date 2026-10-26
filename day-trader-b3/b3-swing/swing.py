#!/usr/bin/env python3
"""Swing trade de ações na B3, comprado ou vendido, para b3-swing.
Só biblioteca padrão. Nunca envia ordem.

    python3 swing.py plano PETR4 --lado compra              # gatilho na máxima de ontem, stop swing:5, alvo 2R
    python3 swing.py plano B3SA3 --lado venda --stop atr:2 --target 3R --prazo 20 --write
    python3 swing.py plano VALE3 --lado compra --entrada fechamento --stop pct:4
    python3 swing.py simular                                # trader-b3/plano.json: 10.000 caminhos diários
    python3 swing.py simular --replays 20000 --seed 7 --json
    python3 swing.py acompanhar                             # posições abertas da carteira com plano
    python3 swing.py mover-stop PETR4 59.10                 # só a favor da posição

Plano (a partir do último pregão completo):
  entrada  gatilho (padrão): compra 1 centavo ACIMA da máxima do pregão de
           sinal, venda 1 centavo ABAIXO da mínima (ordem stop, só entra se o
           preço confirmar); fechamento: o último fechamento; ou um preço.
  stop     swing:N (padrão swing:5): compra abaixo da mínima dos últimos N
           pregões, venda acima da máxima; atr:K: K x ATR(14) diário;
           pct:X; preco:X. Arredondado no centavo para longe da entrada.
  alvo     2R (padrão), 1.5R... ou preco:X
  prazo    pregões máximos na posição (config swing_prazo_pregoes, 15)

Simulação diária (mesma ideia da máquina do tempo, em candles diários de 2
anos): cada dia sorteia um pregão passado como razões (abertura, máxima,
mínima, fechamento) / fechamento anterior. GAP conta: abertura além do stop
executa na abertura (perda maior que 1R); abertura além do alvo executa na
abertura. Dentro do dia o stop é testado antes do alvo. No vendido, o custo
de aluguel (aluguel_taxa_aa_pct) sai do R a cada pregão. Depois, a mesma regra
(setups do b3-scanner no lado do plano, gatilho, stop, alvo e prazo) roda em
cada pregão do histórico.

Vendido: exige "permitir_vendido": true no config para o b3-risco aprovar.
Na B3 a venda a descoberto precisa de aluguel (BTC) e garantia; quem está
vendido paga a taxa de aluguel e reembolsa os proventos ao doador.
Simulação não é previsão.
"""

import argparse
import datetime
import json
import math
import os
import random
import statistics
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "b3-comum"))
sys.path.insert(0, os.path.join(AQUI, "..", "b3-scanner"))
import b3lib  # noqa: E402
import scan  # noqa: E402

ATR_N = 14
MIN_DIAS = 120
EMPATE, FORTE = 0.05, 0.15
CENT = 0.01


# ---------------------------------------------------------------- dados diários

def pregoes_diarios(chart, agora_utc, cfg):
    """[{data, o, h, l, c, v}] de pregões completos (o de hoje só depois do call)."""
    agora = b3lib.para_brt(agora_utc)
    hoje = agora.date()
    s = b3lib.sessao(hoje, cfg)
    hoje_ok = s is None or agora.time() >= b3lib.mais_min(hoje, s[1], 5)
    out = {}
    for b in chart["bars"]:
        d = b3lib.ts_para_brt(b["t"]).date()
        if d > hoje or (d == hoje and not hoje_ok) or not b3lib.dia_de_pregao(d, cfg)[0]:
            continue
        out[d] = dict(b, data=d)
    return [out[d] for d in sorted(out)]


def atr(dias, n=ATR_N):
    trs = []
    for i in range(1, len(dias)):
        h, l, pc = dias[i]["h"], dias[i]["l"], dias[i - 1]["c"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    use = trs[-n:]
    return sum(use) / len(use) if use else None


def longe(x, s):
    """Arredonda um stop no centavo para longe da entrada: para baixo no comprado (s=+1)."""
    c = round(x * 100, 6)
    return (math.floor(c) if s > 0 else math.ceil(c)) / 100.0


def cent(x):
    return math.floor(x * 100 + 0.5 + 1e-9) / 100.0


# ---------------------------------------------------------------- plano

def ler_regra_stop(texto):
    t = str(texto).strip().lower()
    for pref in ("swing", "atr", "pct", "preco"):
        if t.startswith(pref + ":"):
            try:
                v = float(t.split(":", 1)[1].replace(",", "."))
            except ValueError:
                break
            if v <= 0 or (pref == "pct" and v >= 100) or (pref == "swing" and v != int(v)):
                break
            return pref, v
    raise b3lib.B3Erro("--stop é swing:N, atr:K, pct:X ou preco:X (recebi %r)" % texto)


def ler_alvo(texto):
    t = str(texto).strip().lower().replace(",", ".")
    try:
        if t.endswith("r"):
            r = float(t[:-1])
            if r > 0:
                return "r", r
        elif t.startswith("preco:"):
            return "preco", float(t[6:])
    except ValueError:
        pass
    raise b3lib.B3Erro("--target é 2R, 1.5R... ou preco:X (recebi %r)" % texto)


def stop_de(regra, v, dias, entrada, s):
    if regra == "swing":
        janela = dias[-int(v):]
        bruto = (min(d["l"] for d in janela) - CENT) if s > 0 else (max(d["h"] for d in janela) + CENT)
        nome = "%s dos últimos %d pregões %s 1 centavo" % ("mínima" if s > 0 else "máxima", int(v), "menos" if s > 0 else "mais")
    elif regra == "atr":
        a = atr(dias)
        if a is None:
            raise b3lib.B3Erro("poucos pregões para o ATR")
        bruto, nome = entrada - s * v * a, "%s x ATR(14) diário (%s)" % (b3lib.num(v), b3lib.reais(a))
    elif regra == "pct":
        bruto, nome = entrada * (1 - s * v / 100.0), "%s%% %s da entrada" % (b3lib.num(v), "abaixo" if s > 0 else "acima")
    else:
        bruto, nome = v, "seu preço"
    return longe(bruto, s), nome


def montar_plano(sym, lado, dias, cfg, entrada_txt="gatilho", stop_txt="swing:5", alvo_txt="2R", prazo=None,
                 hoje=None):
    s = b3lib.sinal_lado(lado)
    if len(dias) < scan.MIN_PREGOES:
        raise b3lib.B3Erro("só %d pregões completos de %s; preciso de %d" % (len(dias), sym, scan.MIN_PREGOES))
    ult = dias[-1]
    if entrada_txt == "gatilho":
        entrada = cent(ult["h"] + CENT) if s > 0 else cent(ult["l"] - CENT)
        nome_e = "gatilho: %s do pregão de %s %s 1 centavo" % ("máxima" if s > 0 else "mínima",
                                                              ult["data"].strftime("%d/%m"), "mais" if s > 0 else "menos")
        tipo = "stop"
    elif entrada_txt == "fechamento":
        entrada, nome_e, tipo = cent(ult["c"]), "último fechamento", "limitada"
    else:
        try:
            entrada = cent(float(str(entrada_txt).replace(",", ".")))
        except ValueError:
            raise b3lib.B3Erro("--entrada é gatilho, fechamento ou um preço")
        nome_e, tipo = "seu preço", "limitada"
    regra, v = ler_regra_stop(stop_txt)
    stop, nome_s = stop_de(regra, v, dias, entrada, s)
    risco = s * (entrada - stop)
    if risco <= 0:
        raise b3lib.B3Erro("o stop %s está do lado errado da entrada %s para %s" % (
            b3lib.reais(stop), b3lib.reais(entrada), "compra" if s > 0 else "venda"))
    if risco < entrada * 0.0005:
        raise b3lib.B3Erro("stop a menos de 0,05%% da entrada: apertado demais")
    ra, va = ler_alvo(alvo_txt)
    alvo = cent(entrada + s * va * risco) if ra == "r" else cent(va)
    rr = s * (alvo - entrada) / risco
    if rr <= 0:
        raise b3lib.B3Erro("o alvo %s está do lado errado da entrada" % b3lib.reais(alvo))
    prazo = int(prazo or cfg["swing_prazo_pregoes"])
    hoje = hoje or ult["data"]
    dia = b3lib.proximo_pregao(ult["data"], cfg) if hoje <= ult["data"] else b3lib.pregoes_a_frente(hoje, 0, cfg)
    tags, _ = scan.setups([d["c"] for d in dias])
    lado_tags = [t for t in tags if scan.LADO_SETUP[t] == lado]
    plano = {"symbol": sym, "estrategia": "swing", "lado": lado, "dia_sinal": ult["data"].isoformat(),
             "dia": dia.isoformat(), "tipo_entrada": tipo, "entrada": entrada, "entrada_regra": nome_e,
             "stop": stop, "stop_regra": nome_s, "alvo": alvo, "risco_por_acao": round(risco, 2),
             "risco_retorno": round(rr, 2), "prazo_pregoes": prazo,
             "prazo_ate": b3lib.pregoes_a_frente(dia, prazo - 1, cfg).isoformat(),
             "setups": lado_tags, "setup": lado_tags[0] if lado_tags else "manual",
             "ultimo_fechamento": round(ult["c"], 2), "zerar_ate": None,
             "regra": {"stop": regra, "stop_param": v, "alvo_r": round(rr, 2) if ra == "preco" else va,
                       "entrada": entrada_txt if entrada_txt in ("gatilho", "fechamento") else "preco"}}
    avisos = []
    if not lado_tags:
        avisos.append("nenhum setup de %s do scanner está ativo em %s agora" % (lado, sym))
    if abs(entrada / ult["c"] - 1) > 0.03:
        avisos.append("a entrada está %s do último fechamento" % b3lib.pct(100 * (entrada / ult["c"] - 1)))
    if rr < float(cfg["min_risco_retorno"]):
        avisos.append("risco/retorno %s abaixo do mínimo do config: b3-risco vai bloquear" % b3lib.num(rr))
    if lado == "venda":
        aluguel = entrada * float(cfg["aluguel_taxa_aa_pct"]) / 100.0 * prazo / 252.0
        plano["aluguel_estimado_por_acao"] = round(aluguel, 4)
        avisos.append("vendido: aluguel estimado de %s por ação em %d pregões (%s%% a.a.); proventos no período "
                      "são reembolsados ao doador" % (b3lib.reais(aluguel, 4), prazo, b3lib.num(cfg["aluguel_taxa_aa_pct"])))
        if not cfg["permitir_vendido"]:
            avisos.append("\"permitir_vendido\" está false no config: b3-risco vai bloquear a venda a descoberto")
    plano["avisos"] = avisos
    return plano


def descrever_plano(p):
    s = b3lib.sinal_lado(p["lado"])
    linhas = ["Plano de swing %s %s (sinal de %s, entrada a partir de %s):" % (
        "COMPRADO em" if s > 0 else "VENDIDO em", p["symbol"], p["dia_sinal"], p["dia"]),
        "  entrada %s (%s)" % (b3lib.reais(p["entrada"]), p["entrada_regra"]),
        "  stop    %s (%s) — risco de %s por ação" % (b3lib.reais(p["stop"]), p["stop_regra"], b3lib.reais(p["risco_por_acao"])),
        "  alvo    %s (%sR)" % (b3lib.reais(p["alvo"]), b3lib.num(p["risco_retorno"])),
        "  prazo   %d pregões, até %s" % (p["prazo_pregoes"], p["prazo_ate"]),
        "  setups ativos: %s" % (", ".join(p["setups"]) or "nenhum")]
    for a in p.get("avisos") or []:
        linhas.append("  aviso: " + a)
    linhas.append("  Um stop é um plano, não garantia: no swing o gap de abertura pode executar bem pior.")
    return "\n".join(linhas)


# ---------------------------------------------------------------- simulação diária

def montar_pool(dias):
    return [(d["o"] / p["c"], d["h"] / p["c"], d["l"] / p["c"], d["c"] / p["c"]) for p, d in zip(dias, dias[1:])]


def um_dia(o, h, l, c, stop, alvo, s):
    """(saída, motivo) do dia, ou (None, None). Gap primeiro, depois stop antes do alvo."""
    if s > 0:
        if o <= stop:
            return o, "stop"
        if o >= alvo:
            return o, "alvo"
        if l <= stop:
            return stop, "stop"
        if h >= alvo:
            return alvo, "alvo"
    else:
        if o >= stop:
            return o, "stop"
        if o <= alvo:
            return o, "alvo"
        if h >= stop:
            return stop, "stop"
        if l <= alvo:
            return alvo, "alvo"
    return None, None


def simular(pool, entrada, stop, alvo, lado, prazo, replays=10000, seed=19, aluguel_dia=0.0):
    s = b3lib.sinal_lado(lado)
    risco = s * (entrada - stop)
    rng = random.Random(seed)
    escolha = rng.choice
    res, Rs, dias_pos, finais = [], [], [], []
    for _ in range(replays):
        p, sai, mot, n = entrada, None, None, 0
        for n in range(1, prazo + 1):
            o, h, l, c = escolha(pool)
            sai, mot = um_dia(p * o, p * h, p * l, p * c, stop, alvo, s)
            if sai is not None:
                break
            p *= c
        if sai is None:
            sai, mot = p, "prazo"
        R = s * (sai - entrada) / risco - (aluguel_dia * n / risco if s < 0 else 0.0)
        res.append(mot)
        Rs.append(R)
        dias_pos.append(n)
        finais.append(sai)
    cont = {k: res.count(k) for k in ("alvo", "stop", "prazo")}
    srt = sorted(Rs)
    q = lambda x: srt[min(len(srt) - 1, int(x * len(srt)))]
    gap = sum(1 for r, m in zip(Rs, res) if m == "stop" and r < -1.05)
    return {"replays": replays, "seed": seed, "p_alvo": round(cont["alvo"] / float(replays), 4),
            "p_stop": round(cont["stop"] / float(replays), 4), "p_prazo": round(cont["prazo"] / float(replays), 4),
            "p_positivo": round(sum(1 for r in Rs if r > 0) / float(replays), 4),
            "R_medio": round(statistics.mean(Rs), 3), "R_p5": round(q(0.05), 2), "R_p95": round(q(0.95), 2),
            "p_gap_no_stop": round(gap / float(replays), 4), "dias_medios": round(statistics.mean(dias_pos), 1),
            "r_alvo": round(s * (alvo - entrada) / risco, 2)}


def historico(dias, plano, cfg):
    """A regra do plano em cada pregão passado: setup do mesmo lado no fechamento,
    gatilho no pregão seguinte, stop, alvo e prazo, sem operações sobrepostas."""
    lado, regra = plano["lado"], plano["regra"]
    s = b3lib.sinal_lado(lado)
    prazo = int(plano["prazo_pregoes"])
    exigidos = set(plano.get("setups") or [])
    ops, t = [], scan.MIN_PREGOES
    while t < len(dias) - 1:
        tags, _ = scan.setups([d["c"] for d in dias[:t + 1]])
        tags = [x for x in tags if scan.LADO_SETUP[x] == lado and (not exigidos or x in exigidos)]
        if not tags:
            t += 1
            continue
        sinal, prox = dias[t], dias[t + 1]
        if regra.get("entrada") == "gatilho":
            gat = sinal["h"] + CENT if s > 0 else sinal["l"] - CENT
            if not (prox["h"] >= gat if s > 0 else prox["l"] <= gat):
                t += 1
                continue
            e = max(prox["o"], gat) if s > 0 else min(prox["o"], gat)
        else:
            e = sinal["c"]
        try:
            st, _ = stop_de(regra["stop"], regra["stop_param"], dias[:t + 1], e, s)
        except b3lib.B3Erro:
            t += 1
            continue
        risco = s * (e - st)
        if risco <= 0:
            t += 1
            continue
        alvo = e + s * float(regra["alvo_r"]) * risco
        sai, mot, j = None, None, t + 1
        if (prox["l"] <= st) if s > 0 else (prox["h"] >= st):  # stop no próprio dia da entrada
            sai, mot = st, "stop"
        for j in range(t + 2, min(len(dias), t + 1 + prazo)):
            if sai is not None:
                break
            d = dias[j]
            sai, mot = um_dia(d["o"], d["h"], d["l"], d["c"], st, alvo, s)
        if sai is None:
            j = min(len(dias) - 1, t + prazo)
            sai, mot = dias[j]["c"], "prazo"
        ops.append({"sinal": sinal["data"].isoformat(), "entrada": round(e, 2), "stop": st, "alvo": round(alvo, 2),
                    "saida": round(sai, 2), "resultado": mot, "R": round(s * (sai - e) / risco, 2)})
        t = j + 1
    return {"operacoes": len(ops), "alvo": sum(1 for o in ops if o["resultado"] == "alvo"),
            "stop": sum(1 for o in ops if o["resultado"] == "stop"),
            "prazo": sum(1 for o in ops if o["resultado"] == "prazo"),
            "R_medio": round(statistics.mean(o["R"] for o in ops), 3) if ops else None,
            "exigiu_setups": sorted(exigidos) or "qualquer setup do lado", "detalhe": ops[-20:]}


def veredito(mc):
    pa, ps = mc["p_alvo"], mc["p_stop"]
    if pa + ps <= 0:
        return "Nenhum caminho tocou alvo ou stop no prazo: o preço no fim do prazo decide."
    r = mc["r_alvo"] or 1.0
    fatia, empate = pa / (pa + ps), 1.0 / (1.0 + r)
    d = fatia - empate
    cab = ("Perto do empate" if abs(d) < EMPATE else ("Pende para o alvo" if d > 0 else "Pende para o stop")
           if abs(d) < FORTE else ("Forte para o alvo" if d > 0 else "Forte para o stop"))
    return "%s: com alvo de %sR o alvo precisa vir primeiro em %s dos caminhos que tocaram um lado; veio em %s." % (
        cab, b3lib.num(r), b3lib.pct(100 * empate, 0), b3lib.pct(100 * fatia, 0))


def rodar_simulacao(chart, plano, cfg, agora_utc, replays=10000, seed=19):
    dias = pregoes_diarios(chart, agora_utc, cfg)
    dias = [d for d in dias if d["data"].isoformat() <= plano["dia_sinal"]]
    if len(dias) < MIN_DIAS:
        raise b3lib.B3Erro("só %d pregões diários; preciso de %d para a simulação" % (len(dias), MIN_DIAS))
    aluguel_dia = plano["entrada"] * float(cfg["aluguel_taxa_aa_pct"]) / 100.0 / 252.0
    mc = simular(montar_pool(dias), plano["entrada"], plano["stop"], plano["alvo"], plano["lado"],
                 int(plano["prazo_pregoes"]), replays, seed, aluguel_dia)
    return {"plano": plano, "pregoes_usados": len(dias), "de": dias[0]["data"].isoformat(),
            "ate": dias[-1]["data"].isoformat(), "simulacao": mc, "veredito": veredito(mc),
            "historico": historico(dias, plano, cfg),
            "aviso": "Simulação com %d pregões do próprio ativo; não é previsão." % len(dias)}


def sinal_num(x):
    return ("+" if x >= 0 else "") + b3lib.num(x, 3)


def relatorio_sim(doc):
    p, mc, h = doc["plano"], doc["simulacao"], doc["historico"]
    linhas = ["Simulação de swing %s %s: entrada %s, stop %s, alvo %s, prazo %d pregões" % (
        "comprado" if p["lado"] == "compra" else "vendido", p["symbol"], b3lib.reais(p["entrada"]),
        b3lib.reais(p["stop"]), b3lib.reais(p["alvo"]), p["prazo_pregoes"]),
        "  %d caminhos (semente %d) sorteados de %d pregões (%s a %s)" % (
            mc["replays"], mc["seed"], doc["pregoes_usados"], doc["de"], doc["ate"]),
        "  alvo primeiro %s | stop primeiro %s | venceu o prazo %s | terminou positivo %s" % (
            b3lib.pct(100 * mc["p_alvo"], 1), b3lib.pct(100 * mc["p_stop"], 1), b3lib.pct(100 * mc["p_prazo"], 1),
            b3lib.pct(100 * mc["p_positivo"], 1)),
        "  R médio %s (5%% a 95%%: %s a %s) | stop por gap pior que 1R em %s | %s pregões em média" % (
            sinal_num(mc["R_medio"]), b3lib.num(mc["R_p5"]), b3lib.num(mc["R_p95"]), b3lib.pct(100 * mc["p_gap_no_stop"], 1),
            b3lib.num(mc["dias_medios"], 1)),
        "  " + doc["veredito"],
        "  Histórico da regra: %d operações — alvo %d, stop %d, prazo %d, R médio %s (setups: %s)" % (
            h["operacoes"], h["alvo"], h["stop"], h["prazo"], "-" if h["R_medio"] is None else sinal_num(h["R_medio"]),
            h["exigiu_setups"] if isinstance(h["exigiu_setups"], str) else ", ".join(h["exigiu_setups"])),
        "  " + doc["aviso"]]
    return "\n".join(linhas)


# ---------------------------------------------------------------- acompanhamento

def planos_path():
    return b3lib.caminho("swing", "planos.json")


def ler_planos():
    return b3lib.ler_json(planos_path(), {}) or {}


def avaliar_posicao(sym, pos, plano, dias, hoje, cfg):
    qtd = int(pos["qtd"])
    s = 1 if qtd > 0 else -1
    medio = abs(pos["custo"]) / abs(qtd) if qtd else 0.0
    desde = [d for d in dias if d["data"].isoformat() >= plano["dia"]]
    preco = dias[-1]["c"] if dias else None
    stop, alvo = plano["stop"], plano["alvo"]
    risco = s * (medio - stop) if medio else plano["risco_por_acao"]
    tocou = None
    for d in desde:
        saida, mot = um_dia(d["o"], d["h"], d["l"], d["c"], stop, alvo, s)
        if saida is not None:
            tocou = {"motivo": mot, "dia": d["data"].isoformat(), "preco": round(saida, 2)}
            break
    em_posicao = b3lib.pregoes_entre(datetime.date.fromisoformat(plano["dia"]), hoje, cfg) + 1
    r_atual = s * (preco - medio) / risco if preco and risco > 0 else None
    acoes, sugestao = [], None
    if tocou:
        acoes.append("%s tocado em %s (%s): se a OCO não executou, zere (ticket.py zerar --symbol %s)" % (
            tocou["motivo"], tocou["dia"], b3lib.reais(tocou["preco"]), sym))
    if hoje.isoformat() >= plano["prazo_ate"]:
        acoes.append("prazo de %d pregões vence em %s: zere hoje" % (plano["prazo_pregoes"], plano["prazo_ate"]))
    if r_atual is not None and not tocou:
        if r_atual >= 2 and len(dias) >= 3:
            ult3 = dias[-3:]
            sugestao = longe(min(d["l"] for d in ult3) - CENT, s) if s > 0 else longe(max(d["h"] for d in ult3) + CENT, s)
        elif r_atual >= 1:
            sugestao = round(medio, 2)
        if sugestao is not None and s * (sugestao - stop) > 0:
            acoes.append("a favor %sR: considere mover o stop para %s (swing.py mover-stop %s %s)" % (
                b3lib.num(r_atual), b3lib.reais(sugestao), sym, "%.2f" % sugestao))
    out = {"symbol": sym, "lado": "comprado" if s > 0 else "vendido", "qtd": qtd, "preco_medio": round(medio, 2),
           "preco": preco, "resultado": round(s * (preco - medio) * abs(qtd), 2) if preco else None,
           "R": round(r_atual, 2) if r_atual is not None else None, "stop": stop, "alvo": alvo,
           "pregoes_em_posicao": em_posicao, "prazo_ate": plano["prazo_ate"], "tocou": tocou, "acoes": acoes}
    if s < 0:
        out["aluguel_acumulado"] = round(medio * abs(qtd) * float(cfg["aluguel_taxa_aa_pct"]) / 100.0 * em_posicao / 252.0, 2)
    return out


def cmd_acompanhar(a, cfg, agora):
    cart = b3lib.ler_json(b3lib.caminho("carteira.json"), {}) or {}
    planos = ler_planos()
    hoje = b3lib.para_brt(agora).date()
    res, sem_plano = [], []
    for sym, pos in sorted((cart.get("posicoes") or {}).items()):
        if not pos.get("qtd"):
            continue
        plano = planos.get(sym)
        if not plano:
            sem_plano.append(sym)
            continue
        dias = pregoes_diarios(b3lib.obter_chart(sym, "3mo", "1d", a.offline), agora, cfg)
        res.append(avaliar_posicao(sym, pos, plano, dias, hoje, cfg))
    if a.json:
        print(json.dumps({"posicoes": res, "sem_plano": sem_plano}, ensure_ascii=False, indent=2))
        return 0 if res else 1
    if not res:
        print("Nenhuma posição de swing aberta com plano em trader-b3/swing/planos.json.")
    for r in res:
        print("%s %s %d a %s — último %s, resultado %s (%sR), %d pregões, prazo até %s%s" % (
            r["symbol"], r["lado"], abs(r["qtd"]), b3lib.reais(r["preco_medio"]), b3lib.reais(r["preco"]),
            b3lib.reais(r["resultado"]), b3lib.num(r["R"]), r["pregoes_em_posicao"], r["prazo_ate"],
            ", aluguel ≈ %s" % b3lib.reais(r["aluguel_acumulado"]) if "aluguel_acumulado" in r else ""))
        print("  stop %s | alvo %s" % (b3lib.reais(r["stop"]), b3lib.reais(r["alvo"])))
        for x in r["acoes"] or ["nada a fazer: dentro do plano"]:
            print("  -> " + x)
    if sem_plano:
        print("Posições sem plano de swing: %s (crie com swing.py plano ... --write)" % ", ".join(sem_plano))
    return 0


def cmd_mover_stop(a, cfg):
    sym = b3lib.sem_fracionario(a.symbol)
    planos = ler_planos()
    p = planos.get(sym)
    if not p:
        raise b3lib.B3Erro("não há plano de swing para %s" % sym)
    novo = float(str(a.preco).replace(",", "."))
    s = b3lib.sinal_lado(p["lado"])
    if s * (novo - p["stop"]) <= 0:
        raise b3lib.B3Erro("o stop só anda a favor da posição: %s -> %s %s" % (
            b3lib.reais(p["stop"]), b3lib.reais(novo), "afrouxa o risco" if s * (novo - p["stop"]) < 0 else "não muda"))
    if s * (p["alvo"] - novo) <= 0:
        raise b3lib.B3Erro("o novo stop passaria do alvo %s" % b3lib.reais(p["alvo"]))
    p.setdefault("historico_stop", []).append({"de": p["stop"], "para": novo,
                                                "em": b3lib.para_brt(b3lib.ler_agora(a.now)).strftime("%Y-%m-%d %H:%M")})
    p["stop"] = novo
    b3lib.gravar_json(planos_path(), planos)
    print("Stop de %s movido para %s. Ajuste também a OCO na corretora." % (sym, b3lib.reais(novo)))
    return 0


# ---------------------------------------------------------------- main

def main(argv=None):
    pa = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    pa.add_argument("cmd", choices=["plano", "simular", "acompanhar", "mover-stop"])
    pa.add_argument("symbol", nargs="?")
    pa.add_argument("preco", nargs="?")
    pa.add_argument("--lado", choices=["compra", "venda"])
    pa.add_argument("--entrada", default="gatilho")
    pa.add_argument("--stop", default="swing:5")
    pa.add_argument("--target", default="2R")
    pa.add_argument("--prazo", type=int)
    pa.add_argument("--replays", type=int, default=10000)
    pa.add_argument("--seed", type=int, default=19)
    pa.add_argument("--now")
    pa.add_argument("--offline")
    pa.add_argument("--config")
    pa.add_argument("--write", action="store_true")
    pa.add_argument("--json", action="store_true")
    a = pa.parse_args(argv)
    try:
        cfg = b3lib.ler_config(a.config)
        agora = b3lib.ler_agora(a.now)
        if a.cmd == "plano":
            if not a.symbol or not a.lado:
                raise b3lib.B3Erro("uso: swing.py plano PETR4 --lado compra|venda")
            sym = b3lib.sem_fracionario(a.symbol)
            dias = pregoes_diarios(b3lib.obter_chart(sym, "1y", "1d", a.offline), agora, cfg)
            p = montar_plano(sym, a.lado, dias, cfg, a.entrada, a.stop, a.target, a.prazo, b3lib.para_brt(agora).date())
            if a.write:
                b3lib.gravar_json(b3lib.caminho("plano.json"), p)
                planos = ler_planos()
                planos[sym] = p
                b3lib.gravar_json(planos_path(), planos)
            print(json.dumps(p, ensure_ascii=False, indent=2) if a.json else descrever_plano(p))
            if a.write and not a.json:
                print("Gravado em trader-b3/plano.json e trader-b3/swing/planos.json. Próximos passos: "
                      "swing.py simular, /b3-orcamento e /b3-risco.")
            return 0
        if a.cmd == "simular":
            plano = b3lib.ler_json(b3lib.caminho("plano.json"), obrigatorio=True, o_que="o plano (swing.py plano --write)")
            if plano.get("estrategia") != "swing":
                raise b3lib.B3Erro("o plano.json não é de swing; para day trade use /b3-maquina-do-tempo")
            doc = rodar_simulacao(b3lib.obter_chart(plano["symbol"], "2y", "1d", a.offline), plano, cfg, agora,
                                  a.replays, a.seed)
            if a.write:
                b3lib.gravar_json(b3lib.caminho("swing", "simulacao.json"), doc)
            print(json.dumps(doc, ensure_ascii=False, indent=2) if a.json else relatorio_sim(doc))
            return 0
        if a.cmd == "acompanhar":
            return cmd_acompanhar(a, cfg, agora)
        if not a.symbol or not a.preco:
            raise b3lib.B3Erro("uso: swing.py mover-stop PETR4 59.10")
        return cmd_mover_stop(a, cfg)
    except b3lib.B3Erro as e:
        print("swing: %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
