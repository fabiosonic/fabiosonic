"""Cobrança: meio de pagamento por título (boleto+PIX pela API do Banco Inter ou PIX próprio), mensagens e régua.

Nenhum intermediário: o boleto é registrado direto no Inter (conta do escritório) e o PIX "copia e cola"
próprio sai da chave PIX da empresa. Régua padrão (dias em relação ao vencimento): -3, 0, +1, +5, +15, +30.
E-mail sai sozinho (SMTP do próprio escritório) com o PDF do boleto anexado. WhatsApp: fila com o texto pronto
e um clique para abrir a conversa (wa.me), sem serviço intermediário.
"""

from __future__ import annotations

import os
import re
import smtplib
from email.utils import formataddr
import ssl
import urllib.parse
from datetime import date
from email.message import EmailMessage
from pathlib import Path

from . import clientes, config, db, emissor, financeiro, inter, pix


# ---------------------------------------------------------------- meio de pagamento

def preparar_pagamento(tid: int, cfg: dict | None = None) -> dict:
    """Registra o boleto no Inter (provedor 'inter') ou gera o PIX copia-e-cola próprio (provedor 'pix')."""
    cfg = cfg or config.carregar()
    t = financeiro.obter_titulo(tid)
    if t["status"] != "aberto":
        return t
    prov = cfg["cobranca"]["provedor"]
    if prov == "inter" and not t["banco_id"] and inter.configurado(cfg):
        financeiro.atualizar_titulo(tid, **inter.criar_cobranca(t, cfg))
        db.registrar("boleto", f"Título {tid} ({t['cliente_nome']}): boleto registrado no Inter")
        try:
            salvar_boleto(tid, cfg)
        except Exception as ex:  # noqa: BLE001 — o robô tenta o PDF de novo na próxima execução
            db.registrar("boleto", f"Título {tid}: PDF ainda indisponível ({ex})")
    elif prov in ("pix", "inter") and cfg["empresa"].get("pix_chave") and not t["pix_copia_cola"] \
            and not t["banco_id"]:  # Inter ainda não configurado: PIX próprio enquanto isso
        emp = cfg["empresa"]
        financeiro.atualizar_titulo(tid, pix_copia_cola=pix.payload(
            emp["pix_chave"], t["valor_cent"], emp["nome"], emp["pix_cidade"], f"T{t['id']}",
            f"NFSE {t['nfse_numero']}" if t["nfse_numero"] else ""))
    return financeiro.obter_titulo(tid)


def cancelar_boleto(t: dict, motivo: str = "", cfg: dict | None = None) -> None:
    """Cancela no banco o boleto de um título cancelado (para o cliente não pagar por engano)."""
    if not t.get("banco_id"):
        return
    try:
        inter.cancelar(t["banco_id"], motivo or "Titulo cancelado", cfg)
        db.registrar("boleto", f"Boleto do título {t['id']} cancelado no Inter")
    except inter.ErroInter as ex:
        db.registrar("boleto", f"Cancelamento do boleto do título {t['id']}: {ex}")


# ---------------------------------------------------------------- PDF dos boletos

def pasta_boletos(cfg: dict | None = None) -> Path:
    cfg = cfg or config.carregar()
    p = Path(os.path.expanduser(cfg["pastas"].get("boletos") or "~/Downloads/Boletos"))
    return p if p.is_absolute() else emissor.RAIZ / p


def _nome_base(t: dict) -> str:
    nome = re.sub(r'[\\/:*?"<>|]+', " ", t["cliente_nome"]).strip()[:60].strip()
    return f"{t['vencimento']} - {nome} - titulo {t['id']}"


def _texto_pagamento(t: dict) -> str:
    linhas = [f"Cliente: {t['cliente_nome']} ({t['cpf_cnpj']})", f"Referente a: {t['descricao']}",
              f"Competência: {t['competencia'][5:]}/{t['competencia'][:4]}",
              f"Vencimento: {_data(t['vencimento'])}", f"Valor: {_brl(t['valor_cent'])}"]
    if t.get("nosso_numero"):
        linhas.append(f"Nosso número: {t['nosso_numero']}")
    if t.get("linha_digitavel"):
        linhas += ["", "Linha digitável do boleto:", t["linha_digitavel"]]
    if t.get("pix_copia_cola"):
        linhas += ["", "PIX copia e cola:", t["pix_copia_cola"]]
    return "\r\n".join(linhas) + "\r\n"


