"""Motor de decisão: transforma histórico + carteira em ordens para o próximo pregão.

É o MESMO código no backtest, no modo simulado e no modo real.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from . import fiscal, risco
from .config import Config
from .carteira import Carteira
from .modelos import brl, AJUSTAR_STOP, COMPRAR, VENDER, Ordem

JANELA = 400  # pregões usados no cálculo (suficiente para MMS200 + aquecimento das MMEs)


def _arred(v: float) -> float:
    return round(float(v) + 1e-9, 2)


def planejar(cfg: Config, estrategia, carteira: Carteira, historicos: dict[str, pd.DataFrame],
             data_ref: str, data_execucao: Optional[str] = None,
             bloqueados: set[str] | None = None) -> tuple[list[Ordem], list[str]]:
    """Gera as ordens a executar em `data_execucao` com base no fechamento de `data_ref`."""
    bloqueados = bloqueados or set()
    r = cfg.risco
    avisos: list[str] = []
    saidas: list[Ordem] = []
    ajustes: list[Ordem] = []
    entradas: list[Ordem] = []

    janelas = {t: df.loc[:data_ref].iloc[-JANELA:] for t, df in historicos.items()}
    precos = {t: float(df["close"].iloc[-1]) for t, df in janelas.items() if len(df)}
    patrimonio = carteira.patrimonio(precos)
    mes_exec = (data_execucao or data_ref)[:7]
    vendas_mes = fiscal.vendas_acoes_no_mes(carteira.operacoes, mes_exec, cfg.fiscal.tipos_ativo)

    # ------------------------------------------------------------- posições abertas
    for ticker, pos in list(carteira.posicoes.items()):
        df = janelas.get(ticker)
        if df is None or df.empty or ticker in bloqueados:
            continue
        pregoes = int((df.index > pd.Timestamp(pos.data_entrada)).sum())
        sinal = estrategia.saida(df, pos, pregoes)
        if sinal:
            if data_execucao and pos.data_entrada >= data_execucao:
                avisos.append(f"{ticker}: saída adiada para não gerar day trade (entrada hoje).")
                continue
            preco = _arred(precos[ticker] * (1 - r.folga_preco))
            valor = pos.quantidade * preco
            lucro = pos.quantidade * (precos[ticker] - pos.preco_medio) > 0
            if fiscal.tipo_ativo(ticker, cfg.fiscal.tipos_ativo) == "acao":
                limite = cfg.fiscal.limite_isencao_mensal
                if vendas_mes <= limite < vendas_mes + valor:
                    msg = (f"{ticker}: esta venda faz o mês ultrapassar R$ {brl(limite)} em vendas de ações "
                           f"— os ganhos do mês deixam de ser isentos (15%).")
                    if cfg.fiscal.bloquear_venda_acima_isencao and lucro and sinal.motivo != "tempo":
                        avisos.append(msg + " Venda ADIADA (bloquear_venda_acima_isencao=true).")
                        continue
                    avisos.append(msg)
                vendas_mes += valor
            saidas.append(Ordem(VENDER, ticker, pos.quantidade, preco, None, sinal.motivo, data_ref))
            continue
        novo = estrategia.novo_stop(df, pos)
        if novo:
            ajustes.append(Ordem(AJUSTAR_STOP, ticker, pos.quantidade, _arred(novo * (1 - r.folga_stop)),
                                 novo, "trailing", data_ref))

    # ------------------------------------------------------------- novas entradas
    if risco.kill_switch(r, patrimonio):
        avisos.append(f"KILL SWITCH: patrimônio R$ {brl(patrimonio)} atingiu a perda máxima. "
                      f"Nenhuma nova entrada; stops mantidos.")
    else:
        vagas = r.max_posicoes - len(carteira.posicoes)
        caixa = carteira.caixa
        sinais = []
        for ticker, df in janelas.items():
            if ticker in carteira.posicoes or ticker in bloqueados or df.empty:
                continue
            if df.index[-1] != pd.Timestamp(data_ref):
                continue  # sem pregão no dia de referência (dado faltante ou ativo suspenso)
            s = estrategia.entrada(ticker, df)
            if s:
                sinais.append(s)
        for s in sorted(sinais, key=lambda s: s.forca, reverse=True):
            if vagas <= 0:
                break
            limite_preco = _arred(s.referencia * (1 + r.folga_preco))
            qtd = risco.dimensionar(r, patrimonio, caixa, limite_preco, s.stop)
            if qtd <= 0:
                avisos.append(f"{s.ticker}: sinal de compra ignorado (capital/risco insuficiente).")
                continue
            entradas.append(Ordem(COMPRAR, s.ticker, qtd, limite_preco, s.stop, "entrada", data_ref, s.alvo))
            caixa -= qtd * limite_preco * (1 + r.custo_percentual)
            vagas -= 1

    ordens = (saidas + ajustes + entradas)
    if len(ordens) > r.max_ordens_dia:
        avisos.append(f"Limite de {r.max_ordens_dia} ordens/dia: {len(ordens) - r.max_ordens_dia} descartada(s).")
        ordens = ordens[: r.max_ordens_dia]
    return ordens, avisos
