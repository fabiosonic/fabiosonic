#!/usr/bin/env python3
"""Dimensionamento de posição para b3-orcamento. Só biblioteca padrão, sem rede.

Lê o plano (trader-b3/plano.json, de b3-saida) e o config, calcula quantas
ações comprar e grava a(s) ordem(ns) em trader-b3/ordens.json. Nunca envia
nada: b3-risco confere e b3-boleta pede o seu sim.

    python3 size.py                       # mostra o cálculo
    python3 size.py --write               # grava trader-b3/ordens.json
    python3 size.py --limit               # ordem limitada no preço de entrada do plano
    python3 size.py --limit 58.60 --write
    python3 size.py --orcamento 15000

Quantidade = o MENOR entre
  perda máxima   (max_perda_por_operacao - custos) / risco por ação
  posição        orcamento x max_posicao_pct / entrada
  ordem máxima   max_ordem / entrada
  caixa          (orcamento - reserva de caixa) / entrada, e o caixa da carteira

Custos estimados: custos_pct (padrão 0,03% sobre compra e venda, cobrindo
emolumentos e liquidação da B3) + corretagem_por_ordem x ordens. Confira a
tabela vigente da B3 e da sua corretora e ajuste o config.

Lote padrão: 100 ações. A parte que não fecha lote vai para o fracionário
(código com F, ex.: PETR4F) se "permitir_fracionario" for true; senão é
descartada. Zero ações (stop longe demais para a sua perda máxima) é uma
recusa simples.

Preço usado: o limite de uma ordem limitada; numa ordem a mercado, o MAIOR
entre a entrada do plano e o preço de trader-b3/precos.json com menos de 15
minutos, porque um preço que subiu aumenta a perda até o mesmo stop.
"""

import argparse
import datetime
import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "b3-comum"))
import b3lib  # noqa: E402

FRESCO_MIN = 15


def preco_fresco(precos, sym, agora_utc):
    item = ((precos or {}).get("precos") or {}).get(sym)
    if not item or not item.get("hora_utc"):
        return None
    hora = datetime.datetime.strptime(item["hora_utc"][:19], "%Y-%m-%dT%H:%M:%S")
    return item["preco"] if (agora_utc - hora).total_seconds() <= FRESCO_MIN * 60 else None


def custos(qtd, preco_compra, preco_venda, n_ordens, cfg):
    """Custo estimado de ida e volta."""
    pct = float(cfg["custos_pct"]) / 100.0
    return qtd * (preco_compra + preco_venda) * pct + 2 * n_ordens * float(cfg["corretagem_por_ordem"])


def dividir_lote(qtd, cfg):
    lote = int(cfg["lote_padrao"])
    cheio = qtd // lote * lote
    resto = qtd - cheio
    if resto and not cfg["permitir_fracionario"]:
        resto = 0
    return cheio, resto


def dimensionar(plano, cfg, orcamento=None, limite=None, preco=None, caixa=None):
    orc = orcamento if orcamento is not None else cfg.get("orcamento")
    if not orc or orc <= 0:
        raise b3lib.B3Erro("defina \"orcamento\" em trader-b3/config.json ou use --orcamento")
    entrada_plano, stop, alvo = float(plano["entrada"]), float(plano["stop"]), float(plano["alvo"])
    if limite is not None:
        ref, ref_nome = float(limite), "o preço limite"
    elif preco is not None and preco > entrada_plano:
        ref, ref_nome = float(preco), "o último preço (acima da entrada do plano)"
    else:
        ref, ref_nome = entrada_plano, "a entrada do plano"
    risco = ref - stop
    if risco <= 0:
        raise b3lib.B3Erro("o preço %s já está no stop %s ou abaixo: refaça o plano" % (b3lib.reais(ref), b3lib.reais(stop)))
    rr = (alvo - ref) / risco
    if rr < float(cfg["min_risco_retorno"]):
        raise b3lib.B3Erro("a %s o risco/retorno é %s, abaixo do mínimo %s: o preço já andou para o alvo"
                           % (b3lib.reais(ref), b3lib.num(rr), b3lib.num(cfg["min_risco_retorno"])))
    reserva = orc * float(cfg["reserva_caixa_pct"]) / 100.0
    tetos = {
        "perda máxima": float(cfg["max_perda_por_operacao"]) / risco,
        "posição máxima": orc * float(cfg["max_posicao_pct"]) / 100.0 / ref,
        "ordem máxima": float(cfg["max_ordem"]) / ref,
        "caixa": (orc - reserva) / ref,
    }
    if caixa is not None:
        tetos["caixa da carteira"] = max(0.0, float(caixa)) / ref
    limitante = min(tetos, key=tetos.get)
    qtd = int(math.floor(tetos[limitante] + 1e-9))
    # a perda no stop inclui os custos de ida e volta
    while qtd > 0:
        cheio, resto = dividir_lote(qtd, cfg)
        q = cheio + resto
        n_ord = (1 if cheio else 0) + (1 if resto else 0)
        perda = q * risco + custos(q, ref, stop, n_ord, cfg)
        if q and perda <= float(cfg["max_perda_por_operacao"]) + 1e-9:
            break
        qtd = q - 1 if q == qtd else q
    cheio, resto = dividir_lote(max(qtd, 0), cfg)
    total = cheio + resto
    if total <= 0:
        raise b3lib.B3Erro("zero ações: com risco de %s por ação, a perda máxima de %s não paga nem uma ação%s"
                           % (b3lib.reais(risco), b3lib.reais(cfg["max_perda_por_operacao"]),
                              "" if cfg["permitir_fracionario"] else " (fracionário desligado: mínimo de %d)" % cfg["lote_padrao"]))
    n_ord = (1 if cheio else 0) + (1 if resto else 0)
    c = custos(total, ref, stop, n_ord, cfg)
    return {"symbol": plano["symbol"], "preco_ref": round(ref, 2), "preco_ref_nome": ref_nome, "stop": stop,
            "alvo": alvo, "risco_por_acao": round(risco, 2), "risco_retorno": round(rr, 2), "tetos": tetos,
            "limitante": limitante, "qtd": total, "lote": cheio, "fracionario": resto,
            "valor": round(total * ref, 2), "custos_estimados": round(c, 2),
            "perda_no_stop": round(total * risco + c, 2), "ganho_no_alvo": round(total * (alvo - ref) - custos(total, ref, alvo, n_ord, cfg), 2),
            "orcamento": orc, "reserva": round(reserva, 2), "limitada": limite is not None}


