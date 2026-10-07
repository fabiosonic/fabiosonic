"""Conferência de folha (INSS e IRRF do empregado) contra tabelas CONFERIDAS do catálogo.

Sem TABELA_INSS_SEGURADO / TABELA_IRRF_MENSAL conferidas, a conferência fica INATIVA (regra 3).
Entrada (exportação da folha, CSV `;`):
cpf;nome;competencia;salario_contribuicao;inss_descontado;base_irrf;dependentes;irrf_descontado
[;remuneracao_fgts;fgts_depositado]   (opcionais: conferência do FGTS)
"""
from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from ..especialista.modelo import Achado, natureza_por_normas
from ..util.arquivos import ler_csv
from ..util.dinheiro import CENTAVO, dinheiro, dinheiro_br

INSS, IRRF, FGTS = "TABELA_INSS_SEGURADO", "TABELA_IRRF_MENSAL", "LEI_8036_FGTS"


def _q(v: Decimal) -> Decimal:
    return v.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def inss_progressivo(base: Decimal, faixas: list[dict]) -> Decimal:
    """faixas: [{ate: valor, aliquota: fração}] em ordem; teto = última faixa."""
    total, anterior = Decimal("0"), Decimal("0")
    for f in faixas:
        ate = Decimal(str(f["ate"]))
        aliq = Decimal(str(f["aliquota"]))
        if base <= anterior:
            break
        faixa = min(base, ate) - anterior
        total += faixa * aliq
        anterior = ate
    return _q(total)


def irrf_mensal(base: Decimal, dependentes: int, params: dict) -> Decimal:
    base_calc = base - Decimal(str(params["deducao_por_dependente"])) * dependentes
    imposto = Decimal("0")
    for f in params["faixas"]:
        ate = f.get("ate")
        if ate is None or base_calc <= Decimal(str(ate)):
            imposto = base_calc * Decimal(str(f["aliquota"])) - Decimal(str(f["deduzir"]))
            break
    else:  # base acima de todas as faixas: a tabela conferida não cobre o caso — não zera em silêncio
        raise ValueError(f"base {base_calc} acima da última faixa da {IRRF} (última faixa deve ser sem 'ate')")
    imposto = max(imposto, Decimal("0"))
    red = params.get("redutor")
    if red:
        # sobre qual valor o redutor é medido é decisão LEGAL: vem da norma (`redutor.base`)
        if red.get("base") == "rendimento":
            ref = base
        elif red.get("base") == "base_calculo":
            ref = base_calc
        else:
            raise ValueError("TABELA_IRRF_MENSAL.redutor.base não informado (rendimento | base_calculo)")
        if ref <= Decimal(str(red["zera_ate"])):
            imposto = Decimal("0")
        elif ref <= Decimal(str(red["faixa_ate"])):
            reducao = Decimal(str(red["constante"])) - Decimal(str(red["coeficiente"])) * ref
            imposto = max(imposto - max(reducao, Decimal("0")), Decimal("0"))
    return _q(imposto)


def ler_folha(caminho: Path) -> list[dict]:
    linhas = ler_csv(caminho)
    out = []
    for l in linhas:
        out.append({"cpf": l["cpf"], "nome": l.get("nome", ""), "competencia": l["competencia"],
                    "salario_contribuicao": dinheiro_br(l["salario_contribuicao"]),
                    "inss_descontado": dinheiro_br(l["inss_descontado"]), "base_irrf": dinheiro_br(l["base_irrf"]),
                    "dependentes": int(l.get("dependentes") or 0), "irrf_descontado": dinheiro_br(l["irrf_descontado"]),
                    "remuneracao_fgts": dinheiro_br(l["remuneracao_fgts"]) if l.get("remuneracao_fgts") else None,
                    "fgts_depositado": dinheiro_br(l["fgts_depositado"]) if l.get("fgts_depositado") else None})
    return out


