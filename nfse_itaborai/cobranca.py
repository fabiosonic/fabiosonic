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
from datetime import date, timedelta
from email.message import EmailMessage
from pathlib import Path

from . import clientes, config, db, emissor, financeiro, horario, inter, mensagens, pix, textos, whatsapp, whatsapp_web


# ---------------------------------------------------------------- meio de pagamento

def preparar_pagamento(tid: int, cfg: dict | None = None) -> dict:
    """Registra o boleto no Inter (provedor 'inter') ou gera o PIX copia-e-cola próprio (provedor 'pix')."""
    cfg = cfg or config.carregar()
    t = financeiro.obter_titulo(tid)
    if t["status"] != "aberto":
        return t
    prov = cfg["cobranca"]["provedor"]
    if t.get("boleto_situacao"):
        return t                         # cobrança sem boleto (dispensado/expirado): nenhum boleto é registrado
    sem_endereco = prov == "inter" and not t["banco_id"] and inter.configurado(cfg) \
        and inter.endereco_faltando(clientes.obter(t["cpf_cnpj"])) and cfg["empresa"].get("pix_chave")
    if sem_endereco and not t["pix_copia_cola"]:
        # pessoa física cadastrada só com CPF e nome (o Emissor Nacional não exige endereço), mas o banco exige o
        # endereço do pagador no boleto: cobra pelo PIX do escritório; com o endereço preenchido, o boleto sai depois
        db.registrar("boleto", f"Título {tid} ({t['cliente_nome']}): cliente sem endereço — cobrança pelo PIX do "
                               "escritório até o cadastro ser completado")
    if prov == "inter" and not t["banco_id"] and inter.configurado(cfg) and not sem_endereco:
        # um único boleto por título; se já venceu, ele sai com o valor atualizado (multa e juros até hoje)
        hoje = financeiro.hoje()
        atualizado, extra = None, {}
        if date.fromisoformat(t["vencimento"]) < hoje:
            venc = (hoje + timedelta(days=int(cfg["cobranca"].get("dias_boleto_atrasado", 5)))).isoformat()
            atualizado = {"valor_cent": financeiro.encargos(t, hoje)["total_cent"], "vencimento": venc,
                          "original_cent": t["valor_cent"], "venc_original": t["vencimento"], "ate": hoje.isoformat()}
            extra = {"boleto_valor_cent": atualizado["valor_cent"], "boleto_vencimento": venc}
        financeiro.atualizar_titulo(tid, **inter.criar_cobranca(t, cfg, atualizado=atualizado), **extra)
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
    t = financeiro.obter_titulo(tid)
    if t.get("cobranca_erro") and financeiro.tem_meio_de_pagamento(t):
        financeiro.atualizar_titulo(tid, cobranca_erro="")
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


def refazer_cobranca(tid: int, motivo: str = "Titulo alterado", cfg: dict | None = None) -> dict:
    """Título editado (valor/vencimento): cancela no banco o boleto antigo — o cliente não pode pagar o valor errado —
    e registra um novo com os dados atuais (PIX próprio é regerado; cobrança 'dispensada' continua sem boleto).
    O link de cartão antigo é descartado; um novo é oferecido com o valor certo."""
    cfg = cfg or config.carregar()
    t = financeiro.obter_titulo(tid)
    if t["status"] != "aberto":
        return t
    if t.get("banco_id"):
        cancelar_boleto(t, motivo, cfg)
    if t.get("boleto_pdf"):
        try:
            Path(t["boleto_pdf"]).unlink(missing_ok=True)      # PDF do boleto antigo não pode ser reenviado
        except OSError:
            pass
    financeiro.atualizar_titulo(tid, banco_id="", nosso_numero="", linha_digitavel="", pix_copia_cola="", boleto_pdf="",
                                boleto_valor_cent=0, boleto_vencimento="", cobranca_link="",
                                cartao_id="", cartao_link="", cartao_total_cent=0, cartao_parcelas=0, cartao_status="")
    if t.get("boleto_situacao") in ("expirado", "cancelado"):
        financeiro.atualizar_titulo(tid, boleto_situacao="")    # boleto antigo foi embora; o novo sai normalmente
    if t.get("cobrar", 1):
        try:
            preparar_pagamento(tid, cfg)
        except Exception as ex:  # noqa: BLE001 — o motivo fica no título e o robô tenta de novo
            financeiro.atualizar_titulo(tid, cobranca_erro=str(ex)[:300])
            db.registrar("boleto", f"Título {tid}: cobrança não refeita ({ex})")
    return financeiro.obter_titulo(tid)


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
    if not (t.get("banco_id") and cfg["cobranca"].get("anexar_boleto", True)) or t.get("boleto_situacao"):
        return ""
    try:
        return salvar_boleto(t["id"], cfg)
    except Exception as ex:  # noqa: BLE001 — sem o PDF a mensagem sai com a linha digitável e o PIX
        db.registrar("boleto", f"Título {t['id']} ({t['cliente_nome']}): PDF do boleto não veio do banco ({str(ex)[:160]})")
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
        elif st["baixado"] and t.get("boleto_situacao") != st["situacao"].lower():
            # o banco derrubou o boleto (prazo de pagamento após o vencimento acabou): NÃO se registra outro
            # (cada boleto tem custo); as próximas mensagens levam o PIX da chave do escritório, sem custo
            financeiro.atualizar_titulo(t["id"], boleto_situacao=st["situacao"].lower())
            db.registrar("boleto", f"Boleto do título {t['id']} ({t['cliente_nome']}) está {st['situacao']} no Inter: "
                                   "a cobrança segue pelo PIX do escritório, sem novo boleto")
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


ETAPA_BOLETO = -100          # envio do boleto assim que a cobrança é gerada (antes de qualquer etapa da régua)
ETAPA_PAGO = 1001            # agradecimento pelo pagamento
ETAPA_NFSE = 1002            # envio da nota fiscal depois do pagamento
ETAPA_SUSPENSAO = -900       # aviso de suspensão dos serviços (débito com 90 dias de atraso)


