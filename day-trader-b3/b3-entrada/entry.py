#!/usr/bin/env python3
"""Cronômetro de entrada para b3-entrada: acompanha um setup candle a candle e
diz a hora de entrar. Só biblioteca padrão. Só compra (posição comprada).
Nunca envia ordem.

    python3 entry.py check PETR4                       # rompimento da faixa de abertura, 5 min
    python3 entry.py check PETR4 --setup nivel --nivel 59.40
    python3 entry.py check PETR4 --now "2026-10-23 10:40" --offline PETR4.json
    python3 entry.py check PETR4 --min-volume-x 1.5 --write
    python3 entry.py watch PETR4 --every 30            # uma linha por candle fechado
    python3 entry.py watchlist                         # todos os hits de trader-b3/watchlist.json

Setups:
  orb    faixa = máxima e mínima dos primeiros --or-minutes (padrão 15). Sinal no
         primeiro candle COMPLETO depois da faixa que FECHA acima da máxima.
  nivel  primeiro candle completo que fecha acima de --nivel (ex.: a máxima de
         20 pregões do scanner).
  --min-volume-x X  o candle do sinal precisa de X vezes o volume médio dos
         candles da faixa (o candle das 10h00 traz o leilão de abertura).

Status: disparou, aguardando, expirado (sem sinal até o limite de novas
entradas, padrão 40 min antes do fim da negociação) ou sem-dados.
Horário do sinal = fechamento do candle; preço = o fechamento.

trader-b3/config.json: "sem_entradas_antes" (10:15) e
"sem_entradas_ultimos_min" (40). Horários de Brasília.
Código de saída: 0 = disparou, 1 = qualquer outra coisa.
"""

import argparse
import datetime
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "b3-comum"))
import b3lib  # noqa: E402

INTERVALOS = {"1m": 60, "5m": 300}
ESPERA_DADO = 60  # segundos que um candle fechado pode esperar o Yahoo atualizar


