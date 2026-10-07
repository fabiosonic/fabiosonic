"""Revisão 14: perfil da competência no último dia do mês (abertura/opção no meio do mês), nomes
reais aceitos como conferente, formas legítimas de URL oficial."""
from datetime import date

import pytest

from mo_autonomo.clientes.perfil import data_da_competencia, montar_perfil
from mo_autonomo.normas.catalogo import Catalogo, NormaInvalida, url_oficial
from tests.conftest import catalogo_teste
from tests.test_perfil import emp, rfb


def test_empresa_aberta_no_meio_do_mes_tem_regime_na_competencia():
    s = {"opcao_simples": "S", "data_opcao_simples": date(2026, 9, 15), "data_exclusao_simples": None,
         "opcao_mei": "N", "data_opcao_mei": None, "data_exclusao_mei": None}
    r = rfb(s)
    r["estabelecimento"].update({"data_inicio": date(2026, 9, 15), "data_situacao": date(2026, 9, 15)})
    p = montar_perfil(emp("SIMPLES"), r, catalogo_teste(), data_da_competencia("2026-09"))
    assert p.regime == "SIMPLES" and not [x for x in p.pendencias if x.bloqueia]
    assert data_da_competencia("2026-02") == date(2026, 2, 28)


def _n(quem):
    return {"id": "N", "titulo": "N", "area": "t", "status": "CONFERIDO", "fonte_url": "https://www.gov.br/x",
            "conferido_por": quem, "conferido_em": "2026-01-01", "hash_texto": "a" * 64}


@pytest.mark.parametrize("quem", ["Ai Ling", "Kauã Ai", "Maria Ia", "Auto Ferreira", "Ana Modelo",
                                  "Roberto Sistema", "Gemini Santos", "Zé", "Lu"])
def test_nomes_reais_aceitos(quem):
    Catalogo.de_lista([_n(quem)])


@pytest.mark.parametrize("quem", ["IA", "Sistema", "Claude", "ChatGPT", "IA local", "gpt-4o", "Ollama"])
def test_ferramenta_recusada(quem):
    with pytest.raises(NormaInvalida):
        Catalogo.de_lista([_n(quem)])


@pytest.mark.parametrize("url", ["https://www.planalto.gov.br:443/x", "HTTPS://www.planalto.gov.br/x",
                                 "https://www.planalto.gov.br./x", "https://www.gov.br/x?mailto=a@b"])
def test_formas_legitimas_de_url_oficial(url):
    assert url_oficial(url)


@pytest.mark.parametrize("url", ["https://evil.com\\.gov.br/x", "https://a@www.gov.br/x", "https://www.gov.br:8443/x",
                                 "http://www.gov.br/x", "https://www.gov.br.evil.com/x"])
def test_truques_continuam_recusados(url):
    assert not url_oficial(url)


# --- revisão 15 ---
from mo_autonomo.clientes.perfil import Perfis, perfil_na_competencia  # noqa: E402
from mo_autonomo.clientes.cadastro import Carteira  # noqa: E402


def test_exclusao_do_simples_no_meio_do_mes_vira_pendencia():
    s = {"opcao_simples": "S", "data_opcao_simples": date(2020, 1, 1), "data_exclusao_simples": date(2026, 9, 15),
         "opcao_mei": "N", "data_opcao_mei": None, "data_exclusao_mei": None}
    e = emp("PRESUMIDO")
    perfis = Perfis(Carteira([e]), {e.cnpj: rfb(s)}, catalogo_teste())
    p = perfil_na_competencia(perfis, e.cnpj, "2026-09")
    assert p.regime is None and any(x.codigo == "REGIME_ALTERADO_NA_COMPETENCIA" and x.bloqueia for x in p.pendencias)
    assert perfil_na_competencia(perfis, e.cnpj, "2026-10").regime == "PRESUMIDO"


@pytest.mark.parametrize("quem", ["I.A.", "A.I.", "IA.", "ia!", "Sistema.", "Automático.", "IA IA", "ia-local",
                                  "Ia - local", "IA (revisado)", "Modelo de IA", "IA Generativa", "Gemini 2.5",
                                  "Opus", "Claude_Code", "ClaudeOpus"])
def test_ferramenta_disfarcada_recusada(quem):
    with pytest.raises(NormaInvalida):
        Catalogo.de_lista([_n(quem)])


def test_host_com_dois_pontos_finais_recusado():
    assert not url_oficial("https://www.gov.br..:443/x")
