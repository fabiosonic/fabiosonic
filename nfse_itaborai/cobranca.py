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

from . import clientes, config, db, emissor, financeiro, inter, pix, whatsapp


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
    _oferecer_cartao(tid, cfg)
    return financeiro.obter_titulo(tid)


def _atualizar_cartao(t: dict, cfg: dict, em: date | None = None) -> dict:
    """Título em atraso: o link do cartão passa a cobrar o valor atualizado (multa e juros) + a taxa."""
    if not (t.get("cartao_link") and t.get("cartao_status") == "aberto"):
        return t
    from . import cartao
    try:
        cartao.gerar_link(t["id"], cfg=cfg, em=em)
    except Exception as ex:  # noqa: BLE001 — sem o link atualizado, a mensagem segue sem o cartão
        db.registrar("cartao", f"Título {t['id']}: link do cartão não atualizado ({ex})")
        financeiro.atualizar_titulo(t["id"], cartao_status="encerrado")
    return financeiro.obter_titulo(t["id"])


def _oferecer_cartao(tid: int, cfg: dict) -> None:
    """Se o cartão estiver ligado, a cobrança já leva o link 'pagar com cartão' (o cliente escolhe o meio)."""
    from . import cartao
    t = financeiro.obter_titulo(tid)
    if t["status"] != "aberto" or t.get("cartao_id") or not cfg["cobranca"].get("cartao_oferecer") \
            or not cartao.configurado(cfg) or clientes.eh_exterior(clientes.obter(t["cpf_cnpj"])) or not t.get("cobrar", 1):
        return
    try:
        cartao.gerar_link(tid, cfg=cfg)
    except Exception as ex:  # noqa: BLE001 — boleto/PIX continuam valendo; o robô tenta o cartão de novo
        db.registrar("cartao", f"Título {tid}: link de cartão não criado ({ex})")


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


SIGLAS = {"LTDA", "ME", "EPP", "EIRELI", "S/A", "SA", "S.A.", "MEI", "SS", "SLU"}
MINUSCULAS = {"de", "da", "do", "das", "dos", "e", "em", "a", "o"}


def nome_cliente(nome: str) -> str:
    """'RPS CONSULTORIA E SERVICOS LTDA' -> 'RPS Consultoria e Servicos LTDA' (nomes em maiúsculas ficam legíveis)."""
    nome = nome.split(" - ")[0].strip()
    if nome != nome.upper():
        return nome
    out = []
    for i, w in enumerate(nome.split()):
        sem_vogal = not any(ch in "AEIOUÁÉÍÓÚÂÊÔÃÕ" for ch in w)
        if w in SIGLAS or (sem_vogal and len(w) <= 4):
            out.append(w)
        elif i and w.lower() in MINUSCULAS:
            out.append(w.lower())
        else:
            out.append(w.capitalize())
    return " ".join(out)


def _conteudo(t: dict, etapa: int, cfg: dict, em: date | None = None) -> dict:
    """Partes da mensagem de cobrança (usadas no texto, no HTML e no WhatsApp)."""
    t = financeiro.enriquecer(t, em)
    nome = nome_cliente(t["cliente_nome"])
    if etapa < 0:
        assunto = f"Lembrete: honorários vencem em {_data(t['vencimento'])}"
        abertura = f"Lembramos que o pagamento de {_brl(t['valor_cent'])} vence em {_data(t['vencimento'])}."
    elif etapa == 0:
        assunto = f"Vence hoje: {_brl(t['valor_cent'])}"
        abertura = f"O pagamento de {_brl(t['valor_cent'])} vence hoje ({_data(t['vencimento'])})."
    else:
        assunto = f"Pagamento em aberto há {t['dias_atraso']} dia(s)"
        abertura = (f"Não identificamos o pagamento de {_brl(t['valor_cent'])}, vencido em {_data(t['vencimento'])}. "
                    f"Valor atualizado com multa e juros: {_brl(t['total_cent'])}.")
    cartao = None
    if t.get("cartao_link") and t.get("cartao_status") == "aberto":
        base = t["total_cent"] if etapa > 0 else t["valor_cent"]
        cartao = {"link": t["cartao_link"], "valor": t.get("cartao_total_cent") or 0,
                  "acrescimo": max(0, (t.get("cartao_total_cent") or 0) - base)}
    emp = cfg["empresa"]
    return {"assunto": assunto, "nome": nome, "abertura": abertura, "atraso": etapa > 0,
            "referente": t["descricao"], "competencia": f"{t['competencia'][5:]}/{t['competencia'][:4]}",
            "vencimento": _data(t["vencimento"]), "valor": _brl(t["valor_cent"]),
            "total": _brl(t["total_cent"]) if etapa > 0 else "",
            "nfse": t["nfse_numero"], "nfse_link": t["nfse_link"] if str(t["nfse_link"]).startswith("http") else "",
            "boleto_link": t["cobranca_link"], "boleto_pdf": bool(t.get("banco_id")),
            "linha": t["linha_digitavel"], "pix": t["pix_copia_cola"], "cartao": cartao,
            "assinatura": emp.get("assinatura") or emp["nome"], "whatsapp": emp.get("whatsapp", "")}


