"""Identidade visual dos e-mails (Configurações › Empresa e PIX › Aparência dos e-mails).

A logo fica na pasta da empresa (dados/logo_email.png) e vai DENTRO do e-mail (imagem embutida, cid:logo):
aparece no Gmail/Outlook sem depender de site nem de "baixar imagens". Cada empresa tem a sua logo e as suas cores.
"""

from __future__ import annotations

import base64
import re
from html import escape as e

from . import emissor

ARQUIVO = "logo_email.png"
CID = "logo"
COR_PADRAO = "#1f4fbf"
FUNDO_PADRAO = "#0b1f3a"
VERMELHO = "#b42318"
MAX_BYTES = 600_000


def _caminho():
    return emissor.raiz() / "dados" / ARQUIVO


def logo() -> bytes:
    p = _caminho()
    return p.read_bytes() if p.is_file() else b""


def _cor(v: str, padrao: str) -> str:
    v = str(v or "").strip()
    return v.lower() if re.fullmatch(r"#[0-9a-fA-F]{6}", v) else padrao


def salvar_logo(arquivo_b64: str, fundo: str = "", cor: str = "") -> dict:
    """A tela já manda a logo em PNG, recortada e reduzida (até 560 px de largura)."""
    from . import config
    dados = base64.b64decode(str(arquivo_b64 or "").split(",")[-1] or b"")
    if not dados.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("A logo precisa ser uma imagem (PNG, JPG ou WEBP).")
    if len(dados) > MAX_BYTES:
        raise ValueError("Logo grande demais para e-mail (máx. 600 KB). Use uma imagem menor.")
    p = _caminho()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(dados)
    emp = {"logo_fundo": _cor(fundo, FUNDO_PADRAO)}
    if cor:
        emp["cor_email"] = _cor(cor, COR_PADRAO)
    config.salvar({"empresa": emp})
    return info()


def remover_logo() -> dict:
    p = _caminho()
    if p.is_file():
        p.unlink()
    return info()


def info() -> dict:
    d = logo()
    return {"tem_logo": bool(d), "logo": ("data:image/png;base64," + base64.b64encode(d).decode()) if d else ""}


def cores(cfg: dict) -> dict:
    emp = cfg.get("empresa", {})
    return {"destaque": _cor(emp.get("cor_email"), COR_PADRAO), "fundo": _cor(emp.get("logo_fundo"), FUNDO_PADRAO)}


def clara(cor: str, quanto: float = 0.9) -> str:
    """Tom bem claro da cor (fundo do selo e do destaque), sem transparência — o Outlook não entende rgba."""
    r, g, b = (int(cor[i:i + 2], 16) for i in (1, 3, 5))
    return "#" + "".join(f"{round(x + (255 - x) * quanto):02x}" for x in (r, g, b))


def _whats_link(numero: str) -> str:
    d = re.sub(r"\D", "", numero or "")
    if not d:
        return ""
    return "https://wa.me/" + (d if d.startswith("55") else "55" + d)


def _fone(d: str) -> str:
    d = re.sub(r"\D", "", d or "")
    if d.startswith("55") and len(d) > 11:
        d = d[2:]
    if len(d) == 11:
        return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    if len(d) == 10:
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    return d


def _cnpj(d: str) -> str:
    d = re.sub(r"\D", "", d or "")
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}" if len(d) == 14 else d


