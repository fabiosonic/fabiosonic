#!/usr/bin/env python3
"""Checagem de risco antes da ordem para b3-risco. Só biblioteca padrão, sem rede.

Lê as ordens propostas (trader-b3/ordens.json) e confere cada uma contra suas
regras (config.json), sua carteira (carteira.json), preços (precos.json) e o que
já foi enviado hoje (estado/boleta.json). Cada ordem recebe APROVADA ou
BLOQUEADA com os motivos. As ordens são conferidas em sequência como se cada
aprovada tivesse sido executada, então compras que passam sozinhas mas estouram
um limite juntas são pegas.

    python3 check.py                          # grava trader-b3/estado/risco.json
    python3 check.py --now "2026-10-23 10:26"
    python3 check.py --json --no-write

Bloqueia qualquer ordem:
  formato      ativo inválido, lado diferente de compra/venda, quantidade não
               inteira, ordem limitada sem preço; lote padrão com quantidade
               fora do múltiplo do lote; fracionário com 100 ou mais ou sem o F
  ativo        opções, a menos que "permitir_opcoes": true
  vendido      vender mais do que tem, a menos que "permitir_vendido": true

Bloqueia uma ENTRADA (compra ou venda que abre posição), além do acima:
  bloqueado    ativo na lista "bloqueados"
  tamanho      abaixo de min_ordem ou acima de max_ordem
  posição      o ativo passaria de max_posicao_pct do orçamento
  caixa        a compra usaria a reserva de caixa ou exigiria alavancagem
  duplicada    mesmo código e lado duas vezes no lote, ou já enviado hoje
  limite       max_ordens_dia ordens já enviadas hoje
  stop         sem stop quando "exigir_stop": true, ou stop acima da entrada
  perda        qtd x (preço - stop) + custos acima de max_perda_por_operacao,
               somando lote e fracionário do mesmo ativo
  risco/retorno abaixo de min_risco_retorno
  perda diária soma das perdas no stop das entradas de hoje acima de max_perda_diaria
  operações    max_operacoes_dia ativos diferentes já operados hoje
  horário      fora da janela de novas entradas, ou sem pregão

Uma SAÍDA (só reduz posição) passa a ser sempre possível: só formato, ativo e
vendido bloqueiam; o resto vira aviso. Código de saída 0 se todas passarem.
"""

import argparse
import datetime
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "b3-comum"))
import b3lib  # noqa: E402

CAMPOS = ("symbol", "codigo", "mercado", "lado", "qtd", "tipo", "preco_limite", "stop", "alvo", "validade")


def impressao(ordem):
    """Impressão digital da ordem: b3-boleta só aceita a ordem que ESTA checagem aprovou."""
    base = {k: ordem.get(k) for k in CAMPOS}
    return hashlib.sha256(json.dumps(base, sort_keys=True).encode()).hexdigest()[:16]


def registros_de_hoje(estado, hoje):
    return [r for r in (estado or {}).get("registros") or [] if r.get("dia") == hoje.isoformat()]


def enviadas_hoje(estado, hoje):
    return [r for r in registros_de_hoje(estado, hoje) if r.get("evento") == "resultado" and r.get("status") == "enviada"]


