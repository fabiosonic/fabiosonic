#!/usr/bin/env python3
"""Alertas de preço para b3-alertas. Só biblioteca padrão.

    python3 alerts.py clock                          # pregão aberto? horários de hoje
    python3 alerts.py quote PETR4,VALE3              # cotações -> trader-b3/precos.json
    python3 alerts.py add PETR4 acima 59.17
    python3 alerts.py add PETR4 abaixo 58.27
    python3 alerts.py add PETR4 zerar                # toca no horário de zerar do dia
    python3 alerts.py from-plan                      # stop, alvo e zerar do trader-b3/plano.json
    python3 alerts.py check                          # confere uma vez; cada alerta toca uma vez por dia
    python3 alerts.py list
    python3 alerts.py reset

Tipos: acima X, abaixo X (preço), abertura (toca quando o pregão abre),
zerar (toca no horário de zerar). Os alertas ficam em trader-b3/alertas.json.
Para acompanhar, rode `check` periodicamente (por exemplo com /loop 1m).

Dados: último preço do Yahoo (sufixo .SA), gratuito e com possível atraso de
até 15 minutos. Confirme na sua corretora antes de agir.
Código de saída de check: 0 se algum alerta tocou, 1 se nenhum.
"""

import argparse
import datetime
import json
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "b3-comum"))
import b3lib  # noqa: E402

TIPOS = ("acima", "abaixo", "abertura", "zerar")


def status_mercado(agora_utc, cfg):
    agora = b3lib.para_brt(agora_utc)
    hoje = agora.date()
    s = b3lib.sessao(hoje, cfg)
    if s is None:
        motivo = b3lib.dia_de_pregao(hoje, cfg)[1]
        return {"aberto": False, "fase": "sem pregão", "motivo": motivo,
                "proximo": b3lib.proximo_pregao(hoje, cfg).isoformat()}
    abre, fecha = s
    antes, depois, zerar = b3lib.janela_entradas(hoje, cfg)
    t = agora.time()
    call_fim = b3lib.mais_min(hoje, fecha, 5)
    if t < b3lib.mais_min(hoje, abre, -15):
        fase = "antes da abertura"
    elif t < abre:
        fase = "pré-abertura"
    elif t < fecha:
        fase = "negociação"
    elif t < call_fim:
        fase = "call de fechamento"
    else:
        fase = "encerrado"
    return {"aberto": abre <= t < fecha, "fase": fase, "abertura": b3lib.hm(abre), "fim_negociacao": b3lib.hm(fecha),
            "call_ate": b3lib.hm(call_fim), "entradas": "%s a %s" % (b3lib.hm(antes), b3lib.hm(depois)),
            "zerar_ate": b3lib.hm(zerar), "agora": agora.strftime("%H:%M"), "aviso": b3lib.aviso_calendario(hoje)}


def cotacoes(syms, offline=None):
    out, falhas = {}, {}
    for s in syms:
        try:
            ch = b3lib.obter_chart(s, "1d", "1m", offline)
            meta = ch["meta"]
            preco = meta.get("regularMarketPrice") or (ch["bars"][-1]["c"] if ch["bars"] else None)
            t = meta.get("regularMarketTime") or (ch["bars"][-1]["t"] if ch["bars"] else None)
            if preco is None:
                raise b3lib.B3Erro("sem preço")
            out[s] = {"preco": round(float(preco), 2),
                      "hora_utc": (b3lib.EPOCH + datetime.timedelta(seconds=int(t))).strftime("%Y-%m-%dT%H:%M:%S") if t else None}
        except b3lib.B3Erro as e:
            falhas[s] = str(e)
    return out, falhas


def gravar_precos(novos):
    doc = b3lib.ler_json(b3lib.caminho("precos.json"), {"precos": {}}) or {"precos": {}}
    doc.setdefault("precos", {}).update(novos)
    doc["fonte"] = "Yahoo Finance (pode ter atraso)"
    b3lib.gravar_json(b3lib.caminho("precos.json"), doc)


def ler_alertas():
    return b3lib.ler_json(b3lib.caminho("alertas.json"), {"alertas": []}) or {"alertas": []}


def gravar_alertas(doc):
    b3lib.gravar_json(b3lib.caminho("alertas.json"), doc)


def novo(sym, tipo, preco=None, nota=""):
    if tipo not in TIPOS:
        raise b3lib.B3Erro("tipo é acima, abaixo, abertura ou zerar")
    if tipo in ("acima", "abaixo") and (preco is None or preco <= 0):
        raise b3lib.B3Erro("alerta %s precisa de um preço" % tipo)
    return {"id": uuid.uuid4().hex[:8], "symbol": b3lib.sem_fracionario(sym), "tipo": tipo,
            "preco": preco, "nota": nota, "tocou_em": None}


