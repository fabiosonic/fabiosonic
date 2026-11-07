"""Dimensionamento de posição, lotes da B3 e travas de segurança."""
from __future__ import annotations

import math
from pathlib import Path

from .config import ConfigRisco

LOTE_PADRAO = 100


def dimensionar(cfg: ConfigRisco, patrimonio: float, caixa: float, preco: float, stop: float) -> int:
    """Quantidade de ações arriscando `risco_por_operacao` do patrimônio.

    Limitada pelo caixa disponível e pelo peso máximo por posição.
    """
    risco_unitario = preco - stop
    if risco_unitario <= 0 or preco <= 0:
        return 0
    por_risco = math.floor(patrimonio * cfg.risco_por_operacao / risco_unitario)
    por_peso = math.floor(patrimonio * cfg.max_peso_posicao / preco)
    custo_unit = preco * (1 + cfg.custo_percentual)
    por_caixa = math.floor(max(caixa, 0) / custo_unit)
    return max(0, min(por_risco, por_peso, por_caixa))


def dividir_lotes(ticker: str, quantidade: int) -> list[tuple[str, int]]:
    """Divide em mercado padrão (múltiplos de 100) e fracionário (sufixo F)."""
    partes = []
    padrao = (quantidade // LOTE_PADRAO) * LOTE_PADRAO
    fracionario = quantidade - padrao
    if padrao:
        partes.append((ticker, padrao))
    if fracionario:
        partes.append((f"{ticker}F", fracionario))
    return partes


def parada_manual_ativa(raiz: str | Path = ".") -> bool:
    """Crie um arquivo chamado PARAR na pasta do projeto para travar o robô."""
    return (Path(raiz) / "PARAR").exists()


def kill_switch(cfg: ConfigRisco, patrimonio: float) -> bool:
    """True quando a perda acumulada atingiu o limite: robô para de abrir posições."""
    return patrimonio <= cfg.capital_teste * (1 - cfg.perda_maxima_total)
