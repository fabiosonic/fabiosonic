"""Roteamento de XML para as pastas lidas pelas Rotinas Automáticas do Domínio.

Estrutura: <base>/<TIPO>/<Código-Apelido>/MMAAAA/<chave>.xml
- Nunca sobrescreve: mesmo nome com conteúdo diferente vira pendência.
- Em modo simulação a base é _STAGING/XML NOTAS.
- O sentido da NF-e (tpNF) é lido com o parâmetro `tp_nf_saida` da norma MOC_NFE (regra 3);
  sem ele, NF-e emitida pela empresa fica com rota pendente.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..util.arquivos import escrever_atomico, nome_seguro, sha256_arquivo, sha256_bytes

TIPOS_PADRAO = {
    "NFSE_EMITIDA": "NFSE EMITIDA", "NFSE_TOMADA": "NFSE TOMADA", "NFE_ENTRADA": "NFE ENTRADA",
    "NFE_SAIDA": "NFE SAIDA", "NFE_EVENTOS": "NFE EVENTOS", "NFCE_SAIDA": "NFCE SAIDA",
    "NFCE_EVENTOS": "NFCE EVENTOS", "CTE_ENTRADA": "CTE ENTRADA", "OUTROS_EVENTOS": "OUTROS EVENTOS",
}


@dataclass
class Rota:
    cnpj: str | None
    tipo: str | None          # chave de TIPOS_PADRAO
    pendencia: str | None = None


def _cnpj_da_chave(chave: str | None) -> str | None:
    return chave[6:20] if chave and len(chave) == 44 else None


def rotas(doc: dict, carteira, catalogo) -> list[Rota]:
    t = doc["tipo"]
    nossos = [c for c in dict.fromkeys(doc.get("participantes") or []) if carteira.get(c)]
    out: list[Rota] = []
    if t == "NFE":
        saida = catalogo.parametro("MOC_NFE", "tp_nf_saida")
        for c in nossos:
            if c == doc.get("emitente_cnpj"):
                if saida is None:
                    out.append(Rota(c, None, "Sentido da NF-e não verificável: MOC_NFE.tp_nf_saida não conferido."))
                elif str(doc.get("tp_nf")) == str(saida):
                    out.append(Rota(c, "NFE_SAIDA"))
                else:
                    out.append(Rota(c, None, "NF-e de entrada emitida pela própria empresa: definir pasta/tratamento."))
            else:
                if saida is None:
                    out.append(Rota(c, None, "Sentido da NF-e não verificável: MOC_NFE.tp_nf_saida não conferido."))
                elif str(doc.get("tp_nf")) == str(saida):
                    out.append(Rota(c, "NFE_ENTRADA"))
                else:
                    out.append(Rota(c, None, "NF-e de entrada emitida por terceiro contra a empresa: tratar manualmente."))
    elif t == "NFCE":
        for c in nossos:
            if c == doc.get("emitente_cnpj"):
                out.append(Rota(c, "NFCE_SAIDA"))
    elif t == "NFSE":
        for c in nossos:
            if c == doc.get("prestador_cnpj"):
                out.append(Rota(c, "NFSE_EMITIDA"))
            if c == doc.get("tomador_cnpj"):
                out.append(Rota(c, "NFSE_TOMADA"))
    elif t == "CTE":
        for c in nossos:
            if c == doc.get("emitente_cnpj"):
                out.append(Rota(c, None, "CT-e emitido pela empresa: não há pasta de CT-e de saída configurada."))
            else:
                out.append(Rota(c, "CTE_ENTRADA"))
    elif t.startswith("EVENTO_"):
        tipo = {"EVENTO_NFE": "NFE_EVENTOS", "EVENTO_NFCE": "NFCE_EVENTOS"}.get(t, "OUTROS_EVENTOS")
        donos = [c for c in (_cnpj_da_chave(doc.get("chave_ref")), doc.get("emitente_cnpj")) if c and carteira.get(c)]
        out.extend(Rota(c, tipo) for c in dict.fromkeys(donos))
    if not out:
        out.append(Rota(None, None, "Nenhuma empresa da carteira identificada no documento (cruzamento por CNPJ)."))
    return out


class ConflitoArquivo(RuntimeError):
    pass


class DestinoInvalido(ValueError):
    pass


def caminho_destino(base: Path, tipos: dict, empresa, tipo: str, competencia: str, nome: str) -> Path:
    ano, mes = competencia.split("-")
    if not (ano.isdigit() and mes.isdigit()):
        raise DestinoInvalido(f"competência inválida: {competencia!r}")
    destino = Path(base) / tipos[tipo] / empresa.pasta / f"{mes}{ano}" / nome_seguro(nome)
    base_r = Path(base).resolve()
    if not destino.resolve().is_relative_to(base_r):
        raise DestinoInvalido(f"destino fora da pasta base: {destino}")
    return destino


def gravar(destino: Path, dados: bytes) -> str:
    """Grava sem sobrescrever. Devolve 'GRAVADO' ou 'JA_EXISTIA'; conteúdo diferente levanta erro."""
    if destino.exists():
        if sha256_arquivo(destino) == sha256_bytes(dados):
            return "JA_EXISTIA"
        raise ConflitoArquivo(f"arquivo já existe com conteúdo diferente: {destino}")
    escrever_atomico(destino, dados)
    return "GRAVADO"
