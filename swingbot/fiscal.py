"""Apuração mensal do IR sobre renda variável (pessoa física, mercado à vista).

Base legal: Lei 11.033/2004, Lei 8.981/1995 e IN RFB 1.585/2015.
  * Operações comuns (swing): 15%. Ações: isenção quando o total de vendas de
    ações no mês for <= R$ 20.000 (não vale para ETF, BDR e FII).
  * Day trade: 20%, sem isenção; prejuízo compensa somente com day trade.
  * FII: 20%, sem isenção, compensação própria.
  * IRRF: 0,005% sobre vendas comuns; 1% sobre o resultado positivo diário de day trade.
    Retenção <= R$ 1,00 é dispensada. IRRF é deduzido do imposto devido.
  * DARF código 6015, vencimento no último dia útil do mês seguinte;
    valores abaixo de R$ 10,00 acumulam para o mês seguinte.

IMPORTANTE: os preços registrados pelo robô são de controle. A apuração oficial
deve ser conferida com as NOTAS DE CORRETAGEM (custos reais, preços executados).
Para o limite de R$ 20 mil, adota-se postura conservadora: todas as vendas de
ações no mês (inclusive day trade) entram na soma.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .modelos import Operacao

ALIQ_COMUM = 0.15
ALIQ_DT = 0.20
ALIQ_FII = 0.20
IRRF_COMUM = 0.00005
IRRF_DT = 0.01
DARF_MINIMO = 10.0


def ticker_base(ticker: str) -> str:
    t = ticker.upper()
    return t[:-1] if t.endswith("F") and t[-2:-1].isdigit() else t


def tipo_ativo(ticker: str, overrides: dict | None = None) -> str:
    """acao | etf | bdr | fii. Final 11 é ambíguo (FII, ETF ou unit): defina em tipos_ativo."""
    t = ticker_base(ticker)
    overrides = {k.upper(): v for k, v in (overrides or {}).items()}
    if t in overrides:
        return overrides[t]
    sufixo = "".join(ch for ch in t[4:] if ch.isdigit())
    if sufixo in ("32", "33", "34", "35", "39"):
        return "bdr"
    if sufixo == "11":
        return "etf"  # conservador: sem isenção e alíquota de 15%
    return "acao"


def vendas_acoes_no_mes(operacoes: list[Operacao], mes: str, overrides: dict | None = None) -> float:
    """Soma das vendas de ações (valor bruto) no mês AAAA-MM."""
    return round(sum(
        o.quantidade * o.preco for o in operacoes
        if o.lado == "V" and o.data[:7] == mes and tipo_ativo(o.ticker, overrides) == "acao"
    ), 2)


@dataclass
class Mes:
    mes: str
    vendas_acoes: float = 0.0
    vendas_total: float = 0.0
    resultado_comum_acoes: float = 0.0
    resultado_comum_outros: float = 0.0
    resultado_day_trade: float = 0.0
    resultado_fii: float = 0.0
    isento: bool = False
    ganho_isento: float = 0.0
    base_comum: float = 0.0
    base_day_trade: float = 0.0
    base_fii: float = 0.0
    prejuizo_comum_acumulado: float = 0.0
    prejuizo_dt_acumulado: float = 0.0
    prejuizo_fii_acumulado: float = 0.0
    imposto_bruto: float = 0.0
    irrf_mes: float = 0.0
    irrf_utilizado: float = 0.0
    darf_6015: float = 0.0
    valor_acumulado_proximo_mes: float = 0.0
    avisos: list = field(default_factory=list)


def _compensar(base: float, prejuizo: float) -> tuple[float, float]:
    """Retorna (base após compensação, prejuízo acumulado atualizado)."""
    if base < 0:
        return 0.0, prejuizo - base
    usado = min(base, prejuizo)
    return base - usado, prejuizo - usado


def apurar(operacoes: list[Operacao], limite_isencao: float = 20000.0,
           overrides: dict | None = None) -> list[Mes]:
    ops = sorted(operacoes, key=lambda o: o.data)
    posicao: dict[str, list[float]] = defaultdict(lambda: [0, 0.0])   # ticker -> [qtd, custo total]
    meses: dict[str, Mes] = {}
    irrf_dt_por_dia: dict[str, float] = defaultdict(float)

    grupos: dict[tuple[str, str], list[Operacao]] = defaultdict(list)
    for o in ops:
        grupos[(o.data, ticker_base(o.ticker))].append(o)

    for (data, ticker), lista in sorted(grupos.items()):
        m = meses.setdefault(data[:7], Mes(data[:7]))
        tipo = tipo_ativo(ticker, overrides)
        qc = sum(o.quantidade for o in lista if o.lado == "C")
        vc = sum(o.quantidade * o.preco + o.custos for o in lista if o.lado == "C")
        qv = sum(o.quantidade for o in lista if o.lado == "V")
        vv = sum(o.quantidade * o.preco - o.custos for o in lista if o.lado == "V")
        vendas_brutas = sum(o.quantidade * o.preco for o in lista if o.lado == "V")
        m.vendas_total += vendas_brutas
        if tipo == "acao":
            m.vendas_acoes += vendas_brutas

        pc = vc / qc if qc else 0.0
        pv = vv / qv if qv else 0.0
        dt = min(qc, qv)
        if dt:
            res_dt = dt * (pv - pc)
            if tipo == "fii":
                m.resultado_fii += res_dt
            else:
                m.resultado_day_trade += res_dt
                irrf_dt_por_dia[data] += res_dt
        # compras restantes vão para a posição (custo médio)
        if qc - dt:
            posicao[ticker][0] += qc - dt
            posicao[ticker][1] += (qc - dt) * pc
        # vendas restantes são operações comuns contra o custo médio
        q_comum = qv - dt
        if q_comum:
            qtd, custo = posicao[ticker]
            if q_comum > qtd:
                raise ValueError(f"{data} {ticker}: venda de {q_comum} sem posição suficiente ({qtd})")
            pm = custo / qtd
            res = q_comum * (pv - pm)
            posicao[ticker] = [qtd - q_comum, custo - q_comum * pm]
            if tipo == "acao":
                m.resultado_comum_acoes += res
            elif tipo == "fii":
                m.resultado_fii += res
            else:
                m.resultado_comum_outros += res
            irrf = q_comum * pv * IRRF_COMUM
            m.irrf_mes += irrf if irrf > 1.0 else 0.0

    for data, res in irrf_dt_por_dia.items():
        if res > 0:
            irrf = res * IRRF_DT
            meses[data[:7]].irrf_mes += irrf if irrf > 1.0 else 0.0

    # consolidação mês a mês com compensação de prejuízos
    prej_c = prej_dt = prej_fii = 0.0
    saldo_irrf = acumulado = 0.0
    resultado = []
    for chave in sorted(meses):
        m = meses[chave]
        m.isento = m.vendas_acoes <= limite_isencao
        base_c = m.resultado_comum_outros
        if m.isento and m.resultado_comum_acoes > 0:
            m.ganho_isento = m.resultado_comum_acoes
        else:
            base_c += m.resultado_comum_acoes  # prejuízo em ações compensa mesmo em mês isento
        m.base_comum, prej_c = _compensar(base_c, prej_c)
        m.base_day_trade, prej_dt = _compensar(m.resultado_day_trade, prej_dt)
        m.base_fii, prej_fii = _compensar(m.resultado_fii, prej_fii)
        m.prejuizo_comum_acumulado, m.prejuizo_dt_acumulado, m.prejuizo_fii_acumulado = prej_c, prej_dt, prej_fii

        m.imposto_bruto = m.base_comum * ALIQ_COMUM + m.base_day_trade * ALIQ_DT + m.base_fii * ALIQ_FII
        saldo_irrf += m.irrf_mes
        m.irrf_utilizado = min(saldo_irrf, m.imposto_bruto)
        saldo_irrf -= m.irrf_utilizado
        devido = m.imposto_bruto - m.irrf_utilizado + acumulado
        if devido >= DARF_MINIMO:
            m.darf_6015, acumulado = devido, 0.0
        else:
            m.darf_6015, acumulado = 0.0, devido
        m.valor_acumulado_proximo_mes = acumulado

        if m.resultado_day_trade:
            m.avisos.append("Houve day trade (provável stop no dia da entrada): alíquota de 20%.")
        if m.isento and m.resultado_comum_acoes > 0:
            m.avisos.append("Ganho em ações isento: informar em Rendimentos Isentos (linha 20) na DIRPF.")

        for campo in ("vendas_acoes", "vendas_total", "resultado_comum_acoes", "resultado_comum_outros",
                      "resultado_day_trade", "resultado_fii", "ganho_isento", "base_comum",
                      "base_day_trade", "base_fii", "prejuizo_comum_acumulado", "prejuizo_dt_acumulado",
                      "prejuizo_fii_acumulado", "imposto_bruto", "irrf_mes", "irrf_utilizado",
                      "darf_6015", "valor_acumulado_proximo_mes"):
            setattr(m, campo, round(getattr(m, campo), 2))
        resultado.append(m)
    return resultado
