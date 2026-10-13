"""Alertas: resumo diário para a equipe, cobrança de documentos ao cliente e webhook."""
from __future__ import annotations

import json
import logging
import smtplib
import ssl
import urllib.request
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from html import escape

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from .calendario import formatar_competencia
from .config import Config, get_config
from .models import (
    STATUS_PENDENTE,
    TIPO_RECEBIMENTO,
    Documento,
    Empresa,
    Evento,
    Tarefa,
)

log = logging.getLogger(__name__)
INTERVALO_COBRANCA_CLIENTE = timedelta(days=3)


@dataclass
class Mensagem:
    para: list[str]
    assunto: str
    html: str


@dataclass
class Notificador:
    """Envia e-mails por SMTP e eventos por webhook. Em testes, use ``simular=True``."""

    cfg: Config
    simular: bool = False
    enviadas: list[Mensagem] = field(default_factory=list)

    def email(self, msg: Mensagem) -> bool:
        destinatarios = [d for d in msg.para if d]
        if not destinatarios:
            return False
        self.enviadas.append(msg)
        if self.simular or not self.cfg.smtp_host:
            log.info("[simulado] e-mail para %s: %s", destinatarios, msg.assunto)
            return True
        em = EmailMessage()
        em["From"] = self.cfg.email_remetente or self.cfg.smtp_user
        em["To"] = ", ".join(destinatarios)
        em["Subject"] = msg.assunto
        em.set_content("Este e-mail requer um leitor compatível com HTML.")
        em.add_alternative(msg.html, subtype="html")
        try:
            with smtplib.SMTP(self.cfg.smtp_host, self.cfg.smtp_port, timeout=30) as s:
                s.starttls(context=ssl.create_default_context())  # valida o certificado do servidor SMTP
                if self.cfg.smtp_user:
                    s.login(self.cfg.smtp_user, self.cfg.smtp_password)
                s.send_message(em)
        except (smtplib.SMTPException, OSError) as exc:
            # um endereço ruim não pode derrubar a rotina inteira (e fazê-la reenviar tudo a cada ciclo)
            log.warning("Falha ao enviar e-mail para %s: %s", destinatarios, exc)
            self.enviadas.remove(msg)
            return False
        return True

    def webhook(self, evento: str, dados: dict) -> bool:
        if not self.cfg.webhook_url or self.simular:
            return False
        if not self.cfg.webhook_url.startswith("https://"):
            # o corpo leva CNPJ e WhatsApp de clientes: nunca enviar em texto puro
            log.warning("Webhook recusado: a URL precisa começar com https://")
            return False
        corpo = json.dumps({"evento": evento, **dados}, default=str).encode()
        req = urllib.request.Request(self.cfg.webhook_url, data=corpo, headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req, timeout=15).read()
            return True
        except Exception as exc:  # noqa: BLE001
            log.warning("Webhook falhou: %s", exc)
            return False


# ----------------------------------------------------------------------------
# Consultas
# ----------------------------------------------------------------------------
def tarefas_pendentes(sessao: Session, ate: date) -> list[Tarefa]:
    stmt = (
        select(Tarefa)
        .options(joinedload(Tarefa.empresa), joinedload(Tarefa.obrigacao))
        .where(Tarefa.status == STATUS_PENDENTE, Tarefa.vencimento <= ate)
        .order_by(Tarefa.vencimento)
    )
    return [t for t in sessao.scalars(stmt).unique() if t.empresa.ativa]


def documentos_para_revisar(sessao: Session, desde: datetime) -> list[Documento]:
    stmt = (
        select(Documento)
        .options(joinedload(Documento.empresa))
        .where(Documento.situacao.in_(["nao_identificado", "divergente", "sem_tarefa"]),
               Documento.processado_em >= desde)
        .order_by(Documento.processado_em.desc())
    )
    return list(sessao.scalars(stmt).unique())


