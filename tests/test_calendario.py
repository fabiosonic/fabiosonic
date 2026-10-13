from datetime import date

from mo_obrigacoes.calendario import (calcular_vencimento, eh_dia_util, enesimo_dia_util, feriados_nacionais,
                                      pascoa, ultimo_dia_util)


def test_pascoa():
    assert pascoa(2026) == date(2026, 4, 5)
    assert pascoa(2027) == date(2027, 3, 28)


def test_feriados_2026():
    f = feriados_nacionais(2026)
    assert date(2026, 2, 17) in f  # carnaval
    assert date(2026, 4, 3) in f   # sexta-feira santa
    assert date(2026, 6, 4) in f   # corpus christi
    assert date(2026, 11, 20) in f  # consciência negra (Lei 14.759/2023)
    assert not eh_dia_util(date(2026, 10, 12))


def test_dias_uteis():
    assert ultimo_dia_util(2026, 10) == date(2026, 10, 30)
    assert enesimo_dia_util(2026, 11, 10) == date(2026, 11, 16)  # 02/11 é feriado


def test_vencimentos():
    # DAS 09/2026: 20/10/2026 (terça)
    assert calcular_vencimento({"tipo": "dia_fixo", "dia": 20, "meses_apos": 1, "ajuste": "posterga"}, "2026-09") == date(2026, 10, 20)
    # PIS/COFINS 09/2026: 25/10/2026 é domingo -> antecipa para sexta 23
    assert calcular_vencimento({"tipo": "dia_fixo", "dia": 25, "meses_apos": 1, "ajuste": "antecipa"}, "2026-09") == date(2026, 10, 23)
    # ISS dia 10/10/2026 sábado -> posterga; 12/10 feriado -> 13/10
    assert calcular_vencimento({"tipo": "dia_fixo", "dia": 10, "meses_apos": 1, "ajuste": "posterga"}, "2026-09") == date(2026, 10, 13)
    # DEFIS ano 2026 -> 31/03/2027 (quarta)
    assert calcular_vencimento({"tipo": "dia_fixo", "dia": 31, "mes": 3, "anos_apos": 1}, "2026-12", "anual") == date(2027, 3, 31)
    # ECF ano-calendário 2026 -> último dia útil de julho/2027
    assert calcular_vencimento({"tipo": "ultimo_dia_util", "mes": 7}, "2026-12", "anual") == date(2027, 7, 30)
    # dia 31 em mês de 30 dias
    assert calcular_vencimento({"tipo": "dia_fixo", "dia": 31, "meses_apos": 1, "ajuste": "nenhum"}, "2026-08") == date(2026, 9, 30)
