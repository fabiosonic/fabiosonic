"""Importa e-mails e WhatsApp dos clientes a partir da planilha de contatos do sistema do escritório (CSV ';').

Cada empresa pode ter vários contatos (por departamento). Para cobrança vale o contato do Financeiro:
- e-mail: o do contato do Financeiro, preferindo endereços/nomes com "financeiro";
- WhatsApp: só celular (DDD + 9 dígitos começando por 9); números de enfeite (1111-1111) e fixos são ignorados.
Só clientes já cadastrados são atualizados; quem não está no cadastro aparece na conferência.
"""

from __future__ import annotations

import base64
import csv
import io
import re

from . import clientes


def _txt(dados: str | bytes) -> str:
    if isinstance(dados, bytes):
        for cod in ("utf-8-sig", "cp1252"):
            try:
                return dados.decode(cod)
            except UnicodeDecodeError:
                continue
        return dados.decode("latin-1")
    return dados.lstrip("\ufeff")


def de_base64(b64: str) -> bytes:
    """Arquivo enviado pela tela (data URL ou base64 puro)."""
    return base64.b64decode(b64.split(",", 1)[-1])


def celular(fone: str) -> str:
    """'(21) 99138-2888' -> '21991382888'; fixo, incompleto ou de enfeite -> ''."""
    d = re.sub(r"\D", "", fone or "")
    if d.startswith("55") and len(d) == 13:
        d = d[2:]
    elif len(d) > 11:                                   # '+1 21986275344' (código de país trocado): fica o número
        d = d[-11:]
    d = d.lstrip("0")
    if len(d) != 11 or d[2] != "9" or len(set(d[3:])) <= 2:     # fixo, incompleto ou 9 1111-1111
        return ""
    return d


def provisorio(email: str) -> bool:
    """E-mail de enfeite deixado no cadastro de origem ('aguardando@aguardando.com', 'AGUARDANDO@AGUA.COM')."""
    e = (email or "").strip().lower()
    return bool(re.match(r"aguardando@|.*@aguardando\.|.*@agua\.com$", e) or re.fullmatch(r"(\w+)@\1\.com", e))


def _do_escritorio() -> set[str]:
    """Domínios de e-mail do próprio escritório: e-mail de cliente com eles mandaria a cobrança para o escritório."""
    from . import config
    cfg = config.carregar()
    publicos = {"gmail.com", "hotmail.com", "outlook.com", "yahoo.com.br", "yahoo.com", "icloud.com", "live.com", "uol.com.br",
                "bol.com.br", "terra.com.br", "ig.com.br", "me.com"}
    dom = {str(v).split("@")[-1].strip().lower() for v in (cfg["smtp"].get("usuario"), cfg["smtp"].get("remetente"),
                                                           cfg["empresa"].get("email"), cfg["resumo"].get("email_dono"))
           if v and "@" in str(v)}
    return dom - publicos


def _col(linha: dict, *nomes: str) -> str:
    for n in nomes:
        for k, v in linha.items():
            if k and k.strip().lower() == n.lower():
                return (v or "").strip()
    return ""


def _pontos(c: dict) -> int:
    deps, email, nome = c["departamentos"].lower(), c["email"].lower(), c["nome"].lower()
    return 4 * ("financeiro" in deps) + 3 * ("financ" in email) + 2 * ("financ" in nome) + ("cobran" in email)


def ler(dados: str | bytes) -> dict[str, dict]:
    """{cpf_cnpj: {razao, contatos:[...], fone_empresa}} a partir do CSV."""
    linhas = csv.DictReader(io.StringIO(_txt(dados)), delimiter=";")
    empresas: dict[str, dict] = {}
    proprios = _do_escritorio()
    for r in linhas:
        doc = clientes._digitos(_col(r, "CNPJ", "CPF/CNPJ", "CPF", "CNPJ/CPF"))
        if len(doc) not in (11, 14):
            continue
        e = empresas.setdefault(doc, {"razao": _col(r, "Razão social", "Razao social", "Nome / Razão social", "Nome"), "contatos": [],
                                      "fone_empresa": _col(r, "Fone", "Telefone")})
        contato = {"nome": _col(r, "Nome do Contato"),
                   "email": _col(r, "Email do Contato", "E-mail do Contato", "E-mail", "Email").lower(),
                   "fone": _col(r, "Telefone do Contato", "Celular", "WhatsApp"),
                   "departamentos": _col(r, "Departamentos do Contato") or "Financeiro"}
        if provisorio(contato["email"]) or contato["email"].split("@")[-1] in proprios:
            contato["email"] = ""
        if contato["email"] or contato["fone"]:
            e["contatos"].append(contato)
    return empresas


