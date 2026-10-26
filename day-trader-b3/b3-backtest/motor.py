"""Motor de backtest do swing trade (comprado e vendido) para o b3-backtest.
Só biblioteca padrão; usa multiprocessamento.

Regras, iguais às do b3-swing:
  sinal    setup do b3-scanner no fechamento do pregão i (mesmas fórmulas)
  entrada  gatilho: no pregão i+1, se a máxima passar da máxima de i (compra)
           ou a mínima passar da mínima de i (venda); preço = o pior entre a
           abertura e o gatilho. abertura: na abertura de i+1.
  stop     swing:N (mínima/máxima dos últimos N pregões) ou atr:K (ATR 14)
  alvo     múltiplo de R, ou sem alvo (sai no prazo)
  saída    gap além do stop/alvo executa na abertura; no mesmo pregão o stop
           vem antes do alvo; no pregão de entrada por gatilho só o stop
           conta (não dá para saber a ordem); senão sai no fechamento do
           último pregão do prazo.
  custos   CUSTO (emolumentos e corretagem) sobre entrada e saída, SLIP
           (escorregamento) nas ordens stop, aluguel no vendido.
  sem sobreposição: um ativo só tem uma operação aberta por combinação.

Preços ajustados por proventos (o vendido paga os dividendos).
"""

import math
import multiprocessing
import os
from collections import defaultdict

import dados

CUSTO = 0.0003          # 0,03% por perna
SLIP = 0.0005           # 0,05% de escorregamento nas ordens stop
ALUGUEL_AA = 0.02       # 2% a.a. para quem está vendido
MIN_VOL_FIN = 5e6       # média de 20 pregões
MIN_PRECO = 1.0
TICK = 0.0005           # gatilho e stop swing a 0,05% além da máxima/mínima

SETUPS = {"rompimento_20d": 1, "bandeira_alta": 1, "retomou_mm20": 1, "sobrevendido": 1, "repique": 1,
          "perdeu_20d": -1, "bandeira_baixa": -1, "perdeu_mm20": -1, "sobrecomprado": -1, "repique_baixa": -1}
ENTRADAS = ("gatilho", "abertura")
STOPS = (("swing", 3), ("swing", 5), ("swing", 10), ("atr", 1.5), ("atr", 2.0), ("atr", 3.0))
ALVOS = (1.0, 1.5, 2.0, 3.0, None)
PRAZOS = (5, 10, 15, 20, 30)
FILTROS = ("nenhum", "tendencia", "regime", "ambos")
PADRAO = ("gatilho", ("swing", 5), 2.0, 15, "nenhum")   # parâmetros atuais da skill

DADOS = {}      # preenchido antes do fork: {sym: preparado}


# ---------------------------------------------------------------- preparação

def _ifr(c, n=14):
    out = [None] * len(c)
    if len(c) <= n:
        return out
    g = [max(0.0, c[i] - c[i - 1]) for i in range(1, len(c))]
    p = [max(0.0, c[i - 1] - c[i]) for i in range(1, len(c))]
    mg, mp = sum(g[:n]) / n, sum(p[:n]) / n
    out[n] = 100 - 100 / (1 + mg / mp) if mp else 100.0
    for i in range(n, len(g)):
        mg = (mg * (n - 1) + g[i]) / n
        mp = (mp * (n - 1) + p[i]) / n
        out[i + 1] = 100 - 100 / (1 + mg / mp) if mp else 100.0
    return out


def _media(x, n):
    out, s = [None] * len(x), 0.0
    for i, v in enumerate(x):
        s += v
        if i >= n:
            s -= x[i - n]
        if i >= n - 1:
            out[i] = s / n
    return out


def regime_ibov(ibov):
    """{ordinal: +1 acima da MM200, -1 abaixo}."""
    mm = _media(ibov["c"], 200)
    return {d: (1 if c > m else -1) for d, c, m in zip(ibov["d"], ibov["c"], mm) if m}


