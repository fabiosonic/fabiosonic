import pytest

from mo_autonomo.documentos.classificador import classificar
from mo_autonomo.dominio.pastas import TIPOS_PADRAO, ConflitoArquivo, caminho_destino, gravar, rotas
from tests.conftest import (CNPJ_A, CNPJ_B, CNPJ_X, carteira_teste, catalogo_teste, chave_nfe, cte_xml,
                            evento_xml, nfe_xml, nfse_abrasf_xml, nfse_nacional_xml)


def r(xml, cat=None):
    return [(x.cnpj, x.tipo, bool(x.pendencia)) for x in rotas(classificar(xml)["doc"], carteira_teste(), cat or catalogo_teste())]


def test_nfe_saida_e_entrada_entre_clientes():
    assert r(nfe_xml(emit=CNPJ_A, dest=CNPJ_B)) == [(CNPJ_A, "NFE_SAIDA", False), (CNPJ_B, "NFE_ENTRADA", False)]


def test_nfe_sem_moc_conferido_fica_pendente():
    assert r(nfe_xml(), catalogo_teste(conferidas=[])) == [(CNPJ_A, None, True)]


def test_nfe_entrada_propria_pendente():
    assert r(nfe_xml(tp_nf="0")) == [(CNPJ_A, None, True)]


def test_nfce_nfse_cte_eventos():
    assert r(nfe_xml(modelo="65")) == [(CNPJ_A, "NFCE_SAIDA", False)]
    assert r(nfse_nacional_xml()) == [(CNPJ_A, "NFSE_TOMADA", False)]
    assert r(nfse_abrasf_xml()) == [(CNPJ_A, "NFSE_EMITIDA", False), (CNPJ_B, "NFSE_TOMADA", False)]
    assert r(cte_xml()) == [(CNPJ_A, "CTE_ENTRADA", False)]
    assert r(cte_xml(emit=CNPJ_A, dest=CNPJ_X))[0][2] is True
    assert r(evento_xml(chave_nfe(CNPJ_A, 1), autor=CNPJ_X)) == [(CNPJ_A, "NFE_EVENTOS", False)]


def test_fora_da_carteira():
    assert r(nfe_xml(emit=CNPJ_X, dest=None)) == [(None, None, True)]


def test_gravar_nao_sobrescreve(tmp_path):
    emp = carteira_teste().get(CNPJ_A)
    destino = caminho_destino(tmp_path, TIPOS_PADRAO, emp, "NFE_SAIDA", "2026-10", "x.xml")
    assert str(destino).endswith("NFE SAIDA/101-ALFA COMERCIO/102026/x.xml")
    assert gravar(destino, b"a") == "GRAVADO"
    assert gravar(destino, b"a") == "JA_EXISTIA"
    with pytest.raises(ConflitoArquivo):
        gravar(destino, b"b")
    assert destino.read_bytes() == b"a"
