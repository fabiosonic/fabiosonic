from datetime import date, datetime

from sqlalchemy import select

from mo_obrigacoes.agenda import gerar_agenda
from mo_obrigacoes.alertas import Notificador, executar_alertas
from mo_obrigacoes.demo import criar_demo, gerar_cnpj
from mo_obrigacoes.drive.local import LocalDriveClient
from mo_obrigacoes.models import Documento, Empresa, Tarefa
from mo_obrigacoes.monitor import Monitor, classificar_manual
from mo_obrigacoes.pdfsimples import gerar_pdf
from mo_obrigacoes.relatorios import exportar_csv, indicadores


def _empresa(s, **kw):
    dados = dict(codigo="0100", razao_social="TESTE LTDA", cnpj=gerar_cnpj("55666777"), regime="SIMPLES",
                 drive_folder_id="0100 - TESTE LTDA")
    dados.update(kw)
    e = Empresa(**dados)
    s.add(e)
    s.flush()
    return e


def _codigos(s, emp, comp):
    return {t.obrigacao.codigo for t in s.scalars(select(Tarefa).where(Tarefa.empresa_id == emp.id, Tarefa.competencia == comp))}


def test_aplicabilidade_por_perfil(s):
    simples = _empresa(s, possui_funcionarios=True, comercio=True)
    lucro = _empresa(s, codigo="0101", cnpj=gerar_cnpj("55666888"), regime="PRESUMIDO", servicos=True,
                     possui_funcionarios=False, possui_prolabore=True)
    mei = _empresa(s, codigo="0102", cnpj=gerar_cnpj("55666999"), regime="MEI", possui_prolabore=False)
    gerar_agenda(s, "2026-12")
    c = _codigos(s, simples, "2026-12")
    assert {"PGDAS_D", "DAS", "DEFIS", "DESTDA", "FOLHA", "FGTS_DIGITAL", "DCTFWEB", "ESOCIAL"} <= c
    assert not c & {"PIS_COFINS", "EFD_CONTRIBUICOES", "ECF", "DAS_MEI"}
    c = _codigos(s, lucro, "2026-12")
    assert {"PIS_COFINS", "IRPJ_CSLL", "EFD_CONTRIBUICOES", "ECD", "ECF", "ISS", "DCTFWEB", "PROLABORE"} <= c
    assert not c & {"FOLHA", "FGTS_DIGITAL", "EFD_ICMS_IPI", "PGDAS_D"}
    assert _codigos(s, mei, "2026-12") == {"DAS_MEI", "DASN_SIMEI"}
    # trimestral não aparece em novembro; anual só em dezembro
    gerar_agenda(s, "2026-11")
    assert "IRPJ_CSLL" not in _codigos(s, lucro, "2026-11") and "ECF" not in _codigos(s, lucro, "2026-11")
    # idempotente
    assert gerar_agenda(s, "2026-12")["tarefas_criadas"] == 0


def test_personalizacao_de_prazo(s):
    emp = _empresa(s, regime="PRESUMIDO", comercio=True, personalizacoes={"ICMS": {"dia": 9}, "BALANCETE": {"ignorar": True}})
    gerar_agenda(s, "2026-09")
    t = {t.obrigacao.codigo: t for t in emp.tarefas}
    assert t["ICMS"].vencimento == date(2026, 10, 9)
    assert "BALANCETE" not in t


def test_monitor_baixa_e_atraso(s, cfg, tmp_path):
    emp = _empresa(s)
    gerar_agenda(s, "2026-09")
    raiz = tmp_path / "drive" / emp.drive_folder_id / "2026" / "09 - Setembro" / "01 - Fiscal"
    raiz.mkdir(parents=True)
    (raiz / "das.pdf").write_bytes(gerar_pdf([
        "Documento de Arrecadacao do Simples Nacional", f"CNPJ {emp.cnpj}", "Periodo de Apuracao: 09/2026"]))
    mon = Monitor(s, LocalDriveClient(tmp_path / "drive"))
    r = mon.sincronizar()
    assert r.baixas == 1
    das = next(t for t in emp.tarefas if t.obrigacao.codigo == "DAS")
    assert das.status in ("entregue", "entregue_atraso") and das.origem_baixa == "drive"
    assert das.documentos[0].nome == "das.pdf"
    # segunda varredura incremental não reprocessa
    assert mon.sincronizar().arquivos_lidos == 0


def test_baixa_com_atraso(s, tmp_path):
    from mo_obrigacoes.monitor import dar_baixa

    emp = _empresa(s)
    gerar_agenda(s, "2026-09")
    t = next(t for t in emp.tarefas if t.obrigacao.codigo == "DAS")
    assert dar_baixa(s, t, datetime(2026, 10, 25), "manual")
    assert t.status == "entregue_atraso"
    assert not dar_baixa(s, t, datetime(2026, 10, 26), "manual")


def test_demo_completa_divergencia_e_manual(s, cfg, tmp_path):
    res = criar_demo(s, tmp_path / "drive", "2026-09")
    assert res["divergentes"] == 1 and res["nao_identificados"] == 1 and res["baixas"] == 10
    div = s.scalar(select(Documento).where(Documento.situacao == "divergente"))
    assert "0003" in div.detalhes["empresa_sugerida"]
    scan = s.scalar(select(Documento).where(Documento.situacao == "nao_identificado"))
    t = classificar_manual(s, scan, "DOC_EXTRATOS", "2026-09", "ana")
    assert t.status != "pendente" and scan.situacao == "manual"
    csv = exportar_csv(list(s.scalars(select(Tarefa))))
    assert "Padaria" in csv or "PADARIA" in csv
    k = indicadores(list(s.scalars(select(Tarefa))), hoje=date(2026, 10, 13))
    assert k["entregues"] == 11 and k["atrasadas"] >= 1


def test_alertas_e_cobranca_cliente(s, cfg, tmp_path):
    criar_demo(s, tmp_path / "drive", "2026-09")
    n = Notificador(cfg, simular=True)
    r = executar_alertas(s, n, hoje=date(2026, 10, 13))
    assert r["atrasadas"] > 0 and r["cobrancas_cliente"] >= 1
    destinos = {d for m in n.enviadas for d in m.para}
    assert "gestor@mo.com.br" in destinos and "ana@moraeseoliveira.com.br" in destinos
    assert any(d.startswith("financeiro@") for d in destinos)
    # não cobra o cliente de novo antes de 3 dias
    n2 = Notificador(cfg, simular=True)
    assert executar_alertas(s, n2, hoje=date(2026, 10, 13))["cobrancas_cliente"] == 0
