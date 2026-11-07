"""Estratégia de swing trade: tendência por médias móveis com stop por ATR.

Regras (gráfico diário):
  ENTRADA  — MME rápida cruza para cima a MME lenta, com o fechamento acima da
             MMS de filtro (tendência primária de alta).
  STOP     — fechamento - stop_atr x ATR (enviado à corretora logo após a compra).
  ALVO     — risco x alvo_r (ex.: 2R).
  SAÍDAS   — fechamento >= alvo; fechamento abaixo da MME lenta; tempo máximo.
  TRAILING — opcional: o stop sobe para fechamento - stop_atr x ATR, nunca desce.

A estratégia só decide; não conhece corretora, caixa nem impostos.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from .config import ConfigEstrategia
from .indicadores import atr, mme, mms
from .modelos import Posicao


@dataclass
class SinalEntrada:
    ticker: str
    referencia: float      # fechamento do pregão do sinal
    stop: float
    alvo: float
    forca: float           # usado para ranquear sinais concorrentes


@dataclass
class SinalSaida:
    motivo: str            # alvo | tendencia | tempo


def _arred(valor: float) -> float:
    return round(float(valor) + 1e-9, 2)


class TendenciaMM:
    def __init__(self, cfg: ConfigEstrategia):
        self.cfg = cfg

    @property
    def barras_minimas(self) -> int:
        return self.cfg.mm_filtro + 2

    def _indicadores(self, df: pd.DataFrame):
        c = df["close"]
        return (
            mme(c, self.cfg.mm_rapida),
            mme(c, self.cfg.mm_lenta),
            mms(c, self.cfg.mm_filtro),
            atr(df, self.cfg.atr_periodo),
        )

    def entrada(self, ticker: str, df: pd.DataFrame) -> Optional[SinalEntrada]:
        if len(df) < self.barras_minimas:
            return None
        rapida, lenta, filtro, vol = self._indicadores(df)
        if pd.isna(filtro.iloc[-1]) or pd.isna(vol.iloc[-1]):
            return None
        cruzou = rapida.iloc[-1] > lenta.iloc[-1] and rapida.iloc[-2] <= lenta.iloc[-2]
        fechamento = float(df["close"].iloc[-1])
        if not (cruzou and fechamento > filtro.iloc[-1]):
            return None
        stop = _arred(fechamento - self.cfg.stop_atr * vol.iloc[-1])
        if stop <= 0 or stop >= fechamento:
            return None
        alvo = _arred(fechamento + self.cfg.alvo_r * (fechamento - stop))
        # força = distância ao filtro em ATRs (tendência mais firme primeiro)
        forca = float((fechamento - filtro.iloc[-1]) / vol.iloc[-1])
        return SinalEntrada(ticker, _arred(fechamento), stop, alvo, forca)

    def saida(self, df: pd.DataFrame, pos: Posicao, pregoes_em_posicao: int) -> Optional[SinalSaida]:
        rapida, lenta, _, _ = self._indicadores(df)
        fechamento = float(df["close"].iloc[-1])
        if fechamento >= pos.alvo:
            return SinalSaida("alvo")
        if not pd.isna(lenta.iloc[-1]) and fechamento < lenta.iloc[-1] and rapida.iloc[-1] < lenta.iloc[-1]:
            return SinalSaida("tendencia")
        if pregoes_em_posicao >= self.cfg.tempo_max_dias:
            return SinalSaida("tempo")
        return None

    def novo_stop(self, df: pd.DataFrame, pos: Posicao) -> Optional[float]:
        """Trailing stop por ATR. Retorna novo stop somente se subir ao menos 0,5%."""
        if not self.cfg.trailing_atr:
            return None
        _, _, _, vol = self._indicadores(df)
        if pd.isna(vol.iloc[-1]):
            return None
        candidato = _arred(float(df["close"].iloc[-1]) - self.cfg.stop_atr * vol.iloc[-1])
        if candidato > pos.stop * 1.005:
            return candidato
        return None


def criar(cfg: ConfigEstrategia):
    if cfg.nome == "tendencia_mm":
        return TendenciaMM(cfg)
    raise ValueError(f"Estratégia desconhecida: {cfg.nome}")