def _conteudo(t: dict, etapa: int, cfg: dict, em: date | None = None) -> dict:
    """Partes da mensagem de cobrança (usadas no texto, no HTML e no WhatsApp)."""
    t = financeiro.enriquecer(t, em)
    nome = nome_cliente(t["cliente_nome"])
    chave = ("boleto" if t["dias_atraso"] <= 0 else "atraso") if etapa == ETAPA_BOLETO else \
        "lembrete" if etapa < 0 else "vence_hoje" if etapa == 0 else "atraso"
    if etapa == ETAPA_BOLETO:                   # primeiro envio: o boleto do título (em dia ou já vencido)
        etapa = 1 if t["dias_atraso"] > 0 else -1
        if etapa < 0:
            assunto = f"Boleto dos honorários — vencimento {_data(t['vencimento'])}"
            abertura = (f"Segue a cobrança dos honorários de {_brl(t['valor_cent'])}, com vencimento em "
                        f"{_data(t['vencimento'])}.")
        else:
            assunto = f"Honorários em aberto — vencidos em {_data(t['vencimento'])}"
            abertura = (f"Consta em aberto o pagamento de {_brl(t['valor_cent'])}, vencido em {_data(t['vencimento'])}. "
                        f"Valor atualizado com multa e juros: {_brl(t['total_cent'])}.")
            if t.get("boleto_vencimento"):
                abertura += f" O boleto já está com esse valor e vence em {_data(t['boleto_vencimento'])}."
    elif etapa < 0:
        assunto = f"Lembrete: honorários vencem em {_data(t['vencimento'])}"
        abertura = f"Lembramos que o pagamento de {_brl(t['valor_cent'])} vence em {_data(t['vencimento'])}."
    elif etapa == 0:
        assunto = f"Vence hoje: {_brl(t['valor_cent'])}"
        abertura = f"O pagamento de {_brl(t['valor_cent'])} vence hoje ({_data(t['vencimento'])})."
    else:
        assunto = f"Pagamento em aberto há {t['dias_atraso']} dia(s)"
        abertura = (f"Não identificamos o pagamento de {_brl(t['valor_cent'])}, vencido em {_data(t['vencimento'])}. "
                    f"Valor atualizado com multa e juros: {_brl(t['total_cent'])}.")
    dados = _dados_modelo(t, cfg) | {"cliente": nome}
    assunto = textos.texto(cfg, chave, "assunto", dados, assunto)
    abertura = textos.texto(cfg, chave, "texto", dados, abertura)
    if etapa > 0 and t.get("boleto_vencimento") and t["boleto_vencimento"] >= (em or financeiro.hoje()).isoformat() \
            and "O boleto já está com esse valor" not in abertura:
        abertura += f" O boleto já está com esse valor e vence em {_data(t['boleto_vencimento'])}."
    cartao = None
    if t.get("cartao_link") and t.get("cartao_status") == "aberto":
        base = t["total_cent"] if etapa > 0 else t["valor_cent"]
        cartao = {"link": t["cartao_link"], "valor": t.get("cartao_total_cent") or 0,
                  "acrescimo": max(0, (t.get("cartao_total_cent") or 0) - base)}
    emp = cfg["empresa"]
    linha, pix_, boleto_pdf = t["linha_digitavel"], t["pix_copia_cola"], bool(t.get("banco_id"))
    if t.get("boleto_situacao"):                 # sem boleto (dispensado ou derrubado pelo banco): PIX do escritório
        linha, boleto_pdf = "", False
        try:
            pix_ = pix.payload(emp.get("pix_chave", ""), t["total_cent"] if t["dias_atraso"] > 0 else t["valor_cent"],
                               emp["nome"], emp.get("pix_cidade") or "ITABORAI", f"T{t['id']}")
        except ValueError:
            pix_ = ""
        motivo = "" if t["boleto_situacao"] == "dispensado" else " O boleto deste título expirou no banco;"
        abertura += (f"{motivo} Para pagar, use o PIX abaixo." if pix_ else
                     f"{motivo} Responda esta mensagem para combinarmos o pagamento.")
    return {"assunto": assunto, "nome": nome, "abertura": abertura, "atraso": etapa > 0,
            "referente": t["descricao"], "competencia": f"{t['competencia'][5:]}/{t['competencia'][:4]}",
            "vencimento": _data(t["vencimento"]), "valor": _brl(t["valor_cent"]),
            "total": _brl(t["total_cent"]) if etapa > 0 else "",
            "nfse": t["nfse_numero"], "nfse_link": t["nfse_link"] if str(t["nfse_link"]).startswith("http") else "",
            "boleto_link": t["cobranca_link"], "boleto_pdf": boleto_pdf,
            "linha": linha, "pix": pix_, "cartao": cartao,
            "assinatura": emp.get("assinatura") or emp["nome"], "whatsapp": emp.get("whatsapp", "")}


def _dados_modelo(t: dict, cfg: dict) -> dict:
    """Campos dos modelos editáveis (Mensagens › Modelos) para um título."""
    link = t.get("nfse_link") if str(t.get("nfse_link") or "").startswith("http") else ""
    return {"cliente": nome_cliente(t["cliente_nome"]), "valor": _brl(t["valor_cent"]),
            "vencimento": _data(t["vencimento"]), "atualizado": _brl(t.get("total_cent") or t["valor_cent"]),
            "dias": t.get("dias_atraso", 0), "competencia": f"{t['competencia'][5:]}/{t['competencia'][:4]}",
            "referente": t["descricao"], "nfse": t.get("nfse_numero") or "", "link_nota": link or "",
            "valor_pago": _brl(t.get("valor_pago_cent") or t["valor_cent"]),
            "data_pagamento": _data(t["data_pagamento"]) if t.get("data_pagamento") else "",
            "empresa": cfg["empresa"].get("nome", "")}


def _pdf_vai(c: dict, cfg: dict, canal: str = "email") -> bool:
    """O PDF do boleto vai junto da mensagem? (e-mail: anexo; WhatsApp automático: documento logo depois do texto)"""
    cob = cfg["cobranca"]
    if not c["boleto_pdf"]:
        return False
    if canal == "email":
        return bool(cob.get("anexar_boleto", True))
    return bool(cob.get("whatsapp_web") and cob.get("whatsapp_web_pdf", True))


def _pix_na_mensagem(c: dict, cfg: dict, canal: str = "email") -> bool:
    """O boleto do Inter já traz o QR Code do PIX: com o PDF junto, o copia e cola só vai se a opção estiver ligada.
    Sem o PDF (PIX avulso, link manual de WhatsApp) ele sempre vai — é a única forma de pagar pelo PIX."""
    if not c["pix"]:
        return False
    return bool(cfg["cobranca"].get("pix_nas_mensagens", False)) or not _pdf_vai(c, cfg, canal)


def mensagem(t: dict, etapa: int, cfg: dict | None = None, em: date | None = None,
             canal: str = "email") -> tuple[str, str]:
    """(assunto, texto) conforme a etapa da régua — texto simples (e-mail sem HTML e WhatsApp).
    No WhatsApp não há anexo: sai a linha digitável e o PIX, e o PDF fica no e-mail."""
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
    if _pdf_vai(c, cfg, canal):
        qr = " (pague pelo código de barras ou pelo QR Code do PIX impresso no boleto)" if c["pix"] else ""
        linhas.append(("Boleto em PDF: segue em anexo" if canal == "email" else "O boleto em PDF vai logo a seguir") + qr + ".")
    if c["linha"]:
        linhas.append(f"Linha digitável: {c['linha']}")
    if _pix_na_mensagem(c, cfg, canal):
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
             + ('<p style="margin:6px 0 0;font-size:13px;color:#667085">O boleto em PDF segue em anexo'
                + (" — pague pelo código de barras ou pelo <b>QR Code do PIX</b> impresso no boleto" if c["pix"] else "") + ".</p>"
                if _pdf_vai(c, cfg) else "")
             + (caixa("PIX copia e cola", c["pix"]) if _pix_na_mensagem(c, cfg) else ""))
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


def _para(cli: dict) -> str:
    """Destinatários do e-mail ao cliente: o principal e os adicionais, na mesma mensagem."""
    return ", ".join(clientes.emails(cli))


def _wa1(cli: dict) -> str:
    """WhatsApp principal do cliente (os adicionais recebem a mesma mensagem no envio da fila)."""
    return (clientes.whatsapps(cli) or [""])[0]


def link_whatsapp(telefone: str, texto: str) -> str:
    d = clientes._digitos(telefone)
    if d and not d.startswith("55"):
        d = "55" + d
    return f"https://wa.me/{d}?text={urllib.parse.quote(texto)}" if d else ""


