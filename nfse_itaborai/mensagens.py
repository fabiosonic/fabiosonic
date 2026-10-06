"""Registro de TODAS as mensagens que o sistema manda (e-mail e WhatsApp) — aba Mensagens.

Cada envio (ou falha) vira uma linha com data/hora, canal, destinatário, cliente, tipo, assunto, texto e anexos.
O registro fica no banco da empresa (dados/sistema.db): uma empresa nunca vê as mensagens da outra.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from . import db

# etapa da régua (eventos_cobranca.etapa) -> tipo mostrado na aba
ETAPA_TIPO = {-100: "Cobrança (boleto)", 1001: "Agradecimento", 1002: "Nota fiscal"}


def tipo_da_etapa(etapa: int) -> str:
    if etapa in ETAPA_TIPO:
        return ETAPA_TIPO[etapa]
    return "Lembrete" if etapa < 0 else "Vence hoje" if etapa == 0 else "Cobrança em atraso"


def registrar(canal: str, para: str, assunto: str = "", texto: str = "", status: str = "enviado", detalhe: str = "",
              tipo: str = "", titulo_id: int | None = None, cliente: str = "", anexos: list[str] | None = None) -> None:
    """Nunca derruba o envio: se o registro falhar, a mensagem já saiu."""
    try:
        with db.conexao() as con:
            con.execute("INSERT INTO mensagens (quando, canal, para, cliente, titulo_id, tipo, assunto, texto, anexos,"
                        " status, detalhe) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (db.agora(), canal, str(para or "")[:200], str(cliente or "")[:200], titulo_id,
                         tipo or "Mensagem", str(assunto or "")[:300], str(texto or "")[:6000],
                         ", ".join(Path(a).name for a in (anexos or []) if a), status, str(detalhe or "")[:500]))
    except Exception:  # noqa: BLE001
        pass


def listar(de: str = "", ate: str = "", canal: str = "", status: str = "", limite: int = 1000) -> list[dict]:
    sql, p = "SELECT id, quando, canal, para, cliente, titulo_id, tipo, assunto, anexos, status, detalhe FROM mensagens WHERE 1=1", []
    if de:
        sql += " AND quando>=?"
        p.append(de)
    if ate:
        sql += " AND quando<?"
        p.append(ate + " 99")
    if canal:
        sql += " AND canal=?"
        p.append(canal)
    if status:
        sql += " AND status=?"
        p.append(status)
    return db.linhas(sql + " ORDER BY quando DESC, id DESC LIMIT ?", (*p, int(limite)))


def obter(mid: int) -> dict:
    r = db.linhas("SELECT * FROM mensagens WHERE id=?", (int(mid),))
    if not r:
        raise ValueError("Mensagem não encontrada.")
    return r[0]


def resumo() -> dict:
    from . import cobranca, financeiro
    hoje = financeiro.hoje()
    sete = (hoje - timedelta(days=6)).isoformat()
    cont = {(r["canal"], r["status"]): r["n"] for r in db.linhas(
        "SELECT canal, status, COUNT(*) n FROM mensagens WHERE quando>=? GROUP BY canal, status", (hoje.isoformat(),))}
    erros = db.linhas("SELECT COUNT(*) n FROM mensagens WHERE status='erro' AND quando>=?", (sete,))[0]["n"]
    return {"email_hoje": cont.get(("email", "enviado"), 0), "whatsapp_hoje": cont.get(("whatsapp", "enviado"), 0),
            "erros_7d": erros, "fila_whatsapp": len(cobranca.fila_whatsapp())}


def importar_historico(con) -> None:
    """Primeira abertura: traz os envios já feitos pela régua (eventos_cobranca) para a aba, sem o texto."""
    con.execute(
        "INSERT INTO mensagens (quando, canal, para, cliente, titulo_id, tipo, assunto, texto, anexos, status, detalhe) "
        "SELECT e.data || ' 00:00:00', e.canal, CASE WHEN e.canal='email' AND e.status='enviado' THEN e.detalhe ELSE '' END,"
        " t.cliente_nome, e.titulo_id, CASE e.etapa WHEN -100 THEN 'Cobrança (boleto)' WHEN 1001 THEN 'Agradecimento'"
        " WHEN 1002 THEN 'Nota fiscal' ELSE CASE WHEN e.etapa<0 THEN 'Lembrete' WHEN e.etapa=0 THEN 'Vence hoje'"
        " ELSE 'Cobrança em atraso' END END, '', '', '', CASE e.status WHEN 'feito' THEN 'enviado' ELSE e.status END,"
        " CASE WHEN e.status='erro' THEN e.detalhe WHEN e.status='feito' THEN 'marcado como enviado na tela' ELSE 'anterior à aba Mensagens' END "
        "FROM eventos_cobranca e LEFT JOIN titulos t ON t.id=e.titulo_id WHERE e.status IN ('enviado','erro','feito')"
        " AND NOT EXISTS (SELECT 1 FROM mensagens)")


def reenviar(mid: int) -> dict:
    """Botão 'Reenviar': nota fiscal e cobrança são remontadas (valor atualizado, PDF/XML); o resto repete o texto."""
    from . import clientes, cobranca, financeiro, whatsapp_web
    m = obter(mid)
    t = financeiro.obter_titulo(m["titulo_id"]) if m.get("titulo_id") else None
    if t and m["tipo"] == "Nota fiscal":
        r = cobranca.enviar_nfse_titulo(t["id"])
        return {"mensagem": "Nota reenviada" + (f" por e-mail para {r['email']}" if r["email"] else "")
                + (" e colocada na fila do WhatsApp" if r["whatsapp"] else "") + "."}
    if t and t["status"] == "aberto" and m["tipo"] not in ("Agradecimento", "Boleto (PDF)"):
        r = cobranca.cobrar_agora(t["id"])
        feitos = [x for x in (r.get("email") and f"e-mail para {r['email']}",
                              r.get("whatsapp_enviado") and f"WhatsApp para {r['whatsapp_enviado']}") if x]
        if not feitos:
            raise ValueError(r.get("whatsapp_erro") or "Cliente sem e-mail/WhatsApp para cobrança: complete o cadastro.")
        return {"mensagem": "Cobrança reenviada (valor atualizado): " + " e ".join(feitos) + "."}
    if not m.get("texto"):
        raise ValueError("Esta mensagem é anterior à aba Mensagens e não tem o texto guardado para repetir.")
    ref = {"tipo": m["tipo"], "titulo_id": m["titulo_id"], "cliente": m["cliente"]}
    if m["canal"] == "email":
        para = m["para"] or (clientes.obter(t["cpf_cnpj"]) or {}).get("email", "") if t else m["para"]
        if "@" not in (para or ""):
            raise ValueError("Sem e-mail de destino.")
        cobranca.enviar_email(para, m["assunto"] or "Mensagem", m["texto"], ref=ref)
        return {"mensagem": f"E-mail reenviado para {para}."}
    numero = whatsapp_web.enviar_um(m["para"], m["texto"], ref=ref)
    return {"mensagem": f"WhatsApp reenviado para {numero}."}
