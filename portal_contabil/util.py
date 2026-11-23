"""Utilitários: números, datas, validação de CNPJ/CPF e chaves de acesso."""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

try:  # parser endurecido contra XML malicioso (billion laughs, XXE)
    from defusedxml import ElementTree as ET  # type: ignore
except ImportError:  # pragma: no cover
    import xml.etree.ElementTree as ET  # noqa: N817

ZERO = Decimal("0")
CENTAVO = Decimal("0.01")


def dec(valor, padrao: Decimal = ZERO) -> Decimal:
    """Converte texto em Decimal aceitando '1234.56' e '1.234,56'."""
    if valor is None:
        return padrao
    if isinstance(valor, Decimal):
        return valor
    s = str(valor).strip()
    if not s:
        return padrao
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        return padrao


def q2(valor: Decimal) -> Decimal:
    return valor.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def moeda(valor: Decimal | None) -> str:
    if valor is None:
        return "-"
    s = f"{q2(valor):,.2f}"
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")


def pct(valor: Decimal | None) -> str:
    if valor is None:
        return "-"
    return f"{q2(valor * 100):.2f}%".replace(".", ",")


def parse_data(texto: str | None) -> date | None:
    if not texto:
        return None
    t = texto.strip()
    try:
        if len(t) >= 10 and t[4] == "-":
            return date.fromisoformat(t[:10])
        if len(t) >= 8 and t[:8].isdigit():  # OFX: AAAAMMDD...
            return datetime.strptime(t[:8], "%Y%m%d").date()
        if len(t) >= 10 and t[2] == "/":
            return datetime.strptime(t[:10], "%d/%m/%Y").date()
    except ValueError:
        return None
    return None


def mes(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def somar_meses(competencia: str, n: int) -> str:
    ano, m = int(competencia[:4]), int(competencia[5:7])
    total = ano * 12 + (m - 1) + n
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


# ---------------------------------------------------------------- documentos

def limpar_doc(doc: str | None) -> str:
    """Remove pontuação mantendo letras (CNPJ alfanumérico - IN RFB 2.229/2024)."""
    return re.sub(r"[^0-9A-Za-z]", "", doc or "").upper()


def _valor_char(c: str) -> int:
    # Regra do CNPJ alfanumérico: valor ASCII - 48 (dígitos 0-9 mantêm o valor).
    return ord(c) - 48


def cnpj_valido(cnpj: str | None) -> bool:
    c = limpar_doc(cnpj)
    if len(c) != 14 or not re.fullmatch(r"[0-9A-Z]{12}[0-9]{2}", c):
        return False
    if len(set(c)) == 1:
        return False
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6] + pesos1
    for pesos, pos in ((pesos1, 12), (pesos2, 13)):
        soma = sum(_valor_char(ch) * p for ch, p in zip(c[:pos], pesos))
        resto = soma % 11
        dv = 0 if resto < 2 else 11 - resto
        if dv != int(c[pos]):
            return False
    return True


def cpf_valido(cpf: str | None) -> bool:
    c = re.sub(r"\D", "", cpf or "")
    if len(c) != 11 or len(set(c)) == 1:
        return False
    for pos in (9, 10):
        soma = sum(int(c[i]) * (pos + 1 - i) for i in range(pos))
        dv = (soma * 10) % 11 % 10
        if dv != int(c[pos]):
            return False
    return True


def documento_valido(doc: str | None) -> bool:
    d = limpar_doc(doc)
    if len(d) == 11:
        return cpf_valido(d)
    if len(d) == 14:
        return cnpj_valido(d)
    return False


def fmt_doc(doc: str | None) -> str:
    d = limpar_doc(doc)
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    if len(d) == 11:
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    return d or "-"


def dv_modulo11(base: str) -> int:
    """DV da chave de acesso (NF-e/NFC-e/CT-e): pesos 2..9 da direita para a esquerda."""
    soma, peso = 0, 2
    for ch in reversed(base):
        soma += _valor_char(ch) * peso
        peso = 2 if peso == 9 else peso + 1
    resto = soma % 11
    return 0 if resto < 2 else 11 - resto


def chave_nfe_valida(chave: str | None) -> bool:
    c = (chave or "").strip().upper()
    if len(c) != 44 or not re.fullmatch(r"[0-9A-Z]{43}[0-9]", c):
        return False
    return dv_modulo11(c[:43]) == int(c[43])


# ---------------------------------------------------------------- XML

def remover_namespaces(raiz):
    for el in raiz.iter():
        if isinstance(el.tag, str) and "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    return raiz


def texto(el, caminho: str, padrao: str = "") -> str:
    if el is None:
        return padrao
    v = el.findtext(caminho)
    return v.strip() if v else padrao


def primeiro(el, *caminhos):
    if el is None:
        return None
    for c in caminhos:
        achado = el.find(c)
        if achado is not None:
            return achado
    return None
