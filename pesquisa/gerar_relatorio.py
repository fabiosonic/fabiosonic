"""Gera relatorios/estudo_setups_swing_trade.md a partir de relatorios/ranking_setups.csv."""
import pandas as pd

r = pd.read_csv("relatorios/ranking_setups.csv")
pct = lambda v: f"{v * 100:+.1f}%".replace(".", ",")
pp = lambda v: f"{v * 100:.0f}%"
num = lambda v: "–" if pd.isna(v) else f"{v:.2f}".replace(".", ",")


def tabela(df):
    linhas = ["| # | Setup | Lado | Excesso s/ CDI (a.a.) | 2016–21 | 2021–26 | Queda máx. | Sharpe vs CDI | Trades | Acerto | Fator de lucro |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, x in enumerate(df.itertuples(), 1):
        lado = "Long" if x.lado.startswith("Comprado") else "Short"
        linhas.append(f"| {i} | {x.setup} | {lado} | **{pct(x.excesso_cdi_aa)}** | {pct(x.excesso_1a_metade)} | "
                      f"{pct(x.excesso_2a_metade)} | {pct(x.dd_max)} | {num(x.sharpe_vs_cdi)} | {x.trades} | "
                      f"{pp(x.acerto)} | {num(x.fator_lucro)} |")
    return "\n".join(linhas)


acoes = r[r.universo == "44 ações"].sort_values("excesso_cdi_aa", ascending=False)
ibov = r[r.universo == "Ibovespa"].sort_values("excesso_cdi_aa", ascending=False)
cdi = acoes.cdi_aa.iloc[0]
modelo = open("pesquisa/relatorio_modelo.md", encoding="utf-8").read()
texto = (modelo.replace("{{TABELA_ACOES}}", tabela(acoes))
         .replace("{{TABELA_IBOV}}", tabela(ibov))
         .replace("{{CDI}}", f"{cdi * 100:.2f}%".replace(".", ",")))
open("relatorios/estudo_setups_swing_trade.md", "w", encoding="utf-8").write(texto)
print("ok")
