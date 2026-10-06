"""Modelos das mensagens enviadas aos clientes (Mensagens › Modelos).

Cada modelo tem assunto (e-mail) e texto (o parágrafo principal). Os dados de pagamento (lista de títulos, linha
digitável, PIX, cartão, NFS-e) e a assinatura continuam sendo montados pelo sistema, para nunca sair errado.
Campos entre chaves são trocados pelos dados do cliente/título: {cliente}, {valor}, {vencimento} etc.
Modelo vazio = texto padrão. Os modelos ficam na configuração da empresa (cada empresa tem os seus).
"""

from __future__ import annotations

import re

from . import config

CAMPOS = {
    "cliente": "nome do cliente", "valor": "valor original", "vencimento": "data de vencimento",
    "atualizado": "valor com multa e juros", "dias": "dias de atraso", "competencia": "competência (MM/AAAA)",
    "referente": "descrição do serviço", "qtd": "quantidade de títulos", "total": "total (atualizado)",
    "nfse": "número da NFS-e", "link_nota": "link da nota", "data_pagamento": "data do pagamento",
    "valor_pago": "valor pago", "data_suspensao": "data da suspensão", "empresa": "nome do escritório",
}

# (chave, nome na tela, campos que fazem sentido, assunto padrão, texto padrão)
PADROES = [
    ("boleto", "Envio do boleto (antes do vencimento)", ["cliente", "valor", "vencimento", "competencia", "referente", "empresa"],
     "Boleto dos honorários — vencimento {vencimento}",
     "Segue a cobrança dos honorários de {valor}, com vencimento em {vencimento}."),
    ("lembrete", "Lembrete antes do vencimento", ["cliente", "valor", "vencimento", "competencia", "referente", "empresa"],
     "Lembrete: honorários vencem em {vencimento}",
     "Lembramos que o pagamento de {valor} vence em {vencimento}."),
    ("vence_hoje", "Vence hoje", ["cliente", "valor", "vencimento", "competencia", "referente", "empresa"],
     "Vence hoje: {valor}",
     "O pagamento de {valor} vence hoje ({vencimento})."),
    ("atraso", "Cobrança de atraso (um título)", ["cliente", "valor", "vencimento", "atualizado", "dias", "competencia", "referente", "empresa"],
     "Pagamento em aberto há {dias} dia(s)",
     "Não identificamos o pagamento de {valor}, vencido em {vencimento}. Valor atualizado com multa e juros: {atualizado}."),
    ("grupo", "Vários títulos em dia", ["cliente", "qtd", "total", "empresa"],
     "Boletos dos honorários — {qtd} títulos (total {total})",
     "Seguem os {qtd} títulos de honorários em seu nome, no total de {total}."),
    ("grupo_atraso", "Cobrança de atraso (vários títulos)", ["cliente", "qtd", "total", "empresa"],
     "Honorários em aberto — {qtd} títulos (total atualizado {total})",
     "Constam em aberto {qtd} títulos de honorários em seu nome, no total de {total} (vencidos com multa e juros "
     "até hoje). Seguem os dados de cada um para pagamento."),
    ("suspensao", "Aviso de suspensão dos serviços", ["cliente", "dias", "qtd", "total", "data_suspensao", "empresa"],
     "Aviso de suspensão dos serviços — débito em aberto há {dias} dias",
     "Constam em aberto, há {dias} dias, honorários em seu nome no total atualizado de {total} ({qtd} título(s), "
     "relacionados abaixo). Apesar das cobranças anteriores, o pagamento ainda não foi identificado.\n\n"
     "Caso o débito não seja regularizado até {data_suspensao}, os serviços contábeis serão suspensos a partir dessa "
     "data, nos termos do contrato de prestação de serviços, permanecendo devidos os valores em aberto. Antes disso, "
     "estamos à disposição para negociar a forma de pagamento — basta responder esta mensagem."),
    ("agradecimento", "Agradecimento pelo pagamento", ["cliente", "valor_pago", "data_pagamento", "competencia", "referente", "empresa"],
     "Pagamento recebido — obrigado! ({valor_pago})",
     "Recebemos o seu pagamento de {valor_pago} em {data_pagamento}, referente a: {referente} — competência "
     "{competencia}.\n\nMuito obrigado!"),
    ("nota_fiscal", "Envio da nota fiscal", ["cliente", "nfse", "valor", "competencia", "link_nota", "empresa"],
     "Nota fiscal de serviço nº {nfse}",
     "Segue a nota fiscal de serviço (NFS-e nº {nfse}) no valor de {valor} — competência {competencia}."),
]
_POR_CHAVE = {p[0]: p for p in PADROES}


