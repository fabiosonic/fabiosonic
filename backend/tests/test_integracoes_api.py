import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from moxml import servicos
from moxml.api.app import criar_api
from moxml.db.modelos import ArquivoDrive
from moxml.integracoes import dominio
from moxml.integracoes.gdrive import sincronizar_drive
from moxml.motor.orquestrador import Opcoes, Orquestrador
from moxml.simulador import gerador

from .conftest import CNPJ, RAZAO


class DriveFalso:
    def __init__(self, md5_errado=False, falhar_em=None):
        self.itens: dict[str, dict] = {}
        self.seq = 0
        self.md5_errado = md5_errado
        self.falhar_em = falhar_em
        self.envios = 0

    def _novo(self, nome, pai, pasta, md5=None):
        self.seq += 1
        fid = f"id{self.seq}"
        self.itens[fid] = {"id": fid, "name": nome, "parent": pai, "pasta": pasta, "md5Checksum": md5,
                           "mimeType": "application/vnd.google-apps.folder" if pasta else "application/xml"}
        return fid

    def listar_filhos(self, pai_id, somente_pastas):
        return [i for i in self.itens.values() if i["parent"] == pai_id and (i["pasta"] or not somente_pastas)]

    def criar_pasta(self, nome, pai_id):
        return self._novo(nome, pai_id, True)

    def enviar(self, caminho, nome, pai_id):
        self.envios += 1
        if self.falhar_em and self.envios == self.falhar_em:
            raise ConnectionError("Drive indisponível")
        md5 = hashlib.md5(Path(caminho).read_bytes()).hexdigest()
        fid = self._novo(nome, pai_id, False, "0" * 32 if self.md5_errado else md5)
        return {"id": fid, "md5Checksum": self.itens[fid]["md5Checksum"]}


@pytest.fixture
def capturado(app, empresa, lab, base):
    n65 = lab.popular(CNPJ, RAZAO, "65", 1, 1, 4, base, cancelar={2})
    n55 = lab.popular(CNPJ, RAZAO, "55", 1, 1, 2, base)
    servicos.importar_semente_bytes(app, empresa.id, n65[0].xml_proc)
    servicos.importar_semente_bytes(app, empresa.id, n55[0].xml_proc)
    Orquestrador(app).executar(Opcoes(paralelismo=1))
    return base


def test_drive_confirma_por_md5_e_reaproveita_pastas(app, capturado):
    drv = DriveFalso()
    raiz = "raiz"
    existente = drv._novo("1-Clientes", raiz, True)  # estrutura real com grafia diferente
    app.cfg.gdrive_pasta_raiz_id = raiz
    r = sincronizar_drive(app, drv)
    assert r["confirmados"] == len(list(app.cfg.pasta_xml.rglob("*.xml"))) and r["erros"] == 0
    assert sum(1 for i in drv.itens.values() if i["pasta"] and i["parent"] == raiz) == 1
    assert any(i["parent"] == existente for i in drv.itens.values())
    r2 = sincronizar_drive(app, drv)
    assert r2["ignorados"] == r["confirmados"] and r2["confirmados"] == 0


def test_drive_sem_confirmacao_nao_marca_sincronizado(app, capturado):
    app.cfg.gdrive_pasta_raiz_id = "raiz"
    r = sincronizar_drive(app, DriveFalso(md5_errado=True))
    assert r["confirmados"] == 0 and r["erros"] > 0
    with app.sessoes() as s:
        assert all(a.status == "ERRO" for a in s.scalars(select(ArquivoDrive)))


def test_drive_falha_em_um_arquivo_nao_interrompe(app, capturado):
    app.cfg.gdrive_pasta_raiz_id = "raiz"
    r = sincronizar_drive(app, DriveFalso(falhar_em=2))
    assert r["erros"] == 1 and r["confirmados"] > 0


