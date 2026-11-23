import io
import json
import zipfile
from datetime import timedelta

from conftest import EMPRESA, C, D, E, lote_de
from fastapi.testclient import TestClient

from portal_contabil import auditar
from portal_contabil import fabrica as fb
from portal_contabil.cli import main
from portal_contabil.relatorio import gerar_html, gerar_json, salvar


def _arquivos():
    cliente_html = (C[0], "Cliente <b>X</b>", "SP")
    return [("1.xml", fb.nfe_xml(1, D, E, C, [{"cfop": "5102", "valor": "1000", "ncm": "30049099"}])),
            ("3.xml", fb.nfe_xml(3, D, E, cliente_html, [{"cfop": "5102", "valor": "50"}])),
            ("e.ofx", fb.ofx([(D + timedelta(days=2), "4000.00", "DEPOSITO DINHEIRO")]))]


def test_relatorios(tmp_path):
    res = auditar(lote_de(*_arquivos()))
    html = gerar_html(res)
    assert "Auditoria fiscal" in html and "&lt;b&gt;X&lt;/b&gt;" in html and "<b>X</b>" not in html
    dados = json.loads(gerar_json(res))
    assert dados["empresa"]["cnpj"] == EMPRESA and dados["achados"]
    saidas = salvar(res, tmp_path)
    assert set(saidas) == {"html", "json", "xlsx"} and saidas["xlsx"].stat().st_size > 0


def test_cli(tmp_path):
    pasta = tmp_path / "entrada"
    pasta.mkdir()
    for nome, conteudo in _arquivos():
        (pasta / nome).write_text(conteudo)
    codigo = main(["auditar", str(pasta), "--saida", str(tmp_path / "out")])
    assert codigo == 2  # crédito sem nota é crítico
    assert (tmp_path / "out" / "auditoria.html").exists()


def test_portal_web(tmp_path, monkeypatch):
    from portal_contabil.web import app as web
    monkeypatch.setattr(web, "PASTA", tmp_path)
    monkeypatch.setenv("PORTAL_USUARIO", "escritorio")
    monkeypatch.setenv("PORTAL_SENHA", "s3nha")
    cli = TestClient(web.app)
    assert cli.get("/").status_code == 401
    auth = ("escritorio", "s3nha")
    assert "Envie seus documentos" in cli.get("/", auth=auth).text

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for nome, conteudo in _arquivos():
            z.writestr(nome, conteudo)
    r = cli.post("/auditar", auth=auth, files=[("arquivos", ("lote.zip", buf.getvalue(), "application/zip"))],
                 data={"cnpj": "", "regime": "auto"}, follow_redirects=False)
    assert r.status_code == 303
    url = "/" + r.headers["location"]
    pagina = cli.get(url, auth=auth)
    assert pagina.status_code == 200 and "Baixar Excel" in pagina.text
    assert cli.get(url + "/xlsx", auth=auth).status_code == 200
    assert cli.get("/relatorio/../../etc/passwd", auth=auth).status_code == 404
    assert cli.get("/relatorio/" + "0" * 32, auth=auth).status_code == 404
