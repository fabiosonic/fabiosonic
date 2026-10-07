from datetime import date
from decimal import Decimal

import pytest

from mo_autonomo.documentos.classificador import classificar, tipo_bruto
from mo_autonomo.documentos.ofx import ler_ofx
from mo_autonomo.entrada.anexos import ZipSuspeito, anexos_do_email, expandir
from tests.conftest import (CNPJ_A, CNPJ_B, CNPJ_X, chave_nfe, cte_xml, eml_bytes, evento_xml, nfe_xml,
                            nfse_abrasf_xml, nfse_nacional_xml, ofx_bytes, zip_bytes)


def test_nfe():
    r = classificar(nfe_xml(numero=12, itens=(("12345678", "5102", "60.00"), ("33030010", "5405", "40.00"))))
    d = r["doc"]
    assert r["classe"] == "NFE" and d["chave"] == chave_nfe(CNPJ_A, 12)
    assert d["emitente_cnpj"] == CNPJ_A and d["destinatario_cnpj"] == CNPJ_X
    assert d["emissao"] == date(2026, 10, 1) and d["competencia"] == "2026-10"
    assert d["totais"]["vProd"] == Decimal("100.00") and len(d["itens"]) == 2
    assert d["itens"][1]["ncm"] == "33030010" and d["itens"][0]["csosn"] == "102"
    assert d["autorizacao_cstat"] == "100" and d["crt"] == "1"


def test_nfce_e_evento():
    assert classificar(nfe_xml(modelo="65"))["classe"] == "NFCE"
    ch = chave_nfe(CNPJ_A, 1)
    e = classificar(evento_xml(ch))["doc"]
    assert e["tipo"] == "EVENTO_NFE" and e["chave_ref"] == ch and e["tp_evento"] == "110111"
    ch65 = chave_nfe(CNPJ_A, 1, "65")
    assert classificar(evento_xml(ch65))["classe"] == "EVENTO_NFCE"


def test_cte():
    d = classificar(cte_xml())["doc"]
    assert d["tipo"] == "CTE" and CNPJ_A in d["participantes"] and d["totais"]["vTPrest"] == Decimal("250.00")


def test_nfse_nacional():
    d = classificar(nfse_nacional_xml(fed={"vRetCSLL": "10.00"}))["doc"]
    assert d["tipo"] == "NFSE" and d["padrao"] == "NACIONAL"
    assert d["prestador_cnpj"] == CNPJ_X and d["tomador_cnpj"] == CNPJ_A
    assert d["totais"]["vServ"] == Decimal("1000.00") and d["iss_retencao_codigo"] == "2"
    assert d["retencoes_federais"]["vRetCSLL"] == Decimal("10.00") and d["competencia"] == "2026-10"


def test_nfse_abrasf():
    d = classificar(nfse_abrasf_xml())["doc"]
    assert d["padrao"] == "ABRASF" and d["prestador_cnpj"] == CNPJ_A and d["tomador_cnpj"] == CNPJ_B
    assert d["chave"].startswith("ABRASF-") and d["c_trib_nac"] == "17.01"


def test_desconhecidos():
    assert classificar(b"<?xml version='1.0'?><foo/>")["classe"] == "XML_DESCONHECIDO"
    assert classificar(b"<?xml version='1.0'?><foo>")["classe"] == "XML_INVALIDO"
    assert classificar(b"%PDF-1.4 ...")["classe"] == "PDF"
    assert classificar(b"\x89PNG....")["classe"] == "IMAGEM"
    assert tipo_bruto(b"texto qualquer") == "DESCONHECIDO"


def test_ofx():
    o = ler_ofx(ofx_bytes())["extratos"][0]
    assert o["conta"]["banco"] == "341" and len(o["transacoes"]) == 2
    assert o["transacoes"][1]["valor"] == Decimal("-320.50") and o["transacoes"][0]["data"] == date(2026, 10, 5)


def test_ofx_formato_br_e_varias_contas():
    br = ofx_bytes(trans=(("20261005", "1.234,56", "PIX", "9"),))
    assert ler_ofx(br)["extratos"][0]["transacoes"][0]["valor"] == Decimal("1234.56")
    dois = ofx_bytes().decode("latin-1").replace(
        "</STMTRS>", "</STMTRS><STMTRS><BANKACCTFROM><BANKID>001<ACCTID>999</BANKACCTFROM>"
        "<BANKTRANLIST><STMTTRN><TRNTYPE>OTHER<DTPOSTED>20261007<TRNAMT>-5.00<FITID>Z<MEMO>X</STMTTRN>"
        "</BANKTRANLIST></STMTRS>").encode("latin-1")
    ex = ler_ofx(dois)["extratos"]
    assert [(e["conta"]["banco"], e["conta"]["conta"], len(e["transacoes"])) for e in ex] == [("341", "12345", 2), ("001", "999", 1)]
    nan = ofx_bytes(trans=(("20261005", "NaN", "X", "1"),))
    assert classificar(nan)["classe"] == "OFX_INVALIDO"
    assert classificar(ofx_bytes())["classe"] == "OFX"


def test_email_com_zip_aninhado():
    interno = zip_bytes({"b.xml": nfe_xml(numero=2)})
    externo = zip_bytes({"a.xml": nfe_xml(numero=1), "pasta/interno.zip": interno})
    anexos = anexos_do_email(eml_bytes({"notas.zip": externo, "guia.pdf": b"%PDF-1.4"}), "u1")
    nomes = sorted(a.nome for a in anexos)
    assert nomes == ["a.xml", "b.xml", "guia.pdf"]
    assert any("interno.zip/b.xml" in a.origem for a in anexos)


def test_zip_bomba():
    bomba = zip_bytes({"zeros.xml": b"0" * 5_000_000})
    with pytest.raises(ZipSuspeito):
        expandir("x.zip", bomba, "t")


def test_zip_profundo():
    z = zip_bytes({"a.xml": b"<a/>"})
    for _ in range(7):
        z = zip_bytes({"n.zip": z})
    with pytest.raises(ZipSuspeito, match="níveis"):
        expandir("x.zip", z, "t")


def test_nome_com_caminho_malicioso():
    a = expandir("x.zip", zip_bytes({"../../etc/passwd.xml": b"<a/>"}), "t")
    assert a[0].nome == "passwd.xml"
