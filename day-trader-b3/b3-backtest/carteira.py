"""Simulação de carteira para o b3-backtest: transforma operações em R numa
curva de patrimônio realista.

  - no máximo `max_pos` posições ao mesmo tempo e um ativo por vez;
  - risco por operação = `risco` do patrimônio realizado na entrada;
  - tamanho limitado a patrimônio / max_pos por posição (sem alavancagem);
  - quando há mais sinais do que vagas no mesmo pregão, a ordem decide:
    "mom" (maior retorno de 126 pregões), "baixa_vol" (menor ATR %),
    "aleatorio" (sorteio fixo, referência);
  - "regime": só entra comprado com o Ibovespa acima da MM200 e vendido abaixo;
  - cdi: o caixa livre rende CDI; inicio/fim (ordinais) fixam o período, com
    o dinheiro no CDI antes da primeira e depois da última operação;
  - corretagem: R$ por ordem (entrada e saída);
  - ir: IR de swing trade mês a mês (15%, isenção quando as vendas de ações do
    mês ficam em até R$ 20 mil, prejuízo compensado nos meses seguintes) e 15%
    sobre o rendimento do caixa no CDI (alíquota de longo prazo).
"""

import datetime
import random


def taxa_cdi(cdi, ordinal):
    """Taxa diária (dias corridos) do mês do `ordinal`, a partir de {(ano, mes): % ao mês}."""
    d = datetime.date.fromordinal(ordinal)
    m = cdi.get((d.year, d.month))
    return 0.0 if m is None else (1 + m / 100.0) ** (12 / 365.25) - 1


ISENCAO_MES = 20000.0
ALIQ_SWING = 0.15
ALIQ_RF = 0.15


def simular(ops, max_pos=5, risco=0.01, ordem="mom", regime=False, capital=100000.0, seed=7, cdi=None,
            inicio=None, fim=None, corretagem=0.0, ir=False):
    rng = random.Random(seed)
    por_dia = {}
    for op in ops:
        if regime and op["reg"] != (1 if op["setup_lado"] > 0 else -1):
            continue
        por_dia.setdefault(op["entrada"], []).append(op)
    eq = capital
    abertas = []                 # (saida, symbol, risco_rs, R, nocional)
    t0 = inicio or (min(por_dia) if por_dia else 0)
    curva = [(t0, eq)]
    feitas = []
    pico, dd = eq, 0.0
    relogio = [t0]
    rendeu = [0.0]
    custos = {"corretagem": 0.0, "ir_swing": 0.0, "ir_cdi": 0.0}
    meses = {}                   # (ano, mes) -> [vendas, resultado]
    fisco = {"prejuizo": 0.0, "apurado": None}
    fim_ano = {}

    def apurar(ate):
        """Recolhe o IR de swing dos meses já fechados antes de `ate`."""
        nonlocal eq
        if not ir:
            return
        d = datetime.date.fromordinal(ate)
        for chave in sorted(k for k in meses if k < (d.year, d.month)):
            vendas, res = meses.pop(chave)
            if res > 0 and vendas <= ISENCAO_MES:
                continue
            base = res - fisco["prejuizo"] if res > 0 else res
            if res <= 0:
                fisco["prejuizo"] += -res
            elif base > 0:
                fisco["prejuizo"] = 0.0
                imposto = ALIQ_SWING * base
                eq -= imposto
                custos["ir_swing"] += imposto
            else:
                fisco["prejuizo"] = -base

    def render(ate):
        """CDI sobre o caixa livre (patrimônio menos o nocional das posições) até `ate`."""
        nonlocal eq
        if not cdi or ate <= relogio[0]:
            return
        livre = max(0.0, eq - sum(p[4] for p in abertas))
        d = relogio[0]
        while d < ate:
            ganho = livre * taxa_cdi(cdi, d)
            if ir:
                custos["ir_cdi"] += ganho * ALIQ_RF
                ganho *= 1 - ALIQ_RF
            eq += ganho
            livre += ganho
            rendeu[0] += ganho
            dd_ = datetime.date.fromordinal(d)
            if dd_.month == 12 and dd_.day == 31:
                fim_ano[dd_.year] = eq
            d += 1
        relogio[0] = ate

    def fechar(ate):
        nonlocal eq, pico, dd
        resto = []
        for p in sorted(abertas):
            if p[0] < ate:
                render(p[0])
                apurar(p[0])
                resultado = p[2] * p[3] - 2 * corretagem
                custos["corretagem"] += 2 * corretagem
                eq += resultado
                d = datetime.date.fromordinal(p[0])
                m = meses.setdefault((d.year, d.month), [0.0, 0.0])
                m[0] += max(0.0, p[4] + p[2] * p[3])     # valor da venda
                m[1] += resultado
                curva.append((p[0], eq))
                pico = max(pico, eq)
                dd = max(dd, (pico - eq) / pico)
            else:
                resto.append(p)
        abertas[:] = resto

    for dia in sorted(por_dia):
        fechar(dia)
        render(dia)
        cands = por_dia[dia]
        if ordem == "mom":
            cands.sort(key=lambda o: -o["mom"] if o["setup_lado"] > 0 else o["mom"])
        elif ordem == "baixa_vol":
            cands.sort(key=lambda o: o["atr_pct"])
        else:
            rng.shuffle(cands)
        for op in cands:
            if len(abertas) >= max_pos:
                break
            if any(p[1] == op["symbol"] for p in abertas) or op["risco_pct"] <= 0:
                continue
            risco_rs = eq * risco
            nocional = risco_rs / op["risco_pct"]
            teto = eq / max_pos
            if nocional > teto:
                nocional, risco_rs = teto, teto * op["risco_pct"]
            abertas.append((op["saida"], op["symbol"], risco_rs, op["R"], nocional))
            feitas.append(op)
    fechar(10 ** 9)
    if fim:
        render(fim)
        apurar(fim + 40)
    if not feitas and not cdi:
        return {"operacoes": 0}
    d0 = datetime.date.fromordinal(inicio or feitas[0]["entrada"])
    d1 = datetime.date.fromordinal(fim or max(o["saida"] for o in feitas))
    anos = max((d1 - d0).days / 365.25, 0.1)
    por_ano = {}
    for dia, v in curva:
        if not dia:
            continue
        por_ano[datetime.date.fromordinal(dia).year] = v
    for a, v in fim_ano.items():
        por_ano[a] = v
    por_ano[d1.year] = eq
    ret_ano, ant = {}, capital
    for a in sorted(por_ano):
        ret_ano[a] = round(por_ano[a] / ant - 1, 4)
        ant = por_ano[a]
    n = len(feitas) or 1
    return {"operacoes": len(feitas), "acerto": round(sum(1 for o in feitas if o["R"] > 0) / n, 4),
            "R_medio": round(sum(o["R"] for o in feitas) / n, 4), "final": round(eq, 2),
            "custos": {k: round(v, 2) for k, v in custos.items()},
            "retorno_total": round(eq / capital - 1, 4), "cdi_no_caixa": round(rendeu[0] / capital, 4), "cagr": round((eq / capital) ** (1 / anos) - 1, 4),
            "max_drawdown": round(dd, 4), "anos_positivos": sum(1 for r in ret_ano.values() if r > 0),
            "anos": len(ret_ano), "retorno_por_ano": ret_ano, "inicio": d0.isoformat(), "fim": d1.isoformat()}
