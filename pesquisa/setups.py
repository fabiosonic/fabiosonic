"""Catálogo de setups clássicos de swing trade (gráfico diário).

Cada setup é escrito UMA vez, na lógica de COMPRA. A versão VENDIDA (short) é
obtida aplicando o mesmo setup ao gráfico espelhado (preços multiplicados por -1,
máxima <-> mínima). Médias, bandas, canais, ATR, MACD e Hilo espelham exatamente;
o IFR e o estocástico espelhados viram 100 - valor e o ADX troca DI+ por DI-.
Assim, o short é o espelho fiel do long (ex.: IFR2 < 10 vira IFR2 > 90).

Cada função recebe o DataFrame (open, high, low, close) e devolve arrays:
  entrada      bool  sinal no fechamento de t (executa em t+1)
  nivel        float preço de rompimento (ordem stop em t+1); NaN = abertura de t+1
  stop         float stop inicial; NaN = sem stop
  alvo         float alvo fixo; NaN = sem alvo
  trail        float stop móvel calculado em t (só sobe); NaN = sem efeito
  alvo_dyn     float alvo recalculado em t (vale para t+1)
  saida        bool  sinal de saída no fechamento de t (executa na abertura de t+1)
  max_dias     int   saída por tempo no fechamento (0 = sem)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from swingbot.indicadores import atr, ifr, mme, mms


def _base(df):
    n = len(df)
    nan = np.full(n, np.nan)
    return {"entrada": np.zeros(n, bool), "nivel": nan.copy(), "stop": nan.copy(), "alvo": nan.copy(),
            "trail": nan.copy(), "alvo_dyn": nan.copy(), "saida": np.zeros(n, bool), "max_dias": 0}


def _cruza_acima(a, b):
    a, b = pd.Series(a), pd.Series(b)
    return ((a > b) & (a.shift(1) <= b.shift(1))).to_numpy()


def _np(s):
    return s.to_numpy(dtype=float) if isinstance(s, pd.Series) else s


# ----------------------------------------------------------------------------- tendência
def cruzamento_mme_9_21(df):
    r = _base(df)
    a, b = mme(df.close, 9), mme(df.close, 21)
    r["entrada"] = _cruza_acima(a, b)
    r["saida"] = _cruza_acima(b, a)
    return r


def cruzamento_mms_50_200(df):
    r = _base(df)
    a, b = mms(df.close, 50), mms(df.close, 200)
    r["entrada"] = _cruza_acima(a, b)
    r["saida"] = _cruza_acima(b, a)
    return r


def setup_9_1_larry_williams(df):
    """MME9 vira para cima: compra no rompimento da máxima, stop na mínima.
    Saída: MME9 vira para baixo -> stop na mínima desse candle."""
    r = _base(df)
    m = mme(df.close, 9)
    sobe = m > m.shift(1)
    virou_cima = sobe & ~sobe.shift(1, fill_value=False)
    # ordem de compra válida enquanto a média sobe, até 3 candles após a virada
    recente = virou_cima | virou_cima.shift(1, fill_value=False) | virou_cima.shift(2, fill_value=False)
    r["entrada"] = (recente & sobe).to_numpy()
    r["nivel"] = _np(df.high)
    r["stop"] = _np(df.low)
    virou_baixo = (~sobe) & sobe.shift(1, fill_value=False)
    r["trail"] = np.where(virou_baixo, _np(df.low), np.nan)
    return r


def donchian_20_10_tartarugas(df):
    r = _base(df)
    r["entrada"] = np.ones(len(df), bool)
    r["nivel"] = _np(df.high.rolling(20).max())
    r["stop"] = r["nivel"] - 2 * _np(atr(df, 20))
    r["trail"] = _np(df.low.rolling(10).min())
    return r


def donchian_55_20_tartarugas(df):
    r = _base(df)
    r["entrada"] = np.ones(len(df), bool)
    r["nivel"] = _np(df.high.rolling(55).max())
    r["stop"] = r["nivel"] - 2 * _np(atr(df, 20))
    r["trail"] = _np(df.low.rolling(20).min())
    return r


def bollinger_rompimento(df):
    r = _base(df)
    media, dp = mms(df.close, 20), df.close.rolling(20).std()
    r["entrada"] = _cruza_acima(df.close, media + 2 * dp)
    r["saida"] = (df.close < media).to_numpy()
    return r


def macd_cruzamento(df):
    r = _base(df)
    macd = mme(df.close, 12) - mme(df.close, 26)
    sinal = mme(macd, 9)
    r["entrada"] = _cruza_acima(macd, sinal)
    r["saida"] = _cruza_acima(sinal, macd)
    return r


def hilo_activator_8(df):
    r = _base(df)
    topo, fundo = mms(df.high, 8).shift(1), mms(df.low, 8).shift(1)
    r["entrada"] = _cruza_acima(df.close, topo)
    r["saida"] = _cruza_acima(fundo, df.close)
    return r


def adx_di_14(df):
    r = _base(df)
    up, down = df.high.diff(), -df.low.diff()
    dm_mais = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index)
    dm_menos = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index)
    tr = atr(df, 14)
    di_mais = 100 * dm_mais.ewm(alpha=1 / 14, adjust=False).mean() / tr
    di_menos = 100 * dm_menos.ewm(alpha=1 / 14, adjust=False).mean() / tr
    dx = 100 * (di_mais - di_menos).abs() / (di_mais + di_menos)
    adx = dx.ewm(alpha=1 / 14, adjust=False).mean()
    r["entrada"] = _cruza_acima(di_mais, di_menos) & (adx > 25).to_numpy()
    r["saida"] = _cruza_acima(di_menos, di_mais)
    return r


def momentum_6_meses(df):
    r = _base(df)
    mom = df.close - df.close.shift(126)
    r["entrada"] = _cruza_acima(mom, pd.Series(0.0, index=df.index))
    r["saida"] = _cruza_acima(pd.Series(0.0, index=df.index), mom)
    return r


# ----------------------------------------------------------------------------- pullback / padrões
def pullback_mme21(df):
    """Tendência (MME21 subindo, preço acima da MMS50); candle testa a MME21 e fecha acima."""
    r = _base(df)
    m21, m50 = mme(df.close, 21), mms(df.close, 50)
    cond = (m21 > m21.shift(5)) & (df.close > m50) & (df.low <= m21) & (df.close >= m21)
    r["entrada"] = cond.to_numpy()
    r["nivel"] = _np(df.high)
    r["stop"] = _np(df.low)
    r["alvo"] = r["nivel"] + 2 * (r["nivel"] - r["stop"])
    r["max_dias"] = 20
    return r


def inside_bar(df):
    r = _base(df)
    cond = (df.high < df.high.shift(1)) & (df.low > df.low.shift(1)) & (df.close > mme(df.close, 21))
    r["entrada"] = cond.to_numpy()
    r["nivel"] = _np(df.high)
    r["stop"] = _np(df.low)
    r["alvo"] = r["nivel"] + 2 * (r["nivel"] - r["stop"])
    r["max_dias"] = 15
    return r


def setup_123(df):
    """Candle do meio com a menor mínima; compra no rompimento da máxima do 3º candle."""
    r = _base(df)
    cond = (df.low.shift(1) < df.low.shift(2)) & (df.low.shift(1) < df.low) & (df.close > mms(df.close, 50))
    r["entrada"] = cond.to_numpy()
    r["nivel"] = _np(df.high)
    r["stop"] = _np(df.low.shift(1))
    r["alvo"] = r["nivel"] + 2 * (r["nivel"] - r["stop"])
    r["max_dias"] = 15
    return r


# ----------------------------------------------------------------------------- reversão à média
def ifr2_connors(df):
    """IFR(2) < 10: compra; alvo na máxima dos 2 últimos candles; stop no tempo (7 dias)."""
    r = _base(df)
    r["entrada"] = (ifr(df.close, 2) < 10).to_numpy()
    r["alvo_dyn"] = _np(df.high.rolling(2).max())
    r["max_dias"] = 7
    return r


def ifr2_com_filtro_mm200(df):
    r = ifr2_connors(df)
    r["entrada"] = r["entrada"] & (df.close > mms(df.close, 200)).to_numpy()
    return r


def bollinger_reversao(df):
    r = _base(df)
    media, dp = mms(df.close, 20), df.close.rolling(20).std()
    r["entrada"] = (df.close < media - 2 * dp).to_numpy()
    r["saida"] = (df.close > media).to_numpy()
    r["max_dias"] = 20
    return r


def estocastico_lento(df):
    r = _base(df)
    minimo, maximo = df.low.rolling(14).min(), df.high.rolling(14).max()
    k = (100 * (df.close - minimo) / (maximo - minimo)).rolling(3).mean()
    r["entrada"] = _cruza_acima(k, pd.Series(20.0, index=df.index))
    r["saida"] = _cruza_acima(pd.Series(80.0, index=df.index), k)
    r["stop"] = _np(df.close - 2 * atr(df, 14))
    r["max_dias"] = 30
    return r


SETUPS = {
    "Cruzamento MME 9/21": ("Tendência", cruzamento_mme_9_21),
    "Cruzamento MMS 50/200": ("Tendência", cruzamento_mms_50_200),
    "Setup 9.1 (Larry Williams)": ("Tendência", setup_9_1_larry_williams),
    "Donchian 20/10 (Tartarugas)": ("Rompimento", donchian_20_10_tartarugas),
    "Donchian 55/20 (Tartarugas)": ("Rompimento", donchian_55_20_tartarugas),
    "Bollinger rompimento": ("Rompimento", bollinger_rompimento),
    "MACD cruzamento": ("Tendência", macd_cruzamento),
    "Hilo Activator 8": ("Tendência", hilo_activator_8),
    "ADX/DI 14 (ADX>25)": ("Tendência", adx_di_14),
    "Momentum 6 meses": ("Tendência", momentum_6_meses),
    "Pullback na MME21": ("Pullback", pullback_mme21),
    "Inside bar": ("Padrão de candle", inside_bar),
    "Setup 123": ("Padrão de candle", setup_123),
    "IFR2 (Connors)": ("Reversão", ifr2_connors),
    "IFR2 + filtro MMS200": ("Reversão", ifr2_com_filtro_mm200),
    "Bollinger reversão": ("Reversão", bollinger_reversao),
    "Estocástico lento 14,3": ("Reversão", estocastico_lento),
}
