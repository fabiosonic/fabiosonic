from datetime import date
from types import SimpleNamespace

import pytest

from mo_autonomo.normas.catalogo import Catalogo, NormaInvalida, url_oficial


def base(**kw):
    return {"id": "N1", "titulo": "t", "area": "fiscal", **kw}


def test_catalogo_real_carrega_e_nada_esta_conferido():
    c = Catalogo.carregar("config/normas")
    assert len(c.normas) >= 20
    assert c.resumo()["CONFERIDO"] == 0  # conferência é ato humano


def test_conferido_exige_campos():
    with pytest.raises(NormaInvalida, match="sem"):
        Catalogo.de_lista([base(status="CONFERIDO")])


def test_conferido_exige_fonte_oficial():
    with pytest.raises(NormaInvalida, match="não oficial"):
        Catalogo.de_lista([base(status="CONFERIDO", fonte_url="https://blog.exemplo.com/x",
                                conferido_por="Fulano", conferido_em="2026-01-01")])
    assert url_oficial("https://www.planalto.gov.br/x")
    assert url_oficial("https://www.cfc.org.br/x")
    assert not url_oficial("http://www.planalto.gov.br/x")
    assert not url_oficial("https://gov.br.falso.com/x")


def test_conferido_por_ia_recusado():
    with pytest.raises(NormaInvalida, match="pessoa"):
        Catalogo.de_lista([base(status="CONFERIDO", fonte_url="https://www.gov.br/x",
                                conferido_por="Claude", conferido_em="2026-01-01")])


def test_decisao_judicial_sem_transito():
    with pytest.raises(NormaInvalida, match="regra 4"):
        Catalogo.de_lista([base(status="CONFERIDO", fonte_url="https://portal.stf.jus.br/x",
                                conferido_por="Fulano", conferido_em="2026-01-01",
                                decisao_judicial={"transito_em_julgado": None})])


def test_parametro_so_de_norma_conferida_e_vigente():
    c = Catalogo.de_lista([
        base(id="P", parametros={"x": 1}),
        base(id="C", status="CONFERIDO", fonte_url="https://www.gov.br/x", conferido_por="Fulano",
             conferido_em="2026-01-01", parametros={"x": 2}, vigencia={"inicio": "2026-01-01", "fim": "2026-12-31"}),
    ])
    assert c.parametro("P", "x") is None
    assert c.parametro("C", "x") == 2
    assert c.parametro("C", "x", date(2025, 6, 1)) is None
    assert c.parametro("AUSENTE", "x") is None
    assert c.status("AUSENTE") == "AUSENTE"


def test_aplica_ao_perfil():
    c = Catalogo.de_lista([base(id="RJ", aplica_se={"ufs": ["RJ"], "regimes": ["SIMPLES"]}),
                           base(id="OBRA", aplica_se={"cnae_prefixos": ["412"]})])
    p = SimpleNamespace(regime="SIMPLES", uf="RJ", municipio=None, natureza_juridica=None, cnaes=["4120400"])
    assert {n.id for n in c.aplicaveis(p)} == {"RJ", "OBRA"}
    p2 = SimpleNamespace(regime="PRESUMIDO", uf="RJ", municipio=None, natureza_juridica=None, cnaes=["6201501"])
    assert c.aplicaveis(p2) == []


def test_norma_duplicada(tmp_path):
    (tmp_path / "a.yaml").write_text("- {id: X, titulo: t, area: a}\n", encoding="utf-8")
    (tmp_path / "b.yaml").write_text("- {id: X, titulo: t, area: a}\n", encoding="utf-8")
    with pytest.raises(NormaInvalida, match="duplicada"):
        Catalogo.carregar(tmp_path)


def test_dominio_parecido_nao_e_oficial():
    for u in ("https://fakecfc.org.br/x", "https://notcpc.org.br/x", "https://xgov.br/x", "https://gov.br.evil.com/x"):
        assert not url_oficial(u), u
    assert url_oficial("https://gov.br/x") and url_oficial("https://www.in.gov.br/x")
