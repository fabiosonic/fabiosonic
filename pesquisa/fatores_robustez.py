"""Robustez do momentum: metades, ano a ano e retirada das maiores vencedoras."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pesquisa.fatores import carregar_paineis, simular  # noqa: E402
from pesquisa.fatores_rodar import FIM, INICIO, METADE  # noqa: E402

C, U, D, cdi, ibov = carregar_paineis()


def rodar(colunas, fator="Momentum 12-1", n=10):
    c, u, d = C[colunas], U.reindex(columns=colunas), D.reindex(columns=colunas)
    ew, _ = simular(c, u, d, cdi, ibov, "Universo inteiro (peso igual)", INICIO, FIM, n=0)
    mo, _ = simular(c, u, d, cdi, ibov, fator, INICIO, FIM, n=n)
    return mo, ew


def cagr(r):
    return (1 + r).prod() ** (252 / len(r)) - 1


todas = list(C.columns)
mo, ew = rodar(todas)
print("Ano a ano (momentum top 10 vs universo vs CDI):")
for ano in range(2017, 2027):
    m = (1 + mo[str(ano)]).prod() - 1
    e = (1 + ew[str(ano)]).prod() - 1
    c = (1 + cdi.reindex(mo[str(ano)].index)).prod() - 1
    print(f"  {ano}: momentum {m:+7.1%} | universo {e:+7.1%} | CDI {c:+6.1%} | diferença {m - e:+6.1%}")
for nome, a, b in [("1ª metade", INICIO, METADE), ("2ª metade", METADE, FIM)]:
    print(f"{nome}: momentum {cagr(mo[a:b]):+.1%} a.a. | universo {cagr(ew[a:b]):+.1%} a.a.")

# retorno total de cada ação no período (as maiores vencedoras)
tot = (C.loc[INICIO:FIM].ffill().iloc[-1] / C.loc[INICIO:FIM].bfill().iloc[0] - 1).sort_values(ascending=False)
print("\nMaiores altas no período:", ", ".join(f"{t} {v:+.0%}" for t, v in tot.head(6).items()))
for k in (1, 3, 5, 8):
    fora = list(tot.index[:k])
    mo_k, ew_k = rodar([t for t in todas if t not in fora])
    print(f"Sem as {k} maiores vencedoras ({', '.join(fora)}): momentum {cagr(mo_k):+.1%} a.a. "
          f"| universo {cagr(ew_k):+.1%} | diferença {cagr(mo_k) - cagr(ew_k):+.1%}")


# ---------------------------------------------------------------- dividendos e combinação 50/50
def anual(r1, r2):
    """Duas carteiras com 50% cada, rebalanceadas 1x por ano."""
    df = pd.concat([r1, r2], axis=1).fillna(0)
    partes = []
    for _, b in df.groupby(df.index.year):
        cresc = (1 + b).cumprod().mean(axis=1)
        partes.append(cresc / cresc.shift(1, fill_value=1.0) - 1)
    return pd.concat(partes)


dy, _ = rodar(todas, "Dividend yield")
mix = anual(mo, dy)
print("\nAno a ano (dividendos | 50% momentum + 50% dividendos):")
for ano in range(2017, 2027):
    c = (1 + cdi.reindex(dy[str(ano)].index)).prod() - 1
    print(f"  {ano}: dividendos {(1 + dy[str(ano)]).prod() - 1:+7.1%} | mix {(1 + mix[str(ano)]).prod() - 1:+7.1%} | CDI {c:+6.1%}")
for nome, r in [("Dividendos top 10", dy), ("Mix 50/50", mix), ("Momentum top 10", mo), ("Universo", ew)]:
    eq = (1 + r).cumprod()
    dd = (eq / eq.cummax() - 1).min()
    print(f"{nome:18} total {cagr(r):+.1%} a.a. | 1ª metade {cagr(r[INICIO:METADE]):+.1%} | "
          f"2ª metade {cagr(r[METADE:FIM]):+.1%} | queda máx. {dd:.0%}")
print(f"{'CDI':18} total {cagr(cdi.reindex(ew.index)):+.1%} a.a. | 1ª metade {cagr(cdi.reindex(ew[INICIO:METADE].index)):+.1%} "
      f"| 2ª metade {cagr(cdi.reindex(ew[METADE:FIM].index)):+.1%}")
for k in (1, 5, 8):
    fora = list(tot.index[:k])
    dy_k, ew_k = rodar([t for t in todas if t not in fora], "Dividend yield")
    print(f"Dividendos sem as {k} maiores vencedoras: {cagr(dy_k):+.1%} a.a. (universo {cagr(ew_k):+.1%})")