def avaliar(chart, agora_utc, setup="orb", or_minutes=15, interval="5m", nivel=None,
            min_volume_x=None, cfg=None):
    """Função pura: status do setup em agora_utc a partir dos candles do dia."""
    cfg = cfg or dict(b3lib.DEFAULTS)
    if interval not in INTERVALOS:
        raise b3lib.B3Erro("--interval é 5m ou 1m")
    passo = INTERVALOS[interval]
    if or_minutes <= 0 or (or_minutes * 60) % passo:
        raise b3lib.B3Erro("--or-minutes precisa ser múltiplo do intervalo")
    if setup not in ("orb", "nivel"):
        raise b3lib.B3Erro("--setup é orb ou nivel")
    if setup == "nivel" and nivel is None:
        raise b3lib.B3Erro("--setup nivel precisa de --nivel PREÇO")
    n_or = or_minutes * 60 // passo
    local = b3lib.para_brt(agora_utc)
    dia = local.date()
    res = {"symbol": chart["symbol"], "setup": setup, "lado": "compra", "dia": dia.isoformat(),
           "interval": interval, "or_minutes": or_minutes, "agora": local.strftime("%Y-%m-%d %H:%M:%S"),
           "status": "aguardando", "motivo": "", "faixa": None, "nivel": None, "sinal": None,
           "ultimo": None, "aviso_calendario": b3lib.aviso_calendario(dia)}
    ok, motivo = b3lib.dia_de_pregao(dia, cfg)
    if not ok:
        res.update(status="sem-dados", motivo="não há pregão hoje (%s); próximo pregão %s" % (
            motivo, b3lib.proximo_pregao(dia, cfg).strftime("%d/%m/%Y")))
        return res
    abre, fecha = b3lib.sessao(dia, cfg)
    antes, depois, zerar = b3lib.janela_entradas(dia, cfg)
    abre_dt = datetime.datetime.combine(dia, abre)
    fecha_dt = datetime.datetime.combine(dia, fecha)
    antes_dt = datetime.datetime.combine(dia, antes)
    corte = datetime.datetime.combine(dia, depois)
    fim_faixa = abre_dt + datetime.timedelta(minutes=or_minutes)
    res.update(abertura=b3lib.hm(abre), fim_negociacao=b3lib.hm(fecha),
               sem_entradas_antes=b3lib.hm(antes), sem_entradas_depois=b3lib.hm(depois), zerar_ate=b3lib.hm(zerar))

    dt = chart.get("data_time")
    todos = b3lib.candles_do_dia(chart, dia, passo, cfg)
    agora_ts = b3lib.brt_para_ts(local)
    topo = max(todos) if todos else -1
    candles = []
    for slot in sorted(todos):
        b = todos[slot]
        fim_ts = b["t"] + passo
        if fim_ts <= agora_ts and (dt is None or dt >= fim_ts or slot < topo or agora_ts >= fim_ts + ESPERA_DADO):
            candles.append(b)
    res["candles_fechados"] = len(candles)

    if local < abre_dt:
        res.update(motivo="o pregão abre às %s" % b3lib.hm(abre))
        return res
    faixa = [b for b in candles if b["slot"] < n_or]
    vol_med = (sum(b["v"] for b in faixa) / float(len(faixa))) if faixa else None
    if faixa:
        res["faixa"] = {"max": round(max(b["h"] for b in faixa), 2), "min": round(min(b["l"] for b in faixa), 2),
                        "minutos": or_minutes, "completa": local >= fim_faixa,
                        "volume_medio": int(round(vol_med))}
    if setup == "orb":
        if local < fim_faixa:
            res.update(motivo="%d de %d candles da faixa fechados; a faixa fecha às %s" % (
                len(faixa), n_or, fim_faixa.strftime("%H:%M")))
            return res
        if not faixa:
            res.update(status="sem-dados", motivo="o Yahoo não mandou os candles da faixa de abertura")
            return res
        alvo = max(b["h"] for b in faixa)
    else:
        alvo = float(nivel)
    res["nivel"] = round(alvo, 2)

    primeiro = n_or if setup == "orb" else 0
    sinal = fraco = None
    for b in candles:
        if b["slot"] < primeiro or b["fim"] < antes_dt or b["fim"] > corte:
            continue
        if b["c"] > alvo:
            vx = (b["v"] / vol_med) if vol_med else None
            if min_volume_x and (vx is None or vx < min_volume_x):
                fraco = fraco or b
                continue
            sinal = b
            break
    ultimo = candles[-1] if candles else None
    if ultimo:
        res["ultimo"] = {"candle": b3lib.hm(ultimo["local"]), "fechamento": round(ultimo["c"], 2),
                         "vs_nivel_pct": round(100.0 * (ultimo["c"] / alvo - 1), 2)}
    if sinal:
        vx = (sinal["v"] / vol_med) if vol_med else None
        res.update(status="disparou", motivo="o candle das %s fechou acima %s" % (
            b3lib.hm(sinal["local"]), "da máxima da faixa" if setup == "orb" else "do nível"))
        res["sinal"] = {"hora": sinal["fim"].strftime("%H:%M"), "candle": b3lib.hm(sinal["local"]),
                        "slot": sinal["slot"], "preco": round(sinal["c"], 2), "volume": sinal["v"],
                        "volume_x": round(vx, 2) if vx else None,
                        "pct_acima": round(100.0 * (sinal["c"] / alvo - 1), 2)}
        return res
    if not candles:
        res.update(status="sem-dados", motivo="o Yahoo ainda não mandou candles de hoje")
        return res
    if local >= corte:
        res.update(status="expirado", motivo="nenhum fechamento acima de %s até %s, o limite para novas entradas"
                   % (b3lib.reais(alvo), corte.strftime("%H:%M")))
        return res
    if fraco is not None:
        res["motivo"] = "o candle das %s fechou acima, mas com volume abaixo de %.2fx a média da faixa" % (
            b3lib.hm(fraco["local"]), min_volume_x)
    elif ultimo["c"] > alvo and ultimo["fim"] < antes_dt:
        res["motivo"] = "fechou acima, mas antes de %s (sem_entradas_antes)" % b3lib.hm(antes)
    else:
        res["motivo"] = "último fechamento %s, %s %s do nível %s" % (
            b3lib.reais(ultimo["c"]), b3lib.reais(abs(alvo - ultimo["c"])),
            "abaixo" if ultimo["c"] <= alvo else "acima", b3lib.reais(alvo))
    return res


