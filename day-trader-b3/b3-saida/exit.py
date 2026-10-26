#!/usr/bin/env python3
"""Planejador de saída para b3-saida: define o stop e o alvo ANTES da entrada.
Só biblioteca padrão. Só compra. Nunca envia ordem.

    python3 exit.py plan                                   # de trader-b3/entrada.json: stop no meio da faixa, alvo 2R
    python3 exit.py plan --stop or-low --target 1.5R --write
    python3 exit.py plan --symbol PETR4 --entry 58.57 --or-high 58.53 --or-low 58.01
    python3 exit.py plan --stop atr:1.5 --offline PETR4.json
    python3 exit.py plan --symbol VALE3 --entry 62.10 --setup nivel --stop pct:1
    python3 exit.py show

Stops (arredondados PARA BAIXO no centavo, longe da entrada):
  or-mid     meio da faixa de abertura (padrão para entrada orb)
  or-low     mínima da faixa
  preco:X    seu preço
  pct:X      X% abaixo da entrada
  atr:K      K vezes o ATR de 14 candles abaixo da entrada (precisa dos candles)
Alvos (arredondados no centavo): 2R (padrão), 1R, 1.5R... = entrada + R x risco,
ou preco:X.

Recusa, com o motivo: stop na entrada ou acima, alvo na entrada ou abaixo,
risco menor que 0,05% do preço (dentro do spread), entrada que não disparou.
Zerar até: "zerar_min_antes_fechamento" (padrão 10 min antes do fim da
negociação: 16h45 ou 17h45). Muitas corretoras zeram o day trade sozinhas
antes do call de fechamento: confira o horário da sua.

Um stop é um plano, não uma garantia: gap ou mercado rápido podem executar pior.
"""

import argparse
import datetime
import json
import os
import re
import sys
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP, InvalidOperation

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "b3-comum"))
import b3lib  # noqa: E402

CENT = Decimal("0.01")
MIN_RISCO_PCT = Decimal("0.05")
ATR_N = 14
AVISO = "Um stop é um plano, não uma garantia: gap ou mercado rápido podem executar pior."


def D(x, o_que="um número"):
    try:
        return Decimal(str(x).replace(",", "."))
    except (InvalidOperation, ValueError):
        raise b3lib.B3Erro("esperava %s, recebi %r" % (o_que, x))


def cent(x):
    return D(x).quantize(CENT, rounding=ROUND_HALF_UP)


def cent_baixo(x):
    return D(x).quantize(CENT, rounding=ROUND_FLOOR)


def ler_stop(texto):
    t = str(texto).strip().lower()
    if t in ("or-mid", "or_mid", "meio"):
        return "or_mid", None
    if t in ("or-low", "or_low", "minima"):
        return "or_low", None
    m = re.match(r"^(preco|price|pct|atr):\s*([0-9]+[.,]?[0-9]*)$", t)
    if not m:
        raise b3lib.B3Erro("--stop é or-mid, or-low, preco:X, pct:X ou atr:K (recebi %r)" % texto)
    tipo = {"price": "preco"}.get(m.group(1), m.group(1))
    v = D(m.group(2))
    if v <= 0 or (tipo == "pct" and v >= 100):
        raise b3lib.B3Erro("--stop %s precisa de um valor válido" % tipo)
    return tipo, v


def ler_alvo(texto):
    t = str(texto).strip()
    m = re.match(r"^([0-9]*[.,]?[0-9]+)\s*[Rr]$", t)
    if m:
        r = D(m.group(1))
        if r <= 0:
            raise b3lib.B3Erro("--target precisa de um múltiplo de R acima de 0")
        return "r", r
    m = re.match(r"^(preco|price):\s*([0-9]+[.,]?[0-9]*)$", t.lower())
    if m:
        return "preco", D(m.group(2))
    raise b3lib.B3Erro("--target é 2R, 1R, 1.5R... ou preco:X (recebi %r)" % texto)


