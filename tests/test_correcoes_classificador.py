"""Pacote C: extração de competência e falsos positivos."""
from datetime import datetime

import pytest

from mo_obrigacoes.catalogo import CATALOGO
from mo_obrigacoes.classificador import Regra, classificar, competencia_por_caminho, extrair_competencia

REGRAS = [Regra(c["codigo"], c.get("periodicidade", "mensal"), c["departamento"], c["reconhecimento"]) for c in CATALOGO]


@pytest.mark.parametrize("texto, esperado", [
    ("Recibo\nData da transmissão: 15/10/2026\nPeríodo de apuração: 2026-09", "2026-09"),
    ("Recibo de Entrega da DCTFWeb\nData de transmissão 14/10/2026 10:31", None),
    ("Extrato\nPeríodo: 01/09/2026 a 30/09/2026", "2026-09"),
    ("Referência: 01/09/2026", "2026-09"),
    ("<det><prod><qCom>12.2000</qCom></prod></det><ide><dhEmi>2026-09-15T10:00:00-03:00</dhEmi></ide>", "2026-09"),
    ("Endereço: Rua do Mar 2026, Centro", None),
    ("DAS set/2026.pdf", "2026-09"),
    ("Holerite SET-2026", "2026-09"),
    ("Competência: setembro de 2026", "2026-09"),
])
def test_competencia_mensal(texto, esperado):
    assert extrair_competencia(texto) == esperado


def test_exercicio_nao_vence_ano_calendario():
    assert extrair_competencia("Exercício 2026 Ano-calendário 2025", "anual") == "2025-12"
    assert extrair_competencia("Demonstrações do exercício 2025", "anual") == "2025-12"


def test_pasta_com_mes_abreviado():
    assert competencia_por_caminho("2026/Set/01 - Fiscal/x.pdf") == "2026-09"


def test_nome_sem_competencia_nao_identifica_sozinho():
    r = classificar(REGRAS, "Comprovante das despesas.pdf", "", "", datetime(2026, 10, 5))
    assert not r.identificado
    r = classificar(REGRAS, "DAS.pdf", "", "2026/09 - Setembro/01 - Fiscal/DAS.pdf", datetime(2026, 10, 5))
    assert (r.codigo, r.competencia) == ("DAS", "2026-09")  # digitalizado na pasta do mês continua identificado
    r = classificar(REGRAS, "FGTS setembro 2026.pdf", "", "", datetime(2026, 10, 5))
    assert r.codigo == "FGTS_DIGITAL"