def enviar_email(para: str, assunto: str, texto: str, cfg: dict | None = None, anexos: list[str] | None = None,
                 html: str = "", teste: bool = False, ref: dict | None = None) -> None:
    """Todo e-mail do sistema passa por aqui. Fora do horário comercial (fim de semana, noite) nada sai —
    exceto os testes que o próprio escritório dispara na tela (teste=True).
    Cada envio (ou falha do servidor) fica na aba Mensagens; ref = {tipo, titulo_id, cliente}."""
    cfg = cfg or config.carregar()
    if not teste and not horario.comercial(cfg=cfg):
        raise RuntimeError(horario.motivo(cfg=cfg))
    s = cfg["smtp"]
    if not s.get("host"):
        raise RuntimeError("SMTP não configurado.")
    msg = EmailMessage()
    usuario = str(s.get("usuario") or "").strip()
    remetente = str(s.get("remetente") or "").strip()
    # "FULANO" sozinho não é endereço: vira o nome de exibição do e-mail do usuário (FULANO <usuario@...>)
    msg["From"] = remetente if "@" in remetente else formataddr((remetente, usuario)) if remetente else usuario
    msg["To"] = para
    if s.get("copia_para"):
        msg["Bcc"] = s["copia_para"]
    msg["Subject"] = assunto
    msg.set_content(texto)
    if html:
        msg.add_alternative(html, subtype="html")
    import mimetypes
    for caminho in anexos or []:
        tipo = (mimetypes.guess_type(str(caminho))[0] or "application/octet-stream").split("/", 1)
        if Path(caminho).suffix.lower() == ".xml":
            tipo = ["application", "xml"]
        msg.add_attachment(Path(caminho).read_bytes(), maintype=tipo[0], subtype=tipo[1], filename=Path(caminho).name)
    ref = ref or {}
    reg = {"tipo": ref.get("tipo") or ("Teste" if teste else "E-mail"), "titulo_id": ref.get("titulo_id"),
           "cliente": ref.get("cliente", ""), "anexos": [str(a) for a in anexos or []]}
    try:
        _smtp_enviar(s, usuario, msg)
    except Exception as ex:
        mensagens.registrar("email", para, assunto, texto, "erro", str(ex)[:500], **reg)
        raise
    mensagens.registrar("email", para, assunto, texto, "enviado", **reg)


def _smtp_enviar(s: dict, usuario: str, msg: EmailMessage) -> None:
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
    """Etapas ANTES do vencimento e no dia (regua_dias <= 0). Os atrasados seguem o ciclo próprio (rodar_regua):
    1ª cobrança N dias após o vencimento sem pagamento e depois a cada X dias."""
    return sorted({int(e) for e in cob["regua_dias"] if int(e) <= 0})


def etapa_devida(dias: int, etapas: list[int], enviadas: set[int]) -> int | None:
    """Etapa mais recente já alcançada e ainda não enviada (tolerância de 2 dias, sem disparar etapas velhas)."""
    candidatas = [e for e in sorted(etapas) if e <= dias and dias - e <= 2 and e not in enviadas]
    return candidatas[-1] if candidatas else None


def etapa_atraso(dias: int) -> int:
    """Etapa de uma cobrança de atraso (= dias de atraso; acima de 999 desloca para não colidir com 1001/1002)."""
    return dias if dias < 1000 else 1_000_000 + dias


# eventos que contam como "cobrança de atraso" já mandada ao cliente (ciclo de 7 dias)
_SQL_ATRASO = (f"((e.etapa>0 AND e.etapa NOT IN ({ETAPA_PAGO},{ETAPA_NFSE})) OR e.etapa={ETAPA_SUSPENSAO}"
               f" OR (e.etapa={ETAPA_BOLETO} AND e.data>t.vencimento))")


def ultima_cobranca_atraso(cpf_cnpj: str, canal: str) -> date | None:
    """Data da última cobrança de valores em atraso mandada ao cliente no canal."""
    r = db.linhas("SELECT MAX(e.data) d FROM eventos_cobranca e JOIN titulos t ON t.id=e.titulo_id WHERE t.cpf_cnpj=?"
                  " AND e.canal=? AND e.status IN ('enviado','pendente','feito') AND " + _SQL_ATRASO, (cpf_cnpj, canal))
    return date.fromisoformat(r[0]["d"][:10]) if r and r[0]["d"] else None


def _registrar_whatsapp(t: dict, etapa: int, cli: dict, cfg: dict, em: date, res: dict, texto: str = "") -> None:
    """Evento de WhatsApp da régua: API oficial envia já; senão vai para a fila (WhatsApp Web ou envio manual)."""
    if not cli.get("whatsapp_cobranca"):
        return                                   # cliente não marcado para receber cobrança por WhatsApp
    if not clientes.whatsapps(cli):
        status, det = "sem_contato", "cliente sem telefone"
        res["sem_contato"] += 1
    elif whatsapp.configurado(cfg) and not texto:  # API oficial (modelos aprovados na Meta): envia sozinho
        try:
            for n in clientes.whatsapps(cli):     # o principal e os adicionais
                whatsapp.enviar_cobranca(t, etapa, n, cfg, em)
            status, det = "enviado", ", ".join(whatsapp.numero(n) for n in clientes.whatsapps(cli))
            res["whatsapp"] += 1
        except Exception as ex:  # noqa: BLE001 — registra a falha; o e-mail segue normalmente
            status, det = "erro", str(ex)[:300]
            res["erros"] += 1
    else:
        status, det = "pendente", link_whatsapp(_wa1(cli), texto or mensagem(t, etapa, cfg, em, "whatsapp")[1])
        res["whatsapp"] += 1
    with db.conexao() as con:
        con.execute("INSERT OR IGNORE INTO eventos_cobranca (titulo_id, etapa, canal, data, status, detalhe)"
                    " VALUES (?,?,?,?,?,?)", (t["id"], etapa, "whatsapp", em.isoformat(), status, det))


def mensagem_suspensao(titulos: list[dict], cfg: dict, em: date) -> tuple[str, str]:
    """Aviso de suspensão dos serviços: todos os títulos em atraso do cliente, total atualizado e prazo."""
    cob = cfg["cobranca"]
    ts = sorted((financeiro.enriquecer(t, em) for t in titulos), key=lambda t: t["vencimento"])
    total = sum(t["total_cent"] for t in ts)
    dados = {"cliente": nome_cliente(ts[0]["cliente_nome"]), "dias": max(t["dias_atraso"] for t in ts), "qtd": len(ts),
             "total": _brl(total), "empresa": cfg["empresa"].get("nome", ""),
             "data_suspensao": _data((em + timedelta(days=int(cob.get("suspensao_prazo_dias") or 10))).isoformat())}
    emp = cfg["empresa"]
    linhas = [f"Olá, {dados['cliente']}!", "", textos.texto(cfg, "suspensao", "texto", dados), ""]
    for i, t in enumerate(ts, 1):
        linhas.append(f"{i}) {t['descricao']} — competência {t['competencia'][5:]}/{t['competencia'][:4]} · vencimento "
                      f"{_data(t['vencimento'])} · {t['dias_atraso']} dia(s) em atraso · atualizado {_brl(t['total_cent'])}")
    linhas += ["", f"Total atualizado: {_brl(total)}", "",
               "Se já pagou, por favor desconsidere este aviso e nos envie o comprovante.", "",
               "Atenciosamente,", emp.get("assinatura") or emp["nome"]]
    if emp.get("whatsapp"):
        linhas.append(f"WhatsApp: {emp['whatsapp']}")
    return textos.texto(cfg, "suspensao", "assunto", dados), "\n".join(linhas)


