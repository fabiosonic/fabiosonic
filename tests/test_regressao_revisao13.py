"""Revisão 13: URL oficial sem truque, conferente humano, hash obrigatório, vigência padrão = hoje,
perfil na data (situação/abertura), decisão judicial, faturamento sem chave, calendário avisa."""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from mo_autonomo.clientes.perfil import montar_perfil
from mo_autonomo.especialista.faturamento import faturamento
from mo_autonomo.normas.catalogo import Catalogo, NormaInvalida, url_oficial
from mo_autonomo.obrigacoes.calendario import sem_regime
from tests.conftest import CNPJ_A, catalogo_teste
from tests.test_perfil import emp, rfb


@pytest.mark.parametrize("url", ["https://evil.com\\.gov.br/lei", "https://evil.com\\@www.gov.br/lei",
                                 "https://user@www.gov.br/x", "https://www.gov.br:8443/x", "https://gov.br.evil.com/x"])
def test_url_oficial_nao_se_burla(url):
    assert not url_oficial(url)


def _norma(**kw):
    d = {"id": "N", "titulo": "N", "area": "t", "status": "CONFERIDO", "fonte_url": "https://www.gov.br/x",
         "conferido_por": "Maria Souza", "conferido_em": "2026-01-01", "hash_texto": "a" * 64, "parametros": {"p": 1}}
    d.update(kw)
    return d


@pytest.mark.parametrize("quem", ["   ", "-", "Claude Opus", "IA local (Ollama)", "gpt-4", "Sistema"])
def test_conferente_precisa_ser_pessoa(quem):
    with pytest.raises(NormaInvalida):
        Catalogo.de_lista([_norma(conferido_por=quem)])


def test_conferencia_no_futuro_e_sem_hash_recusadas():
    with pytest.raises(NormaInvalida):
        Catalogo.de_lista([_norma(conferido_em=str(date.today() + timedelta(days=1)))])
    with pytest.raises(NormaInvalida):
        Catalogo.de_lista([_norma(hash_texto=None)])


def test_decisao_judicial_exige_data_e_modulacao():
    for dj in ({"transito_em_julgado": "não", "modulacao": "x"}, {"transito_em_julgado": "2024-01-01", "modulacao": "pendente"}):
        with pytest.raises(NormaInvalida):
            Catalogo.de_lista([_norma(decisao_judicial=dj)])


def test_parametro_sem_data_usa_vigencia_de_hoje():
    c = Catalogo.de_lista([_norma(vigencia={"inicio": "2010-01-01", "fim": "2020-12-31"})])
    assert c.parametro("N", "p") is None and c.parametro("N", "p", date(2015, 1, 1)) == 1


def test_situacao_atual_nao_vale_para_data_anterior():
    r = rfb()
    r["estabelecimento"].update({"data_situacao": date(2026, 5, 1), "data_inicio": date(2026, 3, 1)})
    p = montar_perfil(emp("SIMPLES"), r, catalogo_teste(), date(2026, 4, 10))
    assert p.situacao_ativa is None and any(x.codigo == "SITUACAO_NA_DATA_DESCONHECIDA" for x in p.pendencias)
    p = montar_perfil(emp("SIMPLES"), r, catalogo_teste(), date(2026, 2, 10))
    assert any(x.codigo == "ANTERIOR_A_ABERTURA" for x in p.pendencias)


def test_faturamento_sem_chave_nao_se_anula():
    regs = [{"chave": None, "sha256": s, "resumo": {"tipo": "NFSE", "prestador": CNPJ_A, "valor": v}}
            for s, v in (("a", "1000.00"), ("b", "2500.00"))]
    f = faturamento(regs, CNPJ_A, catalogo_teste())
    assert f["por_tipo"]["NFSE"] == Decimal("3500.00")


def test_calendario_avisa_regime_indefinido():
    from types import SimpleNamespace
    p = SimpleNamespace(regime=None, apelido="ALFA", pendencias=[SimpleNamespace(codigo="REGIME_DIVERGENTE")])
    cat = Catalogo.de_lista([_norma(id="OB", parametros={"obrigacoes": [
        {"codigo": "G", "dia": 20, "meses_apos_competencia": 1, "regimes": ["SIMPLES"]}]})])
    assert sem_regime({CNPJ_A: p}, cat) == ["ALFA: regime indefinido (REGIME_DIVERGENTE)"]