def test_drive_conflito_nao_sobrescreve(app, capturado):
    app.cfg.gdrive_pasta_raiz_id = "raiz"
    drv = DriveFalso()
    sincronizar_drive(app, drv)
    with app.sessoes() as s:
        reg = s.scalars(select(ArquivoDrive)).first()
    drv.itens[reg.drive_file_id]["md5Checksum"] = "f" * 32  # alguém alterou o arquivo no Drive
    with app.sessoes() as s:
        s.get(ArquivoDrive, reg.id).status = "PENDENTE"
        s.commit()
    r = sincronizar_drive(app, drv)
    assert r["conflitos"] == 1
    assert any(i["name"].endswith("-v2.xml") for i in drv.itens.values())


def test_exportacao_dominio_preserva_xml(app, empresa, capturado, tmp_path):
    r = dominio.exportar(app, empresa.id, capturado.year, capturado.month, tmp_path)
    pasta = Path(r["pasta"])
    man = json.loads((pasta / "manifesto.json").read_text(encoding="utf-8"))
    assert r["documentos"] == 6 and r["cancelamentos"] == 1
    for item in man["arquivos"]:
        f = pasta / item["arquivo"]
        assert hashlib.sha256(f.read_bytes()).hexdigest() == item["sha256"]
    originais = {p.name: p.read_bytes() for p in app.cfg.pasta_xml.rglob("*.xml")}
    for f in (pasta / "IMPORTAR_DOMINIO").rglob("*.xml"):
        assert f.read_bytes() == originais[f.name]
    assert (pasta / "IMPORTAR_DOMINIO" / "NFCE_65").is_dir() and (pasta / "IMPORTAR_DOMINIO" / "NFE_55").is_dir()
    assert Path(r["zip"]).exists()


def test_api_fluxo_basico(app, lab, base):
    cli = TestClient(criar_api(app, iniciar_agendador=False))
    assert cli.get("/api/saude").json()["modo"] == "SIMULADO"
    r = cli.post("/api/empresas", json={"razao_social": RAZAO, "cnpj": "99.000.001/0001-01"})
    assert r.status_code == 201
    eid = r.json()["id"]
    assert cli.post("/api/empresas", json={"razao_social": "X", "cnpj": "99000001000102"}).status_code == 422
    pfx, _, _ = gerador.gerar_certificado_teste(CNPJ, RAZAO)
    r = cli.post(f"/api/empresas/{eid}/certificado", files={"arquivo": ("a.pfx", pfx)},
                 data={"senha": "errada", "autorizado_por": "Sócio", "termo": "Contrato", "confirmo_autorizacao": "true"})
    assert r.status_code == 422 and "senha" in r.json()["detail"]
    r = cli.post(f"/api/empresas/{eid}/certificado", files={"arquivo": ("a.pfx", pfx)},
                 data={"senha": "teste", "autorizado_por": "Sócio", "termo": "Contrato", "confirmo_autorizacao": "true"})
    assert r.status_code == 201
    n = lab.popular(CNPJ, RAZAO, "55", 1, 1, 3, base)
    assert cli.post(f"/api/empresas/{eid}/semente", files={"arquivo": ("s.xml", n[0].xml_proc)}).status_code == 200
    Orquestrador(app).executar(Opcoes(paralelismo=1))
    res = cli.get("/api/resumo").json()
    assert res["nfe_recuperadas"] == 3 and res["xmls_recuperados"] == 3 and res["modo"] == "SIMULADO"
    docs = cli.get("/api/documentos", params={"modelo": "55"}).json()
    assert docs["total"] == 3
    xml = cli.get(f"/api/documentos/{docs['itens'][0]['id']}/xml")
    assert xml.status_code == 200 and b"nfeProc" in xml.content
    assert cli.get("/api/certificados").json()[0]["status"] == "VALIDO"
    matriz = cli.get("/api/integracoes").json()["matriz"]
    assert any(m["conector"] == "svrs_portal_download" and m["uf"] == "RJ" for m in matriz)


def test_api_token(app):
    app.cfg.api_token = "segredo-forte"
    cli = TestClient(criar_api(app, iniciar_agendador=False))
    assert cli.get("/api/resumo").status_code == 401
    assert cli.get("/api/resumo", headers={"x-api-token": "segredo-forte"}).status_code == 200
    assert cli.get("/api/saude").status_code == 200