def _avisos_suspensao(abertos: list[dict], em: date, cfg: dict, res: dict) -> None:
    """Débito com N dias (padrão 90) de atraso: aviso de suspensão dos serviços, uma vez por título que chega lá
    (no máximo um aviso a cada 30 dias por cliente). Conta como a cobrança de atraso da semana."""
    cob = cfg["cobranca"]
    if not cob.get("suspensao_ativa", True):
        return
    limite = int(cob.get("suspensao_dias") or 90)
    por_cli: dict[str, list[dict]] = {}
    for t in abertos:
        if (em - date.fromisoformat(t["vencimento"])).days > 0:
            por_cli.setdefault(t["cpf_cnpj"], []).append(t)
    for cpf, ts in por_cli.items():
        velhos = [t for t in ts if (em - date.fromisoformat(t["vencimento"])).days >= limite]
        if not velhos:
            continue
        cli = clientes.obter(cpf) or {}
        assunto, texto = mensagem_suspensao(ts, cfg, em)
        for canal, ligado in (("email", cob["regua_email"]), ("whatsapp", cob["regua_whatsapp"])):
            if not ligado:
                continue
            avisados = {r["titulo_id"] for r in db.linhas(
                "SELECT titulo_id FROM eventos_cobranca WHERE etapa=? AND canal=? AND titulo_id IN (%s)"
                % ",".join("?" * len(velhos)), (ETAPA_SUSPENSAO, canal, *[t["id"] for t in velhos]))}
            recente = db.linhas("SELECT MAX(e.data) d FROM eventos_cobranca e JOIN titulos t ON t.id=e.titulo_id "
                                "WHERE t.cpf_cnpj=? AND e.canal=? AND e.etapa=?", (cpf, canal, ETAPA_SUSPENSAO))[0]["d"]
            if all(t["id"] in avisados for t in velhos) or (recente and (em - date.fromisoformat(recente)).days < 30):
                continue
            if canal == "email":
                if not clientes.emails(cli):
                    status, det = "sem_contato", "cliente sem e-mail"
                    res["sem_contato"] += 1
                else:
                    try:
                        enviar_email(_para(cli), assunto, texto, cfg,
                                     ref={"tipo": "Aviso de suspensão", "titulo_id": velhos[0]["id"],
                                          "cliente": velhos[0]["cliente_nome"]})
                        status, det = "enviado", _para(cli)
                        res["email"] += 1
                    except Exception as ex:  # noqa: BLE001
                        status, det = "erro", str(ex)[:300]
                        res["erros"] += 1
                with db.conexao() as con:
                    for t in velhos:
                        con.execute("INSERT OR IGNORE INTO eventos_cobranca (titulo_id, etapa, canal, data, status, detalhe)"
                                    " VALUES (?,?,?,?,?,?)", (t["id"], ETAPA_SUSPENSAO, canal, em.isoformat(), status, det))
            else:
                _registrar_whatsapp(velhos[0], ETAPA_SUSPENSAO, cli, cfg, em, res, texto)
                with db.conexao() as con:          # os demais títulos ficam marcados como avisados
                    for t in velhos[1:]:
                        con.execute("INSERT OR IGNORE INTO eventos_cobranca (titulo_id, etapa, canal, data, status, detalhe)"
                                    " VALUES (?,?,?,?,?,?)", (t["id"], ETAPA_SUSPENSAO, canal, em.isoformat(), "feito",
                                                              "aviso de suspensão junto com o título " + str(velhos[0]["id"])))


def previa_suspensao(em: date | None = None, cfg: dict | None = None) -> list[dict]:
    """Clientes que hoje têm débito com N dias (padrão 90) ou mais — quem receberia o aviso de suspensão."""
    em = em or financeiro.hoje()
    limite = int((cfg or config.carregar())["cobranca"].get("suspensao_dias") or 90)
    r = db.linhas("SELECT cliente_nome, cpf_cnpj, COUNT(*) n, MIN(vencimento) v FROM titulos WHERE status='aberto' AND "
                  + financeiro.SQL_COBRADO + " AND nfse_status IN ('emitida','nao_emitir','apos_pagamento') AND vencimento<=?"
                  " GROUP BY cpf_cnpj ORDER BY v", ((em - timedelta(days=limite)).isoformat(),))
    return [{"cliente": x["cliente_nome"], "titulos": x["n"], "dias": (em - date.fromisoformat(x["v"])).days} for x in r]


def rodar_regua(em: date | None = None, cfg: dict | None = None) -> dict:
    em = em or financeiro.hoje()
    cfg = cfg or config.carregar()
    cob = cfg["cobranca"]
    res = {"email": 0, "whatsapp": 0, "sem_contato": 0, "erros": 0}
    if not horario.comercial(cfg=cfg):
        return res | {"fora_do_horario": horario.motivo(cfg=cfg)}
    # Só cobra títulos com NFS-e válida, sem nota ou com nota após o pagamento: nunca dispara por nota de teste.
    # Títulos lançados sem cobrança (cobrar=0) ficam fora da régua.
    abertos = db.linhas("SELECT * FROM titulos WHERE status='aberto' AND " + financeiro.SQL_COBRADO +
                        " AND nfse_status IN ('emitida','nao_emitir','apos_pagamento')")
    _avisos_suspensao(abertos, em, cfg, res)
    por_cliente: dict[str, tuple[dict, list]] = {}
    # Atrasados: por cliente e canal, a 1ª cobrança sai N dias (padrão 3) após o vencimento sem pagamento e as
    # seguintes a cada X dias (padrão 7) contados da última cobrança de atraso — cada mensagem já cobra todos os
    # títulos em atraso dele. Boleto, lembrete e "vence hoje" (antes do vencimento) não entram nessa conta.
    inicio, cada = int(cob.get("recorrente_apos_dias") or 3), max(1, int(cob.get("recorrente_a_cada_dias") or 7))
    ultimas: dict[tuple[str, str], date | None] = {}       # foto do início da rodada (não muda com os envios dela)
    for t in abertos:
        dias = (em - date.fromisoformat(t["vencimento"])).days
        cli = clientes.obter(t["cpf_cnpj"]) or {}
        for canal, ligado in (("email", cob["regua_email"]), ("whatsapp", cob["regua_whatsapp"])):
            if not ligado:
                continue
            enviadas = {e["etapa"] for e in db.linhas(
                "SELECT etapa FROM eventos_cobranca WHERE titulo_id=? AND canal=?", (t["id"], canal))}
            if dias <= 0:
                etapa = etapa_devida(dias, etapas_da_regua(dias, cob), enviadas)
                if etapa is None and not enviadas and cob.get("enviar_ao_gerar", True):
                    etapa = ETAPA_BOLETO             # cobrança gerada e ainda sem nenhuma mensagem: manda o boleto já
            else:
                etapa = None
                if cob.get("recorrente_ativa", True) and dias >= inicio and etapa_atraso(dias) not in enviadas:
                    chave = (t["cpf_cnpj"], canal)
                    if chave not in ultimas:
                        ultimas[chave] = ultima_cobranca_atraso(*chave)
                    if ultimas[chave] is None or (em - ultimas[chave]).days >= cada:
                        etapa = etapa_atraso(dias)
            if etapa is None:
                continue
            if (etapa > 0 or (etapa == ETAPA_BOLETO and dias > 0)) and canal == "email":
                t = _atualizar_cartao(t, cfg, em)
            if canal == "email":                     # junta os títulos do mesmo cliente num único e-mail
                por_cliente.setdefault(t["cpf_cnpj"], (cli, []))[1].append((t, etapa))
                continue
            _registrar_whatsapp(t, etapa, cli, cfg, em, res)
    for cli, itens in por_cliente.values():
        _email_cobranca(cli, itens, em, cfg, res)
    _pos_pagamento(em, cfg, res)
    if any(res.values()):
        db.registrar("regua", f"Régua: {res}")
    return res