def salvar_boleto(tid: int, cfg: dict | None = None, refazer: bool = False) -> str:
    """Salva em <pasta de boletos>/AAAA-MM/ o PDF do boleto e, ao lado, um .txt com a linha digitável e o PIX."""
    cfg = cfg or config.carregar()
    t = financeiro.obter_titulo(tid)
    if t.get("boleto_pdf") and Path(t["boleto_pdf"]).exists() and not refazer:
        return t["boleto_pdf"]
    if not t.get("banco_id"):
        raise RuntimeError("Este título ainda não tem boleto registrado no Inter (use o botão Cobrar ou "
                           "aguarde o robô).")
    dados = inter.pdf(t["banco_id"], cfg)
    if not t.get("linha_digitavel"):  # registro concluído depois da emissão: completa os dados
        d = inter.consultar(t["banco_id"], cfg)
        financeiro.atualizar_titulo(tid, **{k: d[k] for k in ("linha_digitavel", "pix_copia_cola", "nosso_numero")
                                            if d[k]})
        t = financeiro.obter_titulo(tid)
    destino = pasta_boletos(cfg) / t["competencia"] / (_nome_base(t) + ".pdf")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(dados)
    destino.with_name(_nome_base(t) + " - pagamento.txt").write_text(_texto_pagamento(t), encoding="utf-8")
    financeiro.atualizar_titulo(tid, boleto_pdf=str(destino))
    return str(destino)


def salvar_boletos(competencia: str = "", cfg: dict | None = None) -> dict:
    """Salva os PDFs que faltam dos títulos em aberto com boleto (opcionalmente de uma competência)."""
    cfg = cfg or config.carregar()
    sql = "SELECT id FROM titulos WHERE status='aberto' AND banco_id!=''"
    params: tuple = ()
    if competencia:
        sql, params = sql + " AND competencia=?", (competencia,)
    res = {"baixados": 0, "ja_existiam": 0, "erros": [], "pasta": str(pasta_boletos(cfg))}
    for tid in (r["id"] for r in db.linhas(sql, params)):
        t = financeiro.obter_titulo(tid)
        if t.get("boleto_pdf") and Path(t["boleto_pdf"]).exists():
            res["ja_existiam"] += 1
            continue
        try:
            salvar_boleto(tid, cfg)
            res["baixados"] += 1
        except Exception as ex:  # noqa: BLE001 — segue para os próximos
            res["erros"].append(f"{t['cliente_nome']}: {ex}")
    return res


def _pdf_boleto(t: dict, cfg: dict) -> str:
    if not (t.get("banco_id") and cfg["cobranca"].get("anexar_boleto", True)):
        return ""
    try:
        return salvar_boleto(t["id"], cfg)
    except Exception:  # noqa: BLE001 — sem o PDF a mensagem sai com a linha digitável e o PIX
        return ""


def sincronizar_banco(cfg: dict | None = None) -> int:
    """Baixa automática: consulta no Inter os títulos em aberto que têm boleto registrado."""
    cfg = cfg or config.carregar()
    baixados = 0
    for t in db.linhas("SELECT * FROM titulos WHERE status='aberto' AND banco_id!=''"):
        st = inter.consultar(t["banco_id"], cfg)
        if st["pago"]:
            financeiro.baixar(t["id"], st["data_pagamento"][:10] or financeiro.hoje().isoformat(),
                              financeiro.reais(financeiro.cent(st["valor_pago"])), "inter")
            baixados += 1
        elif st["baixado"]:
            db.registrar("boleto", f"Boleto do título {t['id']} ({t['cliente_nome']}) está {st['situacao']} no Inter")
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
    if t.get("banco_id"):
        linhas.append("Boleto em PDF: segue em anexo.")
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


