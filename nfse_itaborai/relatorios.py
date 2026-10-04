"""Painel e relatórios gerenciais: KPIs, aging, faturamento, clientes, fluxo de caixa, DRE, RBT12."""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import date, timedelta

from . import config, db, financeiro

# Anexo III da LC 123/2006 (serviços de contabilidade — art. 18, § 5º-B, XIV): faixas por RBT12
# (teto, alíquota nominal %, parcela a deduzir, participação do ISS na repartição %)
ANEXO_III = [(180_000_00, 6.0, 0, 33.5), (360_000_00, 11.2, 9_360_00, 32.0), (720_000_00, 13.5, 17_640_00, 32.5),
             (1_800_000_00, 16.0, 35_640_00, 32.5), (3_600_000_00, 21.0, 125_640_00, 33.5),
             (4_800_000_00, 33.0, 648_000_00, 0.0)]


def _meses(ate: date, n: int) -> list[str]:
    a, m, out = ate.year, ate.month, []
    for _ in range(n):
        out.append(f"{a}-{m:02d}")
        a, m = (a, m - 1) if m > 1 else (a - 1, 12)
    return out[::-1]


def _titulos(em: date) -> list[dict]:
    return [financeiro.enriquecer(t, em) for t in db.linhas("SELECT * FROM titulos WHERE status!='cancelado'")]


def aliquota_efetiva_anexo3(rbt12_cent: int, iss_fixo: bool | None = None) -> float:
    """Alíquota efetiva do DAS (Anexo III) = (RBT12 × nominal − parcela a deduzir) / RBT12.

    Escritório contábil recolhe o ISS em valor fixo (LC 123/2006, art. 18, § 22-A): a parcela do ISS
    da repartição sai do DAS. Configurável em financeiro.iss_fixo (padrão: sim).
    """
    if iss_fixo is None:
        iss_fixo = config.carregar()["financeiro"].get("iss_fixo", True)
    faixa = next((f for f in ANEXO_III if rbt12_cent <= f[0]), ANEXO_III[-1])
    teto, nominal, deduzir, iss = faixa
    efetiva = nominal if rbt12_cent <= 0 else (rbt12_cent * nominal / 100 - deduzir) / rbt12_cent * 100
    if iss_fixo:
        efetiva *= (1 - iss / 100)
    return round(efetiva, 2)


def rbt12(em: date, ts: list[dict] | None = None) -> int:
    """Receita bruta dos 12 meses anteriores ao mês corrente, pelas competências faturadas (NFS-e emitidas)."""
    ts = ts if ts is not None else _titulos(em)
    meses = set(_meses(em, 13)[:-1])
    return sum(t["valor_cent"] for t in ts if t["competencia"] in meses and t["nfse_status"] in ("emitida", "nao_emitir"))


def score_cliente(ts: list[dict]) -> dict:
    """Média de dias de atraso (pagos e vencidos em aberto) + quantidade em aberto → nota de 0 (péssimo) a 100."""
    pagos = [t for t in ts if t["status"] == "pago" and t["data_pagamento"]]
    atrasos = [max((date.fromisoformat(t["data_pagamento"]) - date.fromisoformat(t["vencimento"])).days, 0) for t in pagos]
    atrasos += [t["dias_atraso"] for t in ts if t["situacao"] == "atrasado"]
    media = sum(atrasos) / len(atrasos) if atrasos else 0
    abertos_atrasados = sum(1 for t in ts if t["situacao"] == "atrasado")
    nota = max(0, round(100 - media * 1.5 - abertos_atrasados * 10))
    return {"media_atraso": round(media, 1), "atrasados_abertos": abertos_atrasados, "score": nota,
            "faixa": "bom" if nota >= 80 else "atenção" if nota >= 50 else "risco"}