def avaliar(alertas, precos, st, agora_utc):
    agora = b3lib.para_brt(agora_utc)
    hoje = agora.date().isoformat()
    tocaram = []
    for al in alertas:
        if (al.get("tocou_em") or "")[:10] == hoje:
            continue
        p = (precos.get(al["symbol"]) or {}).get("preco")
        bate = False
        if al["tipo"] == "acima" and p is not None:
            bate = p >= al["preco"]
        elif al["tipo"] == "abaixo" and p is not None:
            bate = p <= al["preco"]
        elif al["tipo"] == "abertura":
            bate = st["aberto"]
        elif al["tipo"] == "zerar" and st.get("zerar_ate"):
            bate = st["aberto"] and agora.strftime("%H:%M") >= st["zerar_ate"]
        if bate:
            al["tocou_em"] = agora.strftime("%Y-%m-%d %H:%M")
            tocaram.append(dict(al, preco_atual=p))
    return tocaram


def frase(al):
    if al["tipo"] in ("acima", "abaixo"):
        return "%s %s de %s (agora %s)%s" % (al["symbol"], al["tipo"], b3lib.reais(al["preco"]),
                                             b3lib.reais(al.get("preco_atual")), " — " + al["nota"] if al.get("nota") else "")
    return "%s: %s%s" % (al["symbol"], "o pregão abriu" if al["tipo"] == "abertura" else "hora de zerar o day trade",
                         " — " + al["nota"] if al.get("nota") else "")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cmd", choices=["clock", "quote", "add", "from-plan", "check", "list", "reset"])
    p.add_argument("args", nargs="*")
    p.add_argument("--nota", default="")
    p.add_argument("--now")
    p.add_argument("--offline")
    p.add_argument("--config")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    try:
        cfg = b3lib.ler_config(a.config)
        agora = b3lib.ler_agora(a.now)
        if a.cmd == "clock":
            st = status_mercado(agora, cfg)
            print(json.dumps(st, ensure_ascii=False, indent=2) if a.json else
                  "B3 %s (%s)%s" % (st["fase"], st.get("agora") or st.get("motivo"),
                                     "" if "abertura" not in st else ": negociação %s a %s, call até %s, entradas %s, zerar até %s"
                                     % (st["abertura"], st["fim_negociacao"], st["call_ate"], st["entradas"], st["zerar_ate"])))
            return 0 if st["aberto"] else 1
        if a.cmd == "quote":
            syms = [b3lib.normalizar(s) for s in ",".join(a.args).split(",") if s.strip()]
            if not syms:
                raise b3lib.B3Erro("informe os ativos, ex.: quote PETR4,VALE3")
            q, falhas = cotacoes(syms, a.offline)
            gravar_precos(q)
            for s, v in q.items():
                print("%-7s %s" % (s, b3lib.reais(v["preco"])))
            for s, e in falhas.items():
                print("%-7s sem preço: %s" % (s, e))
            return 0 if q else 1
        doc = ler_alertas()
        if a.cmd == "add":
            if len(a.args) < 2:
                raise b3lib.B3Erro("uso: add PETR4 acima 59.17 | add PETR4 zerar")
            preco = float(a.args[2].replace(",", ".")) if len(a.args) > 2 else None
            al = novo(a.args[0], a.args[1].lower(), preco, a.nota)
            doc["alertas"].append(al)
            gravar_alertas(doc)
            print("Alerta %s criado: %s %s %s" % (al["id"], al["symbol"], al["tipo"], b3lib.reais(preco) if preco else ""))
            return 0
        if a.cmd == "from-plan":
            pl = b3lib.ler_json(b3lib.caminho("plano.json"), obrigatorio=True, o_que="o plano (rode /b3-saida)")
            for al in (novo(pl["symbol"], "abaixo", pl["stop"], "stop do plano"),
                       novo(pl["symbol"], "acima", pl["alvo"], "alvo do plano"),
                       novo(pl["symbol"], "zerar", None, "zerar até %s" % pl.get("zerar_ate"))):
                doc["alertas"].append(al)
            gravar_alertas(doc)
            print("3 alertas criados para %s: stop %s, alvo %s e zerar." % (pl["symbol"], b3lib.reais(pl["stop"]), b3lib.reais(pl["alvo"])))
            return 0
        if a.cmd == "list":
            for al in doc["alertas"]:
                print("%s %-7s %-8s %-12s %s" % (al["id"], al["symbol"], al["tipo"], b3lib.reais(al["preco"]) if al["preco"] else "",
                                                 "tocou " + al["tocou_em"] if al.get("tocou_em") else ""))
            return 0 if doc["alertas"] else 1
        if a.cmd == "reset":
            gravar_alertas({"alertas": []})
            print("Alertas apagados.")
            return 0
        st = status_mercado(agora, cfg)
        syms = sorted({al["symbol"] for al in doc["alertas"] if al["tipo"] in ("acima", "abaixo")})
        q, falhas = cotacoes(syms, a.offline) if syms else ({}, {})
        if q:
            gravar_precos(q)
        tocaram = avaliar(doc["alertas"], q, st, agora)
        gravar_alertas(doc)
        if a.json:
            print(json.dumps({"mercado": st, "tocaram": tocaram, "falhas": falhas}, ensure_ascii=False, indent=2))
        else:
            for al in tocaram:
                print("ALERTA " + frase(al))
            if not tocaram:
                print("Nenhum alerta tocou (%s, %s)." % (st["fase"], b3lib.para_brt(agora).strftime("%H:%M")))
            for s, e in falhas.items():
                print("%s sem preço: %s" % (s, e))
        return 0 if tocaram else 1
    except b3lib.B3Erro as e:
        print("alertas: %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
