"""E-mails e mensagens só saem de segunda a sexta, em horário comercial (padrão 08:00 às 18:00)."""

from datetime import date, datetime

import pytest

from nfse_itaborai import cobranca, config, financeiro, horario, importacao, whatsapp_web
from test_emissor import ambiente  # noqa: F401  (fixture)
from test_financeiro import CLI_A, base  # noqa: F401  (fixture)


@pytest.fixture
def no_relogio(monkeypatch):
    monkeypatch.delenv("NFSE_ENVIO_SEMPRE", raising=False)
    def ajustar(quando: str):
        monkeypatch.setattr(horario, "agora", lambda: datetime.fromisoformat(quando))
    return ajustar


@pytest.mark.parametrize("quando,ok", [("2026-10-05 08:00", True), ("2026-10-05 07:59", False), ("2026-10-09 17:59", True),
                                       ("2026-10-09 18:00", False), ("2026-10-10 10:00", False), ("2026-10-11 10:00", False)])
def test_horario_comercial(base, no_relogio, quando, ok):  # noqa: F811
    no_relogio(quando)                                   # 05/10/2026 é segunda; 10 e 11 são sábado e domingo
    assert horario.comercial() is ok


def test_horario_configuravel_mas_nunca_desligavel(base, no_relogio):  # noqa: F811
    no_relogio("2026-10-05 19:00")
    config.salvar({"cobranca": {"envio_hora_fim": "20:00"}})
    assert horario.comercial()
    no_relogio("2026-10-10 10:00")
    assert not horario.comercial()
    config.salvar({"cobranca": {"envio_horario_comercial": False, "envio_hora_inicio": "", "envio_hora_fim": ""}})
    assert not horario.comercial()                      # caso real: a opção desligada mandou cobrança num domingo
    no_relogio("2026-10-04 08:11")                       # domingo de manhã
    assert not horario.comercial() and horario.horas() == ("08:00", "18:00")
    config.salvar({"cobranca": {"envio_hora_inicio": "18:00", "envio_hora_fim": "08:00"}})   # faixa inválida
    no_relogio("2026-10-05 09:00")
    assert horario.horas() == ("08:00", "18:00") and horario.comercial()


def test_fora_do_horario_nada_sai_e_depois_sai(base, no_relogio, monkeypatch):  # noqa: F811
    enviados = []
    monkeypatch.setattr(cobranca, "enviar_email", lambda *a, **k: enviados.append(a[0]))
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "300", vencimento="2026-09-25", emitir_nfse=False)
    cobranca.preparar_pagamento(tid)
    no_relogio("2026-10-03 21:00")                       # sábado à noite (título 8 dias em atraso)
    r = cobranca.rodar_regua(date(2026, 9, 30))
    assert "Fora do horário comercial" in r["fora_do_horario"] and enviados == [] and cobranca.fila_whatsapp() == []
    with pytest.raises(ValueError, match="horário comercial"):
        cobranca.cobrar_agora(tid)
    assert whatsapp_web.enviar_fila()["enviados"] == 0
    with pytest.raises(whatsapp_web.ErroWhatsAppWeb, match="horário comercial"):
        whatsapp_web.enviar_um("21988887777", "oi")
    config.salvar({"resumo": {"email_dono": "dono@x.com"}, "smtp": {"host": "smtp.x"}})
    assert "fora do horário" in importacao.resumo_diario({}, date(2026, 10, 3))
    no_relogio("2026-10-05 09:00")                       # segunda de manhã: a régua cobra o que ficou
    r = cobranca.rodar_regua(date(2026, 9, 30))
    assert r["email"] == 1 and enviados == ["fin@rps.com.br"]


def test_nenhum_email_ou_whatsapp_sai_fora_do_horario_mesmo_chamando_direto(base, no_relogio, monkeypatch):  # noqa: F811
    """Defesa de fundo: a própria função de envio recusa fora do horário — só o teste da tela passa (teste=True)."""
    import smtplib
    enviados = []

    class SMTP:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def starttls(self, **k): pass
        def login(self, *a): pass
        def send_message(self, msg): enviados.append(msg["Subject"])
    monkeypatch.setattr(smtplib, "SMTP", SMTP)
    config.salvar({"smtp": {"host": "smtp.x", "usuario": "a@x.com", "senha": "s"}, "cobranca": {"envio_horario_comercial": False}})
    no_relogio("2026-10-04 09:00")                       # domingo
    with pytest.raises(RuntimeError, match="domingo"):
        cobranca.enviar_email("c@x.com", "Cobrança", "texto")
    cobranca.enviar_email("dono@x.com", "Teste", "texto", teste=True)
    assert enviados == ["Teste"]
    with pytest.raises(whatsapp_web.ErroWhatsAppWeb, match="horário comercial"):
        whatsapp_web.enviar([{"numero": "5521988887777", "texto": "oi"}])
    no_relogio("2026-10-05 09:00")                       # segunda
    cobranca.enviar_email("c@x.com", "Cobrança", "texto")
    assert enviados == ["Teste", "Cobrança"]
