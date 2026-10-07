"""Mascaramento reversível de dados pessoais antes de enviar texto à IA na nuvem (regra 11)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

PADROES = {
    "CNPJ": re.compile(r"(?<!\d)\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}(?!\d)"),
    "CPF": re.compile(r"(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)"),
    "EMAIL": re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"),
    "TELEFONE": re.compile(r"(?<!\d)(?:\(?\d{2}\)?\s?)?9?\d{4}-?\d{4}(?!\d)"),
    "CHAVE_DFE": re.compile(r"(?<!\d)\d{44}(?!\d)"),
}


@dataclass
class Mascara:
    mapa: dict[str, str] = field(default_factory=dict)  # token -> original
    _rev: dict[str, str] = field(default_factory=dict)

    def _token(self, tipo: str, original: str) -> str:
        if original in self._rev:
            return self._rev[original]
        tok = f"[{tipo}_{len(self.mapa) + 1}]"
        self.mapa[tok] = original
        self._rev[original] = tok
        return tok

    def mascarar(self, texto: str, nomes: list[str] | None = None) -> str:
        out = texto
        for tipo in ("CHAVE_DFE", "CNPJ", "CPF", "EMAIL", "TELEFONE"):
            out = PADROES[tipo].sub(lambda m, t=tipo: self._token(t, m.group(0)), out)
        for nome in sorted(set(n for n in (nomes or []) if n and len(n) >= 3), key=len, reverse=True):
            out = re.sub(re.escape(nome), lambda m: self._token("NOME", m.group(0)), out, flags=re.IGNORECASE)
        return out

    def desmascarar(self, texto: str) -> str:
        out = texto
        for tok, orig in self.mapa.items():
            out = out.replace(tok, orig)
        return out


def contem_dado_pessoal(texto: str) -> list[str]:
    achados = []
    for tipo in ("CNPJ", "CPF", "EMAIL", "CHAVE_DFE"):
        if PADROES[tipo].search(texto):
            achados.append(tipo)
    return achados
