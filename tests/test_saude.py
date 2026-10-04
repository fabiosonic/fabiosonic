"""Checklist de implantação/saúde e fechamento mensal automático."""

from datetime import date
from pathlib import Path

from nfse_itaborai import cobranca, config, db, financeiro, saude
from nfse_itaborai.tela import tratar
from test_emissor import Simulador, ambiente  # noqa: F401  (fixture)
from test_financeiro import CLI_A, CLI_B, base  # noqa: F401  (fixture)


def _itens(r):
    return {i["id"]: i for i in r["itens"]}


def test_checklist_aponta_o_que_falta(base):  # noqa: F811
    config.salvar({"cobranca": {"provedor": "inter"}})
    financeiro.criar_titulo(CLI_B["cpf_cnpj"], "300", vencimento="2026-10-10", emitir_nfse=False)
    r = saude.checklist(date(2026, 10, 2))
    i = _itens(r)
    assert i["prefeitura"]["ok"] and i["producao"]["ok"]
    assert not i["inter"]["ok"] and "client_id" in i["inter"]["detalhe"]
    assert not i["smtp"]["ok"] and not i["robo"]["ok"]
    assert not i["contato"]["ok"] and "Espaco Cultivar" in i["contato"]["detalhe"]   # CLI_B sem e-mail/telefone
    assert r["ok"] < r["total"] and r["erros"] >= 2 and not r["completo"]
    assert tratar("saude", {})["total"] == r["total"]


def test_checklist_completo(base):  # noqa: F811
    config.salvar({"cobranca": {"provedor": "pix"}, "smtp": {"host": "smtp.x"}, "resumo": {"email_dono": "d@x.com"}})
    db.registrar("robo", "ok")
    i = _itens(saude.checklist(financeiro.hoje()))
    assert all(x["ok"] for x in i.values()), [x for x in i.values() if not x["ok"]]


def test_fechamento_mensal_salva_envia_e_nao_repete(base, monkeypatch, tmp_path):  # noqa: F811
    enviados = []
    monkeypatch.setattr(cobranca, "enviar_email", lambda para, assunto, texto, cfg=None, anexos=None, html="", **k:
                        enviados.append((para, assunto, html)))
    config.salvar({"smtp": {"host": "smtp.x"}, "resumo": {"email_dono": "dono@x.com"},
                   "pastas": {"relatorios": str(tmp_path / "rel")}})
    t = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "1000", vencimento="2026-09-10", competencia="2026-09", emitir_nfse=False)
    financeiro.baixar(t, "2026-09-10", "1000")
    assert saude.fechamento_mensal(date(2026, 10, 2)) == "aguardando o dia do fechamento"
    r = saude.fechamento_mensal(date(2026, 10, 3))
    assert r == "fechamento de 2026-09 salvo e enviado para dono@x.com"
    arq = tmp_path / "rel" / "Fechamento 2026-09.html"
    doc = arq.read_text(encoding="utf-8")
    assert "Fechamento de 09/2026" in doc and "RESULTADO LÍQUIDO DO PERÍODO" in doc and "1.000,00" in doc
    assert enviados[0][1] == "Fechamento financeiro de 09/2026" and enviados[0][2] == doc
    assert saude.fechamento_mensal(date(2026, 10, 9)) == "fechamento de 2026-09 já feito" and len(enviados) == 1
    assert Path(arq).exists()


def test_abre_em_outra_porta_se_versao_antiga_ocupa_a_8765(tmp_path, monkeypatch):
    import json as _json
    import socket
    import threading
    import time
    import urllib.request
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from nfse_itaborai import __version__, emissor, tela

    class Antigo(BaseHTTPRequestHandler):           # versão antiga: não conhece /api/versao
        def do_GET(self):
            self.send_response(404)
            self.end_headers()

        def log_message(self, *a):
            pass

    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    porta = s.getsockname()[1]
    s.close()
    velho = ThreadingHTTPServer(("127.0.0.1", porta), Antigo)
    threading.Thread(target=velho.serve_forever, daemon=True).start()
    monkeypatch.setattr(emissor, "BASE", tmp_path)
    monkeypatch.setattr(emissor, "RAIZ", emissor._Raiz(tmp_path))
    threading.Thread(target=tela.servir, args=(porta, False, False), daemon=True).start()
    for _ in range(50):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{porta + 1}/api/versao", timeout=1) as r:
                info = _json.loads(r.read())
            break
        except OSError:
            time.sleep(0.1)
    assert info["versao"] == __version__ and info["pasta"] == str(tmp_path)
    assert tela._quem_esta_na_porta(porta) == {}
    velho.shutdown()
