from datetime import datetime

from mo_obrigacoes.catalogo import CATALOGO
from mo_obrigacoes.classificador import (Regra, classificar, cnpj_valido, competencia_por_caminho,
                                         extrair_cnpjs, extrair_competencia)

REGRAS = [Regra(c["codigo"], c.get("periodicidade", "mensal"), c["departamento"], c["reconhecimento"]) for c in CATALOGO]
CNPJ = "11.222.333/0001-81"


def test_cnpj():
    assert cnpj_valido(CNPJ)
    assert not cnpj_valido("11.222.333/0001-80")
    assert extrair_cnpjs(f"CNPJ {CNPJ} e 00.000.000/0000-00") == ["11222333000181"]


def test_competencia():
    assert extrair_competencia("Período de Apuração (PA): 09/2026") == "2026-09"
    assert extrair_competencia("DAS setembro 2026.pdf") == "2026-09"
    assert extrair_competencia("guia_202609.pdf") == "2026-09"
    assert extrair_competencia("Período de apuração: 30/09/2026") == "2026-09"
    assert extrair_competencia("IRPJ 3º tri 2026", "trimestral") == "2026-09"
    assert extrair_competencia("Recibo 08/2026", "trimestral") == "2026-09"
    assert extrair_competencia("ECF ano-calendário 2025", "anual") == "2025-12"
    assert competencia_por_caminho("2026/09 - Setembro/01 - Fiscal/x.pdf") == "2026-09"


def _c(nome, texto="", caminho=""):
    return classificar(REGRAS, nome, texto, caminho, datetime(2026, 10, 5))


def test_pgdas_vs_das():
    r = _c("recibo.pdf", f"Programa Gerador do Documento de Arrecadação do Simples Nacional\nRecibo de Entrega da Apuração\nCNPJ {CNPJ}\nPA 09/2026")
    assert (r.codigo, r.competencia) == ("PGDAS_D", "2026-09")
    r = _c("guia.pdf", f"Documento de Arrecadação do Simples Nacional\nCNPJ {CNPJ}\nPeríodo de Apuração: Setembro/2026")
    assert (r.codigo, r.competencia) == ("DAS", "2026-09")
    assert r.cnpjs == ["11222333000181"]


def test_das_mei_nao_confunde():
    r = _c("x.pdf", "Documento de Arrecadação do Simples Nacional\nMicroempreendedor Individual PGMEI\nPA 09/2026")
    assert r.codigo == "DAS_MEI"


def test_darfs_por_codigo_de_receita():
    base = "Documento de Arrecadação de Receitas Federais\nPeríodo de Apuração 30/09/2026\nCódigo de Receita "
    assert _c("a.pdf", base + "2172").codigo == "PIS_COFINS"
    assert _c("b.pdf", base + "2089").codigo == "IRPJ_CSLL"
    assert _c("c.pdf", base + "1082 CP SEGURADOS").codigo == "DARF_DCTFWEB"
    assert _c("d.pdf", base + "9999").codigo is None


def test_nome_sozinho_quando_pdf_sem_texto():
    r = _c("FGTS setembro 2026.pdf")
    assert (r.codigo, r.competencia) == ("FGTS_DIGITAL", "2026-09")


def test_nome_nao_basta_quando_texto_contradiz():
    r = _c("relação das notas.pdf", "Planilha de controle interno sem relação com guias")
    assert r.codigo != "DAS"


def test_xml_nfe_e_competencia_pela_pasta():
    r = _c("000123.xml", "<nfeProc><NFe><infNFe></infNFe></NFe></nfeProc>", "2026/09 - Setembro/04 - Documentos do Cliente/000123.xml")
    assert (r.codigo, r.competencia, r.origem_competencia) == ("DOC_NOTAS_FISCAIS", "2026-09", "pasta")


def test_ecd_x_ecf():
    assert _c("r.pdf", "Recibo de Entrega - Escrituração Contábil Digital - ano-calendário 2025").codigo == "ECD"
    r = _c("r.pdf", "Recibo de Entrega - Escrituração Contábil Fiscal - ECF - ano-calendário 2025")
    assert (r.codigo, r.competencia) == ("ECF", "2025-12")


def test_documento_desconhecido():
    assert not _c("foto_reuniao.jpg").identificado
