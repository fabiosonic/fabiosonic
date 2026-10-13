"""Pacote B: varredura do Drive, reprocessamento e baixas."""
import os
import shutil
import time
from datetime import datetime

from sqlalchemy import func, select

from mo_obrigacoes.agenda import gerar_agenda
from mo_obrigacoes.demo import fmt, gerar_cnpj
from mo_obrigacoes.drive.local import LocalDriveClient
from mo_obrigacoes.models import Documento, Empresa, EstadoSync, Obrigacao, Tarefa
from mo_obrigacoes.monitor import Monitor, classificar_manual
from mo_obrigacoes.pdfsimples import gerar_pdf

FISCAL = "2026/09 - Setembro/01 - Fiscal/"


def _emp(s, codigo, base):
    e = Empresa(codigo=codigo, razao_social=f"{codigo} LTDA", cnpj=gerar_cnpj(base), regime="SIMPLES",
                drive_folder_id=codigo)
    s.add(e)
    s.flush()
    return e


def _pdf(raiz, emp, rel, linhas, mtime=None):
    p = raiz / emp.drive_folder_id / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(gerar_pdf(linhas))
    if mtime:
        os.utime(p, (mtime, mtime))
    return p


def _das(emp, comp="09/2026"):
    return ["Documento de Arrecadacao do Simples Nacional", f"CNPJ {fmt(emp.cnpj)}", f"Periodo de Apuracao: {comp}"]


def _tarefa(s, emp, codigo, comp="2026-09"):
    ob = s.scalar(select(Obrigacao).where(Obrigacao.codigo == codigo))
    return s.scalar(select(Tarefa).where(Tarefa.empresa_id == emp.id, Tarefa.obrigacao_id == ob.id,
                                         Tarefa.competencia == comp))


def _cenario(s, tmp_path):
    a = _emp(s, "A", "55666777")
    gerar_agenda(s, "2026-09")
    raiz = tmp_path / "drive"
    return a, raiz, LocalDriveClient(raiz)


def test_arquivo_com_data_antiga_depositado_depois_e_lido(s, tmp_path):
    a, raiz, drive = _cenario(s, tmp_path)
    _pdf(raiz, a, FISCAL + "das.pdf", _das(a))
    Monitor(s, drive).sincronizar()
    _pdf(raiz, a, "2026/09 - Setembro/04 - Documentos do Cliente/extrato.pdf",
         ["Extrato de conta corrente", "Saldo anterior 1,00", "Periodo: 09/2026"], mtime=time.time() - 20 * 86400)
    assert Monitor(s, drive).sincronizar().arquivos_lidos == 1
    assert _tarefa(s, a, "DOC_EXTRATOS").status != "pendente"


def test_arquivo_apagado_reabre_baixa_automatica(s, tmp_path):
    a, raiz, drive = _cenario(s, tmp_path)
    p = _pdf(raiz, a, FISCAL + "das.pdf", _das(a))
    Monitor(s, drive).sincronizar()
    assert _tarefa(s, a, "DAS").status != "pendente"
    p.unlink()
    Monitor(s, drive).sincronizar()
    assert _tarefa(s, a, "DAS").status == "pendente"
    assert s.scalar(select(Documento).where(Documento.nome == "das.pdf")).situacao == "removido"


def test_conteudo_trocado_reabre_tarefa_anterior(s, tmp_path):
    a, raiz, drive = _cenario(s, tmp_path)
    p = _pdf(raiz, a, FISCAL + "guia.pdf", _das(a))
    Monitor(s, drive).sincronizar()
    time.sleep(1.1)
    p.write_bytes(gerar_pdf(_das(a, "08/2026")))  # a pessoa trocou pelo DAS de agosto
    Monitor(s, drive).sincronizar()
    assert _tarefa(s, a, "DAS").status == "pendente"
    assert _tarefa(s, a, "DAS", "2026-08").status != "pendente"


