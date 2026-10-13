"""Classificação automática de arquivos do Drive.

Para cada arquivo, combina quatro sinais:
  1. Texto do conteúdo (PDF/XML/TXT)  -> sinal mais forte (recibos e guias oficiais)
  2. Nome do arquivo                  -> padrões usuais da equipe ("DAS 09-2026.pdf")
  3. Pasta onde foi depositado        -> dica de departamento ("Fiscal", "Pessoal"...)
  4. Extensão                         -> XML de NF-e, OFX de extrato etc.

Extrai também a competência (período de apuração) e os CNPJs presentes,
para conferir se o documento foi salvo na pasta da empresa correta.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime

from .calendario import competencia_str, somar_meses

LIMIAR_CLASSIFICACAO = 50

MESES = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
    "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
    "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12,
}


def sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


# ----------------------------------------------------------------------------
# CNPJ / CPF
# ----------------------------------------------------------------------------
def so_digitos(texto: str) -> str:
    return re.sub(r"\D", "", texto or "")


def cnpj_valido(cnpj: str) -> bool:
    c = so_digitos(cnpj)
    if len(c) != 14 or c == c[0] * 14:
        return False

    def dv(base: str, pesos: list[int]) -> str:
        r = sum(int(d) * p for d, p in zip(base, pesos)) % 11
        return "0" if r < 2 else str(11 - r)

    p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    p2 = [6] + p1
    return c[12] == dv(c[:12], p1) and c[13] == dv(c[:12] + c[12], p2)


def cpf_valido(cpf: str) -> bool:
    c = so_digitos(cpf)
    if len(c) != 11 or c == c[0] * 11:
        return False
    for i in (9, 10):
        soma = sum(int(c[j]) * (i + 1 - j) for j in range(i))
        if str((soma * 10 % 11) % 10) != c[i]:
            return False
    return True


RE_CNPJ = re.compile(r"(?<!\d)(\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2})(?!\d)")


def extrair_cnpjs(texto: str) -> list[str]:
    vistos: list[str] = []
    for m in RE_CNPJ.finditer(texto or ""):
        c = so_digitos(m.group(1))
        if cnpj_valido(c) and c not in vistos:
            vistos.append(c)
    return vistos


# ----------------------------------------------------------------------------
# Competência
# ----------------------------------------------------------------------------
_RE_ROTULO = re.compile(
    r"(?:per[ií]odo de apura[cç][aã]o|compet[eê]ncia|\bPA\b|refer[eê]ncia|m[eê]s/ano|per[ií]odo)"
    r"\s*[:\-]?\s*(\d{1,2})\s*[/\-.]\s*(\d{4})",
    re.IGNORECASE,
)
_RE_ROTULO_DATA = re.compile(
    r"(?:per[ií]odo de apura[cç][aã]o|compet[eê]ncia)\s*[:\-]?\s*\d{1,2}/(\d{1,2})/(\d{4})", re.IGNORECASE
)
_RE_ANO_CALENDARIO = re.compile(r"(?:ano[- ]calend[aá]rio|exerc[ií]cio|ano[- ]base)\s*[:\-]?\s*(\d{4})", re.IGNORECASE)
_RE_MES_ANO = re.compile(r"(?<!\d)(0?[1-9]|1[0-2])\s*[/\-_. ]\s*(20\d{2})(?!\d)")
_RE_ANO_MES = re.compile(r"(?<!\d)(20\d{2})\s*[/\-_. ]?\s*(0[1-9]|1[0-2])(?!\d)")
_RE_MES_EXTENSO = re.compile(
    r"\b(" + "|".join(sorted(MESES, key=len, reverse=True)) + r")\b\s*(?:de\s*|/|-|_|\.)?\s*(20\d{2})",
    re.IGNORECASE,
)
_RE_TRIMESTRE = re.compile(r"(?<!\d)([1-4])\s*[ºo°]?\s*(?:tri(?:mestre)?|T)\s*[/\-_ ]?\s*(?:de\s*)?(20\d{2})", re.IGNORECASE)


def _valida(ano: int, mes: int) -> str | None:
    if 2000 <= ano <= 2100 and 1 <= mes <= 12:
        return competencia_str(ano, mes)
    return None


def extrair_competencia(texto: str, periodicidade: str = "mensal") -> str | None:
    """Procura a competência no texto (conteúdo, nome do arquivo ou caminho)."""
    if not texto:
        return None
    t = sem_acento(texto)
    if periodicidade == "anual":
        m = _RE_ANO_CALENDARIO.search(t)
        if m:
            return _valida(int(m.group(1)), 12)
    if periodicidade == "trimestral":
        m = _RE_TRIMESTRE.search(t)
        if m:
            return _valida(int(m.group(2)), int(m.group(1)) * 3)
    for rx in (_RE_ROTULO, _RE_ROTULO_DATA):
        m = rx.search(t)
        if m:
            c = _valida(int(m.group(2)), int(m.group(1)))
            if c:
                return _ajustar(c, periodicidade)
    m = _RE_MES_EXTENSO.search(t)
    if m:
        c = _valida(int(m.group(2)), MESES[m.group(1).lower()])
        if c:
            return _ajustar(c, periodicidade)
    m = _RE_MES_ANO.search(t)
    if m:
        c = _valida(int(m.group(2)), int(m.group(1)))
        if c:
            return _ajustar(c, periodicidade)
    m = _RE_ANO_MES.search(t)
    if m:
        c = _valida(int(m.group(1)), int(m.group(2)))
        if c:
            return _ajustar(c, periodicidade)
    if periodicidade == "anual":
        m = re.search(r"(?<!\d)(20\d{2})(?!\d)", t)
        if m:
            return _valida(int(m.group(1)), 12)
    return None


def _ajustar(comp: str, periodicidade: str) -> str:
    ano, mes = int(comp[:4]), int(comp[5:])
    if periodicidade == "trimestral":
        return competencia_str(ano, ((mes - 1) // 3 + 1) * 3)
    if periodicidade == "anual":
        return competencia_str(ano, 12)
    return comp


def competencia_por_caminho(caminho: str, periodicidade: str = "mensal") -> str | None:
    """Estrutura padrão: .../2026/09 - Setembro/Fiscal/arquivo.pdf"""
    partes = [sem_acento(p) for p in caminho.replace("\\", "/").split("/") if p]
    ano = None
    for i, p in enumerate(partes):
        if re.fullmatch(r"20\d{2}", p.strip()):
            ano = int(p)
            if i + 1 < len(partes):
                m = re.match(r"\s*(0?[1-9]|1[0-2])(?!\d)", partes[i + 1])
                if m:
                    return _ajustar(competencia_str(ano, int(m.group(1))), periodicidade)
                m = _RE_MES_EXTENSO.search(partes[i + 1] + f" {ano}")
                if m:
                    return _ajustar(competencia_str(ano, MESES[m.group(1).lower()]), periodicidade)
    if ano and periodicidade == "anual":
        return competencia_str(ano, 12)
    return None


def competencia_por_data(data: datetime | None, periodicidade: str = "mensal") -> str | None:
    """Último recurso: o documento normalmente é gerado no mês seguinte à competência."""
    if not data:
        return None
    if periodicidade == "anual":
        return competencia_str(data.year - 1, 12)
    ano, mes = somar_meses(data.year, data.month, -1)
    return _ajustar(competencia_str(ano, mes), periodicidade)


# ----------------------------------------------------------------------------
# Classificação
# ----------------------------------------------------------------------------
@dataclass
class Regra:
    codigo: str
    periodicidade: str
    departamento: str
    reconhecimento: dict


@dataclass
class Resultado:
    codigo: str | None = None
    confianca: int = 0
    competencia: str | None = None
    origem_competencia: str = ""
    cnpjs: list[str] = field(default_factory=list)
    candidatos: list[tuple[str, int]] = field(default_factory=list)
    motivos: list[str] = field(default_factory=list)

    @property
    def identificado(self) -> bool:
        return self.codigo is not None


def _algum(padroes: list[str], texto: str) -> list[str]:
    return [p for p in padroes if re.search(p, texto, re.IGNORECASE | re.DOTALL)]


def pontuar(regra: Regra, nome: str, texto: str, caminho: str) -> tuple[int, list[str]]:
    rec = regra.reconhecimento or {}
    nome_n = sem_acento(nome.lower())
    caminho_n = sem_acento(caminho.lower())
    motivos: list[str] = []

    exts = rec.get("extensoes")
    if exts and not any(nome_n.endswith(e) for e in exts):
        return 0, ["extensão incompatível"]

    if _algum(rec.get("exclui", []), texto) or _algum(rec.get("exclui", []), nome):
        return 0, ["padrão de exclusão encontrado"]

    pontos = 0
    obrig = rec.get("conteudo_obrigatorio", [])
    conteudo = rec.get("conteudo", [])
    hits_conteudo = _algum(conteudo, texto) if texto else []
    obrig_ok = bool(obrig) and bool(texto) and len(_algum(obrig, texto)) == len(obrig)

    if obrig_ok:
        pontos += 60 + 10 * min(len(hits_conteudo), 3)
        motivos.append("conteúdo obrigatório encontrado")
    elif hits_conteudo and not obrig:
        pontos += 60 + 10 * min(len(hits_conteudo) - 1, 3)
        motivos.append(f"conteúdo: {len(hits_conteudo)} padrão(ões)")
    elif obrig and texto and not obrig_ok:
        # o texto existe mas não traz os elementos obrigatórios: forte indício de que não é esta obrigação
        pontos -= 30

    if _algum(rec.get("nome", []), nome_n):
        if pontos > 0:
            pontos += 35
        elif texto.strip() and (conteudo or obrig):
            # há texto legível e ele não confirma a obrigação: o nome sozinho não basta
            pontos += 35
        else:
            pontos += 50  # PDF digitalizado (imagem) ou formato sem texto: vale o nome
        motivos.append("nome do arquivo")

    pastas = rec.get("pastas", [])
    if pastas and any(p in caminho_n for p in pastas):
        pontos += 10
        motivos.append("pasta do departamento")

    return max(0, min(pontos, 100)), motivos


def classificar(regras: list[Regra], nome: str, texto: str = "", caminho: str = "",
                data_arquivo: datetime | None = None) -> Resultado:
    res = Resultado(cnpjs=extrair_cnpjs(texto) or extrair_cnpjs(nome))
    pontuacoes = []
    for r in regras:
        p, motivos = pontuar(r, nome, texto, caminho)
        if p > 0:
            pontuacoes.append((p, r, motivos))
    pontuacoes.sort(key=lambda x: x[0], reverse=True)
    res.candidatos = [(r.codigo, p) for p, r, _ in pontuacoes[:5]]
    if not pontuacoes or pontuacoes[0][0] < LIMIAR_CLASSIFICACAO:
        res.motivos = ["nenhuma regra atingiu a confiança mínima"]
        return res

    p, regra, motivos = pontuacoes[0]
    # empate técnico entre obrigações diferentes reduz a confiança
    if len(pontuacoes) > 1 and pontuacoes[1][0] == p:
        p -= 15
        motivos.append(f"empate com {pontuacoes[1][1].codigo}")
        if p < LIMIAR_CLASSIFICACAO:
            res.motivos = motivos
            return res
    res.codigo, res.confianca, res.motivos = regra.codigo, p, motivos

    per = regra.periodicidade
    for origem, valor in (
        ("conteudo", extrair_competencia(texto[:5000], per) if texto else None),
        ("nome", extrair_competencia(nome, per)),
        ("pasta", competencia_por_caminho(caminho, per)),
        ("data_arquivo", competencia_por_data(data_arquivo, per)),
    ):
        if valor:
            res.competencia, res.origem_competencia = valor, origem
            break
    return res
