"""Analista gratuito por regras: análise do dia sem modelo de linguagem, sem chave, sem custo.

Usa só os dados quantitativos do painel e a evidência dos estudos de 10 anos:
  - regime de mercado (Ibovespa x MMS200) e custo de oportunidade (CDI);
  - sinais do scanner com evidência positiva (setups comprados de tendência);
  - carteira de dividendos (fator mais consistente) sem armadilhas de DY;
  - convergência com o consenso de analistas;
  - alertas de reversão, risco e concentração da carteira.
Devolve o mesmo formato da IA (resumo, regime, postura, oportunidades, alertas, riscos).
"""
from __future__ import annotations


def _pct(v, casas=1):
    return "—" if v is None else f"{v * 100:+.{casas}f}%".replace(".", ",")


def analisar(ctx: dict) -> dict:
    m = ctx.get("mercado", {})
    cart = ctx.get("carteira", {})
    acima = m.get("ibov_acima_mm200")
    dist = m.get("ibov_dist_mm200") or 0
    cdi = m.get("cdi_aa") or 0
    regime = "alta" if acima and dist > 0.03 else "baixa" if not acima and dist < -0.03 else "lateral"

    cdi_txt = f"{cdi * 100:.1f}".replace(".", ",")
    resumo = (f"Ibovespa {_pct(dist)} em relação à média de 200 dias ({'acima' if acima else 'abaixo'}), "
              f"{_pct(m.get('ibov_12m'))} em 12 meses. CDI em {cdi_txt}% a.a.")
    if regime == "baixa":
        resumo += " Mercado em tendência de baixa: no estudo, setups comprados de tendência rendem menos nesse regime."
        postura = ("Defensiva: exposição reduzida, priorizar a carteira de dividendos e só entradas com evidência "
                   "positiva e stop curto. Caixa no CDI é uma opção competitiva.")
    elif regime == "alta":
        resumo += " Tendência primária de alta favorece setups comprados de tendência (MACD, médias, rompimentos)."
        postura = "Construtiva: seguir sinais de tendência com evidência positiva e manter stops/trailing ativos."
    else:
        resumo += " Mercado sem direção definida perto da média de 200 dias."
        postura = "Neutra: posições menores, preferência por dividendos e confirmação antes de entrar."
    if cdi >= 0.12:
        postura += f" Com CDI de {cdi_txt}% a.a., só vale risco com assimetria clara."

    # ------------------------------------------------------------- oportunidades
    consenso = {c["ticker"]: c for c in ctx.get("consenso_top", [])}
    ops = []
    for o in ctx.get("scanner_oportunidades", []):
        ev = o.get("evidencia") or {}
        exc = ev.get("excesso_cdi_aa")
        if o.get("direcao") != "Compra" or exc is None or exc <= 0:
            continue
        cons = consenso.get(o["ticker"])
        consistente = (ev.get("metade1") or 0) > 0 and (ev.get("metade2") or 0) > 0
        pontos = (1 if consistente else 0) + (1 if o.get("acima_mm200") else 0) + (1 if cons and (cons.get("nota_media") or 9) <= 2.5 else 0)
        conf = "alta" if pontos >= 3 else "media" if pontos == 2 else "baixa"
        tese = f"{o['setup']}: {o['gatilho']}."
        if cons:
            tese += f" Consenso dos analistas: {cons['recomendacao']} (potencial {_pct(cons.get('upside'))})."
        if not o.get("acima_mm200"):
            tese += " Atenção: ativo abaixo da MMS200 (contra a tendência primária)."
        ops.append({
            "ticker": o["ticker"], "direcao": "Compra", "estrategia": o["setup"], "tese": tese,
            "entrada": o["entrada"], "stop": o["stop"], "saida": o["saida"], "risco_pct": o.get("risco_pct") or 0,
            "confianca": conf,
            "evidencia": f"{_pct(exc)} a.a. acima do CDI em 10 anos"
                         + (" (positivo nas duas metades)" if consistente else " (inconsistente entre períodos)"),
            "_ordem": pontos + exc * 10,
        })
    for a in ctx.get("ranking_resumido", []):
        if not a.get("top_dividendos") or a.get("alerta_dy") or a["ticker"] in {x["ticker"] for x in ops}:
            continue
        cons = consenso.get(a["ticker"])
        if not cons or (cons.get("nota_media") or 9) > 2.5:
            continue
        preco = a["preco"]
        stop = round(preco * (1 - max(0.08, (a.get("vol_anual") or 0.3) / 3)), 2)
        ops.append({
            "ticker": a["ticker"], "direcao": "Compra", "estrategia": "Carteira de dividendos",
            "tese": f"Top 10 em dividend yield ({_pct(a.get('dy_12m'), 1)} em 12 meses) com consenso "
                    f"{cons['recomendacao']} e potencial {_pct(cons.get('upside'))}.",
            "entrada": preco, "stop": stop, "saida": "Sai do top 10 no rebalanceamento mensal ou alerta de reversão",
            "risco_pct": round(1 - stop / preco, 4), "confianca": "media",
            "evidencia": "Fator mais consistente no estudo: acima do CDI nas duas metades (2016–21 e 2021–26)",
            "_ordem": 2.5,
        })
    ops.sort(key=lambda x: -x.pop("_ordem"))
    ops = ops[:5]

    # ------------------------------------------------------------- alertas e riscos
    alertas = []
    for al in ctx.get("alertas", []):
        if al.get("nivel") == "SAIR":
            alertas.append(f"{al['ticker']}: reversão de tendência ({'; '.join(al['sinais'][:3])}) — considere sair.")
        elif al.get("nivel") == "ATENÇÃO":
            alertas.append(f"{al['ticker']}: tendência enfraquecendo ({'; '.join(al['sinais'][:2])}).")
    for p in cart.get("posicoes", []):
        if not p.get("stop_enviado"):
            alertas.append(f"{p['ticker']}: posição sem stop registrado na Clear.")
    if cart.get("kill_switch"):
        alertas.append("Kill switch ativo: perda máxima atingida, novas entradas bloqueadas.")
    if (cart.get("risco_aberto_pct") or 0) > 0.05:
        alertas.append(f"Risco aberto alto: {_pct(cart['risco_aberto_pct'])} do patrimônio até os stops.")

    riscos = []
    if regime == "baixa":
        riscos.append("Regime de baixa: rompimentos falham com mais frequência; reduza o tamanho das posições.")
    armadilhas = [a["ticker"] for a in ctx.get("ranking_resumido", []) if a.get("alerta_dy")]
    if armadilhas:
        riscos.append(f"Possíveis armadilhas de dividendos (queda > 30% desde a máxima de 6 meses): {', '.join(armadilhas)}.")
    if cdi >= 0.12:
        riscos.append("Custo de oportunidade elevado: o CDI superou a maioria dos setups de swing desde 2021.")
    riscos.append("Sinais técnicos não garantem resultado; respeite stop e tamanho de posição.")

    return {"resumo_mercado": resumo, "regime": regime, "postura_recomendada": postura,
            "oportunidades": ops, "alertas_carteira": alertas, "riscos": riscos,
            "modelo": "Analista por regras (gratuito, local)"}


