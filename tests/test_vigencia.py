from datetime import datetime

from sqlalchemy import select

from mo_obrigacoes.agenda import gerar_agenda, ocorre_na_competencia
from mo_obrigacoes.catalogo import CATALOGO
from mo_obrigacoes.classificador import Regra, classificar
from mo_obrigacoes.demo import gerar_cnpj
from mo_obrigacoes.models import Empresa, Obrigacao, Tarefa

REGRAS = [Regra(c["codigo"], c.get("periodicidade", "mensal"), c["departamento"], c["reconhecimento"]) for c in CATALOGO]
CAMINHO = "2026/09 - Setembro/01 - Fiscal/"


def _empresa(s, **kw):
    dados = dict(codigo="0200", razao_social="VIGENCIA LTDA", cnpj=gerar_cnpj("77888999"), regime="PRESUMIDO",
                 drive_folder_id="0200 - VIGENCIA LTDA")
    dados.update(kw)
    e = Empresa(**dados)
    s.add(e)
    s.flush()
    return e


def _codigos(s, emp, comp):
    return {t.obrigacao.codigo for t in s.scalars(select(Tarefa).where(Tarefa.empresa_id == emp.id, Tarefa.competencia == comp))}


def test_pis_cofins_e_efd_encerram_em_2026(s):
    emp = _empresa(s)
    gerar_agenda(s, "2026-12")
    gerar_agenda(s, "2027-01")
    assert {"PIS_COFINS", "EFD_CONTRIBUICOES"} <= _codigos(s, emp, "2026-12")
    assert not _codigos(s, emp, "2027-01") & {"PIS_COFINS", "EFD_CONTRIBUICOES"}


def test_vigencia_em_memoria():
    ob = Obrigacao(codigo="X", nome="X", departamento="FISCAL", periodicidade="mensal",
                   vigente_desde="2026-03", vigente_ate="2026-12")
    assert not ocorre_na_competencia(ob, "2026-02")
    assert ocorre_na_competencia(ob, "2026-03")
    assert ocorre_na_competencia(ob, "2026-12")
    assert not ocorre_na_competencia(ob, "2027-01")
    sem_limite = Obrigacao(codigo="Y", nome="Y", departamento="FISCAL", periodicidade="mensal")
    assert ocorre_na_competencia(sem_limite, "2030-06")


def _c(nome, texto=""):
    return classificar(REGRAS, nome, texto, CAMINHO, datetime(2026, 10, 5))


def test_comprovante_das_despesas_nao_e_das():
    assert _c("Comprovante das despesas.pdf").codigo != "DAS"


def test_das_com_numero_e_competencia_no_nome():
    assert _c("DAS 09-2026.pdf").codigo == "DAS"
    assert _c("das_092026.pdf").codigo == "DAS"
    assert _c("DAS setembro 2026.pdf").codigo == "DAS"
