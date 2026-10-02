"""Cobrança: meio de pagamento por título (PIX próprio ou Asaas), mensagens e régua automática.

Régua padrão (dias em relação ao vencimento): -3 lembrete, 0 vence hoje, +1, +5, +15, +30 atraso.
E-mail sai sozinho (SMTP configurado). WhatsApp fica numa fila com o texto pronto e um clique
para abrir a conversa (envio automático por WhatsApp exige API paga; o link evita custo e bloqueio).
"""

from __future__ import annotations

import smtplib
import ssl
import urllib.parse
from datetime import date
from email.message import EmailMessage

from . import asaas, clientes, config, db, financeiro, pix


# ---------------------------------------------------------------- meio de pagamento

def preparar_pagamento(tid: int, cfg: dict | None = None) -> dict:
    """Gera PIX copia-e-cola (provedor 'pix') ou cobrança Asaas (boleto+PIX) para o título."""
    cfg = cfg or config.carregar()
    t = financeiro.obter_titulo(tid)
    if t["status"] != "aberto":
        return t
    prov = cfg["cobranca"]["provedor"]
    if prov == "asaas" and not t["asaas_id"]:
        financeiro.atualizar_titulo(tid, **asaas.criar_cobranca(t, cfg))
    elif prov == "pix" and cfg["empresa"].get("pix_chave"):
        emp = cfg["empresa"]
        financeiro.atualizar_titulo(tid, pix_copia_cola=pix.payload(
            emp["pix_chave"], t["valor_cent"], emp["nome"], emp["pix_cidade"], f"T{t['id']}",
            f"NFSE {t['nfse_numero']}" if t["nfse_numero"] else ""))
    return financeiro.obter_titulo(tid)


def sincronizar_asaas(cfg: dict | None = None) -> int:
    """Baixa automática: consulta no Asaas os títulos em aberto que têm cobrança lá."""
    cfg = cfg or config.carregar()
    baixados = 0
    for t in db.linhas("SELECT * FROM titulos WHERE status='aberto' AND asaas_id!=''"):
        st = asaas.consultar(t["asaas_id"], cfg)
        if st["pago"]:
            financeiro.baixar(t["id"], st["data_pagamento"], financeiro.reais(financeiro.cent(st["valor_pago"])),
                              "asaas")
            baixados += 1
    return baixados


# ---------------------------------------------------------------- mensagens

def _brl(c: int) -> str:
    return f"R$ {c / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _data(iso: str) -> str:
    return f"{iso[8:10]}/{iso[5:7]}/{iso[0:4]}"


def mensagem(t: dict, etapa: int, cfg: dict | None = None, em: date | None = None) -> tuple[str, str]:
    """(assunto, texto) conforme a etapa da régua."""
    cfg = cfg or config.carregar()
    t = financeiro.enriquecer(t, em)
    nome = t["cliente_nome"].split(" - ")[0]
    ref = f"{t['descricao']} — competência {t['competencia'][5:]}/{t['competencia'][:4]}"
    if etapa < 0:
        assunto = f"Lembrete: honorários vencem em {_data(t['vencimento'])}"
        abertura = f"Lembramos que o pagamento de {_brl(t['valor_cent'])} vence em {_data(t['vencimento'])}."
    elif etapa == 0:
        assunto = f"Vence hoje: {_brl(t['valor_cent'])}"
        abertura = f"O pagamento de {_brl(t['valor_cent'])} vence hoje ({_data(t['vencimento'])})."
    else:
        assunto = f"Pagamento em aberto há {t['dias_atraso']} dia(s)"
        abertura = (f"Não identificamos o pagamento de {_brl(t['valor_cent'])}, vencido em {_data(t['vencimento'])}. "
                    f"Valor atualizado com multa e juros: {_brl(t['total_cent'])}. "
                    "Se já pagou, por favor desconsidere e nos envie o comprovante.")
    linhas = [f"Olá, {nome}!", "", abertura, "", f"Referente a: {ref}"]
    if t["nfse_numero"]:
        linhas.append(f"NFS-e nº {t['nfse_numero']}" + (f": {t['nfse_link']}" if t["nfse_link"].startswith("http") else ""))
    if t["cobranca_link"]:
        linhas.append(f"Boleto/PIX: {t['cobranca_link']}")
    if t["linha_digitavel"]:
        linhas.append(f"Linha digitável: {t['linha_digitavel']}")
    if t["pix_copia_cola"]:
        linhas += ["", "PIX copia e cola:", t["pix_copia_cola"]]
    emp = cfg["empresa"]
    linhas += ["", "Atenciosamente,", emp.get("assinatura") or emp["nome"]]
    if emp.get("whatsapp"):
        linhas.append(f"WhatsApp: {emp['whatsapp']}")
    return assunto, "\n".join(linhas)


def link_whatsapp(telefone: str, texto: str) -> str:
    d = clientes._digitos(telefone)
    if d and not d.startswith("55"):
        d = "55" + d
    return f"https://wa.me/{d}?text={urllib.parse.quote(texto)}" if d else ""


