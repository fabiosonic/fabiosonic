#!/usr/bin/env python3
"""Apuração mensal de IR sobre renda variável (pessoa física).

Base: Lei 11.033/2004, IN RFB 1.585/2015, Lei 9.430/1996 (art. 68).

Entrada (CSV): data,ativo,tipo,modalidade,operacao,quantidade,preco,custos
  tipo       ACAO | ETF | BDR | FII | OPCAO | FUTURO
  modalidade ST (operação comum) | DT (day trade)
  operacao   C (compra) | V (venda)
  custos     corretagem + emolumentos + taxas rateados para a linha

Para FUTURO, informe em `preco` o valor financeiro por contrato (pontos x
multiplicador), de forma que quantidade x preco seja o financeiro da operação.
"""

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
ZERO = Decimal("0")

ALIQ_COMUM = Decimal("0.15")
ALIQ_DT = Decimal("0.20")
ALIQ_FII = Decimal("0.20")
IRRF_ST = Decimal("0.00005")  # 0,005% sobre o valor de alienação
IRRF_DT = Decimal("0.01")  # 1% sobre o resultado positivo do day trade
LIMITE_ISENCAO_ACOES = Decimal("20000")
DISPENSA_IRRF_ST = Decimal("1.00")
DARF_MINIMO = Decimal("10.00")
CODIGO_DARF = "6015"

TIPOS = {"ACAO", "ETF", "BDR", "FII", "OPCAO", "FUTURO"}