def preencher(modelo: str, dados: dict) -> str:
    """Troca {campo} pelos dados; campo desconhecido fica como está (nunca quebra o envio)."""
    return re.sub(r"\{(\w+)\}", lambda m: str(dados[m.group(1)]) if m.group(1) in dados else m.group(0), modelo or "")


def personalizado(cfg: dict | None, chave: str, parte: str) -> str:
    """Texto editado pelo escritório para a parte ('assunto' ou 'texto') do modelo, ou '' (usa o padrão)."""
    return str(((cfg or config.carregar()).get("modelos") or {}).get(chave, {}).get(parte) or "").strip()


def texto(cfg: dict | None, chave: str, parte: str, dados: dict, padrao: str | None = None) -> str:
    """Parte do modelo já preenchida: a editada ou, sem edição, o padrão (do sistema ou o informado)."""
    m = personalizado(cfg, chave, parte)
    if not m:
        if padrao is not None:
            return padrao
        m = _POR_CHAVE[chave][3 if parte == "assunto" else 4]
    return preencher(m, dados)


def listar(cfg: dict | None = None) -> list[dict]:
    cfg = cfg or config.carregar()
    return [{"chave": k, "nome": n, "campos": [{"campo": c, "desc": CAMPOS[c]} for c in campos],
             "assunto_padrao": a, "texto_padrao": t, "assunto": personalizado(cfg, k, "assunto"),
             "texto": personalizado(cfg, k, "texto")} for k, n, campos, a, t in PADROES]


def salvar(chave: str, assunto: str, texto_: str) -> dict:
    if chave not in _POR_CHAVE:
        raise ValueError("Modelo desconhecido.")
    for parte, v in (("assunto", assunto), ("texto", texto_)):
        desconhecidos = sorted(set(re.findall(r"\{(\w+)\}", v or "")) - set(CAMPOS))
        if desconhecidos:
            raise ValueError(f"Campo(s) que não existem no {parte}: " + ", ".join("{" + d + "}" for d in desconhecidos)
                             + ". Use os campos listados abaixo do texto.")
    padrao = _POR_CHAVE[chave]
    # igual ao padrão = sem edição (assim, se o padrão melhorar numa versão nova, ele vale)
    assunto = "" if (assunto or "").strip() == padrao[3] else (assunto or "").strip()
    texto_ = "" if (texto_ or "").strip() == padrao[4] else (texto_ or "").strip()
    config.salvar({"modelos": {chave: {"assunto": assunto, "texto": texto_}}})
    return {"ok": True}


EXEMPLO = {"cliente": "Exemplo Comércio Ltda", "valor": "R$ 500,00", "vencimento": "10/10/2026",
           "atualizado": "R$ 514,17", "dias": 25, "competencia": "09/2026", "referente": "Honorários contábeis mensais",
           "qtd": 2, "total": "R$ 1.014,17", "nfse": "202600000123", "link_nota": "https://exemplo/nota/123",
           "data_pagamento": "12/10/2026", "valor_pago": "R$ 500,00", "data_suspensao": "20/10/2026"}


def previa(chave: str, assunto: str, texto_: str) -> dict:
    """Como a mensagem fica com dados de exemplo (antes de salvar)."""
    p = _POR_CHAVE[chave]
    dados = EXEMPLO | {"empresa": config.carregar()["empresa"].get("nome", "")}
    if chave == "suspensao":
        dados["dias"] = 95
    return {"assunto": preencher(assunto or p[3], dados), "texto": preencher(texto_ or p[4], dados)}
