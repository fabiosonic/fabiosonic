#!/usr/bin/env python3
"""Boletas e diário de decisões para b3-boleta. Só biblioteca padrão.

Esta ferramenta nunca fala com corretora e nunca envia nada. Ela cuida do
momento que importa, o seu sim:

  show      mostra cada ordem como boleta em português, com o passo a passo para
            digitar no home broker ou na plataforma (MetaTrader 5, Profit...).
            Uma ordem só fica PRONTA se b3-risco aprovou ESTA ordem hoje
            (mesma impressão digital) e ninguém decidiu sobre ela ainda.
  approve   registra o seu sim para UMA ordem, com a resposta palavra por
            palavra. Recusa "sim para todas", "ok", "pode ser", um sim que cita
            outro ativo ou outra quantidade, e ordem que não está PRONTA.
  decline   registra um não.
  result    registra o que aconteceu depois que você digitou na corretora:
            enviada (com o número da ordem), recusada ou falhou.
  fill      registra uma execução: atualiza trader-b3/carteira.json e
            acrescenta a linha em trader-b3/execucoes.csv (base do b3-fiscal).
  zerar     monta a(s) ordem(ns) que zeram a posição de um ativo: venda para
            comprado, compra para vendido.
            Ainda passa por b3-risco e pelo seu sim.
  log       decisões de hoje.

    python3 ticket.py show
    python3 ticket.py approve --index 1 --reply "sim"
    python3 ticket.py result --index 1 --status enviada --id 123456
    python3 ticket.py fill --codigo PETR4 --lado compra --qtd 200 --preco 58.57 --custos 3.51
    python3 ticket.py fill --codigo B3SA3 --lado venda --qtd 100 --preco 22.69 --custos 0.68   # abre vendido
    python3 ticket.py zerar --symbol PETR4 --write
    python3 ticket.py log

Tudo vai para trader-b3/estado/boleta.json (só acrescenta). Datas e horas de Brasília.
"""

import argparse
import csv
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "b3-comum"))
import b3lib  # noqa: E402

DIR_RISCO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "b3-risco")
sys.path.insert(0, DIR_RISCO)
import check as risco  # noqa: E402

SIM = ("sim", "s", "yes", "y", "confirmo", "confirmado")
LOTE_PALAVRAS = {"todas", "todos", "tudo", "ambas", "ambos", "resto", "restantes", "cada", "elas", "eles"}
DUVIDA = {"nao", "não", "espera", "espere", "aguarda", "aguarde", "talvez", "mas", "depois", "cancela",
          "cancelar", "se", "pare", "para", "nem", "acho"}
CSV_CAMPOS = ["data", "hora", "codigo", "symbol", "lado", "quantidade", "preco", "custos", "ordem_id"]


def estado_path():
    return b3lib.caminho("estado", "boleta.json")


def ler_estado():
    return b3lib.ler_json(estado_path(), {"registros": []}) or {"registros": []}


def registrar(reg):
    est = ler_estado()
    est["registros"].append(reg)
    b3lib.gravar_json(estado_path(), est)


def decisao(est, imp, dia):
    for r in reversed(est["registros"]):
        if r.get("dia") == dia and r.get("impressao") == imp and r.get("evento") in ("aprovacao", "recusa"):
            return r
    return None


def veredito_risco(res, imp, dia):
    if not res or res.get("dia") != dia:
        return None
    return next((o for o in res.get("ordens") or [] if o["impressao"] == imp), None)


def status(ordem, res, est, dia):
    imp = risco.impressao(ordem)
    v = veredito_risco(res, imp, dia)
    d = decisao(est, imp, dia)
    if d:
        return ("APROVADA POR VOCÊ" if d["evento"] == "aprovacao" else "RECUSADA POR VOCÊ"), v
    if v is None:
        return "SEM CHECAGEM (rode /b3-risco)", v
    if v["veredito"] != "APROVADA":
        return "BLOQUEADA PELO RISCO", v
    return "PRONTA", v


VALIDADE = {"dia": "válida para hoje", "vac": "válida até cancelar"}


def texto(o):
    if o["lado"] == "compra":
        acao = "COMPRA para zerar vendido" if o.get("zerando_vendido") else "COMPRA"
    else:
        acao = "VENDA A DESCOBERTO" if o.get("vendido") else "VENDA"
    partes = ["%s %d %s" % (acao, o["qtd"], o["codigo"])]
    if o["tipo"] == "mercado":
        partes.append("a mercado")
    elif o["tipo"] == "stop":
        partes.append("ordem stop: gatilho %s, limite %s" % (b3lib.reais(o["preco_gatilho"]), b3lib.reais(o["preco_limite"])))
    else:
        partes.append("limitada a %s" % b3lib.reais(o["preco_limite"]))
    v = o.get("validade", "dia")
    partes.append(VALIDADE.get(v, "válida até %s" % v))
    return ", ".join(partes)


