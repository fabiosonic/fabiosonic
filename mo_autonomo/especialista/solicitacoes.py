"""Rascunhos de solicitação ao cliente (não envia: e-mail para fora é ação externa).

Gera um texto por empresa/competência com o que falta receber, a partir dos achados cuja
correção é responsabilidade do cliente (regras listadas em REGRAS_CLIENTE).
"""
from __future__ import annotations

from pathlib import Path

from ..util.arquivos import escrever_atomico
from ..util.documentos_id import formatar_cnpj

REGRAS_CLIENTE = {
    "COMP_SEQUENCIA": "XML de notas emitidas que não recebemos (ou comprovante de inutilização/cancelamento)",
    "DFE_SEM_PROTOCOLO": "XML de distribuição (com protocolo de autorização) das notas abaixo",
    "NFE_SOMA_ITENS": "Confirmação/correção de notas com soma dos itens diferente do total",
    "DOMINIO_SEM_DOCUMENTO": "XML de notas que constam na escrituração e não foram enviados",
    "SEM_CONTRAPARTIDA": "Explicação de movimentações bancárias sem histórico conhecido",
}


def rascunho(empresa, competencia: str, achados: list[dict], pendencias: list[dict]) -> str | None:
    itens = []
    for a in achados:
        if a["regra"] in REGRAS_CLIENTE:
            itens.append((REGRAS_CLIENTE[a["regra"]], a["mensagem"]))
    for p in pendencias:
        if p.get("codigo") in REGRAS_CLIENTE:
            itens.append((REGRAS_CLIENTE[p["codigo"]], p["mensagem"]))
    if not itens:
        return None
    ano, mes = competencia.split("-")
    linhas = [f"Assunto: {empresa.apelido} — documentos pendentes da competência {mes}/{ano}", "",
              "Olá,", "",
              f"Na conferência da competência {mes}/{ano} da {empresa.apelido} ({formatar_cnpj(empresa.cnpj)}) "
              "precisamos dos itens abaixo para concluir a escrituração:", ""]
    grupos: dict[str, list[str]] = {}
    for titulo, detalhe in itens:
        grupos.setdefault(titulo, []).append(detalhe)
    for titulo, detalhes in grupos.items():
        linhas.append(f"• {titulo}:")
        linhas += [f"   - {d}" for d in detalhes]
    linhas += ["", "Pode responder este e-mail com os arquivos em anexo (XML ou ZIP).", "",
               "Obrigado,", "Moraes & Oliveira Contabilidade", "",
               "[RASCUNHO GERADO AUTOMATICAMENTE — revisar antes de enviar]"]
    return "\n".join(linhas)


def salvar(pasta: Path, empresa, competencia: str, texto: str) -> Path:
    destino = Path(pasta) / competencia / f"{empresa.pasta}.txt"
    escrever_atomico(destino, texto.encode("utf-8"))
    return destino
