"""Detecção de reversão de tendência em posições compradas (alerta de saída).

Cada regra tem um peso. A soma define o nível:
  0      -> tendência intacta
  1-2    -> ATENÇÃO  (enfraquecimento: aperte o stop / acompanhe)
  >= 3   -> SAIR     (reversão confirmada por mais de um critério)

Regras (gráfico diário; o último candle pode ser o pregão em andamento):
  MME9 virou para baixo                     peso 1   (saída do setup 9.1)
  MACD cruzou abaixo da linha de sinal      peso 2   (saída do setup mais consistente no estudo)
  Fechamento abaixo da MME21                peso 1
  MME9 cruzou abaixo da MME21               peso 2
  Rompeu a mínima dos últimos 10 pregões    peso 2   (perda de suporte de curto prazo)
  Perdeu a MMS200 nos últimos 5 pregões     peso 3   (tendência primária virou)
  Já estava abaixo da MMS200                peso 1   (operação contra a tendência)
  Queda >= 2 ATR desde a máxima da posição  peso 2   (devolução relevante do ganho)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from .indicadores import atr, mme, mms

ATENCAO, SAIR = "ATENÇÃO", "SAIR"


@dataclass
class Diagnostico:
    nivel: str                         # OK | ATENÇÃO | SAIR
    pontos: int
    sinais: list = field(default_factory=list)
    preco: Optional[float] = None

    def to_dict(self) -> dict:
        return {"nivel": self.nivel, "pontos": self.pontos, "sinais": self.sinais, "preco": self.preco}


def com_preco_atual(df: pd.DataFrame, preco: Optional[float], data_hoje: Optional[pd.Timestamp] = None) -> pd.DataFrame:
    """Acrescenta (ou atualiza) o candle de hoje com o preço intradiário, para avaliar durante o pregão."""
    if preco is None:
        return df
    hoje = pd.Timestamp(data_hoje or pd.Timestamp.now().normalize())
    df = df.copy()
    if df.index[-1] >= hoje:
        i = df.index[-1]
        df.loc[i, "close"] = preco
        df.loc[i, "high"] = max(df.loc[i, "high"], preco)
        df.loc[i, "low"] = min(df.loc[i, "low"], preco)
    else:
        df.loc[hoje] = {"open": preco, "high": preco, "low": preco, "close": preco,
                        **({"volume": 0} if "volume" in df.columns else {})}
    return df


def avaliar(df: pd.DataFrame, maior_preco: Optional[float] = None) -> Diagnostico:
    if len(df) < 210:
        return Diagnostico("OK", 0, ["histórico insuficiente"], float(df["close"].iloc[-1]))
    c = df["close"]
    m9, m21, m200 = mme(c, 9), mme(c, 21), mms(c, 200)
    macd = mme(c, 12) - mme(c, 26)
    sinal = mme(macd, 9)
    a = float(atr(df, 14).iloc[-1])
    ult = float(c.iloc[-1])
    sinais: list[tuple[int, str]] = []

    if m9.iloc[-1] < m9.iloc[-2] and m9.iloc[-2] >= m9.iloc[-3]:
        sinais.append((1, "MME9 virou para baixo"))
    if macd.iloc[-1] < sinal.iloc[-1] and macd.iloc[-2] >= sinal.iloc[-2]:
        sinais.append((2, "MACD cruzou abaixo da linha de sinal"))
    elif macd.iloc[-1] < sinal.iloc[-1] and macd.iloc[-1] < macd.iloc[-2]:
        sinais.append((1, "MACD abaixo do sinal e caindo"))
    if ult < m21.iloc[-1]:
        sinais.append((1, f"fechamento abaixo da MME21 ({m21.iloc[-1]:.2f})"))
    if m9.iloc[-1] < m21.iloc[-1] and m9.iloc[-2] >= m21.iloc[-2]:
        sinais.append((2, "MME9 cruzou abaixo da MME21"))
    minima10 = float(df["low"].iloc[-11:-1].min())
    if ult < minima10:
        sinais.append((2, f"rompeu a mínima de 10 pregões ({minima10:.2f})"))
    if ult < m200.iloc[-1]:
        perdeu_agora = bool((c.iloc[-6:-1] >= m200.iloc[-6:-1]).any())
        if perdeu_agora:
            sinais.append((3, f"perdeu a MMS200 ({m200.iloc[-1]:.2f}) — tendência primária virou"))
        else:
            sinais.append((1, f"abaixo da MMS200 ({m200.iloc[-1]:.2f}) — operação contra a tendência primária"))
    if maior_preco and a > 0 and maior_preco - ult >= 2 * a:
        sinais.append((2, f"devolveu {(maior_preco - ult) / a:.1f} ATR desde a máxima ({maior_preco:.2f})"))

    pontos = sum(p for p, _ in sinais)
    nivel = SAIR if pontos >= 3 else ATENCAO if pontos >= 1 else "OK"
    return Diagnostico(nivel, pontos, [s for _, s in sinais], ult)
