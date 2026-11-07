"""Execução simulada de ordens com barras diárias (backtest e modo simulado).

Premissas conservadoras por pregão:
  1. vendas (saídas) executam primeiro, na abertura ou no limite;
  2. compras executam na abertura (se abaixo do limite) ou no limite;
  3. stops são verificados depois — inclusive em posições abertas no próprio dia
     (isso gera day trade, exatamente como aconteceria na vida real);
  4. gap abaixo do stop executa na abertura (pior preço).
Ordens não executadas expiram no fim do dia (validade "Hoje").
"""
from __future__ import annotations

from .carteira import Carteira
from .modelos import AJUSTAR_STOP, COMPRAR, VENDER


def executar_dia(carteira: Carteira, barras: dict, data: str) -> list[str]:
    eventos: list[str] = []
    pendentes, carteira.pendentes = carteira.pendentes, []

    for o in (p for p in pendentes if p.acao == VENDER):
        b, pos = barras.get(o.ticker), carteira.posicoes.get(o.ticker)
        if b is None or pos is None:
            continue
        if b["open"] >= o.preco_limite:
            preco = float(b["open"])
        elif b["high"] >= o.preco_limite:
            preco = o.preco_limite
        else:
            eventos.append(f"{data} venda {o.ticker} não executada (limite {o.preco_limite})")
            continue
        t = carteira.vender(data, o.ticker, pos.quantidade, round(preco, 2), o.motivo)
        eventos.append(f"{data} VENDA {o.ticker} {t['quantidade']} @ {t['preco_saida']} ({o.motivo}) "
                       f"resultado {t['resultado']:+.2f}")

    for o in (p for p in pendentes if p.acao == AJUSTAR_STOP):
        pos = carteira.posicoes.get(o.ticker)
        if pos and o.preco_stop > pos.stop:
            pos.stop = o.preco_stop

    for o in (p for p in pendentes if p.acao == COMPRAR):
        b = barras.get(o.ticker)
        if b is None or o.ticker in carteira.posicoes:
            continue
        if b["open"] <= o.preco_limite:
            preco = float(b["open"])
        elif b["low"] <= o.preco_limite:
            preco = o.preco_limite
        else:
            eventos.append(f"{data} compra {o.ticker} não executada (abriu acima de {o.preco_limite})")
            continue
        custo = o.quantidade * preco * (1 + carteira.custo_percentual)
        if custo > carteira.caixa + 1e-6:
            eventos.append(f"{data} compra {o.ticker} cancelada: caixa insuficiente")
            continue
        carteira.comprar(data, o.ticker, o.quantidade, round(preco, 2), o.preco_stop, o.alvo)
        eventos.append(f"{data} COMPRA {o.ticker} {o.quantidade} @ {round(preco, 2)} stop {o.preco_stop} alvo {o.alvo}")

    for ticker, pos in list(carteira.posicoes.items()):
        b = barras.get(ticker)
        if b is None or b["low"] > pos.stop:
            continue
        preco = round(min(float(b["open"]), pos.stop), 2)
        t = carteira.vender(data, ticker, pos.quantidade, preco, "stop")
        dt = " [DAY TRADE]" if t["day_trade"] else ""
        eventos.append(f"{data} STOP {ticker} {t['quantidade']} @ {preco} resultado {t['resultado']:+.2f}{dt}")

    carteira.ultima_data = data
    return eventos
