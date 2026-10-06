"""Aba Mensagens: todo e-mail e WhatsApp enviado (ou que falhou) fica registrado, com texto e reenvio."""

import smtplib
from datetime import date

import pytest

from nfse_itaborai import cobranca, config, db, financeiro, mensagens
from nfse_itaborai.tela import tratar
from test_emissor import ambiente  # noqa: F401  (fixture)
from test_financeiro import CLI_A, base  # noqa: F401  (fixture)


class SMTP:
    enviados: list = []
    falhar = False

    def __init__(self, *a, **k): pass
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def starttls(self, **k): pass
    def login(self, *a): pass

    def send_message(self, msg):
        if SMTP.falhar:
            raise smtplib.SMTPRecipientsRefused({msg["To"]: (550, b"caixa inexistente")})
        SMTP.enviados.append(msg)


@pytest.fixture
def smtp(base, monkeypatch):  # noqa: F811
    SMTP.enviados, SMTP.falhar = [], False
    monkeypatch.setattr(cobranca.smtplib, "SMTP", SMTP)
    monkeypatch.setattr(cobranca.horario, "comercial", lambda **k: True)
    config.salvar({"smtp": {"host": "smtp.exemplo", "porta": 587, "usuario": "a@b.com", "senha": "x"}})
    return SMTP


def test_cobranca_e_falha_ficam_registradas_com_texto(smtp):
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "500", vencimento="2026-10-20", emitir_nfse=False)
    cobranca.preparar_pagamento(tid)
    cobranca.rodar_regua(date(2026, 10, 1))
    lst = tratar("mensagens", {})
    m = [x for x in lst if x["canal"] == "email"][0]
    assert m["status"] == "enviado" and m["para"] == CLI_A["email"] and m["titulo_id"] == tid
    assert m["tipo"] == "Cobrança (boleto)" and m["cliente"]
    assert "R$ 500,00" in tratar("mensagem", {"id": m["id"]})["texto"]
    smtp.falhar = True
    with pytest.raises(Exception):
        cobranca.enviar_email("x@y.com", "Teste", "corpo", teste=True)
    erro = tratar("mensagens", {"status": "erro"})
    assert len(erro) == 1 and "caixa inexistente" in erro[0]["detalhe"] and erro[0]["tipo"] == "Teste"
    assert tratar("mensagens/resumo", {})["erros_7d"] == 1
    assert len(tratar("mensagens", {"canal": "whatsapp"})) == 0


def test_reenviar_cobranca_em_aberto_remonta_a_mensagem(smtp):
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "500", vencimento="2026-10-20", emitir_nfse=False)
    cobranca.preparar_pagamento(tid)
    cobranca.rodar_regua(date(2026, 10, 1))
    m = tratar("mensagens", {"canal": "email"})[0]
    antes = len(smtp.enviados)
    r = tratar("mensagem/reenviar", {"id": m["id"]})
    assert "Cobrança reenviada" in r["mensagem"] and len(smtp.enviados) == antes + 1


def test_reenviar_mensagem_sem_titulo_repete_o_texto(smtp):
    cobranca.enviar_email("dono@escritorio.com", "Resumo", "texto do resumo", ref={"tipo": "Resumo financeiro"})
    m = tratar("mensagens", {})[0]
    assert m["tipo"] == "Resumo financeiro"
    tratar("mensagem/reenviar", {"id": m["id"]})
    assert smtp.enviados[-1]["To"] == "dono@escritorio.com" and len(tratar("mensagens", {})) == 2


def test_historico_da_regua_entra_na_aba(base):  # noqa: F811
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "90", vencimento="2026-09-10", emitir_nfse=False)
    with db.conexao() as con:
        con.execute("DELETE FROM mensagens")
        con.execute("INSERT INTO eventos_cobranca (titulo_id, etapa, canal, data, status, detalhe) VALUES (?,?,?,?,?,?)",
                    (tid, 5, "email", "2026-09-15", "enviado", CLI_A["email"]))
        mensagens.importar_historico(con)
    m = mensagens.listar()
    assert len(m) == 1 and m[0]["tipo"] == "Cobrança em atraso" and m[0]["quando"].startswith("2026-09-15")
