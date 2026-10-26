"""Simulação de carteira para o b3-backtest: transforma operações em R numa
curva de patrimônio realista.

  - no máximo `max_pos` posições ao mesmo tempo e um ativo por vez;
  - risco por operação = `risco` do patrimônio realizado na entrada;
  - tamanho limitado a patrimônio / max_pos por posição (sem alavancagem);
  - quando há mais sinais do que vagas no mesmo pregão, a ordem decide:
    "mom" (maior retorno de 126 pregões), "baixa_vol" (menor ATR %),
    "aleatorio" (sorteio fixo, referência);
  - "regime": só entra comprado com o Ibovespa acima da MM200 e vendido abaixo.
"""

import datetime
import random


def taxa_cdi(cdi, ordinal):
    """Taxa diária (dias corridos) do mês do `ordinal`, a partir de {(ano, mes): % ao mês}."""
    d = datetime.date.fromordinal(ordinal)
    m = cdi.get((d.year, d.month))
    return 0.0 if m is None else (1 + m / 100.0) ** (12 / 365.25) - 1


def simular(ops, max_pos=5, risco=0.01, ordem="mom", regime=False, capital=100000.0, seed=7, cdi=None):
    rng = random.Random(seed)
    por_dia = {}
    for op in ops:
        if regime and op["reg"] != (1 if op["setup_lado"] > 0 else -1):
            continue
        por_dia.setdefault(op["entrada"], []).append(op)
    eq = capital
    abertas = []                 # (saida, symbol, risco_rs, R, nocional)
    curva = [(min(por_dia) if por_dia else 0, eq)]
    feitas = []
    pico, dd = eq, 0.0
    relogio = [min(por_dia) if por_dia else 0]
    rendeu = [0.0]

    def render(ate):
        """CDI sobre o caixa livre (patrimônio menos o nocional das posições) até `ate`."""
        nonlocal eq
        if not cdi or ate <= relogio[0]:
            return
        livre = max(0.0, eq - sum(p[4] for p in abertas))
        d = relogio[0]
        while d < ate:
            ganho = livre * taxa_cdi(cdi, d)
            eq += ganho
            livre += ganho
            rendeu[0] += ganho
            d += 1
        relogio[0] = ate

    def fechar(ate):
        nonlocal eq, pico, dd
        resto = []
        for p in sorted(abertas):
            if p[0] < ate:
                render(p[0])
                eq += p[2] * p[3]
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
    if not feitas:
        return {"operacoes": 0}
    d0 = datetime.date.fromordinal(feitas[0]["entrada"])
    d1 = datetime.date.fromordinal(max(o["saida"] for o in feitas))
    anos = max((d1 - d0).days / 365.25, 0.1)
    por_ano, ultimo = {}, (d0.year - 1, capital)
    for dia, v in curva:
        if not dia:
            continue
        por_ano[datetime.date.fromordinal(dia).year] = v
    ret_ano, ant = {}, capital
    for a in sorted(por_ano):
        ret_ano[a] = round(por_ano[a] / ant - 1, 4)
        ant = por_ano[a]
    return {"operacoes": len(feitas), "acerto": round(sum(1 for o in feitas if o["R"] > 0) / len(feitas), 4),
            "R_medio": round(sum(o["R"] for o in feitas) / len(feitas), 4),
            "retorno_total": round(eq / capital - 1, 4), "cdi_no_caixa": round(rendeu[0] / capital, 4), "cagr": round((eq / capital) ** (1 / anos) - 1, 4),
            "max_drawdown": round(dd, 4), "anos_positivos": sum(1 for r in ret_ano.values() if r > 0),
            "anos": len(ret_ano), "retorno_por_ano": ret_ano, "inicio": d0.isoformat(), "fim": d1.isoformat()}
