"""Estruturas de dados compartilhadas pelo robô."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional

COMPRAR = "COMPRAR"
VENDER = "VENDER"
AJUSTAR_STOP = "AJUSTAR_STOP"


@dataclass
class Ordem:
    acao: str                      # COMPRAR | VENDER | AJUSTAR_STOP
    ticker: str
    quantidade: int
    preco_limite: Optional[float]  # preço limite (compra/venda limitada)
    preco_stop: Optional[float]    # preço de disparo do stop
    motivo: str
    data_referencia: str           # pregão cujo fechamento gerou a ordem (ISO)
    alvo: Optional[float] = None
    data_envio: Optional[str] = None   # modo real: dia em que foi enviada à corretora

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Posicao:
    ticker: str
    quantidade: int
    preco_medio: float
    stop: float
    alvo: float
    data_entrada: str              # ISO (AAAA-MM-DD)
    stop_enviado: bool = False     # modo real: stop já registrado na corretora?

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Operacao:
    """Uma execução (compra ou venda). Base para a apuração do IR."""
    data: str                      # ISO
    ticker: str
    lado: str                      # "C" ou "V"
    quantidade: int
    preco: float
    custos: float = 0.0
    origem: str = ""               # entrada, stop, alvo, tendencia, tempo...
    estimado: bool = False         # preço estimado (conferir nota de corretagem)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ResultadoBacktest:
    patrimonio: list = field(default_factory=list)   # [(data, valor)]
    operacoes: list = field(default_factory=list)    # [Operacao]
    trades: list = field(default_factory=list)       # [dict] trade fechado


def brl(v: float) -> str:
    """1234.5 -> '1.234,50' (formato brasileiro)."""
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
