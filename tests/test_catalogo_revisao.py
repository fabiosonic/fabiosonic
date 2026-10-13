from datetime import date, datetime

from sqlalchemy import select

from mo_obrigacoes.agenda import gerar_agenda
from mo_obrigacoes.calendario import calcular_vencimento
from mo_obrigacoes.catalogo import CATALOGO
from mo_obrigacoes.classificador import Regra, classificar
from mo_obrigacoes.demo import gerar_cnpj
from mo_obrigacoes.models import Empresa, Tarefa

CODIGOS = {c["codigo"] for c in CATALOGO}
REGRAS = [Regra(c["codigo"], c.get("periodicidade", "mensal"), c["departamento"], c["reconhecimento"]) for c in CATALOGO]


def _empresa(s, **kw):
    dados = dict(codigo="0200", razao_social="REVISAO LTDA", cnpj=gerar_cnpj("77888999"), regime="SIMPLES",
                 drive_folder_id="0200 - REVISAO LTDA")
    dados.update(kw)
    e = Empresa(**dados)
    s.add(e)
    s.flush()
    return e


def _tarefas(s, emp, comp):
    return {t.obrigacao.codigo: t for t in s.scalars(
        select(Tarefa).where(Tarefa.empresa_id == emp.id, Tarefa.competencia == comp))}


def _c(nome, texto="", caminho=""):
    return classificar(REGRAS, nome, texto, caminho, datetime(2026, 10, 5))


def test_calendario_dia_fixo_posterga_e_antecipa():
    assert calcular_vencimento({"tipo": "dia_fixo", "dia": 15, "meses_apos": 1, "ajuste": "posterga"}, "2026-10") == date(2026, 11, 16)
    assert calcular_vencimento({"tipo": "dia_fixo", "dia": 20, "mes": 12, "anos_apos": 0, "ajuste": "antecipa"}, "2026-12", "anual") == date(2026, 12, 18)


def test_reinf_e_esocial_prorrogados_para_dia_util_seguinte(s):
    emp = _empresa(s, regime="PRESUMIDO", possui_funcionarios=True, retem_tributos=True)
    gerar_agenda(s, "2026-10", empresas=[emp])
    t = _tarefas(s, emp, "2026-10")
    assert t["EFD_REINF"].vencimento == date(2026, 11, 16)
    assert t["ESOCIAL"].vencimento == date(2026, 11, 16)


def test_aplicabilidade_mei_com_funcionario(s):
    mei = _empresa(s, regime="MEI", possui_funcionarios=True, possui_prolabore=False)
    gerar_agenda(s, "2026-12", empresas=[mei])
    c = set(_tarefas(s, mei, "2026-12"))
    esperados = {"DAS_MEI", "DASN_SIMEI", "FOLHA", "FGTS_DIGITAL", "ESOCIAL", "DCTFWEB", "DARF_DCTFWEB"}
    assert esperados <= c
    for codigo in ("DECIMO_TERCEIRO_1A", "DECIMO_TERCEIRO_2A", "DCTFWEB_ANUAL"):
        if codigo in CODIGOS:
            assert codigo in c


def test_destda_so_com_industria_ou_comercio(s):
    ind = _empresa(s, regime="SIMPLES", industria=True, comercio=False)
    gerar_agenda(s, "2026-12", empresas=[ind])
    assert "DESTDA" in _tarefas(s, ind, "2026-12")


def test_classificador_das_mei():
    r = _c("x.pdf", "Documento de Arrecadação do Simples Nacional\n1001 INSS - SIMEI\nPA 09/2026")
    assert r.codigo == "DAS_MEI"


def test_classificador_darf_dctfweb_codigo_0561():
    r = _c("y.pdf", "Documento de Arrecadação de Receitas Federais\nPeríodo de Apuração 30/09/2026\nCódigo de Receita 0561")
    assert r.codigo == "DARF_DCTFWEB"


def test_classificador_irpj_csll_estimativa():
    if "IRPJ_CSLL_ESTIMATIVA" in CODIGOS:
        r = _c("z.pdf", "Documento de Arrecadação de Receitas Federais\nPeríodo de Apuração 30/09/2026\nCódigo de Receita 2362")
        assert r.codigo == "IRPJ_CSLL_ESTIMATIVA"


def test_classificador_dctfweb_anual():
    if "DCTFWEB_ANUAL" in CODIGOS:
        r = _c("recibo.pdf", "Recibo de Entrega da DCTFWeb\nCategoria: Anual\nPeríodo de Apuração: 2026")
        assert r.codigo == "DCTFWEB_ANUAL"