def _params(catalogo, comp: str, folha_tem_fgts: bool) -> tuple:
    """Parâmetros CONFERIDOS e VIGENTES na competência (tabela de outro ano não serve)."""
    try:
        em = date.fromisoformat(comp.strip()[:7] + "-01")
    except ValueError:
        return None, {"faixas": None}, None, [f"{comp}: competência ilegível (esperado AAAA-MM) — folha não conferida"]
    inativas = []
    faixas_inss = catalogo.parametro(INSS, "faixas", em)
    p_irrf = {k: catalogo.parametro(IRRF, k, em) for k in ("faixas", "deducao_por_dependente", "redutor")}
    if faixas_inss is None:
        inativas.append(f"INSS {comp}: {INSS} não conferida ou não vigente ({catalogo.status(INSS)})")
    if p_irrf["faixas"] is None or p_irrf["deducao_por_dependente"] is None:
        inativas.append(f"IRRF {comp}: {IRRF} não conferida ou não vigente ({catalogo.status(IRRF)})")
        p_irrf["faixas"] = None
    elif p_irrf["redutor"] and p_irrf["redutor"].get("base") not in ("rendimento", "base_calculo"):
        inativas.append(f"IRRF: {IRRF}.redutor.base ausente — sobre qual valor medir o redutor é decisão legal")
        p_irrf["faixas"] = None
    aliq_fgts = catalogo.parametro(FGTS, "aliquota_deposito", em)
    if aliq_fgts is None and folha_tem_fgts:
        inativas.append(f"FGTS {comp}: {FGTS} não conferida ou não vigente ({catalogo.status(FGTS)})")
    return faixas_inss, p_irrf, aliq_fgts, inativas


def conferir(folha: list[dict], cnpj: str, catalogo, tolerancia: Decimal = Decimal("0.01")) -> dict:
    achados, inativas, cache = [], [], {}
    for l in folha:
        comp = l["competencia"]
        if comp not in cache:
            cache[comp] = _params(catalogo, comp, any(x.get("remuneracao_fgts") is not None for x in folha))
            inativas.extend(cache[comp][3])
        faixas_inss, p_irrf, aliq_fgts, _ = cache[comp]
        ref = f"{l['competencia']}/{l['cpf'][-4:]}"
        if aliq_fgts is not None and l.get("remuneracao_fgts") is not None and l.get("fgts_depositado") is not None:
            esperado = _q(l["remuneracao_fgts"] * Decimal(str(aliq_fgts)))
            if abs(esperado - l["fgts_depositado"]) > tolerancia:
                achados.append(Achado("DP_FGTS_DIVERGENTE", "FGTS divergente da alíquota legal",
                                      natureza_por_normas((FGTS,), catalogo),
                                      f"{l['nome']}: depositado {l['fgts_depositado']} × calculado {esperado}.",
                                      cnpj, l["competencia"], ref, [{"id": FGTS, "status": catalogo.status(FGTS)}],
                                      "Conferir base do FGTS e guia (FGTS Digital).", True,
                                      l["fgts_depositado"] - esperado))
        if faixas_inss is not None:
            esperado = inss_progressivo(l["salario_contribuicao"], faixas_inss)
            if abs(esperado - l["inss_descontado"]) > tolerancia:
                achados.append(Achado("DP_INSS_DIVERGENTE", "INSS do empregado divergente da tabela",
                                      natureza_por_normas((INSS,), catalogo),
                                      f"{l['nome']}: descontado {l['inss_descontado']} × calculado {esperado}.",
                                      cnpj, l["competencia"], ref,
                                      [{"id": INSS, "status": catalogo.status(INSS)}],
                                      "Revisar base e tabela no cálculo da folha.", True,
                                      l["inss_descontado"] - esperado))
        if p_irrf["faixas"] is not None:
            try:
                esperado = irrf_mensal(l["base_irrf"], l["dependentes"], p_irrf)
            except ValueError as exc:
                inativas.append(f"IRRF {ref}: {exc}")
                continue
            if abs(esperado - l["irrf_descontado"]) > tolerancia:
                achados.append(Achado("DP_IRRF_DIVERGENTE", "IRRF do empregado divergente da tabela",
                                      natureza_por_normas((IRRF,), catalogo),
                                      f"{l['nome']}: descontado {l['irrf_descontado']} × calculado {esperado}.",
                                      cnpj, l["competencia"], ref,
                                      [{"id": IRRF, "status": catalogo.status(IRRF)}],
                                      "Revisar base, dependentes e tabela/redutor do IRRF.", True,
                                      l["irrf_descontado"] - esperado))
    return {"achados": achados, "inativas": inativas}