def responder(pergunta: str, ctx: dict) -> str:
    """Assistente sem modelo de linguagem: responde sobre ativos citados e temas frequentes."""
    import re
    texto = pergunta.upper()
    tickers = sorted(set(re.findall(r"\b[A-Z]{4}(?:3|4|5|6|11)\b", texto)))
    rk = {a["ticker"]: a for a in ctx.get("ranking_resumido", [])}
    rk.update({a["ticker"]: a for a in ctx.get("ranking_completo", [])})
    cons = {c["ticker"]: c for c in ctx.get("consenso_top", [])}
    alert = {a["ticker"]: a for a in ctx.get("alertas", [])}
    scan = [o for o in ctx.get("scanner_oportunidades", [])]
    linhas = []
    for t in tickers:
        partes = [f"• {t}"]
        a = rk.get(t)
        if a:
            partes.append(f"preço {a['preco']}, DY 12m {_pct(a.get('dy_12m'))}, momentum 12-1 {_pct(a.get('momentum_12_1'))}"
                          + (", ⚠️ possível armadilha de DY" if a.get("alerta_dy") else ""))
        c = cons.get(t)
        if c:
            partes.append(f"consenso {c['recomendacao']} ({c['analistas']} analistas), alvo médio {c['alvo_medio']} ({_pct(c.get('upside'))})")
        s = [o for o in scan if o["ticker"] == t]
        if s:
            partes.append("sinais hoje: " + "; ".join(f"{o['setup']} ({o['direcao']})" for o in s))
        al = alert.get(t)
        if al:
            partes.append(f"tendência: {al['nivel']} — {'; '.join(al['sinais'][:3]) or 'intacta'}")
        linhas.append(" | ".join(partes) if len(partes) > 1 else f"• {t}: sem dados no painel (fora do universo de 44 ações).")
    if not linhas:
        r = analisar(ctx)
        linhas = [f"Mercado ({r['regime']}): {r['resumo_mercado']}", f"Postura: {r['postura_recomendada']}"]
        if r["oportunidades"]:
            linhas.append("Melhores ideias agora: " + ", ".join(f"{o['ticker']} ({o['estrategia']})" for o in r["oportunidades"]))
        if r["alertas_carteira"]:
            linhas.append("Alertas: " + " ".join(r["alertas_carteira"]))
        linhas.append("Dica: cite um ticker (ex.: PETR4) para ver o diagnóstico completo. Para conversa livre, ative o Ollama (gratuito).")
    return "\n".join(linhas)
