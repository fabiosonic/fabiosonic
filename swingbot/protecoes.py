"""Proteções por posição: stop loss, take profit, trailing stop e breakeven.

Regras (posição comprada):
  STOP LOSS   — fica SEMPRE registrado na Clear como ordem stop (ou OCO), para
                proteger mesmo com o computador desligado.
  TAKE PROFIT — preço >= alvo: cancela o stop e vende (ou executa via OCO na Clear).
  BREAKEVEN   — ganho >= breakeven_pct: stop sobe para o preço de entrada (+ custos).
  TRAILING    — após ganho >= ativacao_pct, o stop acompanha a maior cotação:
                  tipo "pct": stop = máxima x (1 - valor)       ex.: valor 0.05 = 5%
                  tipo "atr": stop = máxima - valor x ATR       ex.: valor 2.0 = 2 ATR
                O stop NUNCA desce, e só é reenviado se subir >= passo_min
                (evita cancelar/reenviar ordens a cada centavo).

Este módulo só DECIDE (lógica pura e testável). Quem executa é o monitor.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

CUSTO_BREAKEVEN = 0.002   # stop no breakeven fica 0,2% acima da entrada (cobre custos)


@dataclass
class Trailing:
    tipo: str = "pct"            # pct | atr
    valor: float = 0.05
    ativacao_pct: float = 0.0    # só começa a seguir após esse ganho
    atr: Optional[float] = None  # ATR diário (obrigatório no tipo "atr")

    def validar(self) -> None:
        if self.tipo not in ("pct", "atr"):
            raise ValueError("trailing.tipo deve ser 'pct' ou 'atr'")
        if self.valor <= 0 or (self.tipo == "pct" and self.valor >= 0.5):
            raise ValueError("trailing.valor inválido (pct entre 0 e 50%; atr > 0)")
        if self.tipo == "atr" and not self.atr:
            raise ValueError("trailing por ATR exige o valor do ATR")


@dataclass
class Protecao:
    ticker: str
    quantidade: int
    preco_entrada: float
    stop: float
    take_profit: Optional[float] = None
    trailing: Optional[Trailing] = None
    breakeven_pct: Optional[float] = None
    passo_min: float = 0.005
    maior_preco: float = 0.0
    stop_enviado: bool = False        # stop atual está registrado na Clear?
    usa_oco: bool = False             # stop + alvo registrados juntos (OCO) na Clear
    origem: str = "painel"
    ativa: bool = True
    historico: list = field(default_factory=list)

    def __post_init__(self):
        self.ticker = self.ticker.upper()
        if isinstance(self.trailing, dict):
            self.trailing = Trailing(**self.trailing)
        if not self.maior_preco:
            self.maior_preco = self.preco_entrada

    def validar(self) -> None:
        if self.quantidade <= 0 or self.preco_entrada <= 0:
            raise ValueError("quantidade e preço de entrada devem ser positivos")
        if not 0 < self.stop < self.preco_entrada * 1.5:
            raise ValueError("stop loss inválido")
        if self.take_profit is not None and self.take_profit <= self.preco_entrada:
            raise ValueError("take profit deve ficar acima do preço de entrada")
        if self.take_profit is not None and self.take_profit <= self.stop:
            raise ValueError("take profit deve ficar acima do stop")
        if self.trailing:
            self.trailing.validar()
        if self.breakeven_pct is not None and self.breakeven_pct <= 0:
            raise ValueError("breakeven_pct deve ser positivo")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Decisao:
    acao: str                     # MANTER | TAKE_PROFIT | NOVO_STOP | STOP_ATINGIDO
    novo_stop: Optional[float] = None
    motivo: str = ""


def _arred(v: float) -> float:
    return round(float(v) + 1e-9, 2)


def stop_desejado(p: Protecao) -> float:
    """Maior stop permitido pelas regras de breakeven e trailing (nunca abaixo do atual)."""
    stop = p.stop
    ganho_max = p.maior_preco / p.preco_entrada - 1
    if p.breakeven_pct is not None and ganho_max >= p.breakeven_pct:
        stop = max(stop, _arred(p.preco_entrada * (1 + CUSTO_BREAKEVEN)))
    t = p.trailing
    if t and ganho_max >= t.ativacao_pct:
        candidato = p.maior_preco * (1 - t.valor) if t.tipo == "pct" else p.maior_preco - t.valor * t.atr
        stop = max(stop, _arred(candidato))
    return stop


def avaliar(p: Protecao, preco: float, maxima: Optional[float] = None) -> Decisao:
    """Decide o que fazer com a posição dado o preço atual (e a máxima desde a última leitura)."""
    if not p.ativa:
        return Decisao("MANTER", motivo="proteção inativa")
    p.maior_preco = max(p.maior_preco, preco, maxima or 0)
    if preco <= p.stop:
        return Decisao("STOP_ATINGIDO", motivo=f"preço {preco:.2f} <= stop {p.stop:.2f} (a ordem na Clear executa)")
    if p.take_profit is not None and preco >= p.take_profit and not p.usa_oco:
        return Decisao("TAKE_PROFIT", motivo=f"preço {preco:.2f} >= alvo {p.take_profit:.2f}")
    novo = stop_desejado(p)
    if novo > p.stop * (1 + p.passo_min):
        regra = "breakeven" if p.breakeven_pct and novo <= p.preco_entrada * (1 + CUSTO_BREAKEVEN) + 0.01 else "trailing"
        return Decisao("NOVO_STOP", novo, f"{regra}: stop {p.stop:.2f} -> {novo:.2f} (máxima {p.maior_preco:.2f})")
    return Decisao("MANTER")


# ---------------------------------------------------------------------- armazenamento
class Repositorio:
    """estado/protecoes.json — uma proteção por ativo."""

    def __init__(self, caminho: str | Path):
        self.caminho = Path(caminho)

    def carregar(self) -> dict[str, Protecao]:
        if not self.caminho.exists():
            return {}
        dados = json.loads(self.caminho.read_text(encoding="utf-8"))
        return {t: Protecao(**d) for t, d in dados.items()}

    def salvar(self, itens: dict[str, Protecao]) -> None:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.caminho.with_suffix(".tmp")
        tmp.write_text(json.dumps({t: p.to_dict() for t, p in itens.items()}, indent=2, ensure_ascii=False),
                       encoding="utf-8")
        tmp.replace(self.caminho)

    def upsert(self, p: Protecao) -> Protecao:
        p.validar()
        itens = self.carregar()
        antigo = itens.get(p.ticker)
        if antigo:  # preserva a máxima já observada e o status na corretora
            p.maior_preco = max(p.maior_preco, antigo.maior_preco)
            p.stop_enviado = antigo.stop_enviado and abs(antigo.stop - p.stop) < 0.005
            p.historico = antigo.historico
        itens[p.ticker] = p
        self.salvar(itens)
        return p

    def remover(self, ticker: str) -> bool:
        itens = self.carregar()
        ok = itens.pop(ticker.upper(), None) is not None
        self.salvar(itens)
        return ok