def descrever(res):
    linhas = ["%s %s em %s (%s): %s" % (res["symbol"], "ORB" if res["setup"] == "orb" else "nível",
                                       res["dia"], res["agora"][11:16], res["status"].upper())]
    if res.get("faixa"):
        f = res["faixa"]
        linhas.append("  faixa de %d min: %s a %s%s" % (f["minutos"], b3lib.reais(f["min"]), b3lib.reais(f["max"]),
                                                       "" if f["completa"] else " (formando)"))
    if res.get("sinal"):
        s = res["sinal"]
        linhas.append("  sinal às %s a %s (%s acima do nível%s)" % (
            s["hora"], b3lib.reais(s["preco"]), b3lib.pct(s["pct_acima"]),
            ", volume %sx a média da faixa" % b3lib.num(s["volume_x"]) if s.get("volume_x") else ""))
    if res.get("motivo"):
        linhas.append("  " + res["motivo"])
    if res.get("zerar_ate"):
        linhas.append("  novas entradas de %s a %s; zerar até %s" % (
            res["sem_entradas_antes"], res["sem_entradas_depois"], res["zerar_ate"]))
    if res.get("aviso_calendario"):
        linhas.append("  aviso: " + res["aviso_calendario"])
    return "\n".join(linhas)


def opts(a, cfg):
    return dict(setup=a.setup, or_minutes=a.or_minutes, interval=a.interval,
                nivel=a.nivel, min_volume_x=a.min_volume_x, cfg=cfg)


def carregar(a, sym):
    return b3lib.obter_chart(sym, "1d", a.interval, a.offline)


def gravar(a, res):
    if a.write and res["status"] == "disparou":
        b3lib.gravar_json(b3lib.caminho("entrada.json"), res)
        return True
    return False


def cmd_check(a, cfg):
    sym = b3lib.normalizar(a.symbol)
    res = avaliar(carregar(a, sym), b3lib.ler_agora(a.now), **opts(a, cfg))
    gravou = gravar(a, res)
    print(json.dumps(res, ensure_ascii=False, indent=2) if a.json else descrever(res))
    if gravou and not a.json:
        print("Gravado em %s. Próximo passo: /b3-saida." % b3lib.caminho("entrada.json"))
    return 0 if res["status"] == "disparou" else 1


def cmd_watch(a, cfg):
    sym = b3lib.normalizar(a.symbol)
    simulado = bool(a.now or a.offline)
    agora = b3lib.ler_agora(a.now)
    visto = -1
    chart = carregar(a, sym) if simulado else None
    while True:
        if not simulado:
            chart = carregar(a, sym)
            agora = b3lib.agora_utc()
        res = avaliar(chart, agora, **opts(a, cfg))
        if res["candles_fechados"] != visto or res["status"] != "aguardando":
            visto = res["candles_fechados"]
            print("%s %s %s" % (res["agora"][11:16], res["status"], res.get("motivo", "")), flush=True)
        if res["status"] != "aguardando":
            gravar(a, res)
            return 0 if res["status"] == "disparou" else 1
        if simulado:
            agora += datetime.timedelta(seconds=300)
            if b3lib.para_brt(agora).date().isoformat() != res["dia"]:
                return 1
        else:
            time.sleep(max(5, a.every))


def cmd_watchlist(a, cfg):
    doc = b3lib.ler_json(b3lib.caminho("watchlist.json"), obrigatorio=True, o_que="a watchlist do scanner")
    agora = b3lib.ler_agora(a.now)
    algum = False
    for h in doc.get("hits") or []:
        try:
            res = avaliar(carregar(a, h["symbol"]), agora, **opts(a, cfg))
        except b3lib.B3Erro as e:
            print("%s: %s" % (h["symbol"], e))
            continue
        algum = algum or res["status"] == "disparou"
        print(descrever(res))
    return 0 if algum else 1


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cmd", choices=["check", "watch", "watchlist"])
    p.add_argument("symbol", nargs="?")
    p.add_argument("--setup", default="orb")
    p.add_argument("--nivel", type=float)
    p.add_argument("--or-minutes", type=int, default=15)
    p.add_argument("--interval", default="5m")
    p.add_argument("--min-volume-x", type=float)
    p.add_argument("--every", type=int, default=30)
    p.add_argument("--now")
    p.add_argument("--offline")
    p.add_argument("--config")
    p.add_argument("--write", action="store_true")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    try:
        cfg = b3lib.ler_config(a.config)
        if a.cmd != "watchlist" and not a.symbol:
            raise b3lib.B3Erro("informe o ativo, ex.: entry.py %s PETR4" % a.cmd)
        return {"check": cmd_check, "watch": cmd_watch, "watchlist": cmd_watchlist}[a.cmd](a, cfg)
    except b3lib.B3Erro as e:
        print("entrada: %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
