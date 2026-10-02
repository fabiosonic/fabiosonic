"""PDF dos boletos (Asaas): pasta, anexo no e-mail, robô e tela."""

import threading
from email import message_from_bytes
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from nfse_itaborai import automacao, cobranca, config, financeiro
from nfse_itaborai.tela import tratar
from test_emissor import Simulador, ambiente  # noqa: F401  (fixture)
from test_financeiro import CLI_A, FakeAsaas, base  # noqa: F401  (fixture)


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


@pytest.fixture
def asaas_fake(base, monkeypatch):  # noqa: F811
    _, pasta = base
    srv = ThreadingHTTPServer(("127.0.0.1", 0), FakeAsaas)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    config.salvar({"cobranca": {"provedor": "asaas", "asaas_api_key": "chave-teste",
                                "asaas_url": f"http://127.0.0.1:{srv.server_address[1]}"},
                   "pastas": {"boletos": str(pasta / "Boletos")}, "automacao": {"enriquecer_contatos": False},
                   "smtp": {"host": "smtp.teste", "usuario": "x", "senha": "y", "remetente": "esc@x.com"}})
    FakeSMTP.enviados = []
    monkeypatch.setattr(cobranca.smtplib, "SMTP", FakeSMTP)
    yield pasta
    srv.shutdown()


def test_baixa_pdf_na_pasta_por_competencia(asaas_fake):
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "300", vencimento="2026-10-10", competencia="2026-10",
                                  emitir_nfse=False)
    cobranca.preparar_pagamento(tid)
    t = financeiro.obter_titulo(tid)
    assert t["boleto_url"].endswith(f"/b/pdf/pay_{tid}")
    r = cobranca.baixar_boletos()
    assert r == {"baixados": 1, "ja_existiam": 0, "erros": [], "pasta": str(asaas_fake / "Boletos")}
    arq = Path(financeiro.obter_titulo(tid)["boleto_pdf"])
    assert arq.parent == asaas_fake / "Boletos" / "2026-10"
    assert arq.name == f"2026-10-10 - RPS CONSULTORIA E SERVICOS DE ENGENHARIA LTDA - titulo {tid}.pdf"
    assert arq.read_bytes().startswith(b"%PDF")
    assert cobranca.baixar_boletos()["ja_existiam"] == 1   # não baixa de novo


def test_email_de_cobranca_leva_pdf_e_link(asaas_fake):
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "300", vencimento="2026-10-10", emitir_nfse=False)
    r = cobranca.cobrar_agora(tid)
    assert r["email"] == CLI_A["email"] and "Boleto em PDF: http" in r["texto"]
    msg = FakeSMTP.enviados[-1]
    anexos = [p for p in msg.walk() if p.get_content_disposition() == "attachment"]
    assert len(anexos) == 1 and anexos[0].get_content_type() == "application/pdf"
    assert anexos[0].get_payload(decode=True).startswith(b"%PDF")


def test_robo_salva_pdfs_e_tela(asaas_fake):
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "300", vencimento="2026-10-10", emitir_nfse=False)
    res = automacao.rodar(forcar=True)
    assert res["boletos_pdf"]["baixados"] == 1, res
    assert Path(tratar("titulo/boleto", {"id": tid})["arquivo"]).exists()


def test_titulo_sem_asaas_explica(asaas_fake):
    config.salvar({"cobranca": {"provedor": "pix"}})
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "300", vencimento="2026-10-10", emitir_nfse=False)
    r = tratar("titulo/boleto", {"id": tid})
    assert "Asaas" in r["erro"]
