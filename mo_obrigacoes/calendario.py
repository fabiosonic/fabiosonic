"""Calendário fiscal: feriados nacionais, dias úteis e cálculo de vencimentos.

Regras de vencimento (campo ``Obrigacao.regra_vencimento``):

    {"tipo": "dia_fixo", "dia": 20, "meses_apos": 1, "ajuste": "posterga"}
    {"tipo": "dia_util", "n": 10, "meses_apos": 2}          # 10º dia útil
    {"tipo": "ultimo_dia_util", "meses_apos": 1}
    Anuais: acrescente "mes" (mês do vencimento) e "anos_apos" (padrão 1), ex.:
    {"tipo": "ultimo_dia_util", "mes": 7, "anos_apos": 1}    # ECF

``ajuste`` vale para "dia_fixo": "antecipa" (dia útil anterior), "posterga"
(dia útil seguinte) ou "nenhum".
"""
from __future__ import annotations

import calendar
from datetime import date, timedelta
from functools import lru_cache

# Feriados adicionais (estaduais/municipais) podem ser registrados aqui em tempo de execução,
# p.ex. carregados de um arquivo de configuração do escritório.
FERIADOS_EXTRAS: set[date] = set()


def pascoa(ano: int) -> date:
    """Domingo de Páscoa (algoritmo de Meeus/Jones/Butcher)."""
    a = ano % 19
    b, c = divmod(ano, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    mes = (h + l_ - 7 * m + 114) // 31
    dia = ((h + l_ - 7 * m + 114) % 31) + 1
    return date(ano, mes, dia)


@lru_cache(maxsize=64)
def feriados_nacionais(ano: int) -> dict[date, str]:
    """Feriados nacionais e dias sem expediente bancário (Carnaval e Corpus Christi)."""
    p = pascoa(ano)
    feriados = {
        date(ano, 1, 1): "Confraternização Universal",
        p - timedelta(days=48): "Carnaval (segunda)",
        p - timedelta(days=47): "Carnaval (terça)",
        p - timedelta(days=2): "Sexta-feira Santa",
        date(ano, 4, 21): "Tiradentes",
        date(ano, 5, 1): "Dia do Trabalho",
        p + timedelta(days=60): "Corpus Christi",
        date(ano, 9, 7): "Independência",
        date(ano, 10, 12): "Nossa Senhora Aparecida",
        date(ano, 11, 2): "Finados",
        date(ano, 11, 15): "Proclamação da República",
        date(ano, 12, 25): "Natal",
    }
    if ano >= 2024:  # Lei 14.759/2023
        feriados[date(ano, 11, 20)] = "Dia Nacional de Zumbi e da Consciência Negra"
    return feriados


def eh_dia_util(d: date) -> bool:
    return d.weekday() < 5 and d not in feriados_nacionais(d.year) and d not in FERIADOS_EXTRAS


def proximo_dia_util(d: date) -> date:
    while not eh_dia_util(d):
        d += timedelta(days=1)
    return d


def dia_util_anterior(d: date) -> date:
    while not eh_dia_util(d):
        d -= timedelta(days=1)
    return d


def ultimo_dia_util(ano: int, mes: int) -> date:
    return dia_util_anterior(date(ano, mes, calendar.monthrange(ano, mes)[1]))


def enesimo_dia_util(ano: int, mes: int, n: int) -> date:
    d = date(ano, mes, 1)
    contagem = 0
    while True:
        if eh_dia_util(d):
            contagem += 1
            if contagem == n:
                return d
        d += timedelta(days=1)


def somar_meses(ano: int, mes: int, meses: int) -> tuple[int, int]:
    total = ano * 12 + (mes - 1) + meses
    return total // 12, total % 12 + 1


def dias_uteis_entre(inicio: date, fim: date) -> int:
    """Quantidade de dias úteis no intervalo (inicio, fim]. Negativo se fim < inicio."""
    if fim == inicio:
        return 0
    sinal = 1 if fim > inicio else -1
    a, b = sorted((inicio, fim))
    n = 0
    d = a + timedelta(days=1)
    while d <= b:
        if eh_dia_util(d):
            n += 1
        d += timedelta(days=1)
    return n * sinal


# ----------------------------------------------------------------------------
# Competências
# ----------------------------------------------------------------------------
def competencia_str(ano: int, mes: int) -> str:
    return f"{ano:04d}-{mes:02d}"


def parse_competencia(comp: str) -> tuple[int, int]:
    ano, mes = comp.split("-")
    return int(ano), int(mes)


def competencia_anterior(ref: date | None = None) -> str:
    ref = ref or date.today()
    ano, mes = somar_meses(ref.year, ref.month, -1)
    return competencia_str(ano, mes)


def formatar_competencia(comp: str, periodicidade: str = "mensal") -> str:
    ano, mes = parse_competencia(comp)
    if periodicidade == "anual":
        return f"Ano {ano}"
    if periodicidade == "trimestral":
        return f"{(mes - 1) // 3 + 1}º tri/{ano}"
    return f"{mes:02d}/{ano}"


def calcular_vencimento(regra: dict, competencia: str, periodicidade: str = "mensal") -> date:
    ano, mes = parse_competencia(competencia)
    tipo = regra.get("tipo", "dia_fixo")

    if periodicidade == "anual" or "mes" in regra:
        alvo_ano = ano + int(regra.get("anos_apos", 1))
        alvo_mes = int(regra["mes"])
    else:
        alvo_ano, alvo_mes = somar_meses(ano, mes, int(regra.get("meses_apos", 1)))

    if tipo == "ultimo_dia_util":
        return ultimo_dia_util(alvo_ano, alvo_mes)
    if tipo == "dia_util":
        return enesimo_dia_util(alvo_ano, alvo_mes, int(regra.get("n", 1)))

    # dia fixo
    ultimo = calendar.monthrange(alvo_ano, alvo_mes)[1]
    d = date(alvo_ano, alvo_mes, min(int(regra.get("dia", 20)), ultimo))
    ajuste = regra.get("ajuste", "antecipa")
    if eh_dia_util(d) or ajuste == "nenhum":
        return d
    return proximo_dia_util(d) if ajuste == "posterga" else dia_util_anterior(d)