def escolher(e: dict) -> dict:
    """Melhor e-mail e WhatsApp de cobrança da empresa (e o nome do contato)."""
    ordem = sorted(e["contatos"], key=_pontos, reverse=True)            # sorted é estável: empata pela ordem do arquivo
    com_email = [c for c in ordem if re.fullmatch(r"[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+", c["email"])]
    email = com_email[0] if com_email else None
    zap = None
    if email and celular(email["fone"]):
        zap = email                                                      # mesmo contato do e-mail, se tiver celular
    else:
        zap = next((c for c in ordem if celular(c["fone"])), None)
    fone = celular(zap["fone"]) if zap else celular(e.get("fone_empresa", ""))
    return {"email": email["email"] if email else "", "whatsapp": fone,
            "contato": (email or zap or {}).get("nome", "")}


def analisar(dados: str | bytes) -> dict:
    """Conferência antes de gravar: o que muda em cada cliente do cadastro."""
    empresas = ler(dados)
    cad = {c["cpf_cnpj"]: c for c in clientes.listar()}
    itens, fora = [], []
    for doc, e in empresas.items():
        novo = escolher(e)
        c = cad.get(doc)
        if not c:
            if novo["email"] or novo["whatsapp"]:
                fora.append({"cpf_cnpj": doc, "razao_social": e["razao"]})
            continue
        email_atual, fone_atual = c.get("email", ""), clientes._digitos(c.get("telefone"))
        if provisorio(email_atual):
            email_atual = ""                                 # e-mail de enfeite no cadastro conta como vazio
        muda_email = bool(novo["email"]) and novo["email"].lower() != email_atual.lower()
        muda_fone = bool(novo["whatsapp"]) and novo["whatsapp"] != fone_atual[-11:]
        if not (muda_email or muda_fone):
            continue
        itens.append({"cpf_cnpj": doc, "razao_social": c.get("razao_social") or e["razao"], "contato": novo["contato"],
                      "email_atual": email_atual, "email_novo": novo["email"] if muda_email else "",
                      "fone_atual": fone_atual, "fone_novo": novo["whatsapp"] if muda_fone else "",
                      "fixo": bool(fone_atual) and not celular(fone_atual),
                      "preenche": (muda_email and not email_atual) or (muda_fone and not celular(fone_atual))})
    itens.sort(key=lambda i: i["razao_social"].lower())
    return {"empresas": len(empresas), "itens": itens, "fora_do_cadastro": fora,
            "sem_mudanca": len(empresas) - len(itens) - len(fora)}


def aplicar(dados: str | bytes, substituir: bool = False, apenas: list[str] | None = None) -> dict:
    """Grava os contatos. Sem 'substituir', só preenche o que está vazio no cadastro."""
    a = analisar(dados)
    feitos = emails = fones = 0
    for i in a["itens"]:
        if apenas is not None and i["cpf_cnpj"] not in apenas:
            continue
        c = clientes.obter(i["cpf_cnpj"])
        novo = dict(c)
        if i["email_novo"] and (substituir or not i["email_atual"]):
            novo["email"] = i["email_novo"]
            emails += 1
        if i["fone_novo"] and (substituir or not celular(i["fone_atual"])):   # fixo não recebe WhatsApp: troca
            novo["telefone"] = i["fone_novo"]
            fones += 1
        if novo != c:
            clientes.salvar(novo)
            feitos += 1
    return {"clientes": feitos, "emails": emails, "whatsapp": fones, "fora_do_cadastro": len(a["fora_do_cadastro"])}
