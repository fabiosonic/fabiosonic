"""Roda o estudo de fatores: python pesquisa/fatores_rodar.py"""
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pesquisa.fatores import carregar_paineis, resumo, simular  # noqa: E402

INICIO, FIM, METADE = pd.Timestamp("2016-11-07"), pd.Timestamp("2026-11-06"), pd.Timestamp("2021-11-08")
FATORES = ["Momentum 12-1", "Momentum 6-1", "Baixa volatilidade", "Dividend yield", "Reversão de 1 mês",
           "Momentum + baixa vol.", "Momentum + dividendos", "Baixa vol. + dividendos"]


def main():
    t0 = time.time()
    C, U, D, cdi, ibov = carregar_paineis()
    ew, _ = simular(C, U, D, cdi, ibov, "Universo inteiro (peso igual)", INICIO, FIM, n=0)
    linhas = []

    def add(nome, ret, extra):
        linha = {"estrategia": nome, **resumo(ret, cdi, ew, METADE), **extra}
        linhas.append(linha)
        print(f"{nome:45} CAGR {linha['cagr']:+.1%} | vs CDI {linha['excesso_cdi']:+.1%} "
              f"| vs universo {linha['excesso_universo']:+.1%} | DD {linha['dd_max']:.0%} "
              f"| t {linha['t_vs_universo']:+.2f} | {time.time() - t0:.0f}s", flush=True)

    add("Universo inteiro (peso igual, mensal)", ew, {})
    ib = ibov.loc[INICIO:FIM].pct_change().dropna()
    add("Ibovespa", ib, {})
    curvas = {"Universo": ew, "Ibovespa": ib}
    for f in FATORES:
        ret, x = simular(C, U, D, cdi, ibov, f, INICIO, FIM, n=10)
        add(f"{f} | top 10 | mensal", ret, x)
        curvas[f] = ret
    # sensibilidade e variações dos fatores
    for f in ["Momentum 12-1", "Momentum + baixa vol.", "Baixa volatilidade", "Dividend yield"]:
        for n, meses in [(5, 1), (15, 1), (10, 3)]:
            ret, x = simular(C, U, D, cdi, ibov, f, INICIO, FIM, n=n, meses=meses)
            add(f"{f} | top {n} | {'mensal' if meses == 1 else 'trimestral'}", ret, x)
        ret, x = simular(C, U, D, cdi, ibov, f, INICIO, FIM, n=10, filtro_mercado=True)
        add(f"{f} | top 10 | mensal + filtro Ibov>MM200", ret, x)
        curvas[f + " + filtro"] = ret
    out = Path("relatorios")
    pd.DataFrame(linhas).to_csv(out / "ranking_fatores.csv", index=False, float_format="%.5f")
    eq = (1 + pd.DataFrame(curvas).fillna(0)).cumprod()
    eq["CDI"] = (1 + cdi.reindex(eq.index).fillna(0)).cumprod()
    eq.to_csv(out / "curvas_fatores.csv", float_format="%.5f")


if __name__ == "__main__":
    main()
