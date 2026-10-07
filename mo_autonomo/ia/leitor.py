"""Leitura de documento não estruturado (PDF/texto) com IA — saída validada por código (regra 13)."""
from __future__ import annotations

import json
import re

from ..util.dinheiro import ValorInvalido, dinheiro
from ..util.documentos_id import cnpj_valido, so_digitos
from .cascata import Cascata, SemProvedorDisponivel, VazamentoBloqueado

TIPOS = ("GUIA_TRIBUTO", "BOLETO", "EXTRATO_BANCARIO", "CONTRATO", "FOLHA_PAGAMENTO", "RECIBO",
         "NOTA_FISCAL_PDF", "COMPROVANTE_PAGAMENTO", "DOCUMENTO_SOCIETARIO", "OUTRO")

SISTEMA = (
    "Você classifica documentos de clientes de um escritório contábil. Responda SOMENTE um JSON com as "
    "chaves: tipo (um de " + ", ".join(TIPOS) + "), cnpj (texto exatamente como aparece no documento ou null), "
    "competencia (AAAA-MM ou null), valor (texto exatamente como aparece ou null), confianca (0 a 1), "
    "resumo (até 200 caracteres). Não invente: se não estiver no texto, use null."
)


def extrair_texto_pdf(dados: bytes) -> str:
    import io

    from pypdf import PdfReader
    leitor = PdfReader(io.BytesIO(dados))
    return "\n".join((p.extract_text() or "") for p in leitor.pages[:20])


def _json(texto: str) -> dict:
    m = re.search(r"\{.*\}", texto, re.DOTALL)
    if not m:
        raise ValueError("resposta sem JSON")
    return json.loads(m.group(0))


def ler_nao_estruturado(texto: str, cascata: Cascata, confianca_minima: float = 0.8,
                        nomes_sensiveis: list[str] | None = None) -> dict:
    """Devolve {status: OK|PENDENTE|FILA, ...}. Cada campo é validado contra o texto original."""
    if not texto.strip():
        return {"status": "PENDENTE", "motivo": "documento sem texto extraível (precisa de OCR ou leitura humana)"}
    try:
        r = cascata.completar(SISTEMA, texto[:12000], nomes_sensiveis)
    except SemProvedorDisponivel as exc:
        return {"status": "FILA", "motivo": str(exc)}
    except VazamentoBloqueado as exc:
        return {"status": "PENDENTE", "motivo": str(exc)}
    try:
        dados = _json(r["texto"])
    except (ValueError, json.JSONDecodeError):
        return {"status": "PENDENTE", "motivo": "IA não devolveu JSON válido", "provedor": r["provedor"]}
    motivos = []
    tipo = dados.get("tipo")
    if tipo not in TIPOS:
        motivos.append(f"tipo inválido {tipo!r}")
    cnpj = so_digitos(dados.get("cnpj") or "") or None
    if cnpj and (not cnpj_valido(cnpj) or cnpj not in so_digitos(texto)):
        motivos.append("CNPJ devolvido não confere com o texto")
        cnpj = None
    valor = None
    if dados.get("valor"):
        bruto = str(dados["valor"])
        if bruto.replace("R$", "").strip() not in texto:
            motivos.append("valor devolvido não aparece no texto")
        else:
            try:
                valor = dinheiro(bruto.replace("R$", "").strip())
            except ValorInvalido:
                motivos.append("valor ilegível")
    comp = dados.get("competencia")
    if comp and not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", str(comp)):
        motivos.append("competência em formato inválido")
        comp = None
    try:
        conf = float(dados.get("confianca") or 0)
    except (TypeError, ValueError):
        conf = 0.0
    if conf < confianca_minima:
        motivos.append(f"confiança {conf:.2f} abaixo do mínimo {confianca_minima}")
    return {"status": "PENDENTE" if motivos else "OK", "motivo": "; ".join(motivos) or None,
            "tipo": tipo, "cnpj": cnpj, "competencia": comp, "valor": valor, "confianca": conf,
            "resumo": (dados.get("resumo") or "")[:200], "provedor": r["provedor"], "mascarado": r["mascarado"]}