# ----------------------------------------------------------------------------
# Montagem dos e-mails
# ----------------------------------------------------------------------------
ESTILO = ("font-family:Arial,sans-serif;font-size:13px;border-collapse:collapse;width:100%")


def _tabela(tarefas: list[Tarefa], hoje: date) -> str:
    if not tarefas:
        return "<p><i>Nada pendente.</i></p>"
    linhas = []
    for t in tarefas:
        dias = (t.vencimento - hoje).days
        situacao = f"<b style='color:#b42318'>{-dias} dia(s) em atraso</b>" if dias < 0 else (
            "<b style='color:#b54708'>vence hoje</b>" if dias == 0 else f"vence em {dias} dia(s)")
        linhas.append(
            f"<tr><td>{escape(t.empresa.codigo)} - {escape(t.empresa.nome_exibicao)}</td>"
            f"<td>{escape(t.obrigacao.nome)}</td>"
            f"<td>{formatar_competencia(t.competencia, t.obrigacao.periodicidade)}</td>"
            f"<td>{t.vencimento:%d/%m/%Y}</td><td>{situacao}</td></tr>")
    return (f"<table style='{ESTILO}' border='1' cellpadding='4'><tr style='background:#eef2f6'>"
            "<th>Empresa</th><th>Obrigação</th><th>Competência</th><th>Vencimento</th><th>Situação</th></tr>"
            + "".join(linhas) + "</table>")


def montar_resumo(titulo: str, tarefas: list[Tarefa], docs: list[Documento], hoje: date, cfg: Config) -> str:
    atrasadas = [t for t in tarefas if t.vencimento < hoje]
    proximas = [t for t in tarefas if t.vencimento >= hoje]
    html = [f"<h2 style='font-family:Arial'>{escape(titulo)}</h2>",
            f"<p style='font-family:Arial'>{len(atrasadas)} atrasada(s) · {len(proximas)} a vencer "
            f"nos próximos {cfg.dias_alerta_vencimento} dia(s)</p>",
            "<h3 style='font-family:Arial;color:#b42318'>Em atraso</h3>", _tabela(atrasadas, hoje),
            "<h3 style='font-family:Arial'>A vencer</h3>", _tabela(proximas, hoje)]
    if docs:
        html.append("<h3 style='font-family:Arial'>Documentos para revisar no Drive</h3><ul style='font-family:Arial'>")
        rotulo = {"nao_identificado": "não identificado", "divergente": "CNPJ de outra empresa",
                  "sem_tarefa": "obrigação fora do perfil cadastrado"}
        for d in docs[:50]:
            emp = d.empresa.codigo if d.empresa else "?"
            html.append(f"<li>{escape(emp)} — <a href='{escape(d.link)}'>{escape(d.nome)}</a> "
                        f"({rotulo.get(d.situacao, d.situacao)})</li>")
        html.append("</ul>")
    html.append(f"<p style='font-family:Arial;color:#667085'>{escape(cfg.nome_escritorio)} — "
                "Sistema de Monitoramento de Obrigações</p>")
    return "".join(html)


def montar_cobranca_cliente(emp: Empresa, tarefas: list[Tarefa], cfg: Config) -> str:
    itens = "".join(
        f"<li><b>{escape(t.obrigacao.nome)}</b> — competência "
        f"{formatar_competencia(t.competencia, t.obrigacao.periodicidade)} (prazo {t.vencimento:%d/%m/%Y})</li>"
        for t in tarefas)
    return (
        f"<div style='font-family:Arial;font-size:14px'>"
        f"<p>Olá, {escape(emp.nome_exibicao)}!</p>"
        f"<p>Ainda não localizamos na sua pasta do Google Drive os documentos abaixo:</p><ul>{itens}</ul>"
        "<p>Por favor, deposite-os na pasta <b>04 - Documentos do Cliente</b> do mês correspondente. "
        "Assim que forem salvos, nosso sistema identifica automaticamente e esta cobrança é encerrada.</p>"
        "<p>O envio no prazo garante que apuração de impostos, folha e obrigações acessórias "
        "sejam entregues sem multas.</p>"
        f"<p>Atenciosamente,<br>{escape(cfg.nome_escritorio)}</p></div>")


