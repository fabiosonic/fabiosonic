"""FGTS de aprendiz com alíquota própria (norma) e retenções parciais da NFS-e nacional por código."""
from decimal import Decimal
from types import SimpleNamespace

from mo_autonomo.dp.folha import conferir
from mo_autonomo.especialista.regras import r_retencoes_federais
from mo_autonomo.normas.catalogo import Catalogo
from tests.conftest import CNPJ_A, catalogo_teste

CONF = {"status": "CONFERIDO", "fonte_url": "https://www.gov.br/x", "conferido_por": "Maria Souza",
        "conferido_em": "2026-01-01", "hash_texto": "a" * 64}


def _linha(**kw):
    l = {"cpf": "00000000191", "nome": "Aprendiz", "competencia": "2026-09", "salario_contribuicao": Decimal("1000.00"),
         "inss_descontado": Decimal("100.00"), "base_irrf": Decimal("1000.00"), "dependentes": 0,
         "irrf_descontado": Decimal("0.00"), "remuneracao_fgts": Decimal("1000.00"), "fgts_depositado": Decimal("20.00"),
         "aprendiz": True}
    l.update(kw)
    return l


def _cat_fgts(**params):
    return Catalogo.de_lista([{"id": "LEI_8036_FGTS", "titulo": "FGTS", "area": "dp", "parametros": params, **CONF}])


def test_aprendiz_usa_aliquota_propria():
    r = conferir([_linha()], CNPJ_A, _cat_fgts(aliquota_deposito="0.08", aliquota_deposito_aprendiz="0.02"))
    assert not [a for a in r["achados"] if a.regra == "DP_FGTS_DIVERGENTE"]
    r = conferir([_linha(fgts_depositado=Decimal("80.00"))], CNPJ_A,
                 _cat_fgts(aliquota_deposito="0.08", aliquota_deposito_aprendiz="0.02"))
    assert [a.regra for a in r["achados"]] == ["DP_FGTS_DIVERGENTE"]


def test_aprendiz_sem_parametro_fica_inativo():
    r = conferir([_linha()], CNPJ_A, _cat_fgts(aliquota_deposito="0.08"))
    assert not r["achados"] and any("aprendiz" in i for i in r["inativas"])


def _ctx(mapa):
    cat = Catalogo.de_lista([{"id": "LEIAUTE_NFSE_NACIONAL", "titulo": "L", "area": "f",
                              "parametros": {"retencao_por_codigo": mapa}, **CONF}])
    return SimpleNamespace(params={"codigos_servico_sujeitos": ["17"], "regimes_tomador_obrigados": ["PRESUMIDO"]},
                           perfil=SimpleNamespace(regime="PRESUMIDO"), catalogo=cat)


MAPA = {"0": [], "3": ["pis", "cofins", "csll"], "5": ["pis"], "8": ["csll"]}


def _doc(codigo, **ret):
    return {"padrao": "NACIONAL", "c_trib_nac": "170101", "pis_cofins_retencao_codigo": codigo,
            "retencoes_federais": {"pis": None, "cofins": None, "csll": None, **ret}, "emissao": None}


def test_retencao_parcial_conta():
    assert r_retencoes_federais(_doc("5", pis=Decimal("6.50")), _ctx(MAPA)) == []
    assert r_retencoes_federais(_doc("8", csll=Decimal("10.00")), _ctx(MAPA)) == []


def test_codigo_sem_retencao_aponta_e_codigo_desconhecido_nao_afirma():
    assert len(r_retencoes_federais(_doc("0"), _ctx(MAPA))) == 1
    assert r_retencoes_federais(_doc("9"), _ctx(MAPA)) == []
