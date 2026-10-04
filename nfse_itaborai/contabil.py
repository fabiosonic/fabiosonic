"""Relatórios contábeis e financeiros no padrão profissional: DRE estruturada, indicadores, livro caixa e fluxo de caixa.

A DRE segue o regime tributário da empresa (Configurações › Regras fiscais):
- MEI: DAS-MEI de valor fixo mensal (INSS + ISS), sem outras deduções;
- Simples Nacional: DAS pela alíquota efetiva do Anexo III + ISS (estrutura abaixo);
- Lucro Presumido: PIS 0,65% e COFINS 3% (cumulativos) + ISS; IRPJ (15% + adicional de 10%) e CSLL (9%) sobre a
  base presumida (32% para serviços, configurável);
- Lucro Real: PIS 1,65% e COFINS 7,6% (não cumulativos, sem créditos — estimativa conservadora) + ISS; IRPJ e CSLL
  sobre o lucro antes dos tributos.

DRE (regime de competência, Lei 6.404/76 art. 187 e NBC TG 26):
  RECEITA OPERACIONAL BRUTA
  (−) Deduções da receita: Simples Nacional (DAS) e ISS
  (=) RECEITA OPERACIONAL LÍQUIDA
  (−) Despesas operacionais por grupo (pessoal, ocupação, administrativas, tributárias)
  (=) RESULTADO OPERACIONAL
  (−) Despesas financeiras
  (=) RESULTADO LÍQUIDO DO PERÍODO
O DAS é deduzido pela alíquota efetiva do Anexo III sobre a receita do mês; por isso, pagamentos de DAS/ISS lançados
como despesa (vindos do extrato) NÃO entram de novo nas despesas operacionais — evita a dupla dedução.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, timedelta

from . import config, db, financeiro, relatorios

# Plano de despesas por natureza (CPC 26 / NBC TG 26, item 102), na ordem em que aparecem na DRE.
# Os nomes antigos (Folha, Encargos, Benefícios, Energia/Internet, Material, Impostos, Taxas…) continuam valendo.
GRUPOS = {
    "Despesas com pessoal": ["Folha", "Pró-labore", "Férias e 13º salário", "Rescisões", "Encargos", "INSS patronal",
                             "FGTS", "Vale-transporte", "Vale-refeição/alimentação", "Plano de saúde", "Benefícios",
                             "Estagiários", "Treinamento e cursos", "Uniformes e EPI", "Confraternizações"],
    "Despesas de ocupação": ["Aluguel", "Condomínio", "IPTU", "Energia elétrica", "Água e esgoto", "Telefone e internet",
                             "Energia/Internet", "Manutenção e conservação", "Limpeza", "Segurança e monitoramento",
                             "Seguros"],
    "Despesas administrativas": ["Sistemas", "Contador/Assessoria", "Serviços de terceiros", "Assessoria jurídica",
                                 "Certificado digital", "Material", "Material de copa e limpeza", "Correios e cartório",
                                 "Viagens e deslocamentos", "Combustível", "Estacionamento e pedágio",
                                 "Conselhos de classe (CRC)", "Associações e sindicatos", "Assinaturas e publicações",
                                 "Equipamentos de pequeno valor", "Doações", "Outras"],
    "Despesas comerciais": ["Marketing", "Propaganda e publicidade", "Brindes", "Comissões", "Representação e eventos"],
    "Despesas tributárias": ["Impostos", "Taxas", "Alvará e taxas municipais", "Contribuição sindical patronal",
                             "Multas fiscais"],
}
FINANCEIRAS = ["Bancárias", "Tarifas", "IOF", "Juros", "Juros e multas por atraso", "Juros de empréstimos",
               "Taxas de cartão"]


def _ordem(grupo: str, itens):
    """Categorias na ordem do plano (as criadas pelo escritório vão para o fim, em ordem alfabética)."""
    plano = FINANCEIRAS if grupo == "financeiras" else GRUPOS.get(grupo, [])
    return sorted(itens, key=lambda kv: (plano.index(kv[0]) if kv[0] in plano else len(plano), kv[0].lower()))
_DEDUCAO = re.compile(r"\b(DAS|SIMPLES|PGDAS|ISS|ISSQN)\b", re.IGNORECASE)
# Presumido/Real: PIS, COFINS, IRPJ e CSLL já estão calculados na DRE; o pagamento (DARF) não entra de novo
_DEDUCAO_REG = re.compile(r"\b(DAS|ISS|ISSQN|PIS|COFINS|IRPJ|CSLL)\b", re.IGNORECASE)
RECEITA_VALIDA = ("emitida", "nao_emitir")


def _grupo(categoria: str) -> str:
    if categoria in FINANCEIRAS:
        return "financeiras"
    return next((g for g, cats in GRUPOS.items() if categoria in cats), "Despesas administrativas")


def _competencia(d: dict) -> str:
    return d.get("competencia") or d["vencimento"][:7]


def _eh_deducao(d: dict, regime: str = "simples") -> bool:
    padrao = _DEDUCAO if regime in ("simples", "mei") else _DEDUCAO_REG
    return d["categoria"] == "Impostos" and bool(padrao.search(f"{d['descricao']} {d.get('fornecedor', '')}"))


def _pct(parte: int, todo: int) -> float:
    return round(parte / todo * 100, 1) if todo else 0.0


# ---------------------------------------------------------------- DRE

def _regime() -> str:
    from . import fiscal
    return fiscal.regime(config.carregar())


def _aliq_iss() -> float:
    from . import servicos
    try:
        return float(str(servicos.padrao().get("aliquota_iss") or 0).replace(",", "."))
    except ValueError:
        return 0.0


def _irpj_csll(base: int, adicional_limite: int = 20_000_00) -> tuple[int, int]:
    """IRPJ 15% + adicional de 10% sobre o que passar de R$ 20 mil/mês; CSLL 9% (bases em centavos)."""
    if base <= 0:
        return 0, 0
    irpj = round(base * 0.15) + round(max(base - adicional_limite, 0) * 0.10)
    return irpj, round(base * 0.09)


def dre(ano: int, em: date | None = None) -> dict:
    em = em or financeiro.hoje()
    cfg = config.carregar()["financeiro"]
    regime = _regime()
    if regime != "simples":
        return _dre_regime(ano, em, regime, cfg)
    ts = relatorios._titulos(em)
    desp = db.linhas("SELECT * FROM despesas WHERE status!='cancelado'")
    meses = [f"{ano}-{m:02d}" for m in range(1, 13)]
    iss_fixo = financeiro.cent(cfg.get("iss_fixo_mensal", 0) or 0)

    receita, das, iss, aliq = [], [], [], []
    for m in meses:
        r = sum(t["valor_cent"] for t in ts if t["competencia"] == m and t["nfse_status"] in RECEITA_VALIDA)
        r12 = relatorios.rbt12(date(int(m[:4]), int(m[5:]), 1), ts)
        a = relatorios.aliquota_efetiva_anexo3(r12) if r12 else float(cfg["aliquota_simples_pct"])
        receita.append(r)
        aliq.append(a)
        das.append(round(r * a / 100))
        iss_pago = sum(d["valor_cent"] for d in desp if _competencia(d) == m and _eh_deducao(d)
                       and re.search(r"\bISS", d["descricao"], re.IGNORECASE))
        iss.append(iss_pago or (iss_fixo if r else 0))

    grupos: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(lambda: [0] * 12))
    for d in desp:
        m = _competencia(d)
        if m[:4] != str(ano) or _eh_deducao(d):
            continue
        grupos[_grupo(d["categoria"])][d["categoria"]][int(m[5:]) - 1] += d["valor_cent"]

    linhas: list[dict] = []

    def add(conta, valores, tipo="item", nivel=1, sinal=1):
        linhas.append({"conta": conta, "tipo": tipo, "nivel": nivel, "valores": [v * sinal for v in valores],
                       "total": sum(valores) * sinal})

    soma = lambda *ls: [sum(x) for x in zip(*ls)]  # noqa: E731
    add("RECEITA OPERACIONAL BRUTA", receita, "grupo", 0)
    add("Prestação de serviços", receita)
    deducoes = soma(das, iss)
    add("(−) DEDUÇÕES DA RECEITA BRUTA", deducoes, "grupo", 0, -1)
    add("Simples Nacional (DAS estimado)", das, sinal=-1)
    add("ISS", iss, sinal=-1)
    liquida = [r - d for r, d in zip(receita, deducoes)]
    add("(=) RECEITA OPERACIONAL LÍQUIDA", liquida, "total", 0)
    total_oper = [0] * 12
    for g in GRUPOS:
        if g not in grupos:
            continue
        vg = soma(*grupos[g].values())
        total_oper = soma(total_oper, vg)
        add(f"(−) {g.upper()}", vg, "grupo", 0, -1)
        for cat, v in _ordem(g, grupos[g].items()):
            add(cat, v, sinal=-1)
    oper = [l - d for l, d in zip(liquida, total_oper)]
    add("(=) RESULTADO OPERACIONAL", oper, "total", 0)
    fin = soma(*grupos["financeiras"].values()) if "financeiras" in grupos else [0] * 12
    add("(−) DESPESAS FINANCEIRAS", fin, "grupo", 0, -1)
    for cat, v in _ordem("financeiras", grupos.get("financeiras", {}).items()):
        add(cat, v, sinal=-1)
    liquido = [o - f for o, f in zip(oper, fin)]
    add("(=) RESULTADO LÍQUIDO DO PERÍODO", liquido, "resultado", 0)

    rb = sum(receita)
    for l in linhas:
        l["av"] = _pct(l["total"], rb)
    return {
        "ano": ano, "meses": meses, "linhas": linhas, "aliquotas_das": aliq,
        "resumo": {"receita_bruta": rb, "receita_liquida": sum(liquida), "despesas_operacionais": sum(total_oper),
                   "resultado_operacional": sum(oper), "resultado_liquido": sum(liquido),
                   "margem_operacional": _pct(sum(oper), rb), "margem_liquida": _pct(sum(liquido), rb),
                   "carga_tributaria": _pct(sum(deducoes), rb)},
        "serie": [{"mes": m, "receita_liquida": liquida[i], "despesas": total_oper[i] + fin[i], "resultado": liquido[i]}
                  for i, m in enumerate(meses)],
        "nota": ("DAS pela alíquota efetiva do Anexo III (LC 123/2006) sobre o RBT12 de cada mês"
                 + (", sem a parcela do ISS (ISS fixo — art. 18, § 22-A)" if cfg.get("iss_fixo", True) else "")
                 + ". Pagamentos de DAS/ISS lançados como despesa não são deduzidos de novo."),
    }


def _dre_regime(ano: int, em: date, regime: str, cfg: dict) -> dict:
    """DRE do MEI, do Lucro Presumido e do Lucro Real (o Simples tem a função própria, acima)."""
    ts = relatorios._titulos(em)
    desp = db.linhas("SELECT * FROM despesas WHERE status!='cancelado'")
    meses = [f"{ano}-{m:02d}" for m in range(1, 13)]
    receita = [sum(t["valor_cent"] for t in ts if t["competencia"] == m and t["nfse_status"] in RECEITA_VALIDA)
               for m in meses]
    zeros = [0] * 12
    soma = lambda *ls: [sum(x) for x in zip(*ls)]  # noqa: E731
    deducoes: list[tuple[str, list[int]]] = []
    aliq_iss = _aliq_iss()
    iss = [round(r * aliq_iss / 100) for r in receita]
    if regime == "mei":
        das_mei = financeiro.cent(cfg.get("das_mei_mensal") or 0)
        deducoes.append(("DAS-MEI (INSS + ISS, valor fixo)", [das_mei if r else 0 for r in receita]))
    else:
        p_pis, p_cof = (0.65, 3.0) if regime == "presumido" else (1.65, 7.6)
        deducoes += [(f"PIS ({str(p_pis).replace('.', ',')}%)", [round(r * p_pis / 100) for r in receita]),
                     (f"COFINS ({str(p_cof).replace('.', ',')}%)", [round(r * p_cof / 100) for r in receita]),
                     (f"ISS ({str(aliq_iss).replace('.', ',')}%)", iss)]
    total_ded = soma(*[v for _, v in deducoes]) if deducoes else zeros
    grupos: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(lambda: [0] * 12))
    for d in desp:
        m = _competencia(d)
        if m[:4] != str(ano) or _eh_deducao(d, regime):
            continue
        grupos[_grupo(d["categoria"])][d["categoria"]][int(m[5:]) - 1] += d["valor_cent"]

    linhas: list[dict] = []

    def add(conta, valores, tipo="item", nivel=1, sinal=1):
        linhas.append({"conta": conta, "tipo": tipo, "nivel": nivel, "valores": [v * sinal for v in valores],
                       "total": sum(valores) * sinal})

    add("RECEITA OPERACIONAL BRUTA", receita, "grupo", 0)
    add("Prestação de serviços", receita)
    add("(−) DEDUÇÕES DA RECEITA BRUTA", total_ded, "grupo", 0, -1)
    for nome, v in deducoes:
        add(nome, v, sinal=-1)
    liquida = [r - d for r, d in zip(receita, total_ded)]
    add("(=) RECEITA OPERACIONAL LÍQUIDA", liquida, "total", 0)
    total_oper = zeros
    for g in GRUPOS:
        if g not in grupos:
            continue
        vg = soma(*grupos[g].values())
        total_oper = soma(total_oper, vg)
        add(f"(−) {g.upper()}", vg, "grupo", 0, -1)
        for cat, v in _ordem(g, grupos[g].items()):
            add(cat, v, sinal=-1)
    oper = [l - d for l, d in zip(liquida, total_oper)]
    add("(=) RESULTADO OPERACIONAL", oper, "total", 0)
    fin = soma(*grupos["financeiras"].values()) if "financeiras" in grupos else zeros
    add("(−) DESPESAS FINANCEIRAS", fin, "grupo", 0, -1)
    for cat, v in _ordem("financeiras", grupos.get("financeiras", {}).items()):
        add(cat, v, sinal=-1)
    lair = [o - f for o, f in zip(oper, fin)]
    irpj, csll = zeros, zeros
    if regime in ("presumido", "real"):
        add("(=) RESULTADO ANTES DO IRPJ E DA CSLL", lair, "total", 0)
        if regime == "presumido":
            presuncao = float(str(cfg.get("presuncao_pct") or 32).replace(",", "."))
            bases = [round(r * presuncao / 100) for r in receita]
        else:
            bases = lair
        pares = [_irpj_csll(b) for b in bases]
        irpj, csll = [p[0] for p in pares], [p[1] for p in pares]
        add("(−) PROVISÃO PARA IRPJ E CSLL", soma(irpj, csll), "grupo", 0, -1)
        add("IRPJ (15% + adicional de 10%)", irpj, sinal=-1)
        add("CSLL (9%)", csll, sinal=-1)
    liquido = [a - i - c for a, i, c in zip(lair, irpj, csll)]
    add("(=) RESULTADO LÍQUIDO DO PERÍODO", liquido, "resultado", 0)

    rb = sum(receita)
    for l in linhas:
        l["av"] = _pct(l["total"], rb)
    notas = {
        "mei": "MEI: o DAS-MEI é fixo por mês (Configurações › Financeiro); não há outras deduções sobre a receita.",
        "presumido": f"Lucro Presumido: PIS/COFINS cumulativos; IRPJ e CSLL sobre a base presumida de "
                     f"{cfg.get('presuncao_pct') or 32}% da receita (adicional de IRPJ estimado mês a mês).",
        "real": "Lucro Real: PIS/COFINS não cumulativos sem considerar créditos (estimativa conservadora); IRPJ e CSLL "
                "sobre o resultado do mês (adicional estimado mês a mês). A apuração oficial é do contador.",
    }
    tributos = sum(total_ded) + sum(irpj) + sum(csll)
    return {
        "ano": ano, "meses": meses, "linhas": linhas, "aliquotas_das": [], "regime": regime,
        "resumo": {"receita_bruta": rb, "receita_liquida": sum(liquida), "despesas_operacionais": sum(total_oper),
                   "resultado_operacional": sum(oper), "resultado_liquido": sum(liquido),
                   "margem_operacional": _pct(sum(oper), rb), "margem_liquida": _pct(sum(liquido), rb),
                   "carga_tributaria": _pct(tributos, rb)},
        "serie": [{"mes": m, "receita_liquida": liquida[i], "despesas": total_oper[i] + fin[i], "resultado": liquido[i]}
                  for i, m in enumerate(meses)],
        "nota": notas[regime] + " Pagamentos de tributos lançados como despesa não são deduzidos de novo.",
    }


def carga_sobre_receita_pct(r12: int) -> float:
    """Percentual de tributos que incide sobre a receita (para margem de contribuição e ponto de equilíbrio)."""
    regime = _regime()
    if regime == "simples":
        return relatorios.aliquota_efetiva_anexo3(r12) if r12 else 0
    if regime == "mei":
        return 0.0
    iss = _aliq_iss()
    if regime == "presumido":
        presuncao = float(str(config.carregar()["financeiro"].get("presuncao_pct") or 32).replace(",", "."))
        return round(3.65 + iss + presuncao * 0.24, 2)          # PIS+COFINS + ISS + (IRPJ 15% + CSLL 9%) da base
    return round(9.25 + iss, 2)                                 # Real: PIS+COFINS + ISS (IRPJ/CSLL sobre o lucro)


# ---------------------------------------------------------------- indicadores

def indicadores(em: date | None = None) -> dict:
    em = em or financeiro.hoje()
    ts = relatorios._titulos(em)
    validos = [t for t in ts if t["nfse_status"] in RECEITA_VALIDA]
    m12 = set(relatorios._meses(em, 12))
    m12_ant = set(relatorios._meses(em.replace(day=1) - timedelta(days=365), 12))
    fat12 = sum(t["valor_cent"] for t in validos if t["competencia"] in m12)
    fat12_ant = sum(t["valor_cent"] for t in validos if t["competencia"] in m12_ant)

    pagos = [t for t in ts if t["status"] == "pago" and t["data_pagamento"]]
    peso = sum(t["valor_pago_cent"] for t in pagos)
    atraso_pond = (sum(max((date.fromisoformat(t["data_pagamento"]) - date.fromisoformat(t["vencimento"])).days, 0)
                       * t["valor_pago_cent"] for t in pagos) / peso) if peso else 0
    em_dia = _pct(sum(t["valor_pago_cent"] for t in pagos if t["data_pagamento"] <= t["vencimento"]), peso)

    ini90 = (em - timedelta(days=90)).isoformat()
    fat90 = sum(t["valor_cent"] for t in validos if t["vencimento"] >= ini90 and t["vencimento"] <= em.isoformat())
    aberto = sum(t["valor_cent"] for t in ts if t["status"] == "aberto" and financeiro.tem_cobranca(t))
    dso = round(aberto / (fat90 / 90)) if fat90 else 0
    vencidos90 = [t for t in ts if ini90 <= t["vencimento"] < em.isoformat() and (t["status"] == "pago" or financeiro.tem_cobranca(t))]
    inad90 = _pct(sum(t["valor_cent"] for t in vencidos90 if t["status"] == "aberto"),
                  sum(t["valor_cent"] for t in vencidos90))

    por_cli: dict[str, int] = defaultdict(int)
    nomes: dict[str, str] = {}
    for t in validos:
        if t["competencia"] in m12:
            por_cli[t["cpf_cnpj"]] += t["valor_cent"]
            nomes[t["cpf_cnpj"]] = t["cliente_nome"]
    ranking = sorted(por_cli.items(), key=lambda x: -x[1])
    top = [{"cliente": nomes[d], "valor": v, "pct": _pct(v, fat12)} for d, v in ranking[:10]]
    acum, curva = 0, []
    for i, (_, v) in enumerate(ranking, 1):
        acum += v
        curva.append(_pct(acum, fat12))
    classe_a = next((i for i, p in enumerate(curva, 1) if p >= 80), len(curva))

    recentes = set(relatorios._meses(em, 2))
    anteriores = set(relatorios._meses(em, 6)) - recentes
    ativos_ant = {t["cpf_cnpj"] for t in validos if t["competencia"] in anteriores}
    ativos_rec = {t["cpf_cnpj"] for t in validos if t["competencia"] in recentes}
    perdidos = sorted(nomes.get(d) or d for d in ativos_ant - ativos_rec)

    d3 = db.linhas("SELECT * FROM despesas WHERE status!='cancelado'")
    meses3 = set(relatorios._meses(em.replace(day=1) - timedelta(days=1), 3))
    fixas = sum(d["valor_cent"] for d in d3 if _competencia(d) in meses3 and not _eh_deducao(d)) / 3
    r12 = relatorios.rbt12(em, ts)
    aliq = carga_sobre_receita_pct(r12)
    margem_contrib = 1 - aliq / 100
    equilibrio = round(fixas / margem_contrib) if margem_contrib > 0 else 0
    receita_mes_media = round(fat12 / 12)
    contratos = db.linhas("SELECT valor_cent FROM contratos WHERE ativo=1 AND confirmado=1")
    return {
        "faturamento_12m": fat12, "faturamento_12m_anterior": fat12_ant,
        "crescimento_pct": _pct(fat12 - fat12_ant, fat12_ant) if fat12_ant else None,
        "receita_media_mensal": receita_mes_media, "ticket_medio": round(fat12 / max(1, sum(
            1 for t in validos if t["competencia"] in m12))),
        "atraso_medio_ponderado": round(atraso_pond, 1), "recebido_em_dia_pct": em_dia,
        "dias_a_receber": dso, "inadimplencia_90d": inad90,
        "concentracao_top5": round(sum(x["pct"] for x in top[:5]), 1), "clientes_classe_a": classe_a,
        "clientes_ativos": len(ativos_rec), "clientes_perdidos": perdidos,
        "despesa_media_mensal": round(fixas), "ponto_equilibrio": equilibrio,
        "folga_equilibrio_pct": _pct(receita_mes_media - equilibrio, receita_mes_media),
        "mrr": sum(c["valor_cent"] for c in contratos), "top_clientes": top,
    }


# ---------------------------------------------------------------- livro caixa e fluxo

def livro_caixa(inicio: str, fim: str) -> dict:
    """Movimentação realizada (regime de caixa) em ordem cronológica, com saldo acumulado."""
    mov = [{"data": t["data_pagamento"], "historico": f"Recebimento — {t['cliente_nome']} ({t['competencia'][5:]}/"
            f"{t['competencia'][:4]})", "documento": f"NFS-e {t['nfse_numero']}" if t["nfse_numero"] else f"Título {t['id']}",
            "entrada": t["valor_pago_cent"], "saida": 0}
           for t in db.linhas("SELECT * FROM titulos WHERE status='pago' AND data_pagamento BETWEEN ? AND ?", (inicio, fim))]
    mov += [{"data": d["data_pagamento"], "historico": f"{d['descricao']}" + (f" — {d['fornecedor']}" if d["fornecedor"] else ""),
             "documento": d["categoria"], "entrada": 0, "saida": d["valor_cent"]}
            for d in db.linhas("SELECT * FROM despesas WHERE status='pago' AND data_pagamento BETWEEN ? AND ?", (inicio, fim))]
    mov.sort(key=lambda x: (x["data"], -x["entrada"]))
    saldo = 0
    for x in mov:
        saldo += x["entrada"] - x["saida"]
        x["saldo"] = saldo
    e, s = sum(x["entrada"] for x in mov), sum(x["saida"] for x in mov)
    return {"inicio": inicio, "fim": fim, "movimentos": mov, "entradas": e, "saidas": s, "saldo": e - s}


def fluxo_mensal(em: date | None = None, passado: int = 6, futuro: int = 3) -> list[dict]:
    """Realizado (meses anteriores, pelo caixa) e projetado (próximos meses: títulos, contratos e contas a pagar)."""
    em = em or financeiro.hoje()
    out = []
    for m in relatorios._meses(em, passado + 1):
        ent = sum(t["valor_pago_cent"] for t in db.linhas(
            "SELECT valor_pago_cent FROM titulos WHERE status='pago' AND substr(data_pagamento,1,7)=?", (m,)))
        sai = sum(d["valor_cent"] for d in db.linhas(
            "SELECT valor_cent FROM despesas WHERE status='pago' AND substr(data_pagamento,1,7)=?", (m,)))
        out.append({"mes": m, "tipo": "realizado", "entradas": ent, "saidas": sai})
    atual = em.strftime("%Y-%m")
    futuros = []
    d = em.replace(day=1)
    for _ in range(futuro):
        d = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
        futuros.append(d.strftime("%Y-%m"))
    janela = [atual] + futuros
    proj: dict[str, list[int]] = {m: [0, 0] for m in janela}
    mes_de = lambda iso: max(iso[:7], atual)  # noqa: E731 — vencidos em aberto entram no mês corrente
    corte = (em - timedelta(days=60)).isoformat()  # atraso acima de 60 dias não entra na previsão de caixa
    for t in db.linhas("SELECT vencimento, valor_cent FROM titulos WHERE status='aberto' AND " + financeiro.SQL_COBRADO + " AND vencimento>=?", (corte,)):
        if mes_de(t["vencimento"]) in proj:
            proj[mes_de(t["vencimento"])][0] += t["valor_cent"]
    geradas = {(t["contrato_id"], t["competencia"]) for t in db.linhas("SELECT contrato_id, competencia FROM titulos")}
    for k in db.linhas("SELECT * FROM contratos WHERE ativo=1 AND confirmado=1"):
        for m in janela:
            if (k["id"], m) not in geradas and m >= k["inicio"] and (not k["fim"] or m <= k["fim"]):
                proj[m][0] += k["valor_cent"]
    for x in db.linhas("SELECT vencimento, valor_cent FROM despesas WHERE status='aberto'"):
        if mes_de(x["vencimento"]) in proj:
            proj[mes_de(x["vencimento"])][1] += x["valor_cent"]
    lancadas = {(x["origem_id"], x["competencia"]) for x in db.linhas(
        "SELECT origem_id, competencia FROM despesas WHERE origem_id IS NOT NULL")}
    for x in db.linhas("SELECT * FROM despesas WHERE recorrente=1 AND origem_id IS NULL AND status!='cancelado'"):
        for m in janela:
            if m > (x["competencia"] or x["vencimento"][:7]) and (x["id"], m) not in lancadas:
                proj[m][1] += x["valor_cent"]
    realizados = [x["saidas"] for x in out if x["mes"] < atual][-3:]
    media = round(sum(realizados) / len(realizados)) if realizados else 0
    for m in futuros:
        estimado = proj[m][1] < media  # sem despesas lançadas/recorrentes suficientes: usa a média de 3 meses
        out.append({"mes": m, "tipo": "projetado", "entradas": proj[m][0], "saidas": max(proj[m][1], media),
                    "saidas_estimadas": estimado})
    for x in out:
        if x["mes"] == atual:  # mês corrente: realizado + o que ainda vence no mês
            x["tipo"] = "atual"
            x["entradas"] += proj[atual][0]
            x["saidas"] += proj[atual][1]
        x["saldo"] = x["entradas"] - x["saidas"]
    return out