def checar(ordens, cfg, carteira=None, precos=None, estado=None, agora_utc=None):
    agora = b3lib.para_brt(agora_utc or b3lib.agora_utc())
    hoje = agora.date()
    pos = {k: dict(v) for k, v in ((carteira or {}).get("posicoes") or {}).items()}
    caixa = (carteira or {}).get("caixa")
    orc = cfg.get("orcamento") or 0
    reserva = orc * float(cfg["reserva_caixa_pct"]) / 100.0
    enviadas = enviadas_hoje(estado, hoje)
    perda_hoje = sum(float(r.get("perda_no_stop") or 0) for r in enviadas if r.get("entrada"))
    ativos_hoje = {r["symbol"] for r in enviadas if r.get("entrada")}
    vistos = {(r.get("codigo"), r.get("lado")) for r in enviadas}
    n_enviadas = len(enviadas)
    perda_por_ativo = {}
    jan = b3lib.janela_entradas(hoje, cfg)
    pct_custo = float(cfg["custos_pct"]) / 100.0
    out = []
    for idx, o in enumerate(ordens, 1):
        bloq, avisos = [], []
        sym = b3lib.sem_fracionario(o.get("symbol") or o.get("codigo") or "")
        codigo = b3lib.normalizar(o.get("codigo") or sym)
        lado = o.get("lado")
        qtd = o.get("qtd")
        # formato
        if not b3lib.valido(codigo):
            bloq.append("formato: código %r inválido para a B3" % codigo)
        if lado not in ("compra", "venda"):
            bloq.append("formato: lado precisa ser compra ou venda")
        if not isinstance(qtd, int) or qtd <= 0:
            bloq.append("formato: quantidade precisa ser um inteiro positivo")
            qtd = 0
        if o.get("tipo") not in ("mercado", "limitada"):
            bloq.append("formato: tipo precisa ser mercado ou limitada")
        if o.get("tipo") == "limitada" and not o.get("preco_limite"):
            bloq.append("formato: ordem limitada sem preço limite")
        lote = int(cfg["lote_padrao"])
        frac = codigo.endswith("F") and b3lib.valido(codigo)
        if o.get("mercado") == "fracionario" or frac:
            if not frac:
                bloq.append("formato: fracionário usa o código com F (%sF)" % sym)
            if qtd >= lote:
                bloq.append("formato: fracionário vai de 1 a %d ações" % (lote - 1))
        elif qtd % lote:
            bloq.append("formato: lote padrão é múltiplo de %d (use o fracionário para o resto)" % lote)
        if b3lib.OPCAO.match(codigo) and not b3lib.TICKER.match(codigo) and not cfg["permitir_opcoes"]:
            bloq.append("ativo: opções estão desligadas (permitir_opcoes)")
        tem = (pos.get(sym) or {}).get("qtd", 0)
        entrada = lado == "compra" or (lado == "venda" and qtd > tem)
        if lado == "venda" and qtd > tem and not cfg["permitir_vendido"]:
            bloq.append("vendido: venda de %d com %d em carteira (permitir_vendido está desligado)" % (qtd, tem))
        preco = float(o.get("preco_limite") or 0) or None
        ult = (((precos or {}).get("precos") or {}).get(sym) or {}).get("preco")
        ref = preco or max(float(o.get("entrada_plano") or 0), float(ult or 0)) or None
        regras = []
        if entrada and lado == "compra":
            if sym in [b3lib.normalizar(x) for x in cfg["bloqueados"]]:
                regras.append("bloqueado: %s está na sua lista de bloqueados" % sym)
            valor = qtd * (ref or 0)
            if ref is None:
                regras.append("preço: sem preço de referência (limite, plano ou precos.json)")
            else:
                if valor < float(cfg["min_ordem"]):
                    regras.append("tamanho: %s abaixo do mínimo %s" % (b3lib.reais(valor), b3lib.reais(cfg["min_ordem"])))
                if valor > float(cfg["max_ordem"]):
                    regras.append("tamanho: %s acima do máximo %s" % (b3lib.reais(valor), b3lib.reais(cfg["max_ordem"])))
                if orc:
                    depois = ((pos.get(sym) or {}).get("qtd", 0) + qtd) * ref
                    if depois > orc * float(cfg["max_posicao_pct"]) / 100.0 + 0.005:
                        regras.append("posição: %s ficaria com %s, acima de %s%% do orçamento" % (
                            sym, b3lib.reais(depois), b3lib.num(cfg["max_posicao_pct"], 0)))
                if caixa is not None and not cfg["permitir_alavancagem"] and valor > caixa - reserva + 0.005:
                    regras.append("caixa: a compra de %s usaria a reserva (caixa %s, reserva %s)" % (
                        b3lib.reais(valor), b3lib.reais(caixa), b3lib.reais(reserva)))
            if (codigo, lado) in vistos:
                regras.append("duplicada: %s %s já está neste lote ou foi enviada hoje" % (lado, codigo))
            if n_enviadas >= int(cfg["max_ordens_dia"]):
                regras.append("limite: %d ordens já enviadas hoje (max_ordens_dia)" % n_enviadas)
            stop, alvo = o.get("stop"), o.get("alvo")
            if not stop and cfg["exigir_stop"]:
                regras.append("stop: ordem sem stop e exigir_stop está ligado")
            perda = None
            if stop and ref:
                if stop >= ref:
                    regras.append("stop: o stop %s está acima do preço %s" % (b3lib.reais(stop), b3lib.reais(ref)))
                else:
                    perda = qtd * (ref - stop) + qtd * (ref + stop) * pct_custo + 2 * float(cfg["corretagem_por_ordem"])
                    acum = perda_por_ativo.get(sym, 0) + perda
                    if acum > float(cfg["max_perda_por_operacao"]) + 0.005:
                        regras.append("perda: perda no stop de %s com custos, acima de %s" % (
                            b3lib.reais(acum), b3lib.reais(cfg["max_perda_por_operacao"])))
                    if perda_hoje + perda > float(cfg["max_perda_diaria"]) + 0.005:
                        regras.append("perda diária: %s já em risco hoje + %s passa de %s" % (
                            b3lib.reais(perda_hoje), b3lib.reais(perda), b3lib.reais(cfg["max_perda_diaria"])))
                    if alvo:
                        rr = (alvo - ref) / (ref - stop)
                        if rr < float(cfg["min_risco_retorno"]) - 1e-9:
                            regras.append("risco/retorno: %s abaixo do mínimo %s" % (
                                b3lib.num(rr), b3lib.num(cfg["min_risco_retorno"])))
            if sym not in ativos_hoje and len(ativos_hoje) >= int(cfg["max_operacoes_dia"]):
                regras.append("operações: %d ativos já operados hoje (max_operacoes_dia)" % len(ativos_hoje))
            if jan is None:
                regras.append("horário: não há pregão hoje (%s)" % b3lib.dia_de_pregao(hoje, cfg)[1])
            elif not (jan[0] <= agora.time() <= jan[1]):
                regras.append("horário: são %s, novas entradas só de %s a %s" % (
                    agora.strftime("%H:%M"), b3lib.hm(jan[0]), b3lib.hm(jan[1])))
        else:
            perda = None
        if entrada:
            bloq.extend(regras)
        else:
            avisos.extend(regras)
        aprovada = not bloq
        if aprovada:
            vistos.add((codigo, lado))
            if entrada and lado == "compra":
                n_enviadas += 1
                ativos_hoje.add(sym)
                if perda:
                    perda_hoje += perda
                    perda_por_ativo[sym] = perda_por_ativo.get(sym, 0) + perda
                if caixa is not None and ref:
                    caixa -= qtd * ref
                p = pos.setdefault(sym, {"qtd": 0, "custo": 0.0})
                p["qtd"] += qtd
            elif lado == "venda":
                p = pos.setdefault(sym, {"qtd": 0, "custo": 0.0})
                p["qtd"] -= qtd
        out.append({"indice": idx, "codigo": codigo, "symbol": sym, "lado": lado, "qtd": qtd,
                    "entrada": entrada, "veredito": "APROVADA" if aprovada else "BLOQUEADA",
                    "motivos": bloq, "avisos": avisos, "perda_no_stop": round(perda, 2) if perda else None,
                    "preco_ref": ref, "impressao": impressao(o)})
    return {"dia": hoje.isoformat(), "hora": agora.strftime("%H:%M"), "simulacao": bool(cfg["simulacao"]),
            "aprovadas": sum(1 for r in out if r["veredito"] == "APROVADA"), "ordens": out}


