import io
import zipfile
from datetime import date

from conftest import CLIENTE, EMPRESA, C, D, E, F, lote_de

from portal_contabil import fabrica as fb


def test_nfe_autorizada(venda):
    lote = lote_de(("n1.xml", fb.nfe_xml(1, D, E, C, venda)))
    assert len(lote.documentos) == 1
    d = lote.documentos[0]
    assert d.tipo == "NFE" and d.situacao == "autorizada" and d.numero == "1"
    assert d.emitente.documento == EMPRESA and d.destinatario.documento == CLIENTE
    assert d.valor_total == 1000 and d.itens[0].cfop == "5102" and d.itens[0].csosn == "102"


def test_nfe_sem_protocolo_e_cancelamento(venda):
    xml = fb.nfe_xml(2, D, E, C, venda)
    chave = fb.gerar_chave("SP", D, EMPRESA, "55", 1, 2)
    lote = lote_de(("n2.xml", xml), ("canc.xml", fb.evento_cancelamento_xml(chave, D)),
                   ("n3.xml", fb.nfe_xml(3, D, E, C, venda, protocolo=False)))
    sit = {d.numero: d.situacao for d in lote.documentos}
    assert sit == {"2": "cancelada", "3": "sem_protocolo"}


def test_zip_aninhado_e_duplicidade(venda):
    interno = io.BytesIO()
    with zipfile.ZipFile(interno, "w") as z:
        z.writestr("marco/n1.xml", fb.nfe_xml(1, D, E, C, venda))
    externo = io.BytesIO()
    with zipfile.ZipFile(externo, "w") as z:
        z.writestr("notas.zip", interno.getvalue())
        z.writestr("copia/n1.xml", fb.nfe_xml(1, D, E, C, venda))
        z.writestr("__MACOSX/._lixo", b"x")
        z.writestr("leia-me.pdf", b"%PDF")
    lote = lote_de(("lote.zip", externo.getvalue()))
    assert len(lote.documentos) == 1
    assert len(lote.duplicados) == 1
    assert any("pdf" in e.motivo for e in lote.erros)


def test_xml_invalido_nao_derruba_lote(venda):
    lote = lote_de(("ruim.xml", "<nfeProc><quebrado>"), ("ok.xml", fb.nfe_xml(1, D, E, C, venda)))
    assert len(lote.documentos) == 1 and len(lote.erros) == 1


def test_xml_com_entidade_maliciosa_e_rejeitado():
    bomba = ('<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;">]>'
             "<nfeProc>&b;</nfeProc>")
    lote = lote_de(("bomba.xml", bomba))
    assert not lote.documentos and lote.erros


def test_nfse_nacional():
    xml = fb.nfse_nacional_xml(10, D, E, C, "5000", irrf="75", pis="32.50", cofins="150", csll="50")
    d = lote_de(("s.xml", xml)).documentos[0]
    assert d.tipo == "NFSE" and d.layout == "nacional" and d.emitente.optante_simples is True
    assert d.retencoes == {"irrf": 75, "csll": 50, "pis": 32.5, "cofins": 150}
    assert d.valor_liquido == 5000 - 307.5


def test_nfse_abrasf_aliquota_fracionaria():
    d = lote_de(("a.xml", fb.nfse_abrasf_xml(7, D, F, E, "2000", optante=False, ir="30"))).documentos[0]
    assert d.layout == "abrasf" and d.aliquota_iss == 3 and d.retencoes == {"irrf": 30}
    assert d.destinatario.documento == EMPRESA and d.emitente.optante_simples is False


def test_ofx_dedup_entre_extratos_sobrepostos():
    l1 = [(date(2026, 3, 1), "100.00", "PIX RECEBIDO", "A1"), (date(2026, 3, 2), "-50.00", "TARIFA", "A2")]
    l2 = [(date(2026, 3, 2), "-50.00", "TARIFA", "A2"), (date(2026, 3, 3), "70.00", "TED", "A3")]
    lote = lote_de(("mar1.ofx", fb.ofx(l1)), ("mar2.ofx", fb.ofx(l2)))
    assert [l.fitid for l in lote.lancamentos] == ["A1", "A2", "A3"]
    assert lote.lancamentos[0].valor == 100


def test_folha_csv():
    lote = lote_de(("folha.csv", fb.folha_csv([("01/2026", 3000, 1518, 900)])))
    f = lote.folha[0]
    assert f.competencia == "2026-01" and f.total == 5418