def passo_a_passo(o, cfg):
    linhas = ["  Como digitar na corretora (%s):" % ("conta SIMULADA" if cfg["simulacao"] else "conta REAL")]
    n = 1
    if o.get("vendido"):
        linhas.append("    %d. Confirme que a corretora tem aluguel (BTC) de %s disponível e a taxa; muitas fazem o "
                      "aluguel automático na venda a descoberto. Proventos no período são reembolsados ao doador." % (n, o["symbol"]))
        n += 1
    linhas.append("    %d. %s no %s." % (n, texto(o), "mercado fracionário" if o["mercado"] == "fracionario" else "lote padrão"))
    n += 1
    if o.get("stop") and o.get("alvo"):
        saida = "venda" if o["lado"] == "compra" else "compra"
        linhas.append("    %d. Assim que executar, ordem OCO de %s de %d %s: stop com gatilho %s e ganho (alvo) %s%s."
                      % (n, saida, o["qtd"], o["codigo"], b3lib.reais(o["stop"]), b3lib.reais(o["alvo"]),
                         ", válida até cancelar" if o.get("estrategia") == "swing" else ""))
        n += 1
        if o.get("estrategia") == "swing":
            linhas.append("    %d. Se nada executar até %s (prazo do plano), zere (/b3-boleta zerar). Acompanhe com "
                          "/b3-swing acompanhar; no swing o gap de abertura pode passar do stop." % (n, o.get("prazo_ate")))
        elif o.get("zerar_ate"):
            linhas.append("    %d. Se nenhum dos dois executar, zere até %s (/b3-boleta zerar)." % (n, o["zerar_ate"]))
        if o["tipo"] == "stop":
            linhas.append("    Obs.: a ordem stop de entrada vale só hoje; se não disparar, rode o plano de novo amanhã.")
    return linhas


def render(o, i, total, cfg, res, est, dia):
    st, v = status(o, res, est, dia)
    linhas = ["Boleta %d de %d — %s" % (i, total, st), "  " + texto(o)]
    if o.get("stop"):
        perda = (v or {}).get("perda_no_stop")
        linhas.append("  stop %s | alvo %s%s" % (b3lib.reais(o["stop"]), b3lib.reais(o.get("alvo")),
                                                 " | perda no stop com custos ≈ %s" % b3lib.reais(perda) if perda else ""))
    if v:
        for m in v["motivos"]:
            linhas.append("  bloqueio: " + m)
        for m in v["avisos"]:
            linhas.append("  aviso: " + m)
    if st == "PRONTA":
        linhas.extend(passo_a_passo(o, cfg))
        linhas.append("  Responda \"sim\" para aprovar SÓ esta boleta, ou \"não\".")
    return "\n".join(linhas)


def aceitar_sim(resposta, ordem):
    """(True, "") ou (False, motivo). Um sim explícito para ESTA ordem."""
    t = (resposta or "").strip().lower()
    palavras = re.findall(r"[a-zà-ú0-9]+", t)
    if not palavras or palavras[0] not in SIM:
        return False, "a resposta precisa começar com \"sim\""
    if LOTE_PALAVRAS & set(palavras):
        return False, "um sim vale para uma boleta só; aprove uma de cada vez"
    if DUVIDA & set(palavras[1:]):
        return False, "a resposta tem uma ressalva (%s); responda só \"sim\" ou \"não\"" % ", ".join(sorted(DUVIDA & set(palavras[1:])))
    proprios = {ordem["codigo"].lower(), ordem["symbol"].lower()}
    for p in palavras:
        if b3lib.valido(p) and p not in proprios:
            return False, "a resposta cita %s, mas a boleta é de %s" % (p.upper(), ordem["codigo"])
        if p.isdigit() and int(p) != ordem["qtd"]:
            return False, "a resposta cita %s ações, mas a boleta é de %d" % (p, ordem["qtd"])
    return True, ""


def carregar(a):
    cfg = b3lib.ler_config(a.config)
    doc = b3lib.ler_json(b3lib.caminho("ordens.json"), obrigatorio=True, o_que="as ordens (rode /b3-orcamento)")
    res = b3lib.ler_json(b3lib.caminho("estado", "risco.json"))
    agora = b3lib.para_brt(b3lib.ler_agora(a.now))
    return cfg, doc.get("ordens") or [], res, ler_estado(), agora


def escolher(ordens, idx):
    if not idx or not 1 <= idx <= len(ordens):
        raise b3lib.B3Erro("--index vai de 1 a %d" % len(ordens))
    return ordens[idx - 1]