def enviar_email(para: str, assunto: str, texto: str, cfg: dict | None = None, anexos: list[str] | None = None,
                 html: str = "") -> None:
    cfg = cfg or config.carregar()
    s = cfg["smtp"]
    if not s.get("host"):
        raise RuntimeError("SMTP não configurado.")
    msg = EmailMessage()
    usuario = str(s.get("usuario") or "").strip()
    remetente = str(s.get("remetente") or "").strip()
    # "MORAES" sozinho não é endereço: vira o nome de exibição do e-mail do usuário (MORAES <usuario@...>)
    msg["From"] = remetente if "@" in remetente else formataddr((remetente, usuario)) if remetente else usuario
    msg["To"] = para
    if s.get("copia_para"):
        msg["Bcc"] = s["copia_para"]
    msg["Subject"] = assunto
    msg.set_content(texto)
    if html:
        msg.add_alternative(html, subtype="html")
    for caminho in anexos or []:
        msg.add_attachment(Path(caminho).read_bytes(), maintype="application", subtype="pdf",
                           filename=Path(caminho).name)
    porta = int(s.get("porta") or 587)
    host = str(s["host"]).strip()
    if s.get("ssl") or porta == 465:
        with smtplib.SMTP_SSL(host, porta, context=ssl.create_default_context(), timeout=30) as srv:
            _autenticar(srv, usuario, str(s.get("senha") or ""), host, porta)
            srv.send_message(msg)
    else:
        with smtplib.SMTP(host, porta, timeout=30) as srv:
            srv.starttls(context=ssl.create_default_context())
            _autenticar(srv, usuario, str(s.get("senha") or ""), host, porta)
            srv.send_message(msg)


def _autenticar(srv, usuario: str, senha: str, host: str, porta: int) -> None:
    """Login no SMTP. Tenta também a senha sem espaços nas pontas (comum ao colar) e explica a recusa."""
    if not usuario:
        return
    if not senha:
        raise RuntimeError("Senha do e-mail não informada: preencha a senha em Configurações › E-mail (SMTP) e salve.")
    erro = None
    for tentativa in dict.fromkeys((senha, senha.strip())):
        try:
            srv.login(usuario, tentativa)
            return
        except smtplib.SMTPAuthenticationError as ex:
            erro = ex
    resposta = erro.smtp_error.decode(errors="replace") if isinstance(erro.smtp_error, bytes) else str(erro.smtp_error)
    raise RuntimeError(
        f"O servidor {host} recusou o usuário/senha ({erro.smtp_code} {resposta}). Confira: (1) usuário = o e-mail "
        f"completo ({usuario}); (2) a senha é a da caixa de e-mail (a mesma do webmail) — se a conta tiver "
        f"verificação em duas etapas, use uma senha de aplicativo; (3) no painel do provedor, o envio autenticado "
        f"(SMTP) está liberado para a conta; (4) se continuar, teste a porta 465 com “SSL direto”.") from erro


# ---------------------------------------------------------------- régua

def etapas_da_regua(dias: int, cob: dict) -> list[int]:
    """Etapas fixas da régua + cobrança recorrente dos atrasados: a partir de N dias do vencimento original,
    repete a cada X dias enquanto o título estiver em aberto."""
    etapas = set(int(e) for e in cob["regua_dias"])
    inicio, intervalo = int(cob.get("recorrente_apos_dias") or 0), int(cob.get("recorrente_a_cada_dias") or 0)
    if cob.get("recorrente_ativa", True) and intervalo > 0 and inicio > 0:
        etapas.update(range(inicio, max(dias, inicio) + 1, intervalo))
    return sorted(etapas)


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
            etapa = etapa_devida(dias, etapas_da_regua(dias, cob), enviadas)
            if etapa is None:
                continue
            assunto, texto = mensagem(t, etapa, cfg, em)
            if canal == "email":
                if not cli.get("email"):
                    status, det = "sem_contato", "cliente sem e-mail"
                    res["sem_contato"] += 1
                else:
                    try:
                        pdf_ = _pdf_boleto(t, cfg)
                        enviar_email(cli["email"], assunto, texto, cfg, [pdf_] if pdf_ else [])
                        status, det = "enviado", cli["email"]
                        res["email"] += 1
                    except Exception as ex:  # noqa: BLE001 — registra qualquer falha de envio
                        status, det = "erro", str(ex)[:300]
                        res["erros"] += 1
            elif not cli.get("telefone"):
                status, det = "sem_contato", "cliente sem telefone"
                res["sem_contato"] += 1
            else:
                status, det = "pendente", link_whatsapp(cli["telefone"], texto)
                res["whatsapp"] += 1
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
    out = {"whatsapp": link_whatsapp(cli.get("telefone", ""), texto), "email": "",
           "texto": texto}
    if cli.get("email") and cfg["smtp"].get("host"):
        pdf_ = _pdf_boleto(t, cfg)
        enviar_email(cli["email"], assunto, texto, cfg, [pdf_] if pdf_ else [])
        out["email"] = cli["email"]
    out["pdf"] = t.get("boleto_pdf") or (_pdf_boleto(t, cfg) if t.get("banco_id") else "")
    return out
