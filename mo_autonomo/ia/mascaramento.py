"""Mascaramento reversível de dados pessoais antes de enviar texto à IA na nuvem (regra 11)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_SEP = r"[\s./\-\u2013\u2014]{0,3}"
_DATA = re.compile(r"(?<!\d)\d{2}/\d{2}/\d{4}(?!\d)|(?<!\d)\d{2}/\d{4}(?!\d)")
PADROES = {
    # CNPJ alfanumérico (com ou sem pontuação; exige ao menos uma letra) — numérico cai em DOC_NUM
    "CNPJ": re.compile(r"(?<![A-Z0-9])(?=[A-Z0-9./-]*[A-Z])[A-Z0-9]{2}\.?[A-Z0-9]{3}\.?[A-Z0-9]{3}/?[A-Z0-9]{4}-?\d{2}(?![A-Z0-9])",
                       re.IGNORECASE),
    "EMAIL": re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"),
    "TELEFONE": re.compile(r"(?<!\d)(?:\(?\d{2}\)?\s?)?9?\d{4}[\s-]?\d{4}(?!\d)"),
    # qualquer sequência de 11+ dígitos, mesmo com espaço/ponto/barra/hífen entre eles:
    # cobre CPF, CNPJ, chave de acesso impressa em grupos, PIS, contas.
    "DOC_NUM": re.compile(r"(?<!\d)\d(?:" + _SEP + r"\d){10,}(?!\d)"),
}
ORDEM = ("EMAIL", "CNPJ", "DOC_NUM", "TELEFONE")


@dataclass
class Mascara:
    mapa: dict[str, str] = field(default_factory=dict)  # token -> original
    _rev: dict[str, str] = field(default_factory=dict)

    def _token(self, tipo: str, original: str) -> str:
        if original in self._rev:
            return self._rev[original]
        n = sum(1 for t in self.mapa if t.startswith(f"[{tipo}_")) + 1
        tok = f"[{tipo}_{n}]"
        self.mapa[tok] = original
        self._rev[original] = tok
        return tok

    def mascarar(self, texto: str, nomes: list[str] | None = None) -> str:
        # datas são preservadas (a IA precisa da competência): troca por marcador sem dígitos e volta depois
        datas: list[str] = []

        def guardar(m):
            datas.append(m.group(0))
            return f"\x00DATA{_letras(len(datas) - 1)}\x00"
        out = _DATA.sub(guardar, texto)
        for tipo in ORDEM:
            out = PADROES[tipo].sub(lambda m, t=tipo: self._token(t, m.group(0)), out)
        for i, d in enumerate(datas):
            out = out.replace(f"\x00DATA{_letras(i)}\x00", d)
        for nome in sorted(set(n for n in (nomes or []) if n and len(n) >= 3), key=len, reverse=True):
            out = re.sub(re.escape(nome), lambda m: self._token("NOME", m.group(0)), out, flags=re.IGNORECASE)
        return out

    def desmascarar(self, texto: str) -> str:
        out = texto
        for tok, orig in self.mapa.items():
            out = out.replace(tok, orig)
        return out


def _letras(n: int) -> str:
    s = ""
    while True:
        s = chr(65 + n % 26) + s
        n = n // 26 - 1
        if n < 0:
            return s


def contem_dado_pessoal(texto: str) -> list[str]:
    """Guarda final antes da nuvem: checa o texto e também a versão sem espaços/pontuação."""
    sem_datas = _DATA.sub(" ", texto)
    achados = [tipo for tipo in ORDEM if PADROES[tipo].search(sem_datas)]
    compacto = re.sub(r"(?<=[0-9A-Za-z])[\s./\-\u2013\u2014]+(?=[0-9])", "", sem_datas)
    if "DOC_NUM" not in achados and re.search(r"\d{11,}", compacto):
        achados.append("DOC_NUM")
    return achados