def cmd_show(a):
    cfg, ordens, res, est, agora = carregar(a)
    if not ordens:
        print("Não há ordens em trader-b3/ordens.json.")
        return 1
    dia = agora.date().isoformat()
    sel = [(i, o) for i, o in enumerate(ordens, 1) if not a.index or i == a.index]
    print("\n\n".join(render(o, i, len(ordens), cfg, res, est, dia) for i, o in sel))
    return 0


def cmd_approve(a):
    cfg, ordens, res, est, agora = carregar(a)
    o = escolher(ordens, a.index)
    dia = agora.date().isoformat()
    st, v = status(o, res, est, dia)
    if st != "PRONTA":
        raise b3lib.B3Erro("a boleta %d não está PRONTA (%s)" % (a.index, st))
    ok, motivo = aceitar_sim(a.reply, o)
    if not ok:
        raise b3lib.B3Erro("não registrei: %s" % motivo)
    registrar({"evento": "aprovacao", "dia": dia, "hora": agora.strftime("%H:%M:%S"), "impressao": v["impressao"],
               "codigo": o["codigo"], "symbol": o["symbol"], "lado": o["lado"], "qtd": o["qtd"],
               "resposta": a.reply, "simulacao": bool(cfg["simulacao"])})
    print("Sim registrado para a boleta %d: %s. Agora digite a ordem na corretora e depois rode "
          "`ticket.py result --index %d --status enviada --id <número>`." % (a.index, texto(o), a.index))
    return 0


def cmd_decline(a):
    cfg, ordens, res, est, agora = carregar(a)
    o = escolher(ordens, a.index)
    registrar({"evento": "recusa", "dia": agora.date().isoformat(), "hora": agora.strftime("%H:%M:%S"),
               "impressao": risco.impressao(o), "codigo": o["codigo"], "resposta": a.reply or "não"})
    print("Não registrado para a boleta %d." % a.index)
    return 0


def cmd_result(a):
    cfg, ordens, res, est, agora = carregar(a)
    o = escolher(ordens, a.index)
    dia = agora.date().isoformat()
    imp = risco.impressao(o)
    d = decisao(est, imp, dia)
    if a.status == "enviada" and (not d or d["evento"] != "aprovacao"):
        raise b3lib.B3Erro("a boleta %d não tem o seu sim registrado hoje: aprove antes de enviar" % a.index)
    v = veredito_risco(res, imp, dia) or {}
    registrar({"evento": "resultado", "dia": dia, "hora": agora.strftime("%H:%M:%S"), "impressao": imp,
               "status": a.status, "ordem_id": a.id, "codigo": o["codigo"], "symbol": o["symbol"],
               "lado": o["lado"], "qtd": o["qtd"], "entrada": bool(v.get("entrada")),
               "perda_no_stop": v.get("perda_no_stop")})
    print("Resultado registrado: boleta %d %s%s." % (a.index, a.status, " (ordem %s)" % a.id if a.id else ""))
    return 0


def aplicar_execucao(codigo, lado, qtd, preco, custos):
    """Atualiza a carteira. Quantidade com sinal (negativa = vendido); "custo" é o
    valor da posição ao preço médio, com o mesmo sinal da quantidade."""
    sym = b3lib.sem_fracionario(codigo)
    cart = b3lib.ler_json(b3lib.caminho("carteira.json"), {"caixa": None, "posicoes": {}}) or {}
    pos = cart.setdefault("posicoes", {}).setdefault(sym, {"qtd": 0, "custo": 0.0})
    q, c = int(pos["qtd"]), float(pos["custo"])
    sl = 1 if lado == "compra" else -1
    # parte que reduz a posição existente (lado oposto) baixa pelo preço médio
    reduz = min(qtd, abs(q)) if q * sl < 0 else 0
    if reduz:
        medio = c / q
        q += sl * reduz
        c = medio * q
    abre = qtd - reduz
    if abre:
        # compra soma custos ao preço; venda a descoberto desconta custos do valor recebido
        c += sl * (abre * preco + sl * custos * abre / qtd)
        q += sl * abre
    pos["qtd"], pos["custo"] = q, round(c, 2)
    if cart.get("caixa") is not None:
        cart["caixa"] = round(cart["caixa"] - sl * qtd * preco - custos, 2)
    if pos["qtd"] == 0:
        del cart["posicoes"][sym]
    b3lib.gravar_json(b3lib.caminho("carteira.json"), cart)
    return cart


