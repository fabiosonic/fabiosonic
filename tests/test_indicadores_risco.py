import pandas as pd
import pytest

from swingbot.config import ConfigRisco
from swingbot.indicadores import atr, ifr, mme, mms
from swingbot.risco import dimensionar, dividir_lotes, kill_switch
from tests.conftest import barras


def test_medias():
    s = pd.Series([1, 2, 3, 4, 5], dtype=float)
    assert mms(s, 5).iloc[-1] == 3
    # MME(3): alfa 0,5 -> 1, 1.5, 2.25, 3.125, 4.0625 (min_periods=3)
    assert mme(s, 3).iloc[-1] == pytest.approx(4.0625)


def test_atr_e_ifr():
    df = barras([10] * 30, amplitude=0.01)
    assert atr(df, 14).iloc[-1] == pytest.approx(0.2, rel=1e-6)
    alta = pd.Series(range(1, 40), dtype=float)
    assert ifr(alta, 14).iloc[-1] == pytest.approx(100)


def test_dimensionar_limites():
    r = ConfigRisco(capital_teste=10000, risco_por_operacao=0.01, max_peso_posicao=0.4, custo_percentual=0)
    # risco: 100 / 1,00 = 100 ações; peso: 4000/20 = 200; caixa: 10000/20 = 500
    assert dimensionar(r, 10000, 10000, 20.0, 19.0) == 100
    # stop muito curto -> limitado pelo peso máximo (40%)
    assert dimensionar(r, 10000, 10000, 20.0, 19.9) == 200
    # pouco caixa
    assert dimensionar(r, 10000, 300, 20.0, 19.0) == 15
    assert dimensionar(r, 10000, 10000, 20.0, 21.0) == 0


def test_lotes():
    assert dividir_lotes("PETR4", 250) == [("PETR4", 200), ("PETR4F", 50)]
    assert dividir_lotes("PETR4", 37) == [("PETR4F", 37)]
    assert dividir_lotes("PETR4", 300) == [("PETR4", 300)]


def test_kill_switch():
    r = ConfigRisco(capital_teste=5000, perda_maxima_total=0.1)
    assert not kill_switch(r, 4600)
    assert kill_switch(r, 4500)
