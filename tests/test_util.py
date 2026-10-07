from decimal import Decimal

import pytest

from mo_autonomo.util.arquivos import XMLInseguro, dumps, loads, parse_xml_seguro
from mo_autonomo.util.dinheiro import ValorInvalido, dinheiro, formatar_br, soma
from mo_autonomo.util.documentos_id import cnpj_valido, cpf_valido, formatar_cnpj, gerar_cnpj, gerar_cpf


def test_dinheiro_recusa_float():
    with pytest.raises(ValorInvalido):
        dinheiro(0.1)


def test_dinheiro_arredonda_half_up():
    assert dinheiro("2.345") == Decimal("2.35")
    assert dinheiro("2.344") == Decimal("2.34")
    assert dinheiro("1.234,565") == Decimal("1234.57")
    assert soma(["0.10", "0.20"]) == Decimal("0.30")


def test_formatar_br():
    assert formatar_br(Decimal("1234567.8")) == "R$ 1.234.567,80"
    assert formatar_br(Decimal("-5")) == "-R$ 5,00"


def test_cnpj_cpf():
    c = gerar_cnpj("112223330001")
    assert cnpj_valido(c) and c == "11222333000181"
    assert not cnpj_valido("11222333000182")
    assert not cnpj_valido("11111111111111")
    assert cpf_valido(gerar_cpf("111444777")) and gerar_cpf("111444777") == "11144477735"
    assert formatar_cnpj(c) == "11.222.333/0001-81"


def test_xml_com_entidade_recusado():
    with pytest.raises(XMLInseguro):
        parse_xml_seguro(b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><x>&a;</x>')


def test_json_roundtrip_decimal_data():
    from datetime import date
    obj = {"v": Decimal("1.10"), "d": date(2026, 1, 2), "b": b"abc"}
    volta = loads(dumps(obj))
    assert volta["v"] == Decimal("1.10") and volta["d"] == date(2026, 1, 2)
    assert volta["b"]["tamanho"] == 3