def titulos_em_cobranca(cpf_cnpj: str) -> list[dict]:
    """Todos os títulos em aberto e em cobrança do cliente, do mais antigo para o mais novo."""
    return db.linhas("SELECT * FROM titulos WHERE status='aberto' AND cpf_cnpj=? AND " + financeiro.SQL_COBRADO +
                     " ORDER BY vencimento, id", (cpf_cnpj,))


def todos_do_cliente(cpf_cnpj: str, itens: list[tuple[dict, int]]) -> list[tuple[dict, int]]:
    """A mensagem ao cliente sempre cobra TUDO que ele tem em aberto (não só o título cuja etapa venceu hoje):
    os títulos da vez entram com a etapa deles; os demais, como 'boleto' (em dia ou vencido, conforme a data).
    Mensagem só de títulos ainda no prazo (boleto, lembrete, vence hoje) não cobra os atrasados: esses têm o ciclo
    próprio (3 dias após o vencimento e depois a cada 7 dias)."""
    etapas = {t["id"]: etapa for t, etapa in itens}
    hoje = financeiro.hoje().isoformat()
    so_no_prazo = all(t["vencimento"] >= hoje for t, _ in itens)
    return [(t, etapas.get(t["id"], ETAPA_BOLETO)) for t in titulos_em_cobranca(cpf_cnpj)
            if t["id"] in etapas or not so_no_prazo or t["vencimento"] >= hoje] or itens


def _email_cobranca(cli: dict, itens: list[tuple[dict, int]], em: date, cfg: dict, res: dict) -> None:
    """Um e-mail por cliente com TODOS os títulos em aberto dele (soma e valor atualizado) e todos os boletos
    anexados; um título só usa a mensagem da etapa."""
    if not clientes.emails(cli):
        status, det = "sem_contato", "cliente sem e-mail"
        res["sem_contato"] += 1
    else:
        try:
            todos = todos_do_cliente(itens[0][0]["cpf_cnpj"], itens)
            pdfs = [p for p in (_pdf_boleto(t, cfg) for t, _ in todos) if p]
            if len(todos) == 1:
                t, etapa = todos[0]
                assunto, texto = mensagem(t, etapa, cfg, em)
                html = mensagem_html(t, etapa, cfg, em)
            else:
                assunto, texto = mensagem_grupo(todos, cfg, em)
                html = mensagem_grupo_html(todos, cfg, em)
            enviar_email(_para(cli), assunto, texto, cfg, pdfs, html=html,
                         ref={"tipo": mensagens.tipo_da_etapa(itens[0][1]), "titulo_id": itens[0][0]["id"],
                              "cliente": itens[0][0]["cliente_nome"]})
            status, det = "enviado", _para(cli) + (f" (e-mail com {len(todos)} títulos)" if len(todos) > 1 else "")
            res["email"] += 1
        except Exception as ex:  # noqa: BLE001 — registra qualquer falha de envio
            status, det = "erro", str(ex)[:300]
            res["erros"] += 1
    with db.conexao() as con:
        for t, etapa in itens:
            con.execute("INSERT OR IGNORE INTO eventos_cobranca (titulo_id, etapa, canal, data, status, detalhe)"
                        " VALUES (?,?,?,?,?,?)", (t["id"], etapa, "email", em.isoformat(), status, det))


def _grupo(itens: list[tuple[dict, int]], cfg: dict, em: date | None, canal: str = "email") -> tuple[list[dict], dict]:
    cs = sorted((_conteudo(t, etapa, cfg, em) | {"_t": financeiro.enriquecer(t, em)} for t, etapa in itens),
                key=lambda c: c["_t"]["vencimento"])
    atraso = any(c["atraso"] for c in cs)
    total = sum(c["_t"]["total_cent"] if c["atraso"] else c["_t"]["valor_cent"] for c in cs)
    n = len(cs)
    if atraso:
        assunto = f"Honorários em aberto — {n} títulos (total atualizado {_brl(total)})"
        abertura = (f"Constam em aberto {n} títulos de honorários em seu nome, no total de {_brl(total)} "
                    "(vencidos com multa e juros até hoje). Seguem os dados de cada um para pagamento.")
    else:
        assunto = f"Boletos dos honorários — {n} títulos (total {_brl(total)})"
        abertura = f"Seguem os {n} títulos de honorários em seu nome, no total de {_brl(total)}."
    chave = "grupo_atraso" if atraso else "grupo"
    dados = {"cliente": cs[0]["nome"], "qtd": n, "total": _brl(total), "empresa": cfg["empresa"].get("nome", "")}
    assunto = textos.texto(cfg, chave, "assunto", dados, assunto)
    abertura = textos.texto(cfg, chave, "texto", dados, abertura)
    return cs, {"assunto": assunto, "abertura": abertura, "atraso": atraso, "total": _brl(total),
                "nome": cs[0]["nome"], "assinatura": cs[0]["assinatura"], "whatsapp": cs[0]["whatsapp"],
                "pdf": any(_pdf_vai(c, cfg, canal) for c in cs)}


def mensagem_grupo(itens: list[tuple[dict, int]], cfg: dict | None = None, em: date | None = None,
                   canal: str = "email") -> tuple[str, str]:
    """(assunto, texto) de uma mensagem com vários títulos do mesmo cliente (e-mail ou WhatsApp)."""
    cfg = cfg or config.carregar()
    cs, g = _grupo(itens, cfg, em, canal)
    linhas = [f"Olá, {g['nome']}!", "", g["abertura"]]
    if g["atraso"]:
        linhas.append("Se já pagou, por favor desconsidere e nos envie o comprovante.")
    for i, c in enumerate(cs, 1):
        linhas += ["", f"{i}) {c['referente']} — competência {c['competencia']}",
                   f"   Vencimento {c['vencimento']} · valor {c['valor']}"
                   + (f" · atualizado {c['total']} ({c['_t']['dias_atraso']} dia(s) em atraso)" if c["atraso"] else "")]
        if c["nfse"]:
            linhas.append(f"   NFS-e nº {c['nfse']}" + (f": {c['nfse_link']}" if c["nfse_link"] else ""))
        if c["boleto_link"]:
            linhas.append(f"   Boleto/PIX: {c['boleto_link']}")
        if c["linha"]:
            linhas.append(f"   Linha digitável: {c['linha']}")
        if _pix_na_mensagem(c, cfg, canal):
            linhas.append(f"   PIX copia e cola: {c['pix']}")
        if c["cartao"]:
            linhas.append(f"   Cartão de crédito ({_brl(c['cartao']['valor'])}, taxa por conta de quem paga com cartão): "
                          f"{c['cartao']['link']}")
    linhas += ["", f"Total: {g['total']}"]
    if g["pdf"]:
        linhas.append(("Os boletos em PDF seguem em anexo" if canal == "email" else "Os boletos em PDF vão logo a seguir")
                      + " (pague pelo código de barras ou pelo QR Code do PIX impresso em cada boleto).")
    linhas += ["", "Atenciosamente,", g["assinatura"]]
    if g["whatsapp"]:
        linhas.append(f"WhatsApp: {g['whatsapp']}")
    return g["assunto"], "\n".join(linhas)


