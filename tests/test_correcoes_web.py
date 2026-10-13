"""Pacote A: segurança e validações do painel."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from mo_obrigacoes.demo import criar_demo
from mo_obrigacoes.models import Empresa, Tarefa

AUTH = ("admin", "segredo")


@pytest.fixture()
def cliente(s, cfg, tmp_path):
    from mo_obrigacoes.web.app import criar_app

    criar_demo(s, tmp_path / "drive", "2026-09")
    s.commit()
    with TestClient(criar_app(), raise_server_exceptions=False, follow_redirects=False) as c:
        yield c


def _pendente(c):
    return next(t for t in c.get("/api/tarefas?competencia=2026-09", auth=AUTH).json() if t["status"] == "pendente")


def test_sem_senha_bloqueia_acesso_de_fora(cfg):
    from mo_obrigacoes.web.app import criar_app

    cfg.admin_password = ""
    with TestClient(criar_app(), client=("10.0.0.5", 5000)) as c:
        assert c.get("/api/tarefas").status_code == 503
    with TestClient(criar_app()) as c:  # mesma máquina: modo demonstração continua funcionando
        assert c.get("/api/tarefas").status_code == 200


def test_csrf_post_de_outra_origem_bloqueado(cliente):
    t = _pendente(cliente)
    r = cliente.post(f"/tarefas/{t['id']}/acao", data={"acao": "baixa"}, auth=AUTH,
                     headers={"Origin": "https://malicioso.example"})
    assert r.status_code == 403
    r = cliente.post(f"/tarefas/{t['id']}/acao", data={"acao": "baixa"}, auth=AUTH,
                     headers={"Origin": "http://testserver"})
    assert r.status_code == 303


@pytest.mark.parametrize("destino", ["//malicioso.example/x", "https://malicioso.example", "/\\malicioso.example"])
def test_sem_open_redirect(cliente, destino):
    t = _pendente(cliente)
    for dados in ({"acao": "reabrir"}, {"acao": "dispensar"}, {"acao": "baixa"}):
        r = cliente.post(f"/tarefas/{t['id']}/acao", data={**dados, "voltar": destino}, auth=AUTH)
        assert r.headers["location"].startswith("/tarefas?"), r.headers["location"]


def test_competencia_invalida_nao_quebra_nem_cria_tarefas(cliente, s):
    assert cliente.get("/?competencia=abcd-ef", auth=AUTH).status_code == 200
    assert cliente.get("/relatorios?competencia=2026-13", auth=AUTH).status_code == 200
    r = cliente.post("/acoes/agenda", data={"competencia": "2026-13"}, auth=AUTH)
    assert "inv%C3%A1lida" in r.headers["location"]
    assert s.scalar(select(func.count(Tarefa.id)).where(Tarefa.competencia == "2026-13")) == 0
    r = cliente.post("/documentos/1/classificar", data={"codigo": "DAS", "competencia": "2026-9"}, auth=AUTH)
    assert "inv%C3%A1lida" in r.headers["location"]


def test_acoes_respeitam_status_da_tarefa(cliente):
    feita = next(t for t in cliente.get("/api/tarefas", auth=AUTH).json() if t["status"].startswith("entregue"))
    r = cliente.post(f"/tarefas/{feita['id']}/acao", data={"acao": "dispensar", "observacao": "x"}, auth=AUTH)
    assert "pendente" in r.headers["location"]
    r = cliente.post(f"/tarefas/{feita['id']}/acao", data={"acao": "baixa"}, auth=AUTH)
    assert "conclu%C3%ADda" in r.headers["location"]
    status = {t["id"]: t["status"] for t in cliente.get("/api/tarefas", auth=AUTH).json()}
    assert status[feita["id"]] == feita["status"]


def test_salvar_empresa(cliente, s, cfg):
    assert cliente.post("/empresas/salvar", data={"id": "999", "codigo": "x", "razao_social": "y",
                                                  "cnpj": "04.252.011/0001-10"}, auth=AUTH).status_code == 404
    emp = s.scalar(select(Empresa).where(Empresa.codigo == "0001"))
    emp.personalizacoes = {"ICMS": {"dia": 9, "ajuste": "posterga"}}
    s.commit()
    form = {"id": str(emp.id), "codigo": "0001", "razao_social": emp.razao_social, "cnpj": emp.cnpj,
            "regime": "SIMPLES", "dia_ICMS": "10", "ativa": "on"}
    cliente.post("/empresas/salvar", data=form, auth=AUTH)
    s.expire_all()
    assert s.get(Empresa, emp.id).personalizacoes["ICMS"] == {"dia": 10, "ajuste": "posterga"}
    cfg.drive_backend = "google"
    r = cliente.post("/empresas/salvar", data={**form, "drive_folder_id": "abc' in parents or 'x"}, auth=AUTH)
    assert "inv%C3%A1lida" in r.headers["location"]


def test_documentacao_da_api_nao_exposta(cliente):
    assert cliente.get("/api/docs").status_code == 404
    assert cliente.get("/redoc").status_code == 404
    assert cliente.get("/openapi.json").status_code == 404