def mensagem(t: dict, etapa: int, cfg: dict | None = None, em: date | None = None) -> tuple[str, str]:
    """(assunto, texto) conforme a etapa da régua — texto simples (e-mail sem HTML e WhatsApp)."""
    cfg = cfg or config.carregar()
    c = _conteudo(t, etapa, cfg, em)
    linhas = [f"Olá, {c['nome']}!", "", c["abertura"]]
    if c["atraso"]:
        linhas.append("Se já pagou, por favor desconsidere e nos envie o comprovante.")
    linhas += ["", f"Referente a: {c['referente']} — competência {c['competencia']}"]
    if c["nfse"]:
        linhas.append(f"NFS-e nº {c['nfse']}" + (f": {c['nfse_link']}" if c["nfse_link"] else ""))
    if c["boleto_link"]:
        linhas.append(f"Boleto/PIX: {c['boleto_link']}")
    if c["boleto_pdf"]:
        linhas.append("Boleto em PDF: segue em anexo.")
    if c["linha"]:
        linhas.append(f"Linha digitável: {c['linha']}")
    if c["pix"]:
        linhas += ["", "PIX copia e cola:", c["pix"]]
    if c["cartao"]:
        k = c["cartao"]
        linhas += ["", f"Prefere pagar com cartão de crédito? {k['link']}",
                   f"Valor no cartão: {_brl(k['valor'])}"
                   + (f" (inclui {_brl(k['acrescimo'])} da taxa da operadora, por conta de quem paga com cartão)"
                      if k["acrescimo"] else ""),
                   "Parcelamento disponível, com os juros por conta do titular do cartão."]
        if k["acrescimo"] and (c["linha"] or c["pix"]):
            linhas.append("Pelo boleto ou PIX, sem acréscimo.")
    linhas += ["", "Atenciosamente,", c["assinatura"]]
    if c["whatsapp"]:
        linhas.append(f"WhatsApp: {c['whatsapp']}")
    return c["assunto"], "\n".join(linhas)


