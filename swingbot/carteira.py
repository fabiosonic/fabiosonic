"""Carteira do robô: caixa do capital de teste, posições, ordens pendentes e operações.

O robô NUNCA usa mais do que `capital_teste`, mesmo que a conta tenha mais saldo.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .modelos import Operacao, Ordem, Posicao


class Carteira:
    def __init__(self, capital_inicial: float, custo_percentual: float = 0.0):
        self.capital_inicial = float(capital_inicial)
        self.custo_percentual = float(custo_percentual)
        self.caixa = float(capital_inicial)
        self.posicoes: dict[str, Posicao] = {}
        self.operacoes: list[Operacao] = []
        self.pendentes: list[Ordem] = []
        self.trades: list[dict] = []
        self.ultima_data: Optional[str] = None       # último pregão processado
        self.ultima_execucao: Optional[str] = None   # modo real: último dia em que enviou ordens

    # ------------------------------------------------------------------ execuções
    def _custos(self, valor: float) -> float:
        return round(valor * self.custo_percentual, 2)

    def comprar(self, data: str, ticker: str, qtd: int, preco: float, stop: float, alvo: float,
                origem: str = "entrada", estimado: bool = False) -> None:
        valor = qtd * preco
        custos = self._custos(valor)
        self.caixa -= valor + custos
        self.operacoes.append(Operacao(data, ticker, "C", qtd, preco, custos, origem, estimado))
        atual = self.posicoes.get(ticker)
        if atual:
            total = atual.quantidade + qtd
            atual.preco_medio = (atual.preco_medio * atual.quantidade + preco * qtd) / total
            atual.quantidade = total
            atual.stop, atual.alvo = stop, alvo
        else:
            self.posicoes[ticker] = Posicao(ticker, qtd, preco, stop, alvo, data)

    def vender(self, data: str, ticker: str, qtd: int, preco: float, origem: str,
               estimado: bool = False) -> dict:
        pos = self.posicoes[ticker]
        if qtd > pos.quantidade:
            raise ValueError(f"Venda de {qtd} {ticker} maior que a posição ({pos.quantidade}); robô não opera vendido")
        valor = qtd * preco
        custos = self._custos(valor)
        self.caixa += valor - custos
        self.operacoes.append(Operacao(data, ticker, "V", qtd, preco, custos, origem, estimado))
        trade = {
            "ticker": ticker,
            "entrada": pos.data_entrada,
            "saida": data,
            "quantidade": qtd,
            "preco_entrada": round(pos.preco_medio, 4),
            "preco_saida": preco,
            "resultado": round(qtd * (preco - pos.preco_medio) - custos, 2),
            "motivo": origem,
            "day_trade": pos.data_entrada == data,
        }
        self.trades.append(trade)
        pos.quantidade -= qtd
        if pos.quantidade == 0:
            del self.posicoes[ticker]
        return trade

    # ------------------------------------------------------------------ consultas
    def patrimonio(self, precos: dict[str, float]) -> float:
        marcado = sum(p.quantidade * precos.get(t, p.preco_medio) for t, p in self.posicoes.items())
        return round(self.caixa + marcado, 2)

    # ------------------------------------------------------------------ persistência
    def to_dict(self) -> dict:
        return {
            "capital_inicial": self.capital_inicial,
            "custo_percentual": self.custo_percentual,
            "caixa": self.caixa,
            "ultima_data": self.ultima_data,
            "ultima_execucao": self.ultima_execucao,
            "posicoes": [p.to_dict() for p in self.posicoes.values()],
            "pendentes": [o.to_dict() for o in self.pendentes],
            "operacoes": [o.to_dict() for o in self.operacoes],
            "trades": self.trades,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Carteira":
        c = cls(d["capital_inicial"], d.get("custo_percentual", 0.0))
        c.caixa = d["caixa"]
        c.ultima_data = d.get("ultima_data")
        c.ultima_execucao = d.get("ultima_execucao")
        c.posicoes = {p["ticker"]: Posicao(**p) for p in d.get("posicoes", [])}
        c.pendentes = [Ordem(**o) for o in d.get("pendentes", [])]
        c.operacoes = [Operacao(**o) for o in d.get("operacoes", [])]
        c.trades = d.get("trades", [])
        return c

    def salvar(self, caminho: str | Path) -> None:
        caminho = Path(caminho)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        tmp = caminho.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(caminho)  # escrita atômica: não corrompe o estado se cair no meio

    @classmethod
    def carregar_ou_criar(cls, caminho: str | Path, capital: float, custo: float) -> "Carteira":
        caminho = Path(caminho)
        if caminho.exists():
            return cls.from_dict(json.loads(caminho.read_text(encoding="utf-8")))
        return cls(capital, custo)
