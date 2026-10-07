"""Valores monetários: sempre Decimal, ROUND_HALF_UP no centavo (regra 8)."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CENTAVO = Decimal("0.01")


class ValorInvalido(ValueError):
    pass


def dinheiro(valor) -> Decimal:
    """Converte str/int/Decimal em Decimal arredondado no centavo. float é recusado."""
    if isinstance(valor, float):
        raise ValorInvalido("float não é aceito para valor monetário; use str ou Decimal")
    if isinstance(valor, Decimal):
        d = valor
    elif isinstance(valor, int):
        d = Decimal(valor)
    elif isinstance(valor, str):
        texto = valor.strip()
        if not texto:
            raise ValorInvalido("valor vazio")
        # aceita "1.234,56" (BR) e "1234.56" (XML)
        if "," in texto:
            texto = texto.replace(".", "").replace(",", ".")
        try:
            d = Decimal(texto)
        except InvalidOperation as exc:
            raise ValorInvalido(f"valor inválido: {valor!r}") from exc
    else:
        raise ValorInvalido(f"tipo não suportado: {type(valor).__name__}")
    if not d.is_finite():
        raise ValorInvalido(f"valor não finito: {valor!r}")
    try:
        return d.quantize(CENTAVO, rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise ValorInvalido(f"valor fora da faixa: {valor!r}") from exc


_MILHAR_SEM_CENTAVOS = __import__("re").compile(r"^-?\d{1,3}(\.\d{3})+$")
_MILHAR_VIRGULA = __import__("re").compile(r"^-?\d{1,3}(,\d{3})+$")


def dinheiro_br(valor) -> Decimal:
    """Para valores digitados/exportados no Brasil (CSV, Excel, IA lendo PDF).

    "1.500" sem vírgula é ambíguo (mil e quinhentos ou um e cinquenta?): recusa em vez de chutar.
    Para XML/OFX (ponto decimal por leiaute) use `dinheiro`.
    """
    if isinstance(valor, str):
        t = valor.replace("\xa0", " ").replace("-R$", "-").replace("R$", "").replace(" ", "").strip()
        if "," not in t and _MILHAR_SEM_CENTAVOS.match(t):
            raise ValorInvalido(f"valor ambíguo {valor!r}: use vírgula para os centavos (ex.: 1.500,00)")
        if "." in t and "," in t and t.rfind(".") > t.rfind(","):
            raise ValorInvalido(f"valor em formato americano {valor!r}: use 1.234,56")
        if "." not in t and _MILHAR_VIRGULA.match(t):
            raise ValorInvalido(f"valor ambíguo {valor!r}: vírgula como milhar (1,500?) não é aceita")
        valor = t
    return dinheiro(valor)


def soma(valores) -> Decimal:
    total = Decimal("0.00")
    for v in valores:
        total += dinheiro(v)
    return total.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def formatar_br(valor: Decimal) -> str:
    q = dinheiro(valor)
    sinal = "-" if q < 0 else ""
    inteiro, dec = f"{abs(q):.2f}".split(".")
    grupos = []
    while inteiro:
        grupos.insert(0, inteiro[-3:])
        inteiro = inteiro[:-3]
    return f"{sinal}R$ {'.'.join(grupos)},{dec}"