def calcular(entrada, regra_stop, param_stop, regra_alvo, param_alvo, or_high=None, or_low=None, atr=None):
    """Stop, alvo e risco em centavos exatos. Levanta B3Erro com o motivo."""
    e = cent(entrada)
    if e <= 0:
        raise b3lib.B3Erro("o preço de entrada precisa ser maior que zero")
    if regra_stop in ("or_mid", "or_low"):
        if or_high is None or or_low is None:
            raise b3lib.B3Erro("o stop %s precisa da faixa de abertura (--or-high e --or-low)" % regra_stop)
        oh, ol = cent(or_high), cent(or_low)
        if oh <= ol:
            raise b3lib.B3Erro("a máxima da faixa precisa ser maior que a mínima")
        bruto, nome = ((oh + ol) / 2, "meio da faixa de abertura") if regra_stop == "or_mid" else (ol, "mínima da faixa")
    elif regra_stop == "preco":
        bruto, nome = param_stop, "seu preço"
    elif regra_stop == "pct":
        bruto, nome = e * (1 - param_stop / 100), "%s%% abaixo da entrada" % b3lib.num(param_stop)
    elif regra_stop == "atr":
        if atr is None:
            raise b3lib.B3Erro("o stop atr precisa dos candles do dia (--offline ou Yahoo)")
        bruto, nome = e - param_stop * D(round(atr, 6)), "%s x ATR(%d) abaixo da entrada" % (b3lib.num(param_stop), ATR_N)
    else:
        raise b3lib.B3Erro("regra de stop desconhecida")
    stop = cent_baixo(bruto)
    if stop >= e:
        raise b3lib.B3Erro("o stop %s (%s) está na entrada %s ou acima: numa compra o stop fica abaixo"
                           % (b3lib.reais(stop), nome, b3lib.reais(e)))
    if stop <= 0:
        raise b3lib.B3Erro("o stop ficou em %s: escolha um stop acima de zero" % b3lib.reais(stop))
    risco = e - stop
    piso = e * MIN_RISCO_PCT / 100
    if risco < piso:
        raise b3lib.B3Erro("o stop está %s abaixo da entrada, menos de 0,05%% do preço: apertado demais para "
                           "sobreviver ao spread. Afaste o stop." % b3lib.reais(risco))
    if regra_alvo == "r":
        alvo, r = cent(e + param_alvo * risco), param_alvo
    else:
        alvo = cent(param_alvo)
        r = ((alvo - e) / risco).quantize(CENT, rounding=ROUND_HALF_UP)
    if alvo <= e:
        raise b3lib.B3Erro("o alvo %s está na entrada ou abaixo: numa compra o alvo fica acima" % b3lib.reais(alvo))
    rr = ((alvo - e) / risco).quantize(CENT, rounding=ROUND_HALF_UP)
    return {"entrada": e, "stop": stop, "stop_regra": nome, "alvo": alvo, "alvo_r": r,
            "risco": risco, "risco_retorno": rr}


def atr_de(candles, n=ATR_N):
    trs, ant = [], None
    for b in candles:
        tr = b["h"] - b["l"]
        if ant is not None:
            tr = max(tr, abs(b["h"] - ant), abs(b["l"] - ant))
        trs.append(tr)
        ant = b["c"]
    use = trs[-n:]
    return (sum(use) / len(use), len(use)) if use else (None, 0)