def painel(em: date | None = None) -> dict:
    em = em or financeiro.hoje()
    ts = _titulos(em)
    comp = financeiro.competencia_de(em)
    mes_ini = em.replace(day=1).isoformat()
    abertos = [t for t in ts if t["situacao"] in ("aberto", "atrasado")]   # sem cobrança não entra
    atrasados = [t for t in abertos if t["situacao"] == "atrasado"]
    juridicos = [t for t in ts if t["situacao"] == "juridico"]          # cobrança jurídica: registrados, sem mensagens
    recebido_mes = sum(t["valor_pago_cent"] for t in ts if t["status"] == "pago" and t["data_pagamento"] >= mes_ini)
    faturado_mes = sum(t["valor_cent"] for t in ts if t["competencia"] == comp)
    vencido_total = sum(t["valor_cent"] for t in ts if t["vencimento"] < em.isoformat() and (t["status"] == "pago" or financeiro.tem_cobranca(t)))
    vencido_aberto = sum(t["valor_cent"] for t in atrasados)
    inadimplente = vencido_aberto + sum(t["valor_cent"] for t in juridicos)      # a inadimplência inclui o que está no jurídico
    contratos = db.linhas("SELECT valor_cent FROM contratos WHERE ativo=1 AND confirmado=1")
    a_confirmar = db.linhas("SELECT COUNT(*) n FROM contratos WHERE ativo=1 AND confirmado=0")[0]["n"]
    mrr = sum(c["valor_cent"] for c in contratos)
    desp_abertas = [d for d in financeiro.listar_despesas("a_pagar", em)]
    r12 = rbt12(em, ts)
    serie = []
    despesas = db.linhas("SELECT valor_cent, data_pagamento FROM despesas WHERE status='pago'")
    cobrados = [t for t in ts if t["status"] == "pago" or financeiro.tem_cobranca(t)]
    for m in _meses(em, 12):
        a, mm = int(m[:4]), int(m[5:])
        fim = min(em, (date(a + mm // 12, mm % 12 + 1, 1) - timedelta(days=1))).isoformat()
        # posição no fim do mês: o que estava emitido e ainda não tinha sido pago naquela data
        em_aberto = [t for t in cobrados if t["competencia"] <= m and not (t["status"] == "pago" and t["data_pagamento"] <= fim)]
        vencidos = [t for t in em_aberto if t["vencimento"] < fim]
        serie.append({"mes": m, "faturado": sum(t["valor_cent"] for t in ts if t["competencia"] == m),
                      "recebido": sum(t["valor_pago_cent"] for t in ts if t["status"] == "pago"
                                      and t["data_pagamento"][:7] == m),
                      "despesas": sum(d["valor_cent"] for d in despesas if (d["data_pagamento"] or "")[:7] == m),
                      "a_receber": sum(t["valor_cent"] for t in em_aberto),
                      "atrasado": sum(t["valor_cent"] for t in vencidos)})
    proximos = sorted((t for t in abertos if em.isoformat() <= t["vencimento"] <= (em + timedelta(days=7)).isoformat()),
                      key=lambda t: t["vencimento"])
    cob = config.carregar()["cobranca"]
    criticos = sorted({t["cliente_nome"] for t in atrasados if t["dias_atraso"] >= cob["bloquear_apos_dias"]})
    return {
        "hoje": em.isoformat(), "competencia": comp,
        "faturado_mes": faturado_mes, "recebido_mes": recebido_mes,
        "a_receber": sum(t["valor_cent"] for t in abertos), "atrasado": vencido_aberto,
        "atrasado_qtd": len(atrasados), "clientes_atrasados": len({t["cpf_cnpj"] for t in atrasados}),
        "juridico": sum(t["total_cent"] for t in juridicos), "juridico_qtd": len(juridicos),
        "clientes_juridico": len({t["cpf_cnpj"] for t in juridicos}),
        "inadimplencia_pct": round(inadimplente / vencido_total * 100, 1) if vencido_total else 0.0,
        "mrr": mrr, "contratos_ativos": len(contratos), "contratos_a_confirmar": a_confirmar,
        "divergencias_recorrencia": [{"titulo_id": t["id"], "contrato_id": t["contrato_id"], "cliente": t["cliente_nome"],
                                      "competencia": t["competencia"], "valor_cent": t["valor_cent"],
                                      "valor_recorrencia": t["valor_recorrencia"], "boleto": bool(t["banco_id"])}
                                     for t in financeiro.divergencias_recorrencia()],
        "parciais_pendentes": db.linhas("SELECT COUNT(*) n FROM titulos WHERE parcial_status='pendente'")[0]["n"],
        "ticket_medio": mrr // len(contratos) if contratos else 0,
        "a_pagar": sum(d["valor_cent"] for d in desp_abertas),
        "a_pagar_atrasado": sum(d["valor_cent"] for d in desp_abertas if d["situacao"] == "atrasado"),
        "sem_nfse": sum(1 for t in ts if t["nfse_status"] in ("pendente", "erro")),
        "rbt12": r12, "aliquota_simples_estimada": aliquota_efetiva_anexo3(r12),
        "sublimite_pct": round(r12 / 3_600_000_00 * 100, 1),
        "serie": serie, "proximos_7_dias": proximos[:10], "criticos": criticos, "aging": aging(em)["faixas"],
        "ultima_execucao_robo": (db.linhas("SELECT quando FROM log WHERE tipo='robo' ORDER BY id DESC LIMIT 1")
                                 or [{"quando": ""}])[0]["quando"],
        "maiores_devedores": sorted(
            [{"cliente": n, "valor": sum(t["total_cent"] for t in atrasados if t["cliente_nome"] == n)}
             for n in {t["cliente_nome"] for t in atrasados}], key=lambda x: -x["valor"])[:5],
    }


def aging(em: date | None = None) -> dict:
    em = em or financeiro.hoje()
    faixas = {"a_vencer": 0, "1_30": 0, "31_60": 0, "61_90": 0, "90_mais": 0}
    por_cliente: dict[str, dict] = defaultdict(lambda: dict.fromkeys(faixas, 0))
    for t in _titulos(em):
        if t["situacao"] not in ("aberto", "atrasado"):
            continue
        d = t["dias_atraso"]
        f = "a_vencer" if d <= 0 else "1_30" if d <= 30 else "31_60" if d <= 60 else "61_90" if d <= 90 else "90_mais"
        faixas[f] += t["valor_cent"]
        por_cliente[t["cliente_nome"]][f] += t["valor_cent"]
    return {"faixas": faixas, "clientes": sorted(({"cliente": k, **v} for k, v in por_cliente.items()),
                                                  key=lambda x: -(sum(v for k, v in x.items() if k != "cliente")))}


def por_cliente(em: date | None = None) -> list[dict]:
    em = em or financeiro.hoje()
    grupos: dict[str, list] = defaultdict(list)
    for t in _titulos(em):
        grupos[t["cpf_cnpj"]].append(t)
    lst = []
    doze = set(_meses(em, 12))
    for doc, ts in grupos.items():
        lst.append({"cpf_cnpj": doc, "cliente": ts[-1]["cliente_nome"],
                    "faturado_12m": sum(t["valor_cent"] for t in ts if t["competencia"] in doze),
                    "recebido_total": sum(t["valor_pago_cent"] for t in ts if t["status"] == "pago"),
                    "em_aberto": sum(t["valor_cent"] for t in ts if t["situacao"] in ("aberto", "atrasado")),
                    "atrasado": sum(t["total_cent"] for t in ts if t["situacao"] == "atrasado"),
                    **score_cliente(ts)})
    return sorted(lst, key=lambda x: -x["faturado_12m"])


def fluxo_caixa(em: date | None = None, dias: int = 90) -> list[dict]:
    """Projeção semanal: entradas (títulos em aberto + contratos ainda não gerados) − saídas (contas a pagar)."""
    em = em or financeiro.hoje()
    fim = em + timedelta(days=dias)
    entradas: dict[str, int] = defaultdict(int)
    saidas: dict[str, int] = defaultdict(int)

    def semana(d: date) -> str:
        d = max(d, em)
        return (d - timedelta(days=d.weekday())).isoformat()

    corte = em - timedelta(days=60)  # atraso acima de 60 dias não entra na previsão de caixa
    for t in db.linhas("SELECT * FROM titulos WHERE status='aberto' AND " + financeiro.SQL_COBRADO):
        v = date.fromisoformat(t["vencimento"])
        if corte <= v <= fim:
            entradas[semana(v)] += t["valor_cent"]
    geradas = {(t["contrato_id"], t["competencia"]) for t in db.linhas("SELECT contrato_id, competencia FROM titulos")}
    for k in db.linhas("SELECT * FROM contratos WHERE ativo=1 AND confirmado=1"):
        d = em.replace(day=1)
        while d <= fim:
            comp = d.strftime("%Y-%m")
            venc = financeiro.dia_no_mes(d.year, d.month, k["dia_vencimento"])
            if (k["id"], comp) not in geradas and comp >= k["inicio"] and (not k["fim"] or comp <= k["fim"]) \
                    and em <= venc <= fim:
                entradas[semana(venc)] += k["valor_cent"]
            d = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
    for dsp in db.linhas("SELECT * FROM despesas WHERE status='aberto'"):
        v = date.fromisoformat(dsp["vencimento"])
        if v <= fim:
            saidas[semana(v)] += dsp["valor_cent"]
    saldo, out = 0, []
    s0 = date.fromisoformat(semana(em))
    semanas = {(s0 + timedelta(weeks=k)).isoformat() for k in range((fim - s0).days // 7 + 1)}
    for s in sorted(semanas | set(entradas) | set(saidas)):
        saldo += entradas[s] - saidas[s]
        out.append({"semana": s, "entradas": entradas[s], "saidas": saidas[s], "saldo_acumulado": saldo})
    return out


def csv_titulos(em: date | None = None) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["ID", "Cliente", "CPF/CNPJ", "Competência", "Descrição", "Valor", "Vencimento", "Situação",
                "Dias atraso", "Valor atualizado", "Pago em", "Valor pago", "Forma", "NFS-e", "Status NFS-e"])
    for t in financeiro.listar_titulos(em=em):
        f = lambda c: f"{c / 100:.2f}".replace(".", ",")  # noqa: E731
        w.writerow([t["id"], t["cliente_nome"], t["cpf_cnpj"], t["competencia"], t["descricao"], f(t["valor_cent"]),
                    t["vencimento"], t["situacao"], t["dias_atraso"], f(t["total_cent"]), t["data_pagamento"],
                    f(t["valor_pago_cent"]), t["forma_pagamento"], t["nfse_numero"], t["nfse_status"]])
    return "﻿" + buf.getvalue()