def cmd_fill(a):
    agora = b3lib.para_brt(b3lib.ler_agora(a.now))
    codigo = b3lib.normalizar(a.codigo)
    if not b3lib.valido(codigo) or a.lado not in ("compra", "venda") or a.qtd <= 0 or a.preco <= 0:
        raise b3lib.B3Erro("informe --codigo válido, --lado compra|venda, --qtd e --preco positivos")
    cart = aplicar_execucao(codigo, a.lado, a.qtd, a.preco, a.custos)
    path = b3lib.caminho("execucoes.csv")
    novo = not os.path.exists(path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_CAMPOS)
        if novo:
            w.writeheader()
        w.writerow({"data": agora.date().isoformat(), "hora": agora.strftime("%H:%M:%S"), "codigo": codigo,
                    "symbol": b3lib.sem_fracionario(codigo), "lado": a.lado, "quantidade": a.qtd,
                    "preco": "%.2f" % a.preco, "custos": "%.2f" % a.custos, "ordem_id": a.id or ""})
    registrar({"evento": "execucao", "dia": agora.date().isoformat(), "hora": agora.strftime("%H:%M:%S"),
               "codigo": codigo, "lado": a.lado, "qtd": a.qtd, "preco": a.preco, "custos": a.custos})
    pos = cart["posicoes"].get(b3lib.sem_fracionario(codigo))
    print("Execução registrada: %s %d %s a %s. Posição agora: %s." % (
        a.lado, a.qtd, codigo, b3lib.reais(a.preco),
        ("%d ações compradas" % pos["qtd"] if pos["qtd"] > 0 else "%d ações vendidas" % -pos["qtd"]) if pos else "zerada"))
    return 0


def cmd_zerar(a):
    cfg = b3lib.ler_config(a.config)
    sym = b3lib.sem_fracionario(a.symbol or "")
    cart = b3lib.ler_json(b3lib.caminho("carteira.json"), {}) or {}
    tem = int(((cart.get("posicoes") or {}).get(sym) or {}).get("qtd") or 0)
    if tem == 0:
        raise b3lib.B3Erro("não há posição em %s na carteira" % sym)
    qtd = abs(tem)
    lote = int(cfg["lote_padrao"])
    cheio, resto = qtd // lote * lote, qtd % lote
    base = {"symbol": sym, "lado": "venda" if tem > 0 else "compra", "tipo": "mercado", "validade": "dia",
            "preco_limite": None, "preco_gatilho": None, "stop": None, "alvo": None, "zerando_vendido": tem < 0}
    ords = []
    if cheio:
        ords.append(dict(base, codigo=sym, mercado="lote", qtd=cheio))
    if resto:
        ords.append(dict(base, codigo=sym + "F", mercado="fracionario", qtd=resto))
    agora = b3lib.para_brt(b3lib.ler_agora(a.now))
    if a.write:
        b3lib.gravar_json(b3lib.caminho("ordens.json"), {"gerado_em": agora.strftime("%Y-%m-%d %H:%M"),
                                                         "origem": "b3-boleta zerar", "ordens": ords})
    for o in ords:
        print(texto(o))
    if a.write:
        print("Gravado em trader-b3/ordens.json. Rode /b3-risco e depois show/approve.")
    return 0


def cmd_log(a):
    agora = b3lib.para_brt(b3lib.ler_agora(a.now))
    regs = risco.registros_de_hoje(ler_estado(), agora.date())
    if not regs:
        print("Nenhuma decisão registrada hoje.")
        return 1
    for r in regs:
        print("%s %-10s %s %s %s %s" % (r.get("hora"), r["evento"], r.get("lado", ""), r.get("qtd", ""),
                                        r.get("codigo", ""), r.get("status") or r.get("resposta") or r.get("preco", "")))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cmd", choices=["show", "approve", "decline", "result", "fill", "zerar", "log"])
    p.add_argument("--index", type=int)
    p.add_argument("--reply")
    p.add_argument("--status", choices=["enviada", "recusada", "falhou"])
    p.add_argument("--id")
    p.add_argument("--codigo")
    p.add_argument("--symbol")
    p.add_argument("--lado")
    p.add_argument("--qtd", type=int, default=0)
    p.add_argument("--preco", type=float, default=0.0)
    p.add_argument("--custos", type=float, default=0.0)
    p.add_argument("--now")
    p.add_argument("--config")
    p.add_argument("--write", action="store_true")
    a = p.parse_args(argv)
    try:
        if a.cmd == "result" and not a.status:
            raise b3lib.B3Erro("informe --status enviada|recusada|falhou")
        return {"show": cmd_show, "approve": cmd_approve, "decline": cmd_decline, "result": cmd_result,
                "fill": cmd_fill, "zerar": cmd_zerar, "log": cmd_log}[a.cmd](a)
    except b3lib.B3Erro as e:
        print("boleta: %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