def relatorio(res):
    linhas = ["Checagem de risco em %s %s (%s):" % (res["dia"], res["hora"],
                                                   "SIMULAÇÃO" if res["simulacao"] else "conta REAL")]
    for r in res["ordens"]:
        linhas.append("  %d. %s %d %s: %s" % (r["indice"], r["lado"], r["qtd"], r["codigo"], r["veredito"]))
        for m in r["motivos"]:
            linhas.append("       - " + m)
        for m in r["avisos"]:
            linhas.append("       aviso: " + m)
    return "\n".join(linhas)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ordens", default=b3lib.caminho("ordens.json"))
    p.add_argument("--now")
    p.add_argument("--config")
    p.add_argument("--json", action="store_true")
    p.add_argument("--no-write", action="store_true")
    a = p.parse_args(argv)
    try:
        cfg = b3lib.ler_config(a.config)
        doc = b3lib.ler_json(a.ordens, obrigatorio=True, o_que="as ordens (rode /b3-orcamento)")
        res = checar(doc.get("ordens") or [], cfg, b3lib.ler_json(b3lib.caminho("carteira.json")),
                     b3lib.ler_json(b3lib.caminho("precos.json")),
                     b3lib.ler_json(b3lib.caminho("estado", "boleta.json")), b3lib.ler_agora(a.now))
        if not a.no_write:
            b3lib.gravar_json(b3lib.caminho("estado", "risco.json"), res)
        print(json.dumps(res, ensure_ascii=False, indent=2) if a.json else relatorio(res))
        return 0 if res["aprovadas"] == len(res["ordens"]) and res["ordens"] else 1
    except b3lib.B3Erro as e:
        print("risco: %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