def casca(cfg: dict, assunto: str, corpo: str, selo: str = "", cor_selo: str = "", com_logo: bool | None = None) -> str:
    """Moldura de todo e-mail do sistema: cabeçalho com a logo, conteúdo, contato e rodapé da empresa.
    Só tabelas e estilos em linha (Gmail, Outlook e celular)."""
    emp = cfg.get("empresa", {})
    c = cores(cfg)
    nome = emp.get("nome", "") or ""
    tem_logo = bool(logo()) if com_logo is None else com_logo
    if tem_logo:
        topo = (f'<td align="center" style="background:{c["fundo"]};padding:18px 24px;border-radius:14px 14px 0 0">'
                f'<img src="cid:{CID}" alt="{e(nome)}" width="240" style="display:block;width:240px;max-width:70%;height:auto;'
                f'border:0;outline:none;text-decoration:none;color:#ffffff;font-size:18px;font-weight:700"></td>')
    else:
        topo = (f'<td style="background:{c["fundo"]};padding:22px 24px;border-radius:14px 14px 0 0;font-family:Segoe UI,Arial,sans-serif;'
                f'font-size:19px;font-weight:700;color:#ffffff;letter-spacing:.02em">{e(nome)}</td>')
    faixa = f'<tr><td style="height:4px;line-height:4px;font-size:0;background:{cor_selo or c["destaque"]}">&nbsp;</td></tr>'
    selo_html = (f'<tr><td style="padding:18px 28px 0"><span style="display:inline-block;font-size:11px;font-weight:700;'
                 f'letter-spacing:.08em;color:{cor_selo or c["destaque"]};background:{clara(cor_selo or c["destaque"])};'
                 f'border:1px solid {cor_selo or c["destaque"]};border-radius:999px;padding:4px 12px">{e(selo)}</span></td></tr>'
                 if selo else "")
    whats = emp.get("whatsapp", "")
    contato = ""
    if whats:
        contato = (f'<tr><td style="padding:0 28px 22px"><table role="presentation" width="100%" cellspacing="0" cellpadding="0" '
                   f'style="background:#f4f7fb;border-radius:10px"><tr><td style="padding:14px 16px;font-size:14px;color:#344054;line-height:1.45">'
                   f'<b style="color:#101828">Ficou com alguma dúvida?</b> Fale com a nossa equipe — respondemos rapidinho.<br>'
                   f'<a href="{_whats_link(whats)}" style="display:inline-block;margin-top:10px;background:#1fa855;color:#ffffff;'
                   f'text-decoration:none;font-weight:700;font-size:14px;padding:10px 16px;border-radius:8px">'
                   f'Falar no WhatsApp {e(_fone(whats))}</a></td></tr></table></td></tr>')
    frase = str(emp.get("rodape_email") or "").strip()
    cnpj = _cnpj(emissor.env("ITABORAI_CNPJ"))
    linha_dados = " · ".join(x for x in (f"CNPJ {cnpj}" if cnpj else "", _fone(emp.get("telefone", "")),
                                         emp.get("email", "")) if x)
    site = str(emp.get("site") or "").strip()
    site_html = ""
    if site:
        url = site if site.startswith("http") else "https://" + site
        site_html = f'<br><a href="{e(url)}" style="color:{c["destaque"]};text-decoration:none">{e(site.replace("https://", "").replace("http://", ""))}</a>'
    assinatura = emp.get("assinatura") or nome
    rodape = (f'<tr><td style="padding:18px 28px;background:{c["fundo"]};border-radius:0 0 14px 14px;font-size:12px;'
              f'line-height:1.6;color:#c9d4e5">'
              + (f'<span style="color:#ffffff;font-size:13px">{e(frase)}</span><br>' if frase else "")
              + f'<b style="color:#ffffff">{e(assinatura)}</b>'
              + (f'<br>{e(linha_dados)}' if linha_dados else "") + site_html
              + '<br><span style="color:#8fa1bd">Mensagem enviada pelo sistema financeiro da empresa.</span></td></tr>')
    return (f'<!doctype html><html lang="pt-br"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
            f'<meta name="color-scheme" content="light"><title>{e(assunto)}</title></head>'
            f'<body style="margin:0;padding:0;background:#eef2f7">'
            f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#eef2f7;padding:24px 10px">'
            f'<tr><td align="center"><table role="presentation" width="100%" cellspacing="0" cellpadding="0" '
            f'style="max-width:600px;background:#ffffff;border-radius:14px;font-family:Segoe UI,Arial,sans-serif;'
            f'box-shadow:0 2px 10px rgba(16,24,40,.08)">'
            f'<tr>{topo}</tr>{faixa}{selo_html}'
            f'<tr><td style="padding:18px 28px 22px">{corpo}</td></tr>{contato}{rodape}'
            f'</table></td></tr></table></body></html>')


SELO_DO_TIPO = {"Agradecimento": ("PAGAMENTO RECEBIDO", "#067647"), "Nota fiscal": ("NOTA FISCAL", ""),
                "Aviso de suspensão": ("AVISO IMPORTANTE", VERMELHO)}


def _linkar(t: str, cor: str) -> str:
    return re.sub(r"(https?://[^\s<]+)", lambda m: f'<a href="{m.group(1)}" style="color:{cor};word-break:break-all">{m.group(1)}</a>', t)


def html_de_texto(texto: str, cfg: dict, assunto: str = "", tipo: str = "") -> str:
    """Mensagens que só têm texto (agradecimento, nota fiscal, aviso de suspensão…) ganham a mesma moldura.
    A assinatura do texto sai: ela já está no rodapé."""
    c = cores(cfg)
    linhas = texto.replace("\r\n", "\n").split("\n")
    for i, l in enumerate(linhas):
        if l.strip().lower().rstrip(",") == "atenciosamente":
            linhas = linhas[:i]
            break
    while linhas and not linhas[-1].strip():
        linhas.pop()
    blocos, atual = [], []
    for l in linhas + [""]:
        if l.strip():
            atual.append(l)
        elif atual:
            blocos.append(atual)
            atual = []
    corpo = ""
    for n, b in enumerate(blocos):
        if n == 0 and len(b) == 1 and re.match(r"^(Olá|Ola|Prezad[oa]s?|Bom dia|Boa tarde)\b", b[0]):
            nome = re.sub(r"^(Olá|Ola),\s*", "", b[0]).rstrip("!").strip()
            corpo += (f'<p style="margin:0 0 12px;font-size:17px;color:#101828">Olá, <b>{e(nome)}</b>!</p>'
                      if b[0].startswith(("Olá", "Ola")) else f'<p style="margin:0 0 12px;font-size:17px;color:#101828">{e(b[0])}</p>')
            continue
        corpo += ('<p style="margin:0 0 12px;font-size:15px;line-height:1.6;color:#344054">'
                  + "<br>".join(_linkar(e(x), c["destaque"]) for x in b) + "</p>")
    selo, cor = SELO_DO_TIPO.get(tipo, ("", ""))
    return casca(cfg, assunto, corpo, selo, cor)