# ----------------------------------------------------------------------------
# Rotina diária
# ----------------------------------------------------------------------------
def executar_alertas(sessao: Session, notificador: Notificador | None = None, hoje: date | None = None) -> dict:
    cfg = get_config()
    notificador = notificador or Notificador(cfg)
    hoje = hoje or date.today()
    pendentes = tarefas_pendentes(sessao, hoje + timedelta(days=cfg.dias_alerta_vencimento))
    docs = documentos_para_revisar(sessao, datetime.utcnow() - timedelta(days=1))
    enviados = 0

    # 1) Resumo geral para a gestão
    if cfg.email_gestor and (pendentes or docs):
        enviados += notificador.email(Mensagem(
            [cfg.email_gestor], f"[Obrigações] Resumo de {hoje:%d/%m/%Y}: "
            f"{sum(t.vencimento < hoje for t in pendentes)} em atraso",
            montar_resumo("Resumo geral do escritório", pendentes, docs, hoje, cfg)))

    # 2) Resumo por responsável (apenas tarefas do escritório)
    por_resp: dict[str, list[Tarefa]] = defaultdict(list)
    for t in pendentes:
        if t.obrigacao.tipo == TIPO_RECEBIMENTO:
            continue
        resp = t.empresa.responsavel_do(t.obrigacao.departamento)
        if resp and resp.email and resp.ativo:
            por_resp[resp.email].append(t)
    for email, lista in por_resp.items():
        enviados += notificador.email(Mensagem(
            [email], f"[Obrigações] Suas pendências em {hoje:%d/%m/%Y}",
            montar_resumo("Suas obrigações pendentes", lista, [], hoje, cfg)))

    # 3) Cobrança ao cliente dos documentos que ele deve depositar
    cobrancas = 0
    if cfg.cobranca_automatica_cliente:
        por_emp: dict[int, list[Tarefa]] = defaultdict(list)
        agora = datetime.utcnow()
        for t in pendentes:
            if t.obrigacao.tipo != TIPO_RECEBIMENTO or t.vencimento >= hoje:
                continue
            if t.ultimo_alerta_em and agora - t.ultimo_alerta_em < INTERVALO_COBRANCA_CLIENTE:
                continue
            por_emp[t.empresa_id].append(t)
        for lista in por_emp.values():
            emp = lista[0].empresa
            if not emp.email_cliente:
                continue
            ok = notificador.email(Mensagem(
                [emp.email_cliente], f"{cfg.nome_escritorio}: documentos pendentes", montar_cobranca_cliente(emp, lista, cfg)))
            notificador.webhook("cobranca_cliente", {
                "empresa": emp.razao_social, "cnpj": emp.cnpj, "whatsapp": emp.whatsapp_cliente,
                "pendencias": [f"{t.obrigacao.nome} {t.competencia}" for t in lista]})
            if ok:
                cobrancas += 1
                for t in lista:
                    t.alertas_enviados += 1
                    t.ultimo_alerta_em = agora
                sessao.add(Evento(tipo="cobranca_cliente", empresa_id=emp.id,
                                  mensagem=f"Cobrança de {len(lista)} documento(s) enviada para {emp.email_cliente}"))

    atrasadas = [t for t in pendentes if t.vencimento < hoje]
    if atrasadas:
        notificador.webhook("resumo_atrasos", {"data": hoje.isoformat(), "atrasadas": len(atrasadas)})
    sessao.add(Evento(tipo="alertas", mensagem=f"{enviados} resumo(s) e {cobrancas} cobrança(s) enviados"))
    sessao.flush()
    return {"pendentes": len(pendentes), "atrasadas": len(atrasadas), "emails": enviados,
            "cobrancas_cliente": cobrancas, "documentos_revisar": len(docs)}