def mensagem_html(t: dict, etapa: int, cfg: dict | None = None, em: date | None = None) -> str:
    """Versão formatada do e-mail de cobrança (compatível com Gmail/Outlook: tabelas e estilos em linha)."""
    from html import escape as e
    cfg = cfg or config.carregar()
    c = _conteudo(t, etapa, cfg, em)
    cor = "#b42318" if c["atraso"] else "#1f4fbf"
    selo = "EM ATRASO" if c["atraso"] else ("VENCE HOJE" if etapa == 0 else "LEMBRETE")
    linha = lambda r, v, forte=False: (  # noqa: E731
        f'<tr><td style="padding:6px 0;color:#667085;font-size:14px">{r}</td>'
        f'<td style="padding:6px 0;text-align:right;font-size:14px;{"font-weight:700;color:#101828" if forte else "color:#101828"}">{v}</td></tr>')
    botao = lambda url, txt, fundo: (  # noqa: E731
        f'<a href="{e(url)}" style="display:inline-block;background:{fundo};color:#ffffff;text-decoration:none;'
        f'font-weight:700;font-size:15px;padding:12px 20px;border-radius:8px;margin:4px 6px 4px 0">{txt}</a>')
    caixa = lambda titulo, conteudo: (  # noqa: E731
        f'<p style="margin:18px 0 6px;font-size:13px;color:#667085;font-weight:700;text-transform:uppercase;letter-spacing:.04em">{titulo}</p>'
        f'<div style="background:#f4f6f9;border:1px solid #e3e7ee;border-radius:8px;padding:12px;font-family:Consolas,Menlo,monospace;'
        f'font-size:13px;color:#101828;word-break:break-all">{e(conteudo)}</div>')
    detalhes = (linha("Referente a", e(c["referente"])) + linha("Competência", c["competencia"])
                + linha("Vencimento", c["vencimento"]) + linha("Valor", c["valor"], not c["atraso"])
                + (linha("Valor atualizado (multa e juros)", c["total"], True) if c["atraso"] else "")
                + (linha("NFS-e", (f'<a href="{e(c["nfse_link"])}" style="color:#1f4fbf">nº {e(c["nfse"])}</a>'
                                   if c["nfse_link"] else f"nº {e(c['nfse'])}")) if c["nfse"] else ""))
    pagar = ""
    if c["boleto_link"]:
        pagar += botao(c["boleto_link"], "Pagar boleto / PIX", "#1f4fbf")
    if c["cartao"]:
        pagar += botao(c["cartao"]["link"], "Pagar com cartão de crédito", "#344054")
    corpo = (f'<p style="margin:0 0 4px;font-size:16px;color:#101828">Olá, <b>{e(c["nome"])}</b>!</p>'
             f'<p style="margin:8px 0 16px;font-size:15px;line-height:1.5;color:#344054">{e(c["abertura"])}'
             + (" Se já pagou, por favor desconsidere e nos envie o comprovante." if c["atraso"] else "") + "</p>"
             f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-top:1px solid #e3e7ee;'
             f'border-bottom:1px solid #e3e7ee;margin:0 0 8px">{detalhes}</table>'
             + (f'<div style="margin:16px 0 4px">{pagar}</div>' if pagar else "")
             + (caixa("Linha digitável do boleto", c["linha"]) if c["linha"] else "")
             + ('<p style="margin:6px 0 0;font-size:13px;color:#667085">O boleto em PDF segue em anexo.</p>' if c["boleto_pdf"] else "")
             + (caixa("PIX copia e cola", c["pix"]) if c["pix"] else ""))
    if c["cartao"]:
        k = c["cartao"]
        corpo += (f'<div style="margin:18px 0 0;padding:12px 14px;border:1px solid #e3e7ee;border-radius:8px;font-size:14px;color:#344054;line-height:1.5">'
                  f'<b>Cartão de crédito:</b> {_brl(k["valor"])}'
                  + (f' — inclui {_brl(k["acrescimo"])} da taxa da operadora, por conta de quem paga com cartão.' if k["acrescimo"] else ".")
                  + " Parcelamento disponível, com os juros por conta do titular do cartão."
                  + (" <b>Pelo boleto ou PIX, sem acréscimo.</b>" if k["acrescimo"] and (c["linha"] or c["pix"]) else "")
                  + f'<br><a href="{e(k["link"])}" style="color:#1f4fbf">{e(k["link"])}</a></div>')
    rodape = e(c["assinatura"]) + (f' · WhatsApp {e(c["whatsapp"])}' if c["whatsapp"] else "")
    return (f'<!doctype html><html lang="pt-br"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
            f'<title>{e(c["assunto"])}</title></head><body style="margin:0;padding:0;background:#f4f6f9">'
            f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f4f6f9;padding:24px 12px">'
            f'<tr><td align="center"><table role="presentation" width="100%" cellspacing="0" cellpadding="0" '
            f'style="max-width:600px;background:#ffffff;border-radius:12px;border:1px solid #e3e7ee;font-family:Segoe UI,Arial,sans-serif">'
            f'<tr><td style="padding:18px 24px;border-bottom:4px solid {cor}"><span style="font-size:17px;font-weight:700;color:#101828">'
            f'{e(cfg["empresa"]["nome"])}</span><span style="float:right;font-size:12px;font-weight:700;color:{cor};'
            f'border:1px solid {cor};border-radius:999px;padding:3px 10px">{selo}</span></td></tr>'
            f'<tr><td style="padding:22px 24px">{corpo}</td></tr>'
            f'<tr><td style="padding:14px 24px;background:#f8f9fb;border-top:1px solid #e3e7ee;border-radius:0 0 12px 12px;'
            f'font-size:13px;color:#667085">Atenciosamente,<br><b style="color:#344054">{rodape}</b></td></tr>'
            f'</table></td></tr></table></body></html>')


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
    # Só cobra títulos com NFS-e válida, sem nota ou com nota após o pagamento: nunca dispara por nota de teste.
    # Títulos lançados sem cobrança (cobrar=0) ficam fora da régua.
    for t in db.linhas("SELECT * FROM titulos WHERE status='aberto' AND " + financeiro.SQL_COBRADO +
                       " AND nfse_status IN ('emitida','nao_emitir','apos_pagamento')"):
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
            if etapa > 0 and canal == "email":
                t = _atualizar_cartao(t, cfg, em)
            assunto, texto = mensagem(t, etapa, cfg, em)
            if canal == "email":
                if not cli.get("email"):
                    status, det = "sem_contato", "cliente sem e-mail"
                    res["sem_contato"] += 1
                else:
                    try:
                        pdf_ = _pdf_boleto(t, cfg)
                        enviar_email(cli["email"], assunto, texto, cfg, [pdf_] if pdf_ else [],
                                     html=mensagem_html(t, etapa, cfg, em))
                        status, det = "enviado", cli["email"]
                        res["email"] += 1
                    except Exception as ex:  # noqa: BLE001 — registra qualquer falha de envio
                        status, det = "erro", str(ex)[:300]
                        res["erros"] += 1
            elif not cli.get("whatsapp_cobranca"):
                continue                             # cliente não marcado para receber cobrança por WhatsApp
            elif not cli.get("telefone"):
                status, det = "sem_contato", "cliente sem telefone"
                res["sem_contato"] += 1
            elif whatsapp.configurado(cfg):          # API oficial: envia sozinho
                try:
                    whatsapp.enviar_cobranca(t, etapa, cli["telefone"], cfg, em)
                    status, det = "enviado", whatsapp.numero(cli["telefone"])
                    res["whatsapp"] += 1
                except Exception as ex:  # noqa: BLE001 — registra a falha; o e-mail segue normalmente
                    status, det = "erro", str(ex)[:300]
                    res["erros"] += 1
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
    etapa = max(dias, -1) if dias < 0 else dias
    if etapa > 0:
        t = _atualizar_cartao(t, cfg)
    assunto, texto = mensagem(t, etapa, cfg)
    cli = clientes.obter(t["cpf_cnpj"]) or {}
    out = {"whatsapp": link_whatsapp(cli.get("telefone", ""), texto), "email": "",
           "texto": texto, "whatsapp_enviado": "", "whatsapp_erro": ""}
    if cli.get("telefone") and cli.get("whatsapp_cobranca") and whatsapp.configurado(cfg):
        try:
            whatsapp.enviar_cobranca(t, etapa, cli["telefone"], cfg)
            out["whatsapp_enviado"] = whatsapp.numero(cli["telefone"])
        except Exception as ex:  # noqa: BLE001 — mostra o motivo na tela; o link manual continua disponível
            out["whatsapp_erro"] = str(ex)
    if cli.get("email") and cfg["smtp"].get("host"):
        pdf_ = _pdf_boleto(t, cfg)
        enviar_email(cli["email"], assunto, texto, cfg, [pdf_] if pdf_ else [], html=mensagem_html(t, etapa, cfg))
        out["email"] = cli["email"]
    out["pdf"] = t.get("boleto_pdf") or (_pdf_boleto(t, cfg) if t.get("banco_id") else "")
    return out