def enviar_email(para: str, assunto: str, texto: str, cfg: dict | None = None) -> None:
    cfg = cfg or config.carregar()
    s = cfg["smtp"]
    if not s.get("host"):
        raise RuntimeError("SMTP não configurado.")
    msg = EmailMessage()
    msg["From"] = s.get("remetente") or s.get("usuario")
    msg["To"] = para
    if s.get("copia_para"):
        msg["Bcc"] = s["copia_para"]
    msg["Subject"] = assunto
    msg.set_content(texto)
    porta = int(s.get("porta") or 587)
    if s.get("ssl") or porta == 465:
        with smtplib.SMTP_SSL(s["host"], porta, context=ssl.create_default_context(), timeout=30) as srv:
            if s.get("usuario"):
                srv.login(s["usuario"], s["senha"])
            srv.send_message(msg)
    else:
        with smtplib.SMTP(s["host"], porta, timeout=30) as srv:
            srv.starttls(context=ssl.create_default_context())
            if s.get("usuario"):
                srv.login(s["usuario"], s["senha"])
            srv.send_message(msg)


# ---------------------------------------------------------------- régua

def etapa_devida(dias: int, etapas: list[int], enviadas: set[int]) -> int | None:
    """Etapa mais recente já alcançada e ainda não enviada (tolerância de 2 dias, sem disparar etapas velhas)."""
    candidatas = [e for e in sorted(etapas) if e <= dias and dias - e <= 2 and e not in enviadas]
    return candidatas[-1] if candidatas else None


def rodar_regua(em: date | None = None, cfg: dict | None = None) -> dict:
    em = em or financeiro.hoje()
    cfg = cfg or config.carregar()
    cob = cfg["cobranca"]
    res = {"email": 0, "whatsapp": 0, "sem_contato": 0, "erros": 0}
    # Só cobra títulos com NFS-e válida (ou marcados para não emitir): nunca dispara por nota de teste.
    for t in db.linhas("SELECT * FROM titulos WHERE status='aberto' AND nfse_status IN ('emitida','nao_emitir')"):
        dias = (em - date.fromisoformat(t["vencimento"])).days
        cli = clientes.obter(t["cpf_cnpj"]) or {}
        for canal, ligado in (("email", cob["regua_email"]), ("whatsapp", cob["regua_whatsapp"])):
            if not ligado:
                continue
            enviadas = {e["etapa"] for e in db.linhas(
                "SELECT etapa FROM eventos_cobranca WHERE titulo_id=? AND canal=?", (t["id"], canal))}
            etapa = etapa_devida(dias, cob["regua_dias"], enviadas)
            if etapa is None:
                continue
            assunto, texto = mensagem(t, etapa, cfg, em)
            if canal == "email":
                if not cli.get("email"):
                    status, det = "sem_contato", "cliente sem e-mail"
                    res["sem_contato"] += 1
                else:
                    try:
                        enviar_email(cli["email"], assunto, texto, cfg)
                        status, det = "enviado", cli["email"]
                        res["email"] += 1
                    except Exception as ex:  # noqa: BLE001 — registra qualquer falha de envio
                        status, det = "erro", str(ex)[:300]
                        res["erros"] += 1
            else:
                link = link_whatsapp(cli.get("telefone", ""), texto)
                status, det = ("pendente", link) if link else ("sem_contato", "cliente sem telefone")
                res["whatsapp" if link else "sem_contato"] += 1
            with db.conexao() as con:
                con.execute("INSERT OR IGNORE INTO eventos_cobranca (titulo_id, etapa, canal, data, status, detalhe)"
                            " VALUES (?,?,?,?,?,?)", (t["id"], etapa, canal, em.isoformat(), status, det))
    if any(res.values()):
        db.registrar("regua", f"Régua: {res}")
    return res


def fila_whatsapp() -> list[dict]:
    lst = db.linhas("SELECT e.*, t.cliente_nome, t.valor_cent, t.vencimento FROM eventos_cobranca e "
                    "JOIN titulos t ON t.id=e.titulo_id WHERE e.canal='whatsapp' AND e.status='pendente' "
                    "AND t.status='aberto' ORDER BY e.data")
    return lst


def marcar_whatsapp_feito(evento_id: int) -> None:
    with db.conexao() as con:
        con.execute("UPDATE eventos_cobranca SET status='feito' WHERE id=?", (evento_id,))


def historico(tid: int) -> list[dict]:
    return db.linhas("SELECT * FROM eventos_cobranca WHERE titulo_id=? ORDER BY data, etapa", (tid,))


def cobrar_agora(tid: int, cfg: dict | None = None) -> dict:
    """Envio manual imediato (botão 'Cobrar'): e-mail + link de WhatsApp."""
    cfg = cfg or config.carregar()
    t = preparar_pagamento(tid, cfg)
    dias = (financeiro.hoje() - date.fromisoformat(t["vencimento"])).days
    assunto, texto = mensagem(t, max(dias, -1) if dias < 0 else dias, cfg)
    cli = clientes.obter(t["cpf_cnpj"]) or {}
    out = {"whatsapp": link_whatsapp(cli.get("telefone", ""), texto), "email": "", "texto": texto}
    if cli.get("email") and cfg["smtp"].get("host"):
        enviar_email(cli["email"], assunto, texto, cfg)
        out["email"] = cli["email"]
    return out
