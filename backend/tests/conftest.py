"""Fixtures: aplicação isolada em diretório temporário + laboratório de testes. Nenhuma chamada real."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from moxml.config import Configuracoes
from moxml.db.modelos import Empresa
from moxml.motor.aplicacao import criar_aplicacao
from moxml.sefaz.transporte import LimitadorTaxa
from tests.laboratorio.sefaz_fake import Laboratorio

CNPJ = "99000001000101"
RAZAO = "LOJA LABORATORIO LTDA"


@pytest.fixture
def lab() -> Laboratorio:
    return Laboratorio()


@pytest.fixture
def app(tmp_path, lab):
    cfg = Configuracoes(home=tmp_path / "home", agendamento_ativo=False)
    a = criar_aplicacao(cfg)
    a.modo = "TESTE"  # única forma de usar o laboratório; em "REAL" a injeção é recusada
    a.limitador = LimitadorTaxa(padrao_por_minuto=1_000_000)
    a.transporte_soap = lambda _c: lab.transport()
    a.transporte_http = lambda _c: lab.transport()
    return a


@pytest.fixture
def empresa(app) -> Empresa:
    with app.sessoes() as s:
        e = Empresa(razao_social=RAZAO, cnpj=CNPJ, uf="RJ")
        s.add(e)
        s.commit()
        return e


@pytest.fixture
def base() -> datetime:
    return datetime.now(UTC) - timedelta(days=2)
