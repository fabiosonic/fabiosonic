from datetime import date
from decimal import Decimal

from portal_contabil.fabrica import gerar_chave, gerar_cnpj
from portal_contabil.util import (chave_nfe_valida, cnpj_valido, cpf_valido, dec, moeda, parse_data,
                                  somar_meses)


def test_cnpj_numerico_e_alfanumerico():
    assert cnpj_valido("11.222.333/0001-81")
    assert not cnpj_valido("11.222.333/0001-82")
    # exemplo oficial da Receita Federal para o CNPJ alfanumérico (IN RFB 2.229/2024)
    assert cnpj_valido("12.ABC.345/01DE-35")
    assert not cnpj_valido("00000000000000")
    assert cnpj_valido(gerar_cnpj("AB12CD340001"))


def test_cpf():
    assert cpf_valido("529.982.247-25")
    assert not cpf_valido("111.111.111-11")


def test_chave_nfe():
    chave = gerar_chave("SP", date(2026, 1, 5), gerar_cnpj("123456780001"), "55", 1, 42)
    assert len(chave) == 44 and chave_nfe_valida(chave)
    adulterada = chave[:-1] + str((int(chave[-1]) + 1) % 10)
    assert not chave_nfe_valida(adulterada)


def test_dec_formatos_brasileiros():
    assert dec("1.234,56") == Decimal("1234.56")
    assert dec("1234.56") == Decimal("1234.56")
    assert dec("") == 0 and dec(None) == 0
    assert moeda(Decimal("1234567.8")) == "R$ 1.234.567,80"


def test_datas():
    assert parse_data("2026-03-10T10:00:00-03:00") == date(2026, 3, 10)
    assert parse_data("20260310120000[-3:BRT]") == date(2026, 3, 10)
    assert parse_data("10/03/2026") == date(2026, 3, 10)
    assert somar_meses("2026-01", -1) == "2025-12"
    assert somar_meses("2025-12", 13) == "2027-01"
