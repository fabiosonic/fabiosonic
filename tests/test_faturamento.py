import sqlite3
from decimal import Decimal
from pathlib import Path

from tests.conftest import catalogo_teste as _cat
from mo_autonomo.documentos.classificador import classificar
from mo_autonomo.especialista.faturamento import cruzar, faturamento, ler_receitas_declaradas
from mo_autonomo.fluxos.documento import resumo_documento
from mo_autonomo.trilha.auditoria import Trilha
from tests.conftest import (CNPJ_A, CNPJ_B, CNPJ_X, catalogo_teste, chave_nfe, evento_xml, nfe_xml,
                            nfse_abrasf_xml, nfse_nacional_xml)

CAT = _cat()


def reg(xml, cnpjs=(CNPJ_A,)):
    d = classificar(xml, CAT)["doc"]
    return {"chave": d.get("chave"), "cnpjs": list(cnpjs), "resumo": resumo_documento(d)}


REGS = [reg(nfe_xml(numero=1, itens=(("1", "5102", "100.00"),))),
        reg(nfe_xml(numero=2, itens=(("1", "5102", "50.00"),))),
        reg(nfe_xml(numero=2, itens=(("1", "5102", "50.00"),))),            # duplicado: conta 1 vez
        reg(nfe_xml(numero=3, tp_nf="0", itens=(("1", "1202", "30.00"),))),  # entrada própria: fora
        reg(nfe_xml(numero=4, modelo="65", itens=(("1", "5102", "20.00"),))),
        reg(nfse_abrasf_xml(valor="500.00")),                                  # ALFA prestadora
        reg(nfse_nacional_xml(valor="999.00")),                                # ALFA tomadora: fora
        reg(nfe_xml(emit=CNPJ_X, dest=CNPJ_A, numero=9, itens=(("1", "5102", "777.00"),))),  # compra
        reg(evento_xml(chave_nfe(CNPJ_A, 2)))]                                # cancela a nº 2


def test_faturamento_com_normas_conferidas():
    f = faturamento(REGS, CNPJ_A, catalogo_teste())
    assert f["por_tipo"] == {"NFE": Decimal("100.00"), "NFCE": Decimal("20.00"), "NFSE": Decimal("500.00")}
    assert f["total"] == Decimal("620.00") and f["completo"]


def test_faturamento_sem_moc_tem_ressalva():
    f = faturamento(REGS, CNPJ_A, catalogo_teste(conferidas=[]))
    assert f["por_tipo"]["NFE"] == Decimal("0.00") and not f["completo"] and len(f["observacoes"]) == 2


def test_cruzamento(tmp_path):
    f = faturamento(REGS, CNPJ_A, catalogo_teste())
    arq = tmp_path / "receitas.csv"
    arq.write_text(f"cnpj;competencia;receita_declarada;fonte\n{CNPJ_A};2026-10;600,00;PGDAS-D\n", encoding="utf-8")
    dec = ler_receitas_declaradas(arq)
    a = cruzar(f, dec[(CNPJ_A, "2026-10")], CNPJ_A, "2026-10", Decimal("1.00"))
    assert len(a) == 1 and a[0].valor == Decimal("20.00") and "PGDAS-D" in a[0].mensagem and a[0].bloqueia
    assert cruzar(f, {"valor": Decimal("620.50"), "fonte": "x"}, CNPJ_A, "2026-10", Decimal("1.00")) == []
    assert cruzar(f, None, CNPJ_A, "2026-10", Decimal("1.00")) == []
    assert ler_receitas_declaradas(tmp_path / "nao_existe.csv") == {}


def test_migracao_trilha_antiga(tmp_path):
    caminho = tmp_path / "t.sqlite"
    con = sqlite3.connect(caminho)
    con.execute("CREATE TABLE documentos (sha256 TEXT PRIMARY KEY, tipo TEXT, chave TEXT, cnpjs TEXT, "
                "competencia TEXT, destinos TEXT, situacao TEXT, em TEXT)")
    con.execute("INSERT INTO documentos VALUES ('s','NFE','k','[]','2026-10','[]','OK','x')")
    con.commit()
    con.close()
    t = Trilha(caminho)
    assert t.documentos("2026-10")[0]["resumo"] == {}
    t.registrar_documento("s2", "NFE", "k2", [CNPJ_B], "2026-10", [], "OK", {"valor": Decimal("1.00")})
    assert t.documentos("2026-10")[1]["resumo"]["valor"] == Decimal("1.00")