def preparar(tk, regime):
    c, o, h, l, v, d = tk["c"], tk["o"], tk["h"], tk["l"], tk["v"], tk["d"]
    n = len(c)
    ifr = _ifr(c)
    mm20 = _media(c, 20)
    mm200 = _media(c, 200)
    tr = [h[0] - l[0]] + [max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])) for i in range(1, n)]
    atr = [None] + _media(tr[1:], 14)        # média simples dos 14 últimos TR, como no b3-swing
    vf = _media([ci * vi for ci, vi in zip(c, v)], 20)
    sinais = defaultdict(list)
    reg_ult = 0
    tend, reg = [0] * n, [0] * n
    for i in range(n):
        reg_ult = regime.get(d[i], reg_ult)
        reg[i] = reg_ult
        if mm200[i]:
            tend[i] = 1 if c[i] > mm200[i] else -1
        if i < 30 or not vf[i] or vf[i] < MIN_VOL_FIN or c[i] < MIN_PRECO or ifr[i - 1] is None:
            continue
        ult = c[i]
        max20, min20 = max(c[i - 20:i]), min(c[i - 20:i])
        mm, mm_ant = mm20[i], mm20[i - 1]
        alta = c[i - 5] / c[i - 15] - 1
        janela = c[i - 4:i + 1]
        faixa5 = (max(janela) - min(janela)) / ult
        r, r_ant = ifr[i], ifr[i - 1]
        if ult > max20:
            sinais["rompimento_20d"].append(i)
        if alta > 0.10 and faixa5 < 0.05:
            sinais["bandeira_alta"].append(i)
        if c[i - 1] < mm_ant and ult > mm:
            sinais["retomou_mm20"].append(i)
        if r < 30:
            sinais["sobrevendido"].append(i)
        if r_ant < 30 and ult > c[i - 1]:
            sinais["repique"].append(i)
        if ult < min20:
            sinais["perdeu_20d"].append(i)
        if alta < -0.10 and faixa5 < 0.05:
            sinais["bandeira_baixa"].append(i)
        if c[i - 1] > mm_ant and ult < mm:
            sinais["perdeu_mm20"].append(i)
        if r > 70:
            sinais["sobrecomprado"].append(i)
        if r_ant > 70 and ult < c[i - 1]:
            sinais["repique_baixa"].append(i)
    return {"symbol": tk["symbol"], "c": c, "o": o, "h": h, "l": l, "d": d, "atr": atr,
            "tend": tend, "reg": reg, "sinais": dict(sinais)}


def carregar_universo(syms, base=None, log=None):
    ibov = dados.carregar(dados.IBOV, base)
    regime = regime_ibov(ibov)
    out = {}
    for s in syms:
        try:
            out[s] = preparar(dados.carregar(s, base), regime)
        except (OSError, ValueError, KeyError):
            if log:
                log("  sem histórico: %s" % s)
    return out, ibov


# ---------------------------------------------------------------- simulação

def simular_sinal(t, i, s, entrada, stop):
    """Para um sinal: {(alvo, prazo): (indice_saida, R)} ou None se não entrou."""
    o, h, l, c, n = t["o"], t["h"], t["l"], t["c"], len(t["c"])
    k = i + 1
    if k >= n:
        return None
    if entrada == "gatilho":
        gat = h[i] * (1 + TICK) if s > 0 else l[i] * (1 - TICK)
        if (h[k] < gat) if s > 0 else (l[k] > gat):
            return None
        e = max(o[k], gat) if s > 0 else min(o[k], gat)
        slip_e = SLIP * e
    else:
        e, slip_e = o[k], 0.0
    tipo, p = stop
    if tipo == "swing":
        a0 = max(0, i - int(p) + 1)
        st = min(l[a0:i + 1]) * (1 - TICK) if s > 0 else max(h[a0:i + 1]) * (1 + TICK)
    else:
        if not t["atr"][i]:
            return None
        st = e - s * p * t["atr"][i]
    risco = s * (e - st)
    if risco <= e * 0.001:
        return None
    ult = min(n - 1, k + max(PRAZOS) - 1)
    # dia (relativo à entrada) e preço do stop
    sd, spx = None, None
    for j in range(k, ult + 1):
        if j > k and ((o[j] <= st) if s > 0 else (o[j] >= st)):
            sd, spx = j - k, o[j]
            break
        if (l[j] <= st) if s > 0 else (h[j] >= st):
            sd, spx = j - k, st
            break
    out = {}
    inicio = 1 if entrada == "gatilho" else 0
    for A in ALVOS:
        ad = apx = None
        if A is not None:
            a = e + s * A * risco
            fim = ult if sd is None else k + sd
            for j in range(k + inicio, fim + 1):
                if j > k and ((o[j] >= a) if s > 0 else (o[j] <= a)):
                    ad, apx = j - k, o[j]
                    break
                if (h[j] >= a) if s > 0 else (l[j] <= a):
                    if sd is not None and j - k == sd:
                        break            # mesmo pregão do stop: o stop vem antes
                    ad, apx = j - k, a
                    break
        for P in PRAZOS:
            lim = P - 1
            if k + lim > n - 1:
                continue                 # operação ainda não terminou nos dados
            if ad is not None and ad <= lim:
                dia, px, slip_s = ad, apx, 0.0
            elif sd is not None and sd <= lim:
                dia, px, slip_s = sd, spx, SLIP * spx
            else:
                dia, px, slip_s = lim, c[k + lim], 0.0
            R = s * (px - e) / risco - (CUSTO * (e + px) + slip_e + slip_s) / risco
            if s < 0:
                R -= e * ALUGUEL_AA / 252.0 * (dia + 1) / risco
            out[(A, P)] = (k + dia, R, dia + 1)
    return out


