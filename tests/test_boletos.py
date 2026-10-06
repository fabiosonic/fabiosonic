"""Boletos pela API de Cobrança v3 do Banco Inter (simulada com TLS mútuo): registro, PDF, pasta, e-mail,
baixa automática e cancelamento."""

import base64
import json
import ssl
import threading
import urllib.parse
from email import message_from_bytes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization

from nfse_itaborai import automacao, clientes, cobranca, config, financeiro, inter
from nfse_itaborai.tela import tratar
from test_emissor import Simulador, ambiente  # noqa: F401  (fixture)
from test_financeiro import CLI_A, CLI_B, base  # noqa: F401  (fixture)
from test_nacional import _certificado, _pem

PDF = b"%PDF-1.4 boleto inter"


class FakeInter(BaseHTTPRequestHandler):
    cobrancas: dict = {}
    pedidos: list = []
    tokens = 0
    transacoes: list = []          # extrato (API Banking v2)
    extrato_liberado = True        # integração com o escopo extrato.read
    consultas_extrato: list = []

    def log_message(self, *a):
        pass

    def _json(self, d, code=200):
        b = json.dumps(d).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _corpo(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def _autorizado(self):
        esperado = "Bearer tok-ext" if self.path.startswith("/banking/") else "Bearer tok-123"
        if self.headers.get("Authorization") != esperado:
            self._json({"title": "Não autorizado"}, 401)
            return False
        return True

    def do_POST(self):  # noqa: N802
        corpo = self._corpo()
        if self.path == "/oauth/v2/token":
            f = urllib.parse.parse_qs(corpo.decode())
            assert f["grant_type"] == ["client_credentials"] and f["client_secret"] == ["segredo"]
            if f["scope"] == ["extrato.read"]:
                if not FakeInter.extrato_liberado:
                    return self._json({"title": "Forbidden", "detail": "invalid scope"}, 403)
                return self._json({"access_token": "tok-ext", "expires_in": 3600})
            assert set(f["scope"][0].split()) == {"boleto-cobranca.read", "boleto-cobranca.write"}
            FakeInter.tokens += 1
            return self._json({"access_token": "tok-123", "expires_in": 3600})
        if not self._autorizado():
            return
        js = json.loads(corpo)
        FakeInter.pedidos.append((self.path, js))
        if self.path == "/cobranca/v3/cobrancas":
            if not js["pagador"].get("cidade"):
                return self._json({"title": "Requisição inválida",
                                   "violacoes": [{"propriedade": "pagador.cidade", "razao": "obrigatório"}]}, 400)
            cod = f"cod-{len(FakeInter.cobrancas) + 1}"
            FakeInter.cobrancas[cod] = {"situacao": "A_RECEBER", "valorNominal": js["valorNominal"], "pedido": js}
            return self._json({"codigoSolicitacao": cod})
        if self.path.endswith("/cancelar"):
            FakeInter.cobrancas[self.path.split("/")[-2]]["situacao"] = "CANCELADO"
            return self._json({}, 202)

    def do_GET(self):  # noqa: N802
        if not self._autorizado():
            return
        caminho = self.path.split("?")[0]
        if caminho == "/banking/v2/extrato/completo":
            q = urllib.parse.parse_qs(self.path.split("?", 1)[1])
            FakeInter.consultas_extrato.append(q)
            ini, fim, pag = q["dataInicio"][0], q["dataFim"][0], int(q["pagina"][0])
            dentro = [t for t in FakeInter.transacoes if ini <= t["dataTransacao"] <= fim]
            tam = int(q["tamanhoPagina"][0])
            return self._json({"totalPaginas": max(1, -(-len(dentro) // tam)), "transacoes": dentro[pag * tam:(pag + 1) * tam]})
        if caminho == "/cobranca/v3/cobrancas":
            return self._json({"totalElementos": 0, "cobrancas": []})
        partes = caminho.split("/")
        cod = partes[4]
        c = FakeInter.cobrancas[cod]
        if caminho.endswith("/pdf"):
            return self._json({"pdf": base64.b64encode(PDF).decode()})
        return self._json({
            "cobranca": {"codigoSolicitacao": cod, "situacao": c["situacao"], "valorNominal": c["valorNominal"],
                         "valorTotalRecebido": c.get("recebido", 0), "dataSituacao": "2026-10-08"},
            "boleto": {"nossoNumero": "00012345678", "linhaDigitavel": "07790.00116 12345.678901 23456.789012 1 99990000030000"},
            "pix": {"pixCopiaECola": "00020101021226900014br.gov.bcb.pix2568inter"}})


@pytest.fixture
def banco(base, monkeypatch):  # noqa: F811
    _, pasta = base
    ck, cc = _certificado("MORAES OLIVEIRA:24875410000144")       # certificado da integração (cliente)
    (pasta / "inter.crt").write_bytes(cc.public_bytes(serialization.Encoding.PEM))
    (pasta / "inter.key").write_bytes(ck.private_bytes(serialization.Encoding.PEM,
                                                       serialization.PrivateFormat.TraditionalOpenSSL,
                                                       serialization.NoEncryption()))
    sk, sc = _certificado("127.0.0.1", ip=True)
    (pasta / "srv.pem").write_bytes(_pem(sk, sc))
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(pasta / "srv.pem")
    ctx.verify_mode = ssl.CERT_REQUIRED                              # mTLS, como na API do Inter
    ctx.load_verify_locations(pasta / "inter.crt")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), FakeInter)
    srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    FakeInter.cobrancas, FakeInter.pedidos, FakeInter.tokens = {}, [], 0
    FakeInter.transacoes, FakeInter.extrato_liberado, FakeInter.consultas_extrato = [], True, []
    inter._TOKEN.clear()
    config.salvar({"cobranca": {"provedor": "inter", "inter_client_id": "cli", "inter_client_secret": "segredo",
                                "inter_certificado": str(pasta / "inter.crt"), "inter_chave": str(pasta / "inter.key"),
                                "inter_url": f"https://127.0.0.1:{srv.server_address[1]}",
                                "inter_ca": str(pasta / "srv.pem")},
                   "pastas": {"boletos": str(pasta / "Boletos")},
                   "smtp": {"host": "smtp.teste", "usuario": "x", "senha": "y", "remetente": "esc@x.com"}})
    FakeSMTP.enviados = []
    monkeypatch.setattr(cobranca.smtplib, "SMTP", FakeSMTP)
    yield pasta
    srv.shutdown()


class FakeSMTP:
    enviados: list = []

    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self, **k):
        pass

    def login(self, *a):
        pass

    def send_message(self, msg):
        FakeSMTP.enviados.append(message_from_bytes(msg.as_bytes()))


def _titulo(**kw):
    return financeiro.criar_titulo(CLI_A["cpf_cnpj"], kw.get("valor", "300"), "HONORARIOS CONTABEIS",
                                   vencimento=kw.get("venc", "2026-12-10"), competencia="2026-12", emitir_nfse=False)


def test_registra_boleto_com_pix_e_salva_pdf_e_dados(banco):
    tid = _titulo()
    t = cobranca.preparar_pagamento(tid)
    assert t["banco_id"] == "cod-1" and t["linha_digitavel"].startswith("07790")
    assert t["pix_copia_cola"].startswith("000201") and t["nosso_numero"] == "00012345678"
    path, pedido = FakeInter.pedidos[0]
    assert pedido["seuNumero"] == f"T{tid}" and pedido["valorNominal"] == 300.0
    assert pedido["dataVencimento"] == "2026-12-10" and pedido["numDiasAgenda"] == 60
    assert pedido["multa"] == {"codigo": "PERCENTUAL", "taxa": 2.0}
    assert pedido["mora"] == {"codigo": "TAXAMENSAL", "taxa": 1.0}
    p = pedido["pagador"]
    assert p["tipoPessoa"] == "JURIDICA" and p["cidade"] == "Rio de Janeiro" and p["uf"] == "RJ"
    assert p["ddd"] == "21" and p["telefone"] == "988887777" and p["endereco"] == "AV PRESIDENTE VARGAS"
    pdf = Path(t["boleto_pdf"])
    assert pdf.parent == banco / "Boletos" / "2026-12" and pdf.read_bytes() == PDF
    txt = pdf.with_name(pdf.stem + " - pagamento.txt").read_text(encoding="utf-8")
    assert "07790.00116" in txt and "PIX copia e cola" in txt
    assert cobranca.preparar_pagamento(tid)["banco_id"] == "cod-1" and len(FakeInter.cobrancas) == 1
    assert FakeInter.tokens == 1                                       # token reaproveitado


def test_email_leva_pdf_anexo_e_linha_digitavel(banco):
    tid = _titulo()
    cobranca.preparar_pagamento(tid)
    r = cobranca.cobrar_agora(tid)
    assert r["email"] == CLI_A["email"] and "Linha digitável: 07790" in r["texto"]
    anexos = [x for x in FakeSMTP.enviados[-1].walk() if x.get_content_disposition() == "attachment"]
    assert len(anexos) == 1 and anexos[0].get_payload(decode=True) == PDF


def test_baixa_automatica_quando_pago(banco):
    tid = _titulo()
    cobranca.preparar_pagamento(tid)
    assert cobranca.sincronizar_banco() == 0
    FakeInter.cobrancas["cod-1"].update(situacao="RECEBIDO", recebido=300.0)
    assert cobranca.sincronizar_banco() == 1
    t = financeiro.obter_titulo(tid)
    assert t["status"] == "pago" and t["forma_pagamento"] == "inter" and t["data_pagamento"] == "2026-10-08"


def test_cancelar_titulo_cancela_boleto(banco):
    tid = _titulo()
    cobranca.preparar_pagamento(tid)
    tratar("titulo/cancelar", {"id": tid, "motivo": "Cliente encerrou contrato"})
    assert FakeInter.cobrancas["cod-1"]["situacao"] == "CANCELADO"
    assert FakeInter.pedidos[-1] == ("/cobranca/v3/cobrancas/cod-1/cancelar",
                                     {"motivoCancelamento": "Cliente encerrou contrato"})


def test_robo_registra_boletos_e_cadastro_incompleto_nao_trava(banco):
    clientes.salvar(CLI_B | {"endereco": {**CLI_A["endereco"], "codigo_municipio": "", "cidade": ""}})
    financeiro.criar_titulo(CLI_B["cpf_cnpj"], "200", vencimento="2026-12-10", emitir_nfse=False)
    tid = _titulo()
    sem_pix = config.carregar()["empresa"]["pix_chave"]
    config.salvar({"empresa": {"pix_chave": ""}})           # sem PIX do escritório: o cadastro incompleto é apontado
    res = automacao.rodar(forcar=True)
    assert res["cobrancas_criadas"]["criadas"] == 1, res
    assert "cidade" in res["cobrancas_criadas"]["erros"][0]
    assert Path(financeiro.obter_titulo(tid)["boleto_pdf"]).exists()
    assert tratar("inter/testar", {})["ok"]
    config.salvar({"empresa": {"pix_chave": sem_pix}})


def test_cliente_sem_endereco_e_cobrado_pelo_pix_ate_completar_o_cadastro(banco):
    """Pessoa física cadastrada só com CPF e nome (Emissor Nacional): o banco exige o endereço no boleto, então a
    cobrança sai pelo PIX do escritório; preenchido o endereço, o boleto é registrado (um só por título)."""
    clientes.salvar({"cpf_cnpj": "52998224725", "razao_social": "FULANO DE TAL", "email": "f@x.com", "endereco": {}})
    tid = financeiro.criar_titulo("52998224725", "350", vencimento="2026-12-10", emitir_nfse=False)
    t = cobranca.preparar_pagamento(tid)
    assert t["banco_id"] == "" and t["pix_copia_cola"] and not t["cobranca_erro"]
    clientes.salvar({"cpf_cnpj": "52998224725", "razao_social": "FULANO DE TAL", "endereco": CLI_A["endereco"]})
    t = cobranca.preparar_pagamento(tid)
    assert t["banco_id"]


def test_sem_inter_configurado_usa_pix_proprio(base):  # noqa: F811
    tid = _titulo()
    financeiro.atualizar_titulo(tid, pix_copia_cola="")   # ainda sem cobrança gerada
    t = cobranca.preparar_pagamento(tid)
    assert t["banco_id"] == "" and t["pix_copia_cola"].startswith("000201")
    assert "Inter" in tratar("titulo/boleto", {"id": tid})["erro"]


def test_config_antiga_migra_para_inter(tmp_path, monkeypatch):
    from nfse_itaborai import emissor
    monkeypatch.setattr(emissor, "RAIZ", tmp_path)
    (tmp_path / "dados").mkdir()
    (tmp_path / "dados" / "config.json").write_text(json.dumps(
        {"cobranca": {"provedor": "asaas", "asaas_api_key": "x", "multa_pct": 3}}), encoding="utf-8")
    c = config.carregar()["cobranca"]
    assert c["provedor"] == "inter" and c["multa_pct"] == 3 and "asaas_api_key" not in c
    config.salvar({"cobranca": {"provedor": "pix"}})                  # escolha posterior do usuário é respeitada
    assert config.carregar()["cobranca"]["provedor"] == "pix"


def test_config_antiga_perde_whatsapp_por_api_e_consulta_receita(tmp_path, monkeypatch):
    from nfse_itaborai import emissor
    monkeypatch.setattr(emissor, "RAIZ", tmp_path)
    (tmp_path / "dados").mkdir()
    (tmp_path / "dados" / "config.json").write_text(json.dumps(
        {"whatsapp": {"provedor": "zapi", "zapi_token": "T"}, "automacao": {"enriquecer_contatos": True}}),
        encoding="utf-8")
    c = config.carregar()
    assert "whatsapp" not in c and "enriquecer_contatos" not in c["automacao"]
    assert "zapi" not in (tmp_path / "dados" / "config.json").read_text(encoding="utf-8")


def test_titulo_vencido_registra_um_boleto_com_valor_atualizado(banco, monkeypatch):
    """Vencido: valor original + multa (2%) + juros (1% a.m. pro rata) até o registro, vence em 5 dias, sem nova
    multa e com juros diários só sobre o original (sem juros sobre juros)."""
    from datetime import date
    monkeypatch.setattr(financeiro, "hoje", lambda: date(2026, 10, 5))
    tid = _titulo(valor="400", venc="2026-07-15")                     # 82 dias de atraso em 05/10/2026
    t = cobranca.preparar_pagamento(tid)
    _, pedido = FakeInter.pedidos[0]
    # 400,00 + 8,00 de multa + 400 × 1% / 30 × 82 = 10,93 de juros
    assert pedido["valorNominal"] == 418.93 and pedido["dataVencimento"] == "2026-10-10"
    assert "multa" not in pedido and pedido["mora"] == {"codigo": "VALORDIA", "valor": 0.13}
    assert pedido["mensagem"]["linha3"] == "Original R$ 400,00 venc. 15/07/2026 + multa e juros ate 05/10/2026"
    assert (t["boleto_valor_cent"], t["boleto_vencimento"]) == (41893, "2026-10-10")
    assert financeiro.encargos(t, date(2026, 10, 9))["total_cent"] == 41893      # até o novo vencimento: o do boleto
    assert financeiro.encargos(t, date(2026, 10, 20))["total_cent"] == 41893 + 133   # depois: + 10 dias de juros
    texto = cobranca.mensagem(t, 82, em=date(2026, 10, 5))[1]
    assert "R$ 418,93" in texto and "vence em 10/10/2026" in texto
    cobranca.preparar_pagamento(tid)
    assert len(FakeInter.cobrancas) == 1                                # nunca outro boleto
