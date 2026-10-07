from datetime import date

from mo_autonomo.clientes.cadastro import Carteira, CadastroInvalido, Empresa
from mo_autonomo.clientes.perfil import montar_perfil
from tests.conftest import CNPJ_A, CNPJ_B, CNPJ_C, catalogo_teste

import pytest

D = date(2026, 10, 1)


def rfb(simples=None, situacao="02", uf="RJ", cnae="4781400"):
    return {"estabelecimento": {"situacao_cadastral": situacao, "uf": uf, "cnae_principal": cnae,
                                "cnaes_secundarias": ["4782201"]},
            "empresa": {"natureza_juridica": "2062"}, "simples": simples}


def emp(regime, cnpj=CNPJ_A):
    return Empresa("101", "ALFA", cnpj, regime, uf="RJ")


def test_so_dominio():
    p = montar_perfil(emp("PRESUMIDO", CNPJ_B), None, catalogo_teste(), D)
    assert p.regime == "PRESUMIDO" and p.regime_fonte == "DOMINIO"
    assert any(x.codigo == "SEM_DADOS_RFB" and not x.bloqueia for x in p.pendencias)


def test_rfb_confirma_simples():
    s = {"opcao_simples": "S", "data_opcao_simples": date(2020, 1, 1), "data_exclusao_simples": None,
         "opcao_mei": "N", "data_opcao_mei": None, "data_exclusao_mei": None}
    p = montar_perfil(emp("SIMPLES"), rfb(s), catalogo_teste(), D)
    assert p.regime == "SIMPLES" and p.regime_fonte == "RFB"
    assert p.cnaes == ["4781400", "4782201"] and p.natureza_juridica == "2062" and p.situacao_ativa
    assert not [x for x in p.pendencias if x.bloqueia]


def test_divergencia_rfb_x_dominio_vira_pendencia():
    s = {"opcao_simples": "S", "data_opcao_simples": date(2020, 1, 1), "data_exclusao_simples": None,
         "opcao_mei": "N", "data_opcao_mei": None, "data_exclusao_mei": None}
    p = montar_perfil(emp("PRESUMIDO"), rfb(s), catalogo_teste(), D)
    assert p.regime is None and p.regime_fonte == "DIVERGENTE"
    assert any(x.codigo == "REGIME_DIVERGENTE" and x.bloqueia for x in p.pendencias)


def test_vigencia_exclusao_no_meio_do_ano():
    s = {"opcao_simples": "N", "data_opcao_simples": date(2020, 1, 1), "data_exclusao_simples": date(2026, 6, 30),
         "opcao_mei": "N", "data_opcao_mei": None, "data_exclusao_mei": None}
    cat = catalogo_teste()
    antes = montar_perfil(emp("PRESUMIDO"), rfb(s), cat, date(2026, 5, 10))
    depois = montar_perfil(emp("PRESUMIDO"), rfb(s), cat, date(2026, 8, 10))
    assert antes.regime is None and any(x.codigo == "REGIME_DIVERGENTE" for x in antes.pendencias)
    assert depois.regime == "PRESUMIDO"


def test_dominio_diz_simples_rfb_diz_nao():
    s = {"opcao_simples": "N", "data_opcao_simples": date(2020, 1, 1), "data_exclusao_simples": date(2025, 12, 31),
         "opcao_mei": "N", "data_opcao_mei": None, "data_exclusao_mei": None}
    p = montar_perfil(emp("SIMPLES"), rfb(s), catalogo_teste(), D)
    assert p.regime is None and any(x.codigo == "REGIME_DIVERGENTE" for x in p.pendencias)


def test_mei():
    s = {"opcao_simples": "S", "data_opcao_simples": date(2021, 1, 1), "data_exclusao_simples": None,
         "opcao_mei": "S", "data_opcao_mei": date(2021, 1, 1), "data_exclusao_mei": None}
    assert montar_perfil(emp("MEI", CNPJ_C), rfb(s), catalogo_teste(), D).regime == "MEI"


def test_dicionario_nao_conferido_nao_usa_codigos():
    s = {"opcao_simples": "S", "data_opcao_simples": date(2020, 1, 1), "data_exclusao_simples": None,
         "opcao_mei": "N", "data_opcao_mei": None, "data_exclusao_mei": None}
    cat = catalogo_teste(conferidas=[])
    p = montar_perfil(emp("PRESUMIDO"), rfb(s), cat, D)
    # sem dicionário conferido a RFB não é usada para afirmar regime -> fica o Domínio
    assert p.regime == "PRESUMIDO" and p.situacao_ativa is None
    assert any(x.codigo == "DICIONARIO_RFB_NAO_CONFERIDO" for x in p.pendencias)


def test_situacao_inativa_e_uf_divergente():
    p = montar_perfil(emp("PRESUMIDO", CNPJ_B), rfb(None, situacao="08", uf="SP"), catalogo_teste(), D)
    cods = {x.codigo for x in p.pendencias}
    assert {"SITUACAO_CADASTRAL", "UF_DIVERGENTE"} <= cods and p.situacao_ativa is False


def test_regime_desconhecido():
    p = montar_perfil(emp(None), None, catalogo_teste(), D)
    assert p.regime is None and any(x.codigo == "REGIME_DESCONHECIDO" for x in p.pendencias)


def test_cadastro_csv(tmp_path):
    f = tmp_path / "e.csv"
    f.write_text(f"codigo_dominio;apelido;cnpj;regime;codigo_apuracao;uf;municipio_ibge;ie;ativa\n"
                 f"101;ALFA;{CNPJ_A};simples;;rj;3304557;;S\n", encoding="utf-8")
    c = Carteira.carregar(f)
    e = c.get(CNPJ_A)
    assert e.regime_dominio == "SIMPLES" and e.uf == "RJ" and e.pasta == "101-ALFA"
    f.write_text("codigo_dominio;apelido;cnpj;regime\n1;X;11111111111111;SIMPLES\n2;Y;"
                 f"{CNPJ_B};LUCRO\n", encoding="utf-8")
    with pytest.raises(CadastroInvalido) as exc:
        Carteira.carregar(f)
    assert "CNPJ inválido" in str(exc.value) and "regime desconhecido" in str(exc.value)
