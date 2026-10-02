"""Relatórios contábeis e financeiros no padrão profissional: DRE estruturada, indicadores, livro caixa e fluxo de caixa.

DRE (regime de competência, Lei 6.404/76 art. 187 e NBC TG 26 — adaptada à ME/EPP do Simples Nacional):
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

GRUPOS = {
    "Despesas com pessoal": ["Folha", "Pró-labore", "Encargos", "Benefícios"],
    "Despesas de ocupação": ["Aluguel", "Energia/Internet", "Condomínio"],
    "Despesas administrativas": ["Sistemas", "Contador/Assessoria", "Marketing", "Material", "Outras"],
    "Despesas tributárias": ["Impostos", "Taxas"],
}
FINANCEIRAS = ["Bancárias", "Juros", "Tarifas"]
_DEDUCAO = re.compile(r"\b(DAS|SIMPLES|PGDAS|ISS|ISSQN)\b", re.IGNORECASE)
RECEITA_VALIDA = ("emitida", "nao_emitir")


def _grupo(categoria: str) -> str:
    if categoria in FINANCEIRAS:
        return "financeiras"
    return next((g for g, cats in GRUPOS.items() if categoria in cats), "Despesas administrativas")


def _competencia(d: dict) -> str:
    return d.get("competencia") or d["vencimento"][:7]


def _eh_deducao(d: dict) -> bool:
    return d["categoria"] == "Impostos" and bool(_DEDUCAO.search(f"{d['descricao']} {d.get('fornecedor', '')}"))


def _pct(parte: int, todo: int) -> float:
    return round(parte / todo * 100, 1) if todo else 0.0


# ---------------------------------------------------------------- DRE

def dre(ano: int, em: date | None = None) -> dict:
    em = em or financeiro.hoje()
    cfg = config.carregar()["financeiro"]
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
        for cat, v in sorted(grupos[g].items()):
            add(cat, v, sinal=-1)
    oper = [l - d for l, d in zip(liquida, total_oper)]
    add("(=) RESULTADO OPERACIONAL", oper, "total", 0)
    fin = soma(*grupos["financeiras"].values()) if "financeiras" in grupos else [0] * 12
    add("(−) DESPESAS FINANCEIRAS", fin, "grupo", 0, -1)
    for cat, v in sorted(grupos.get("financeiras", {}).items()):
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
    aberto = sum(t["valor_cent"] for t in ts if t["status"] == "aberto" and t.get("cobrar", 1))
    dso = round(aberto / (fat90 / 90)) if fat90 else 0
    vencidos90 = [t for t in ts if ini90 <= t["vencimento"] < em.isoformat() and t.get("cobrar", 1)]
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
    aliq = relatorios.aliquota_efetiva_anexo3(r12) if r12 else 0
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
    for t in db.linhas("SELECT vencimento, valor_cent FROM titulos WHERE status='aberto' AND cobrar=1 AND vencimento>=?", (corte,)):
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
