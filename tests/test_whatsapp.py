"""WhatsApp pela API oficial da Meta (simulada): modelos com parâmetros válidos, régua e botão Cobrar enviando
sozinhos, erros registrados sem travar o e-mail e fila manual quando a API está desligada."""

import json
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from nfse_itaborai import clientes, cobranca, config, db, financeiro, whatsapp
from nfse_itaborai.tela import tratar
from test_emissor import Simulador, ambiente  # noqa: F401  (fixture)
from test_financeiro import CLI_A, base  # noqa: F401  (fixture)


class FakeMeta(BaseHTTPRequestHandler):
    enviados: list = []
    modelos_aprovados = {"cobranca_lembrete", "cobranca_vence_hoje", "cobranca_atraso"}

    def log_message(self, *a):
        pass

    def _json(self, d, code=200):
        b = json.dumps(d).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _ok(self):
        if self.headers.get("Authorization") != "Bearer EAAG-teste":
            self._json({"error": {"message": "Invalid OAuth access token", "code": 190}}, 401)
            return False
        return True

    def do_GET(self):  # noqa: N802
        if self._ok():
            self._json({"display_phone_number": "+55 21 99999-0000", "verified_name": "Moraes & Oliveira",
                        "quality_rating": "GREEN", "id": "123456"})

    def do_POST(self):  # noqa: N802
        if not self._ok():
            return
        js = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        nome = js["template"]["name"]
        if nome not in FakeMeta.modelos_aprovados:
            return self._json({"error": {"message": "Template name does not exist", "code": 132001}}, 404)
        params = js["template"]["components"][0]["parameters"]
        for p in params:   # regras da Meta para parâmetros de modelo
            assert p["text"] and "\n" not in p["text"] and "\t" not in p["text"] and "     " not in p["text"]
        FakeMeta.enviados.append(js)
        self._json({"messaging_product": "whatsapp", "contacts": [{"wa_id": js["to"]}],
                    "messages": [{"id": f"wamid.{len(FakeMeta.enviados)}"}]})


@pytest.fixture
def meta(base):  # noqa: F811
    srv = ThreadingHTTPServer(("127.0.0.1", 0), FakeMeta)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    FakeMeta.enviados = []
    config.salvar({"cobranca": {"provedor": "pix", "whatsapp_api": True, "whatsapp_token": "EAAG-teste",
                                "whatsapp_phone_id": "123456", "regua_email": False,
                                "whatsapp_api_url": f"http://127.0.0.1:{srv.server_address[1]}"}})
    yield
    srv.shutdown()


def test_numero_de_celular():
    assert whatsapp.numero("(21) 98888-7777") == "5521988887777"
    assert whatsapp.numero("+55 21 98888-7777") == "5521988887777"
    assert whatsapp.numero("21 3333-4444") == ""               # fixo não tem WhatsApp pela API
    assert whatsapp.numero("") == ""


def test_regua_envia_pelo_whatsapp_sozinha(meta):
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "374,40", "HONORARIOS OUTUBRO", vencimento="2026-10-10",
                                  emitir_nfse=False)
    financeiro.atualizar_titulo(tid, linha_digitavel="07790.00116 12345", pix_copia_cola="00020101PIX")
    r = cobranca.rodar_regua(date(2026, 10, 7))                                # 3 dias antes: lembrete
    assert r["whatsapp"] == 1 and r["erros"] == 0
    m = FakeMeta.enviados[0]
    assert m["to"] == "5521988887777" and m["template"]["name"] == "cobranca_lembrete"
    assert m["template"]["language"]["code"] == "pt_BR"
    p = [x["text"] for x in m["template"]["components"][0]["parameters"]]
    assert p[0] == "RPS Consultoria e Servicos de Engenharia LTDA" and p[1] == "R$ 374,40" and p[3] == "10/10/2026"
    assert p[4] == "07790.00116 12345" and p[5] == "00020101PIX" and len(p) == 8
    ev = db.linhas("SELECT * FROM eventos_cobranca WHERE canal='whatsapp'")
    assert ev[0]["status"] == "enviado"
    assert not cobranca.fila_whatsapp()                                        # nada para enviar à mão
    assert cobranca.rodar_regua(date(2026, 10, 7))["whatsapp"] == 0            # não repete a etapa
    cobranca.rodar_regua(date(2026, 10, 25))                                   # em atraso
    atraso = FakeMeta.enviados[-1]
    assert atraso["template"]["name"] == "cobranca_atraso"
    assert "multa e juros" in atraso["template"]["components"][0]["parameters"][1]["text"]


def test_erro_registrado_e_fila_manual_quando_desligado(meta):
    FakeMeta.modelos_aprovados = set()
    try:
        tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "100", vencimento="2026-10-10", emitir_nfse=False)
        financeiro.atualizar_titulo(tid, pix_copia_cola="PIX")
        r = cobranca.rodar_regua(date(2026, 10, 10))
        assert r["erros"] == 1
        ev = db.linhas("SELECT * FROM eventos_cobranca WHERE canal='whatsapp'")[0]
        assert ev["status"] == "erro" and "não aprovado" in ev["detalhe"]
    finally:
        FakeMeta.modelos_aprovados = {"cobranca_lembrete", "cobranca_vence_hoje", "cobranca_atraso"}
    config.salvar({"cobranca": {"whatsapp_api": False}})
    tid2 = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "200", vencimento="2026-10-12", emitir_nfse=False)
    financeiro.atualizar_titulo(tid2, pix_copia_cola="PIX")
    cobranca.rodar_regua(date(2026, 10, 9))
    assert any(e["titulo_id"] == tid2 and e["detalhe"].startswith("https://wa.me/") for e in cobranca.fila_whatsapp())


def test_botao_cobrar_envia_whatsapp(meta):
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "300", vencimento="2026-12-10", emitir_nfse=False)
    r = tratar("titulo/cobrar", {"id": tid})
    assert r["whatsapp_enviado"] == "5521988887777" and FakeMeta.enviados[-1]["template"]["name"] == "cobranca_lembrete"
    clientes.salvar(clientes.obter(CLI_A["cpf_cnpj"]) | {"telefone": "2133334444"})
    r = tratar("titulo/cobrar", {"id": tid})
    assert "celular válido" in r["whatsapp_erro"]


def test_testar_conexao_e_token_protegido(meta):
    r = tratar("whatsapp/testar", {})
    assert r["ok"] and "Moraes & Oliveira" in r["mensagem"]
    from nfse_itaborai import emissor
    assert "EAAG-teste" not in (emissor.RAIZ / "dados" / "config.json").read_text(encoding="utf-8")
    config.salvar({"cobranca": {"whatsapp_token": "errado"}})
    r = tratar("whatsapp/testar", {})
    assert r["sucesso"] is False and "token" in r["erro"]
    assert set(tratar("whatsapp/modelos", {})) == {"lembrete", "hoje", "atraso"}