def test_divergente_movido_sai_da_fila(s, tmp_path):
    a, raiz, drive = _cenario(s, tmp_path)
    b = _emp(s, "B", "55666888")
    gerar_agenda(s, "2026-09")
    _pdf(raiz, a, FISCAL + "guia de B.pdf", _das(b))
    assert Monitor(s, drive).sincronizar().divergentes == 1
    destino = raiz / "B" / FISCAL / "guia de B.pdf"
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(raiz / "A" / FISCAL / "guia de B.pdf", destino)
    Monitor(s, drive).sincronizar()
    assert _tarefa(s, b, "DAS").status != "pendente"
    assert s.scalar(select(func.count(Documento.id)).where(Documento.situacao == "divergente")) == 0


def test_documento_antigo_nao_cria_agenda_inteira(s, tmp_path):
    a, raiz, drive = _cenario(s, tmp_path)
    _pdf(raiz, a, "2024/03 - Marco/01 - Fiscal/das.pdf", _das(a, "03/2024"))
    Monitor(s, drive).sincronizar()
    comps = s.scalars(select(Tarefa).where(Tarefa.competencia == "2024-03")).all()
    assert [t.obrigacao.codigo for t in comps] == ["DAS"]


def test_competencia_so_pela_data_do_arquivo_vai_para_revisao(s, tmp_path):
    a, raiz, drive = _cenario(s, tmp_path)
    _pdf(raiz, a, "guia.pdf", ["Documento de Arrecadacao do Simples Nacional", f"CNPJ {fmt(a.cnpj)}"])
    Monitor(s, drive).sincronizar()
    assert s.scalar(select(Documento)).situacao == "nao_identificado"
    assert all(t.status == "pendente" for t in a.tarefas)


def test_falha_temporaria_de_download_e_tentada_de_novo(s, tmp_path):
    a, raiz, _ = _cenario(s, tmp_path)

    class Instavel(LocalDriveClient):
        falhar = True

        def baixar(self, arq):
            if self.falhar:
                raise RuntimeError("503 backendError")
            return super().baixar(arq)

    drive = Instavel(raiz)
    _pdf(raiz, a, FISCAL + "DAS 09-2026.pdf", ["Programa Gerador do Documento de Arrecadacao do Simples Nacional",
                                               "Recibo de Entrega da Apuracao", f"CNPJ {fmt(a.cnpj)}", "PA 09/2026"])
    r = Monitor(s, drive).sincronizar()
    assert r.erros and _tarefa(s, a, "DAS").status == "pendente"
    drive.falhar = False
    Monitor(s, drive).sincronizar()
    assert s.scalar(select(Documento)).obrigacao_codigo == "PGDAS_D"
    assert _tarefa(s, a, "DAS").status == "pendente" and _tarefa(s, a, "PGDAS_D").status != "pendente"


def test_arquivos_vistos_por_empresa(s, tmp_path):
    a, raiz, drive = _cenario(s, tmp_path)
    b = _emp(s, "B", "55666888")
    _pdf(raiz, a, FISCAL + "das.pdf", _das(a))
    Monitor(s, drive).sincronizar()
    vistos = {e.empresa_id: e.arquivos_vistos for e in s.scalars(select(EstadoSync))}
    assert vistos == {a.id: 1, b.id: 0}


def test_classificacao_manual_valida_e_reabre_anterior(s, tmp_path):
    a, raiz, drive = _cenario(s, tmp_path)
    _pdf(raiz, a, FISCAL + "guia.pdf", _das(a))
    Monitor(s, drive).sincronizar()
    doc = s.scalar(select(Documento))
    try:
        classificar_manual(s, doc, "DAS", "2026-9", "ana")
        assert False, "deveria recusar competência inválida"
    except ValueError:
        pass
    classificar_manual(s, doc, "DAS", "2026-08", "ana")
    assert _tarefa(s, a, "DAS").status == "pendente"
    assert _tarefa(s, a, "DAS", "2026-08").status != "pendente"


def test_baixa_usa_horario_de_brasilia():
    from mo_obrigacoes.drive.google import _dt

    # 21:30 de 20/10 em Brasília = 00:30Z de 21/10
    assert _dt("2026-10-21T00:30:00.000Z") == datetime(2026, 10, 20, 21, 30)
