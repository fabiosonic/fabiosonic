import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swingbot.config import Config  # noqa: E402


def barras(fechamentos, inicio="2022-01-03", amplitude=0.01):
    idx = pd.bdate_range(inicio, periods=len(fechamentos))
    c = pd.Series(fechamentos, index=idx, dtype=float)
    o = c.shift(1).fillna(c.iloc[0])
    return pd.DataFrame({
        "open": o, "close": c,
        "high": np.maximum(o, c) * (1 + amplitude),
        "low": np.minimum(o, c) * (1 - amplitude),
        "volume": 1_000_000,
    })


@pytest.fixture
def cfg():
    return Config(ativos=["TEST3"])


@pytest.fixture
def tendencia():
    """Tendência de alta com correções periódicas: gera cruzamentos de médias."""
    rng = np.random.default_rng(7)
    n = 600
    t = np.arange(n)
    base = 20 + 0.04 * t                      # alta primária
    ciclo = 1.8 * np.sin(2 * np.pi * t / 45)  # correções de ~45 pregões
    return barras(base + ciclo + rng.normal(0, 0.1, n))