def passa(t, i, s, filtro):
    if filtro == "nenhum":
        return True
    ok_t = t["tend"][i] == s
    ok_r = t["reg"][i] == s
    return ok_t if filtro == "tendencia" else ok_r if filtro == "regime" else (ok_t and ok_r)


def _vazio():
    return [0, 0.0, 0.0, 0, 0.0, 0.0, 0]   # n, soma R, soma R², vitórias, soma ganhos, soma perdas, pregões


def rodar_setup(setup):
    """Estatísticas por combinação e por ano: {combo: {ano: [..]}}."""
    s = SETUPS[setup]
    stats = defaultdict(lambda: defaultdict(_vazio))
    for t in DADOS.values():
        idx = t["sinais"].get(setup) or []
        if not idx:
            continue
        anos = {}
        for entrada in ENTRADAS:
            for stop in STOPS:
                sims = [(i, simular_sinal(t, i, s, entrada, stop)) for i in idx]
                sims = [(i, r) for i, r in sims if r]
                for filtro in FILTROS:
                    sel = [(i, r) for i, r in sims if passa(t, i, s, filtro)]
                    for A in ALVOS:
                        for P in PRAZOS:
                            st = stats[(entrada, stop, A, P, filtro)]
                            livre = -1
                            for i, r in sel:
                                res = r.get((A, P))
                                if res is None or i < livre:
                                    continue
                                saida, R, dias = res
                                livre = saida
                                ano = anos.get(i)
                                if ano is None:
                                    ano = anos[i] = _ano(t["d"][i])
                                x = st[ano]
                                x[0] += 1
                                x[1] += R
                                x[2] += R * R
                                if R > 0:
                                    x[3] += 1
                                    x[4] += R
                                else:
                                    x[5] -= R
                                x[6] += dias
    return setup, {k: dict(v) for k, v in stats.items()}


def operacoes(setup, combo):
    """Lista de operações de uma combinação: (data_entrada, data_saida, ativo, R)."""
    s = SETUPS[setup]
    entrada, stop, A, P, filtro = combo
    out = []
    for t in DADOS.values():
        livre = -1
        for i in t["sinais"].get(setup) or []:
            if i < livre or not passa(t, i, s, filtro):
                continue
            r = simular_sinal(t, i, s, entrada, stop)
            res = r and r.get((A, P))
            if not res:
                continue
            saida, R, dias = res
            livre = saida
            c = t["c"]
            out.append({"entrada": t["d"][i + 1], "saida": t["d"][saida], "symbol": t["symbol"], "R": R,
                        "dias": dias, "setup": setup, "reg": t["reg"][i], "tend": t["tend"][i],
                        "mom": c[i] / c[i - 126] - 1 if i >= 126 else 0.0,
                        "atr_pct": (t["atr"][i] or 0) / c[i], "risco_pct": _risco_pct(t, i, s, entrada, stop)})
    out.sort(key=lambda x: (x["entrada"], x["symbol"]))
    return out


def _risco_pct(t, i, s, entrada, stop):
    """Distância até o stop como fração do preço de entrada (para dimensionar na carteira)."""
    h, l, o = t["h"], t["l"], t["o"]
    k = i + 1
    e = (max(o[k], h[i] * (1 + TICK)) if s > 0 else min(o[k], l[i] * (1 - TICK))) if entrada == "gatilho" else o[k]
    tipo, p = stop
    if tipo == "swing":
        a0 = max(0, i - int(p) + 1)
        st = min(l[a0:i + 1]) * (1 - TICK) if s > 0 else max(h[a0:i + 1]) * (1 + TICK)
    else:
        st = e - s * p * t["atr"][i]
    return s * (e - st) / e


_ANOS = {}


def _ano(ordinal):
    a = _ANOS.get(ordinal)
    if a is None:
        import datetime
        a = _ANOS[ordinal] = datetime.date.fromordinal(ordinal).year
    return a


def rodar_todos(setups, processos=None):
    processos = processos or max(1, (os.cpu_count() or 2))
    ctx = multiprocessing.get_context("fork")
    with ctx.Pool(processos) as pool:
        return dict(pool.map(rodar_setup, setups))


# ---------------------------------------------------------------- métricas

def somar(por_ano, anos):
    x = _vazio()
    for a in anos:
        y = por_ano.get(a)
        if y:
            for j in range(7):
                x[j] += y[j]
    return x


def metricas(x):
    n = x[0]
    if not n:
        return {"n": 0}
    media = x[1] / n
    var = max(0.0, x[2] / n - media * media)
    dp = math.sqrt(var * n / (n - 1)) if n > 1 else 0.0
    return {"n": n, "R_medio": round(media, 4), "acerto": round(x[3] / n, 4),
            "fator_lucro": round(x[4] / x[5], 3) if x[5] else None, "R_total": round(x[1], 2),
            "t": round(media / dp * math.sqrt(n), 2) if dp else None, "pregoes_medios": round(x[6] / n, 1),
            "R_por_pregao": round(x[1] / x[6], 4) if x[6] else None}