def money(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def ultimo_dia_util_mes_seguinte(ano, mes):
    """Último dia útil (seg-sex) do mês seguinte. Feriados não considerados."""
    # Dois meses à frente, dia 1, menos um dia = último dia do mês seguinte.
    indice = ano * 12 + (mes - 1) + 2
    dia = date(indice // 12, indice % 12 + 1, 1) - timedelta(days=1)
    while dia.weekday() >= 5:
        dia -= timedelta(days=1)
    return dia


def ler_operacoes(caminho):
    operacoes = []
    with open(caminho, newline="", encoding="utf-8-sig") as f:
        for n, linha in enumerate(csv.DictReader(f), start=2):
            tipo = linha["tipo"].strip().upper()
            modalidade = linha["modalidade"].strip().upper()
            operacao = linha["operacao"].strip().upper()
            if tipo not in TIPOS or modalidade not in {"ST", "DT"} or operacao not in {"C", "V"}:
                sys.exit(f"Linha {n}: tipo/modalidade/operação inválidos: {linha}")
            operacoes.append(
                {
                    "data": date.fromisoformat(linha["data"].strip()),
                    "ativo": linha["ativo"].strip().upper(),
                    "tipo": tipo,
                    "modalidade": modalidade,
                    "operacao": operacao,
                    "quantidade": Decimal(linha["quantidade"]),
                    "preco": Decimal(linha["preco"]),
                    "custos": Decimal(linha.get("custos") or "0"),
                }
            )
    # Ordenação estável por data: preserva a ordem da nota dentro do mesmo dia.
    operacoes.sort(key=lambda op: op["data"])
    return operacoes


def ler_posicao_inicial(caminho):
    posicao = {}
    if not caminho:
        return posicao
    with open(caminho, newline="", encoding="utf-8-sig") as f:
        for linha in csv.DictReader(f):
            posicao[linha["ativo"].strip().upper()] = {
                "quantidade": Decimal(linha["quantidade"]),
                "custo_total": Decimal(linha["custo_total"]),
            }
    return posicao


def novo_mes():
    return {
        "vendas_acoes_st": ZERO,
        "resultado_acoes_st": ZERO,
        "resultado_outros_st": ZERO,
        "resultado_dt": ZERO,
        "resultado_fii": ZERO,
        "vendas_st": ZERO,
        "irrf_dt": ZERO,
    }


def apurar_resultados(operacoes, posicao, alertas):
    meses = defaultdict(novo_mes)
    dt_dia = defaultdict(lambda: ZERO)  # (data, ativo, tipo) -> resultado

    for op in operacoes:
        chave_mes = (op["data"].year, op["data"].month)
        m = meses[chave_mes]
        financeiro = op["quantidade"] * op["preco"]

        if op["modalidade"] == "DT":
            valor = financeiro - op["custos"] if op["operacao"] == "V" else -(financeiro + op["custos"])
            dt_dia[(op["data"], op["ativo"], op["tipo"])] += valor
            continue

        pos = posicao.setdefault(op["ativo"], {"quantidade": ZERO, "custo_total": ZERO})
        if op["operacao"] == "C":
            pos["quantidade"] += op["quantidade"]
            pos["custo_total"] += financeiro + op["custos"]
            continue

        if pos["quantidade"] < op["quantidade"]:
            alertas.append(
                f"{op['data']} {op['ativo']}: venda de {op['quantidade']} com posição de "
                f"{pos['quantidade']} (venda a descoberto ou posição inicial ausente) — "
                "resultado calculado só sobre a quantidade em carteira."
            )
        qtd_coberta = min(pos["quantidade"], op["quantidade"])
        custo_medio = pos["custo_total"] / pos["quantidade"] if pos["quantidade"] else ZERO
        custo_baixa = custo_medio * qtd_coberta
        venda_liquida = (financeiro - op["custos"]) * (qtd_coberta / op["quantidade"])
        resultado = venda_liquida - custo_baixa
        pos["quantidade"] -= qtd_coberta
        pos["custo_total"] -= custo_baixa

        if op["tipo"] == "FII":
            m["resultado_fii"] += resultado
        elif op["tipo"] == "ACAO":
            m["vendas_acoes_st"] += financeiro
            m["resultado_acoes_st"] += resultado
        else:
            m["resultado_outros_st"] += resultado
        m["vendas_st"] += financeiro

    resultado_dt_por_dia = defaultdict(lambda: ZERO)
    for (dia, _ativo, tipo), valor in dt_dia.items():
        m = meses[(dia.year, dia.month)]
        if tipo == "FII":
            m["resultado_fii"] += valor
        else:
            m["resultado_dt"] += valor
        resultado_dt_por_dia[dia] += valor
    for dia, valor in resultado_dt_por_dia.items():
        if valor > 0:
            meses[(dia.year, dia.month)]["irrf_dt"] += valor * IRRF_DT

    return meses


def compensar(resultado, prejuizo):
    """Retorna (base tributável, prejuízo remanescente). Prejuízo é positivo."""
    if resultado <= 0:
        return ZERO, prejuizo - resultado
    usado = min(resultado, prejuizo)
    return resultado - usado, prejuizo - usado


def apurar_impostos(meses, prej_comum, prej_dt, prej_fii, irrf_saldo):
    linhas = []
    imposto_acumulado = ZERO  # imposto < R$ 10 transportado
    for ano, mes in sorted(meses):
        m = meses[(ano, mes)]
        isento = m["vendas_acoes_st"] <= LIMITE_ISENCAO_ACOES and m["resultado_acoes_st"] > 0
        ganho_isento = m["resultado_acoes_st"] if isento else ZERO
        resultado_comum = m["resultado_outros_st"] + (ZERO if isento else m["resultado_acoes_st"])

        base_comum, prej_comum = compensar(resultado_comum, prej_comum)
        base_dt, prej_dt = compensar(m["resultado_dt"], prej_dt)
        base_fii, prej_fii = compensar(m["resultado_fii"], prej_fii)

        imposto = money(base_comum * ALIQ_COMUM + base_dt * ALIQ_DT + base_fii * ALIQ_FII)
        irrf_st = m["vendas_st"] * IRRF_ST
        irrf_st = money(irrf_st) if irrf_st > DISPENSA_IRRF_ST else ZERO
        irrf_mes = irrf_st + money(m["irrf_dt"])
        irrf_saldo += irrf_mes

        irrf_usado = min(imposto, irrf_saldo)
        irrf_saldo -= irrf_usado
        devido = imposto - irrf_usado + imposto_acumulado
        if devido < DARF_MINIMO:
            imposto_acumulado, darf = devido, ZERO
        else:
            imposto_acumulado, darf = ZERO, devido

        linhas.append(
            {
                "periodo": f"{mes:02d}/{ano}",
                "vendas_acoes_st": money(m["vendas_acoes_st"]),
                "ganho_isento_acoes": money(ganho_isento),
                "resultado_comum": money(resultado_comum),
                "resultado_day_trade": money(m["resultado_dt"]),
                "resultado_fii": money(m["resultado_fii"]),
                "base_comum": money(base_comum),
                "base_day_trade": money(base_dt),
                "base_fii": money(base_fii),
                "imposto_devido": imposto,
                "irrf_mes": irrf_mes,
                "irrf_compensado": irrf_usado,
                "darf": darf,
                "darf_codigo": CODIGO_DARF if darf else "",
                "darf_vencimento": ultimo_dia_util_mes_seguinte(ano, mes).isoformat() if darf else "",
                "prejuizo_comum_a_compensar": money(prej_comum),
                "prejuizo_dt_a_compensar": money(prej_dt),
                "prejuizo_fii_a_compensar": money(prej_fii),
                "irrf_a_compensar": money(irrf_saldo),
                "imposto_inferior_10_acumulado": money(imposto_acumulado),
            }
        )
    return linhas


def imprimir(linhas, alertas):
    campos = [
        ("Período", "periodo"),
        ("Vendas ações ST", "vendas_acoes_st"),
        ("Ganho isento", "ganho_isento_acoes"),
        ("Res. comum", "resultado_comum"),
        ("Res. DT", "resultado_day_trade"),
        ("Res. FII", "resultado_fii"),
        ("Imposto", "imposto_devido"),
        ("IRRF comp.", "irrf_compensado"),
        ("DARF 6015", "darf"),
        ("Vencimento", "darf_vencimento"),
        ("Prej. comum", "prejuizo_comum_a_compensar"),
        ("Prej. DT", "prejuizo_dt_a_compensar"),
        ("Prej. FII", "prejuizo_fii_a_compensar"),
        ("IRRF saldo", "irrf_a_compensar"),
    ]
    larguras = [max(len(t), *(len(str(l[c])) for l in linhas)) for t, c in campos]
    print(" | ".join(t.rjust(w) for (t, _), w in zip(campos, larguras)))
    print("-+-".join("-" * w for w in larguras))
    for linha in linhas:
        print(" | ".join(str(linha[c]).rjust(w) for (_, c), w in zip(campos, larguras)))
    if alertas:
        print("\nAlertas:")
        for alerta in alertas:
            print(f"  - {alerta}")
    print("\nVencimentos consideram apenas fins de semana; confira feriados nacionais.")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("operacoes", help="CSV de operações")
    parser.add_argument("--custo-inicial", help="CSV ativo,quantidade,custo_total da posição inicial")
    parser.add_argument("--prejuizo-comum", type=Decimal, default=ZERO)
    parser.add_argument("--prejuizo-dt", type=Decimal, default=ZERO)
    parser.add_argument("--prejuizo-fii", type=Decimal, default=ZERO)
    parser.add_argument("--irrf-anterior", type=Decimal, default=ZERO)
    parser.add_argument("--json", action="store_true", help="Saída em JSON")
    args = parser.parse_args()

    alertas = []
    meses = apurar_resultados(ler_operacoes(args.operacoes), ler_posicao_inicial(args.custo_inicial), alertas)
    linhas = apurar_impostos(meses, args.prejuizo_comum, args.prejuizo_dt, args.prejuizo_fii, args.irrf_anterior)

    if args.json:
        print(json.dumps({"meses": linhas, "alertas": alertas}, default=str, ensure_ascii=False, indent=2))
    else:
        imprimir(linhas, alertas)


if __name__ == "__main__":
    main()
