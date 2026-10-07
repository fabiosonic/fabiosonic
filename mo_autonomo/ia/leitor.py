"""Leitura de documento não estruturado (PDF/texto) com IA — saída validada por código (regra 13)."""
from __future__ import annotations

import json
import re

from ..util.dinheiro import ValorInvalido, dinheiro, dinheiro_br
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


def _token_presente(trecho: str, texto: str) -> bool:
    """O trecho aparece isolado (não como pedaço de outro número: '150,00' não casa '1.150,00')."""
    if not trecho:
        return False
    return re.search(r"(?<![\d.,])" + re.escape(trecho) + r"(?![\d]|[.,]\d)", texto) is not None


def _cnpj_como_token(cnpj: str, texto: str) -> bool:
    """CNPJ presente como um número só (com ou sem pontuação), não costurado de números diferentes."""
    padrao = (rf"(?<![\dA-Za-z]){cnpj[:2]}\.?{cnpj[2:5]}\.?{cnpj[5:8]}/?{cnpj[8:12]}-?{cnpj[12:]}(?![\dA-Za-z])")
    return re.search(padrao, texto) is not None


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
    if cnpj and (not cnpj_valido(cnpj) or not _cnpj_como_token(cnpj, texto)):
        motivos.append("CNPJ devolvido não confere com o texto")
        cnpj = None
    valor = None
    if dados.get("valor"):
        bruto = str(dados["valor"])
        if not _token_presente(bruto.replace("R$", "").strip(), texto):
            motivos.append("valor devolvido não aparece no texto")
        else:
            try:
                valor = dinheiro_br(bruto)
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