def montar(a, cfg):
    ent = None
    if not a.entry:
        ent = b3lib.ler_json(b3lib.caminho("entrada.json"), obrigatorio=True, o_que="a entrada (rode /b3-entrada)")
        if ent.get("status") != "disparou":
            raise b3lib.B3Erro("a entrada de %s não disparou (status %s); use --entry para planejar mesmo assim"
                               % (ent.get("symbol"), ent.get("status")))
    sym = b3lib.normalizar(a.symbol or (ent or {}).get("symbol"))
    if not b3lib.valido(sym):
        raise b3lib.B3Erro("ativo inválido: %r" % sym)
    setup = a.setup or (ent or {}).get("setup") or "orb"
    entrada = a.entry or ent["sinal"]["preco"]
    faixa = (ent or {}).get("faixa") or {}
    oh = a.or_high if a.or_high is not None else faixa.get("max")
    ol = a.or_low if a.or_low is not None else faixa.get("min")
    dia = datetime.date.fromisoformat((ent or {}).get("dia") or a.date or
                                      b3lib.para_brt(b3lib.ler_agora(a.now)).date().isoformat())
    hora = a.entry_time or ((ent or {}).get("sinal") or {}).get("hora")
    stop_txt = a.stop or ("or-mid" if setup == "orb" else None)
    if not stop_txt:
        raise b3lib.B3Erro("um setup nivel não tem stop padrão: informe --stop")
    regra_stop, param_stop = ler_stop(stop_txt)
    regra_alvo, param_alvo = ler_alvo(a.target)
    atr = None
    if regra_stop == "atr":
        chart = b3lib.obter_chart(sym, "1d", "5m", a.offline)
        cs = b3lib.candles_do_dia(chart, dia, 300, cfg)
        lim = ((ent or {}).get("sinal") or {}).get("slot")
        velas = [cs[k] for k in sorted(cs) if lim is None or k <= lim]
        atr, _ = atr_de(velas)
    r = calcular(entrada, regra_stop, param_stop, regra_alvo, param_alvo, oh, ol, atr)
    jan = b3lib.janela_entradas(dia, cfg)
    if jan is None:
        raise b3lib.B3Erro("não há pregão em %s" % dia.isoformat())
    plano = {"symbol": sym, "dia": dia.isoformat(), "setup": setup, "lado": "compra", "hora_entrada": hora,
             "entrada": float(r["entrada"]), "stop": float(r["stop"]), "alvo": float(r["alvo"]),
             "risco_por_acao": float(r["risco"]), "risco_retorno": float(r["risco_retorno"]),
             "stop_regra": r["stop_regra"], "regra": {"stop": regra_stop, "stop_param": float(param_stop or 0),
                                                       "alvo_r": float(r["alvo_r"]),
                                                       "or_minutes": (ent or {}).get("or_minutes", 15)},
             "faixa": {"max": oh, "min": ol} if oh is not None else None, "zerar_ate": b3lib.hm(jan[2])}
    if float(r["risco_retorno"]) < float(cfg["min_risco_retorno"]):
        plano["aviso"] = "risco/retorno %s abaixo do mínimo %s do config: b3-risco vai bloquear" % (
            b3lib.num(r["risco_retorno"]), b3lib.num(cfg["min_risco_retorno"]))
    return plano


def descrever(p):
    linhas = ["Plano %s (%s) em %s:" % (p["symbol"], p["setup"], p["dia"]),
              "  entrada %s%s" % (b3lib.reais(p["entrada"]), " às " + p["hora_entrada"] if p.get("hora_entrada") else ""),
              "  stop    %s (%s) — risco de %s por ação" % (b3lib.reais(p["stop"]), p["stop_regra"],
                                                          b3lib.reais(p["risco_por_acao"])),
              "  alvo    %s (%sR)" % (b3lib.reais(p["alvo"]), b3lib.num(p["risco_retorno"])),
              "  zerar até %s, ganhando ou perdendo" % p["zerar_ate"]]
    if p.get("aviso"):
        linhas.append("  aviso: " + p["aviso"])
    linhas.append("  " + AVISO)
    return "\n".join(linhas)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cmd", choices=["plan", "show"])
    p.add_argument("--symbol")
    p.add_argument("--entry", type=float)
    p.add_argument("--entry-time")
    p.add_argument("--date")
    p.add_argument("--setup")
    p.add_argument("--or-high", type=float)
    p.add_argument("--or-low", type=float)
    p.add_argument("--stop")
    p.add_argument("--target", default="2R")
    p.add_argument("--offline")
    p.add_argument("--now")
    p.add_argument("--config")
    p.add_argument("--write", action="store_true")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    try:
        if a.cmd == "show":
            plano = b3lib.ler_json(b3lib.caminho("plano.json"), obrigatorio=True, o_que="o plano")
        else:
            plano = montar(a, b3lib.ler_config(a.config))
            if a.write:
                b3lib.gravar_json(b3lib.caminho("plano.json"), plano)
        print(json.dumps(plano, ensure_ascii=False, indent=2) if a.json else descrever(plano))
        if a.cmd == "plan" and a.write and not a.json:
            print("Gravado em %s. Próximos passos: /b3-maquina-do-tempo e /b3-orcamento." % b3lib.caminho("plano.json"))
        return 0
    except b3lib.B3Erro as e:
        print("saida: %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
