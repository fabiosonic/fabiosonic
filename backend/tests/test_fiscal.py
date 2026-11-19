from datetime import UTC, datetime

import pytest
from lxml import etree

from moxml.fiscal import chave as chv
from moxml.fiscal import xmlfiscal as xf
from moxml.fiscal.xmlfiscal import TipoXML
from tests.laboratorio import gerador

CNPJ = "99000001000101"


@pytest.fixture(scope="module")
def emissor():
    _pfx, k, c = gerador.gerar_certificado_teste(CNPJ, "EMISSOR")
    return k, c


def test_chave_valida_e_campos():
    ch = chv.montar_chave("RJ", 2026, 11, CNPJ, "65", 1, 1234, 1, "12345678")
    ck = chv.analisar(ch)
    assert (ck.uf, ck.modelo, ck.serie, ck.numero, ck.cnpj, ck.mes) == ("RJ", "65", 1, 1234, CNPJ, 11)


@pytest.mark.parametrize("mutacao,erro", [
    (lambda c: c[:-1] + str((int(c[-1]) + 1) % 10), "dígito verificador"),
    (lambda c: c[:43], "44 posições"),
    (lambda c: c[:20] + "57" + c[22:], "modelo"),
    (lambda c: "99" + c[2:], "UF"),
])
def test_chave_invalida(mutacao, erro):
    ch = chv.montar_chave("RJ", 2026, 11, CNPJ, "55", 1, 10, 1, "87654321")
    with pytest.raises(chv.ChaveInvalida, match=erro):
        chv.analisar(mutacao(ch))


def test_chave_cnpj_alfanumerico():
    ch = chv.montar_chave("RJ", 2026, 11, "12ABC34501DE35", "55", 1, 10, 1, "87654321")
    assert chv.analisar(ch).cnpj == "12ABC34501DE35"


def test_xml_autorizado_e_assinatura(emissor):
    k, c = emissor
    ch, proc, _ = gerador.gerar_nfe(CNPJ, "EMISSOR", "RJ", "55", 1, 7, datetime.now(UTC), k, c)
    d = xf.ler(proc)
    assert d.tipo == TipoXML.NFE_AUTORIZADA and d.e_xml_integral and d.assinatura_ok
    assert d.chave == ch and d.cnpj_emitente == CNPJ and d.protocolo


def test_xml_adulterado_detectado(emissor):
    k, c = emissor
    _, proc, _ = gerador.gerar_nfe(CNPJ, "EMISSOR", "RJ", "55", 1, 8, datetime.now(UTC), k, c)
    adulterado = proc.replace(b"<vNF>", b"<vNF>9")
    d = xf.ler(adulterado)
    assert not d.valido and any(p.codigo == "ASSINATURA_INVALIDA" for p in d.problemas)


def test_xml_sem_protocolo_e_montagem_nfeproc(emissor):
    k, c = emissor
    ch, nfe, prot = gerador.gerar_nfe(CNPJ, "EMISSOR", "RJ", "65", 1, 9, datetime.now(UTC), k, c, protocolo=False)
    d = xf.ler(nfe)
    assert d.tipo == TipoXML.NFE_SEM_PROTOCOLO and not d.e_xml_integral
    proc = xf.montar_nfeproc(nfe, prot)
    d2 = xf.ler(proc)
    assert d2.tipo == TipoXML.NFE_AUTORIZADA and d2.assinatura_ok and d2.chave == ch


def test_evento_e_inutilizacao(emissor):
    k, c = emissor
    ch, _, _ = gerador.gerar_nfe(CNPJ, "EMISSOR", "RJ", "55", 1, 10, datetime.now(UTC), k, c)
    ev = xf.ler(gerador.gerar_evento_cancelamento(ch, CNPJ, datetime.now(UTC), k, c))
    assert ev.tipo == TipoXML.EVENTO and ev.tp_evento == "110111" and ev.protocolo and ev.chave == ch
    inut = xf.ler(gerador.gerar_inutilizacao(CNPJ, "RJ", "55", 1, 11, 15, 2026))
    assert inut.tipo == TipoXML.INUTILIZACAO and (inut.numero, inut.numero_final) == (11, 15)


@pytest.mark.parametrize("conteudo,tipo", [
    (b"<nfeProc xmlns='http://www.portalfiscal.inf.br/nfe'><NFe><infNFe", TipoXML.INCOMPLETO),
    (b"<raiz>texto</raiz>", TipoXML.INVALIDO),
    (b"", TipoXML.INCOMPLETO),
    (b"<?xml version='1.0'?><!DOCTYPE x [<!ENTITY e SYSTEM 'file:///etc/passwd'>]><x>&e;</x>", TipoXML.INVALIDO),
])
def test_xml_invalido_incompleto(conteudo, tipo):
    assert xf.ler(conteudo).tipo == tipo


def test_chave_divergente_do_conteudo(emissor):
    k, c = emissor
    _, proc, _ = gerador.gerar_nfe(CNPJ, "EMISSOR", "RJ", "55", 1, 12, datetime.now(UTC), k, c)
    raiz = etree.fromstring(proc)
    raiz.find(".//{http://www.portalfiscal.inf.br/nfe}nNF").text = "13"
    d = xf.ler(etree.tostring(raiz))
    assert any(p.codigo == "CHAVE_DIVERGENTE" for p in d.problemas)


def test_validacao_xsd_oficial_registra_aviso_sem_rejeitar(emissor):
    # o XML de laboratório é propositalmente mínimo: o pacote PL_010g aponta divergências como AVISO
    k, c = emissor
    _, proc, _ = gerador.gerar_nfe(CNPJ, "EMISSOR", "RJ", "55", 1, 14, datetime.now(UTC), k, c)
    d = xf.ler(proc)
    xsd = [p for p in d.problemas if p.codigo == "XSD"]
    assert xsd and not any(p.grave for p in xsd) and d.e_xml_integral


def test_assinatura_c14n_exclusiva(emissor):
    """Regressão: NF-e/NFC-e reais assinam com C14N exclusiva; a verificação deve aceitá-la."""
    from lxml import etree as ET
    k, c = emissor
    _, proc, _ = gerador.gerar_nfe(CNPJ, "EMISSOR", "RJ", "65", 5, 28593, datetime.now(UTC), k, c)
    inf = ET.fromstring(proc).find(".//{http://www.portalfiscal.inf.br/nfe}infNFe")
    assert inf is not None
    d = xf.ler(proc)
    assert d.assinatura_ok and d.e_xml_integral
