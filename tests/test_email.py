"""Envio de e-mail (SMTP): remetente sem endereço, senha colada com espaço e mensagem clara na recusa."""

import smtplib

import pytest

from nfse_itaborai import cobranca, config
from nfse_itaborai.tela import tratar
from test_emissor import ambiente  # noqa: F401  (fixture)
from test_financeiro import base  # noqa: F401  (fixture)


class FakeSMTP:
    senha_certa = "segredo123"
    enviados: list = []
    logins: list = []

    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self, **k):
        pass

    def login(self, usuario, senha):
        FakeSMTP.logins.append(senha)
        if senha != FakeSMTP.senha_certa:
            raise smtplib.SMTPAuthenticationError(535, b"5.7.8 Error: authentication failed: reason unavailable")

    def send_message(self, msg):
        FakeSMTP.enviados.append(msg)


@pytest.fixture
def smtp(base, monkeypatch):  # noqa: F811
    FakeSMTP.enviados, FakeSMTP.logins = [], []
    monkeypatch.setattr(cobranca.smtplib, "SMTP", FakeSMTP)
    config.salvar({"smtp": {"host": "smtp.exemplo.com.br", "porta": 587, "usuario": "moraes@exemplo.com.br",
                            "senha": "segredo123 ", "remetente": "MORAES"}})


def test_remetente_sem_arroba_vira_nome_e_senha_colada_com_espaco(smtp):
    cobranca.enviar_email("cliente@x.com", "Teste", "ok")
    msg = FakeSMTP.enviados[0]
    assert msg["From"] == "MORAES <moraes@exemplo.com.br>"
    assert FakeSMTP.logins == ["segredo123 ", "segredo123"]


def test_senha_errada_explica_o_que_conferir(smtp):
    config.salvar({"smtp": {"senha": "errada"}})
    r = tratar("email/testar", {"para": "cliente@x.com"})
    assert r["titulo"] == "Erro" and "recusou o usuário/senha (535" in r["erro"] and "moraes@exemplo.com.br" in r["erro"]
    assert not FakeSMTP.enviados