def ordens(s, plano):
    base = {"lado": "compra", "tipo": "limitada" if s["limitada"] else "mercado", "validade": "dia",
            "preco_limite": s["preco_ref"] if s["limitada"] else None, "stop": s["stop"], "alvo": s["alvo"],
            "entrada_plano": plano["entrada"], "zerar_ate": plano.get("zerar_ate"), "dia": plano.get("dia"),
            "setup": plano.get("setup")}
    out = []
    if s["lote"]:
        out.append(dict(base, symbol=s["symbol"], codigo=s["symbol"], mercado="lote", qtd=s["lote"]))
    if s["fracionario"]:
        out.append(dict(base, symbol=s["symbol"], codigo=s["symbol"] + "F", mercado="fracionario", qtd=s["fracionario"]))
    return out


def relatorio(s, ords):
    linhas = ["Dimensionamento %s a %s (%s):" % (s["symbol"], b3lib.reais(s["preco_ref"]), s["preco_ref_nome"]),
              "  risco por ação %s (stop %s), alvo %s, risco/retorno %s" % (
                  b3lib.reais(s["risco_por_acao"]), b3lib.reais(s["stop"]), b3lib.reais(s["alvo"]), b3lib.num(s["risco_retorno"]))]
    for k, v in s["tetos"].items():
        linhas.append("  teto por %-18s %s ações%s" % (k, b3lib.num(math.floor(v + 1e-9), 0),
                                                       "  <- limita" if k == s["limitante"] else ""))
    linhas.append("  comprar %d ações = %s (%s)" % (s["qtd"], b3lib.reais(s["valor"]), " + ".join(
        "%d %s em %s" % (o["qtd"], o["mercado"], o["codigo"]) for o in ords)))
    linhas.append("  custos estimados de ida e volta %s; perda no stop %s; ganho no alvo %s" % (
        b3lib.reais(s["custos_estimados"]), b3lib.reais(s["perda_no_stop"]), b3lib.reais(s["ganho_no_alvo"])))
    return "\n".join(linhas)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--plano", default=b3lib.caminho("plano.json"))
    p.add_argument("--orcamento", type=float)
    p.add_argument("--limit", nargs="?", const="plano")
    p.add_argument("--now")
    p.add_argument("--config")
    p.add_argument("--write", action="store_true")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    try:
        cfg = b3lib.ler_config(a.config)
        plano = b3lib.ler_json(a.plano, obrigatorio=True, o_que="o plano (rode /b3-saida)")
        limite = None if a.limit is None else (float(plano["entrada"]) if a.limit == "plano" else float(a.limit.replace(",", ".")))
        agora = b3lib.ler_agora(a.now)
        preco = preco_fresco(b3lib.ler_json(b3lib.caminho("precos.json"), {}), plano["symbol"], agora)
        carteira = b3lib.ler_json(b3lib.caminho("carteira.json"), None)
        s = dimensionar(plano, cfg, a.orcamento, limite, preco, (carteira or {}).get("caixa"))
        ords = ordens(s, plano)
        if a.write:
            b3lib.gravar_json(b3lib.caminho("ordens.json"), {
                "gerado_em": b3lib.para_brt(agora).strftime("%Y-%m-%d %H:%M"), "origem": "b3-orcamento",
                "simulacao": bool(cfg["simulacao"]), "dimensionamento": s, "ordens": ords})
        print(json.dumps({"dimensionamento": s, "ordens": ords}, ensure_ascii=False, indent=2) if a.json
              else relatorio(s, ords))
        if a.write and not a.json:
            print("Gravado em %s. Próximo passo: /b3-risco." % b3lib.caminho("ordens.json"))
        return 0
    except b3lib.B3Erro as e:
        print("orcamento: %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
