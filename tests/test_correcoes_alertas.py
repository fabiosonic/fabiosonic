"""Pacote D: falha de e-mail não interrompe nem repete a rotina de alertas."""
import smtplib
from datetime import date

from sqlalchemy import select

from mo_obrigacoes.alertas import Notificador, executar_alertas
from mo_obrigacoes.demo import criar_demo
from mo_obrigacoes.models import Empresa, Tarefa


class _SMTPFalso:
    enviados: list[str] = []
    contexto = None

    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self, context=None):
        _SMTPFalso.contexto = context

    def login(self, *a):
        pass

    def send_message(self, em):
        if "invalido" in em["To"]:
            raise smtplib.SMTPRecipientsRefused({em["To"]: (550, b"no such user")})
        _SMTPFalso.enviados.append(em["To"])


def test_email_invalido_nao_derruba_alertas(s, cfg, tmp_path, monkeypatch):
    criar_demo(s, tmp_path / "drive", "2026-09")
    s.scalar(select(Empresa).where(Empresa.codigo == "0002")).email_cliente = "invalido@x"
    monkeypatch.setattr(smtplib, "SMTP", _SMTPFalso)
    _SMTPFalso.enviados = []
    cfg.smtp_host = "smtp.exemplo"
    r = executar_alertas(s, Notificador(cfg), hoje=date(2026, 10, 13))
    assert r["cobrancas_cliente"] >= 1
    assert "financeiro@0001.exemplo.com.br" in _SMTPFalso.enviados
    assert _SMTPFalso.contexto is not None and _SMTPFalso.contexto.verify_mode != 0  # certificado validado
    # cobrança bem-sucedida ficou registrada: não repete no mesmo dia
    emp1 = s.scalar(select(Empresa).where(Empresa.codigo == "0001"))
    assert any(t.ultimo_alerta_em for t in s.scalars(select(Tarefa).where(Tarefa.empresa_id == emp1.id)))


def test_csv_protege_contra_injecao_de_formula(s, tmp_path):
    from sqlalchemy import select

    from mo_obrigacoes.relatorios import exportar_csv

    criar_demo(s, tmp_path / "drive", "2026-09")
    t = s.scalars(select(Tarefa)).first()
    t.observacao = "=1+1"
    s.flush()
    saida = exportar_csv([t])
    assert ";'=1+1" in saida
    assert ";=1+1" not in saida