def mensagem_grupo_html(itens: list[tuple[dict, int]], cfg: dict | None = None, em: date | None = None) -> str:
    """Versão formatada do e-mail com vários títulos (mesmo visual do e-mail de um título)."""
    from html import escape as e
    cfg = cfg or config.carregar()
    cs, g = _grupo(itens, cfg, em)
    cor = "#b42318" if g["atraso"] else "#1f4fbf"
    selo = "EM ATRASO" if g["atraso"] else "COBRANÇA"
    td = 'style="padding:8px 6px;border-bottom:1px solid #e3e7ee;font-size:14px;color:#101828;vertical-align:top"'
    th = 'style="padding:6px;border-bottom:2px solid #e3e7ee;font-size:12px;color:#667085;text-align:left"'
    linhas = "".join(
        f'<tr><td {td}>{e(c["referente"])}<br><span style="color:#667085;font-size:12px">competência {c["competencia"]}'
        + (f' · NFS-e nº {e(c["nfse"])}' if c["nfse"] else "") + f'</span></td><td {td}>{c["vencimento"]}'
        + (f'<br><span style="color:#b42318;font-size:12px">{c["_t"]["dias_atraso"]} dia(s) em atraso</span>' if c["atraso"] else "")
        + f'</td><td {td} align="right"><b>{c["total"] if c["atraso"] else c["valor"]}</b>'
        + (f'<br><span style="color:#667085;font-size:12px">original {c["valor"]}</span>' if c["atraso"] else "")
        + "</td></tr>" for c in cs)
    tabela = (f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin:0 0 8px">'
              f'<tr><th {th}>Referente a</th><th {th}>Vencimento</th><th {th} align="right">Valor</th></tr>{linhas}'
              f'<tr><td colspan="2" style="padding:10px 6px;font-size:14px;font-weight:700">Total</td>'
              f'<td align="right" style="padding:10px 6px;font-size:15px;font-weight:700">{g["total"]}</td></tr></table>')
    caixa = lambda titulo, conteudo: (  # noqa: E731
        f'<p style="margin:10px 0 4px;font-size:12px;color:#667085;font-weight:700">{titulo}</p>'
        f'<div style="background:#f4f6f9;border:1px solid #e3e7ee;border-radius:8px;padding:10px;font-family:Consolas,Menlo,monospace;'
        f'font-size:12px;color:#101828;word-break:break-all">{e(conteudo)}</div>')
    pagar = ""
    for i, c in enumerate(cs, 1):
        bloco = ((f'<a href="{e(c["boleto_link"])}" style="color:#1f4fbf;font-weight:700">Pagar boleto / PIX</a> ' if c["boleto_link"] else "")
                 + (f'· <a href="{e(c["cartao"]["link"])}" style="color:#1f4fbf">cartão de crédito ({_brl(c["cartao"]["valor"])}, taxa por conta de quem paga com cartão)</a>' if c["cartao"] else "")
                 + (caixa("Linha digitável", c["linha"]) if c["linha"] else "") + (caixa("PIX copia e cola", c["pix"]) if _pix_na_mensagem(c, cfg) else ""))
        if bloco:
            pagar += (f'<div style="margin:16px 0 0;padding-top:12px;border-top:1px dashed #e3e7ee">'
                      f'<p style="margin:0 0 6px;font-size:14px;color:#101828"><b>{i}) {e(c["referente"])}</b> — '
                      f'vencimento {c["vencimento"]}</p>{bloco}</div>')
    corpo = (f'<p style="margin:0 0 4px;font-size:16px;color:#101828">Olá, <b>{e(g["nome"])}</b>!</p>'
             f'<p style="margin:8px 0 16px;font-size:15px;line-height:1.5;color:#344054">{e(g["abertura"])}'
             + (" Se já pagou, por favor desconsidere e nos envie o comprovante." if g["atraso"] else "") + "</p>"
             + tabela + ('<p style="margin:6px 0 0;font-size:13px;color:#667085">Os boletos em PDF seguem em anexo.</p>' if g["pdf"] else "")
             + pagar)
    rodape = e(g["assinatura"]) + (f' · WhatsApp {e(g["whatsapp"])}' if g["whatsapp"] else "")
    return (f'<!doctype html><html lang="pt-br"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
            f'<title>{e(g["assunto"])}</title></head><body style="margin:0;padding:0;background:#f4f6f9">'
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


# ---------------------------------------------------------------- depois do pagamento: agradecimento e nota fiscal

def _saldo_parcial(t: dict) -> list[str]:
    """Linhas do agradecimento quando o pagamento foi parcial (saldo em novo boleto ou desconto concedido)."""
    if t.get("parcial_status") == "cobrar" and t.get("saldo_titulo_id"):
        s = financeiro.obter_titulo(t["saldo_titulo_id"])
        return [f"Ficou um saldo de {_brl(s['valor_cent'])}, que será cobrado em boleto à parte, com vencimento em "
                f"{_data(s['vencimento'])}.", ""]
    if t.get("parcial_status") == "desconto":
        return [f"A diferença de {_brl(t['parcial_dif_cent'])} foi concedida como desconto.", ""]
    return []


def mensagem_pagamento(t: dict, cfg: dict) -> tuple[str, str]:
    emp = cfg["empresa"]
    ref = f"{t['descricao']} — competência {t['competencia'][5:]}/{t['competencia'][:4]}"
    dados = _dados_modelo(t, cfg)
    if textos.personalizado(cfg, "agradecimento", "texto") or textos.personalizado(cfg, "agradecimento", "assunto"):
        corpo = textos.texto(cfg, "agradecimento", "texto", dados)
        texto = "\n".join([f"Olá, {dados['cliente']}!", "", corpo, "", *_saldo_parcial(t),
                            "Atenciosamente,", emp.get("assinatura") or emp["nome"]])
        return textos.texto(cfg, "agradecimento", "assunto", dados), texto
    texto = "\n".join([f"Olá, {nome_cliente(t['cliente_nome'])}!", "",
                        f"Recebemos o seu pagamento de {_brl(t['valor_pago_cent'] or t['valor_cent'])} em "
                        f"{_data(t['data_pagamento'])}, referente a: {ref}.", "",
                        *_saldo_parcial(t),
                        "Muito obrigado pela confiança e pela pontualidade!" if (t["data_pagamento"] or "") <= t["vencimento"]
                        and not t.get("parcial_status") else "Muito obrigado!",
                        "", "Atenciosamente,", emp.get("assinatura") or emp["nome"]])
    return f"Pagamento recebido — obrigado! ({_brl(t['valor_pago_cent'] or t['valor_cent'])})", texto


def mensagem_nfse(t: dict, cfg: dict) -> tuple[str, str]:
    emp = cfg["empresa"]
    link = t["nfse_link"] if str(t.get("nfse_link") or "").startswith("http") else ""
    if textos.personalizado(cfg, "nota_fiscal", "texto") or textos.personalizado(cfg, "nota_fiscal", "assunto"):
        dados = _dados_modelo(t, cfg)
        corpo = textos.texto(cfg, "nota_fiscal", "texto", dados)
        texto = "\n".join([f"Olá, {dados['cliente']}!", "", corpo,
                            *([f"Consulta da nota: {link}"] if link and link not in corpo else []),
                            "", "Atenciosamente,", emp.get("assinatura") or emp["nome"]])
        return textos.texto(cfg, "nota_fiscal", "assunto", dados), texto
    texto = "\n".join([f"Olá, {nome_cliente(t['cliente_nome'])}!", "",
                        (f"Segue a nota fiscal de serviço (NFS-e nº {t['nfse_numero']}) referente ao pagamento de "
                         f"{_brl(t['valor_pago_cent'] or t['valor_cent'])} — competência {t['competencia'][5:]}/{t['competencia'][:4]}."
                         if t.get("status") == "pago" else
                         f"Segue a nota fiscal de serviço (NFS-e nº {t['nfse_numero']}) no valor de {_brl(t['valor_cent'])} "
                         f"— competência {t['competencia'][5:]}/{t['competencia'][:4]}."),
                        *([f"Consulta da nota: {link}"] if link else []),
                        "", "Atenciosamente,", emp.get("assinatura") or emp["nome"]])
    return f"Nota fiscal de serviço nº {t['nfse_numero']}", texto


def xml_nfse(t: dict) -> str:
    """XML da NFS-e emitida (salvo em saida/AAAA-MM/...) para anexar ao e-mail; '' se não achar."""
    num = str(t.get("nfse_numero") or "").strip()
    if not num:
        return ""
    for nome in (f"NFSe_{num}.xml", f"NFSe_{t.get('nfse_chave') or '-'}.xml"):
        achados = sorted((emissor.RAIZ / "saida").rglob(nome)) if (emissor.RAIZ / "saida").exists() else []
        if achados:
            return str(achados[-1])
    return ""


def pdf_nfse(t: dict) -> str:
    """PDF da NFS-e para anexar: a página oficial da nota (link da prefeitura/Sefin) impressa pelo Edge/Chrome do
    computador, guardada ao lado do XML. Só vale se a página mostrar o número da nota; senão, '' (vai o link)."""
    num = str(t.get("nfse_numero") or "").strip()
    link = str(t.get("nfse_link") or "")
    if not num or not link.startswith("http"):
        return ""
    xml = xml_nfse(t)
    destino = (Path(xml).parent if xml else emissor.RAIZ / "saida" / "notas_pdf") / f"NFSe_{num}.pdf"
    if destino.exists() and destino.stat().st_size > 1000:
        return str(destino)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return ""
    try:
        with sync_playwright() as p:
            nav = None
            for kw in ({"channel": "msedge"}, {"channel": "chrome"}, {}):
                try:
                    nav = p.chromium.launch(headless=True, **kw)
                    break
                except Exception:  # noqa: BLE001 — tenta o próximo navegador
                    continue
            if nav is None:
                return ""
            try:
                pg = nav.new_page()
                pg.goto(link, timeout=40000, wait_until="networkidle")
                if num.lstrip("0") not in pg.content():
                    return ""                        # página sem a nota (formulário, erro): manda só o link
                destino.parent.mkdir(parents=True, exist_ok=True)
                pg.pdf(path=str(destino), format="A4", print_background=True)
            finally:
                nav.close()
    except Exception:  # noqa: BLE001 — sem PDF a mensagem leva o link da nota e o XML
        return ""
    return str(destino) if destino.exists() else ""


def anexos_nfse(t: dict) -> list[str]:
    return [a for a in (pdf_nfse(t), xml_nfse(t)) if a]


def enviar_nfse_titulo(tid: int, cfg: dict | None = None) -> dict:
    """Botão 'Enviar nota ao cliente': (re)envia a NFS-e do título por e-mail agora e põe na fila do WhatsApp."""
    cfg = cfg or config.carregar()
    t = financeiro.obter_titulo(tid)
    if not t or t.get("nfse_status") != "emitida" or not t.get("nfse_numero"):
        raise ValueError("Este título não tem NFS-e emitida em produção.")
    if not horario.comercial(cfg=cfg):
        raise ValueError(horario.motivo(cfg=cfg).replace("O robô envia", "Envie"))
    cli = clientes.obter(t["cpf_cnpj"]) or {}
    assunto, texto = mensagem_nfse(t, cfg)
    out = {"email": "", "whatsapp": ""}
    with db.conexao() as con:
        con.execute("DELETE FROM eventos_cobranca WHERE titulo_id=? AND etapa=?", (tid, ETAPA_NFSE))
    if clientes.emails(cli) and cfg["smtp"].get("host"):
        enviar_email(_para(cli), assunto, texto, cfg, anexos_nfse(t),
                     ref={"tipo": "Nota fiscal", "titulo_id": tid, "cliente": t["cliente_nome"]})
        out["email"] = _para(cli)
        _evento(tid, ETAPA_NFSE, "email", "enviado", _para(cli))
    if clientes.whatsapps(cli) and cli.get("whatsapp_cobranca"):
        _evento(tid, ETAPA_NFSE, "whatsapp", "pendente", link_whatsapp(_wa1(cli), texto))
        out["whatsapp"] = "na fila do WhatsApp"
    if not out["email"] and not out["whatsapp"]:
        raise ValueError("Cliente sem e-mail e sem WhatsApp marcado para cobrança: complete o cadastro em Clientes.")
    db.registrar("nfse_envio", f"NFS-e {t['nfse_numero']} enviada a {t['cliente_nome']} (manual)")
    return out


def _evento(tid: int, etapa: int, canal: str, status: str, det: str) -> None:
    with db.conexao() as con:
        con.execute("INSERT OR IGNORE INTO eventos_cobranca (titulo_id, etapa, canal, data, status, detalhe)"
                    " VALUES (?,?,?,?,?,?)", (tid, etapa, canal, financeiro.hoje().isoformat(), status, det))


def _pos_pagamento(em: date, cfg: dict, res: dict) -> None:
    """Pagamento reconhecido (baixa manual, banco, extrato ou cartão): agradece e, com a NFS-e emitida, envia a nota.
    Só para pagamentos a partir do dia em que o recurso foi ligado (não reenvia nada do histórico)."""
    cob = cfg["cobranca"]
    envia_nota = cob.get("enviar_nfse_paga", True)
    if not cob.get("agradecer_pagamento", True) and not envia_nota:
        return
    desde = cob.get("agradecer_desde")
    if not desde:
        desde = em.isoformat()
        config.salvar({"cobranca": {"agradecer_desde": desde}})
    desde_nota = cob.get("nfse_envio_desde")
    if not desde_nota:                    # notas emitidas a partir de hoje (nada do histórico é reenviado em massa)
        desde_nota = em.isoformat()
        config.salvar({"cobranca": {"nfse_envio_desde": desde_nota}})
    pagos = db.linhas("SELECT * FROM titulos WHERE status='pago' AND cobrar=1 AND data_pagamento>=?"
                      " AND COALESCE(parcial_status,'')!='pendente'", (desde,))    # parcial: espera a decisão
    vistos = {t["id"] for t in pagos}
    # NFS-e emitida e ainda não enviada: com ou sem cobrança, paga ou ainda em aberto (regra "emitir na geração")
    so_nota = [] if not envia_nota else [t for t in db.linhas(
        "SELECT * FROM titulos WHERE nfse_status='emitida' AND status IN ('aberto','pago') AND COALESCE(nfse_data,'')>=? "
        "AND COALESCE(juridico_em,'')='' AND COALESCE(parcial_status,'')!='pendente'", (desde_nota,)) if t["id"] not in vistos]
    for t in pagos + so_nota:
        cli = clientes.obter(t["cpf_cnpj"]) or {}
        for canal, ligado in (("email", cob["regua_email"]), ("whatsapp", cob["regua_whatsapp"])):
            if not ligado:
                continue
            if canal == "email" and not clientes.emails(cli):
                continue
            if canal == "whatsapp" and not (cli.get("whatsapp_cobranca") and clientes.whatsapps(cli)):
                continue
            feitas = {e["etapa"] for e in db.linhas("SELECT etapa FROM eventos_cobranca WHERE titulo_id=? AND canal=?",
                                                     (t["id"], canal))}
            fila = []
            pago_cobrado = t["status"] == "pago" and t["cobrar"] == 1 and t["id"] in vistos
            if pago_cobrado and cob.get("agradecer_pagamento", True) and ETAPA_PAGO not in feitas:
                fila.append((ETAPA_PAGO, *mensagem_pagamento(t, cfg), []))
            if envia_nota and ETAPA_NFSE not in feitas and t["nfse_status"] == "emitida" \
                    and (not pago_cobrado or ETAPA_PAGO in feitas or fila or not cob.get("agradecer_pagamento", True)):
                fila.append((ETAPA_NFSE, *mensagem_nfse(t, cfg), anexos_nfse(t) if canal == "email" else []))
            for etapa, assunto, texto, anexos in fila:   # primeiro o agradecimento, depois a nota
                if canal == "email":
                    try:
                        enviar_email(_para(cli), assunto, texto, cfg, anexos,
                                     ref={"tipo": mensagens.tipo_da_etapa(etapa), "titulo_id": t["id"],
                                          "cliente": t["cliente_nome"]})
                        status, det = "enviado", _para(cli)
                        res["email"] += 1
                    except Exception as ex:  # noqa: BLE001
                        status, det = "erro", str(ex)[:300]
                        res["erros"] += 1
                else:
                    status, det = "pendente", link_whatsapp(_wa1(cli), texto)   # sai pela fila do WhatsApp
                    res["whatsapp"] += 1
                with db.conexao() as con:
                    con.execute("INSERT OR IGNORE INTO eventos_cobranca (titulo_id, etapa, canal, data, status, detalhe)"
                                " VALUES (?,?,?,?,?,?)", (t["id"], etapa, canal, em.isoformat(), status, det))


def enviar_pos_pagamento(em: date | None = None, cfg: dict | None = None) -> dict:
    """Agradecimento e NFS-e logo depois do pagamento/emissão (rotina rápida), sem esperar a régua da hora cheia."""
    em = em or financeiro.hoje()
    cfg = cfg or config.carregar()
    res = {"email": 0, "whatsapp": 0, "erros": 0}
    if not horario.comercial(cfg=cfg):
        return res | {"fora_do_horario": horario.motivo(cfg=cfg)}
    _pos_pagamento(em, cfg, res)
    return res


def fila_whatsapp() -> list[dict]:
    lst = db.linhas("SELECT e.*, t.cliente_nome, t.valor_cent, t.vencimento FROM eventos_cobranca e "
                    "JOIN titulos t ON t.id=e.titulo_id WHERE e.canal='whatsapp' AND e.status='pendente' "
                    f"AND COALESCE(t.juridico_em,'')='' AND (t.status='aberto' OR e.etapa IN ({ETAPA_PAGO},{ETAPA_NFSE})) ORDER BY e.data, e.etapa")
    return lst


def marcar_whatsapp_feito(evento_id: int) -> None:
    with db.conexao() as con:
        con.execute("UPDATE eventos_cobranca SET status='feito' WHERE id=?", (evento_id,))


def historico(tid: int) -> list[dict]:
    return db.linhas("SELECT * FROM eventos_cobranca WHERE titulo_id=? ORDER BY data, etapa", (tid,))


def cobrar_agora(tid: int, cfg: dict | None = None) -> dict:
    """Envio manual imediato (botão 'Cobrar'): e-mail + link de WhatsApp."""
    cfg = cfg or config.carregar()
    if not horario.comercial(cfg=cfg):
        raise ValueError(horario.motivo(cfg=cfg).replace("O robô envia", "A régua cobra sozinha"))
    if financeiro.no_juridico(financeiro.obter_titulo(tid) or {}):
        raise ValueError("Este título está no jurídico: a cobrança por e-mail e WhatsApp está suspensa. "
                         "Para voltar a cobrar, use 'Voltar do jurídico' na aba Jurídico.")
    t = preparar_pagamento(tid, cfg)
    dias = (financeiro.hoje() - date.fromisoformat(t["vencimento"])).days
    etapa = max(dias, -1) if dias < 0 else dias
    if etapa > 0:
        t = _atualizar_cartao(t, cfg)
    assunto, texto = mensagem(t, etapa, cfg)
    cli = clientes.obter(t["cpf_cnpj"]) or {}
    out = {"whatsapp": link_whatsapp(_wa1(cli), mensagem(t, etapa, cfg, canal="whatsapp")[1]), "email": "",
           "texto": texto, "whatsapp_enviado": "", "whatsapp_erro": ""}
    if clientes.whatsapps(cli) and cli.get("whatsapp_cobranca") and whatsapp.configurado(cfg):
        try:
            for n in clientes.whatsapps(cli):
                whatsapp.enviar_cobranca(t, etapa, n, cfg)
            out["whatsapp_enviado"] = ", ".join(whatsapp.numero(n) for n in clientes.whatsapps(cli))
        except Exception as ex:  # noqa: BLE001 — mostra o motivo na tela; o link manual continua disponível
            out["whatsapp_erro"] = str(ex)
    elif clientes.whatsapps(cli) and cli.get("whatsapp_cobranca") and whatsapp_web.ativo(cfg):
        try:                                   # WhatsApp Web do escritório: envia na hora, sozinho
            out["whatsapp_enviado"] = ", ".join(
                whatsapp_web.enviar_um(n, mensagem(t, etapa, cfg, canal="whatsapp")[1], cfg,
                                       pdf=whatsapp_web._pdf_do_titulo(t["id"], cfg),
                                       ref={"tipo": mensagens.tipo_da_etapa(etapa), "titulo_id": t["id"],
                                            "cliente": t["cliente_nome"]})
                for n in clientes.whatsapps(cli))
        except Exception as ex:  # noqa: BLE001
            out["whatsapp_erro"] = str(ex)
    if clientes.emails(cli) and cfg["smtp"].get("host"):
        pdf_ = _pdf_boleto(t, cfg)
        enviar_email(_para(cli), assunto, texto, cfg, [pdf_] if pdf_ else [], html=mensagem_html(t, etapa, cfg),
                     ref={"tipo": mensagens.tipo_da_etapa(etapa), "titulo_id": t["id"], "cliente": t["cliente_nome"]})
        out["email"] = _para(cli)
    out["pdf"] = t.get("boleto_pdf") or (_pdf_boleto(t, cfg) if t.get("banco_id") else "")
    return out
