"""Mascaramento reversível de dados pessoais antes de enviar texto à IA na nuvem (regra 11)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_SEP = r"[\s./-]?"
PADROES = {
    # CNPJ alfanumérico (formato pontuado) — numérico cai em DOC_NUM abaixo
    "CNPJ": re.compile(r"(?<![A-Z0-9])[A-Z0-9]{2}\.[A-Z0-9]{3}\.[A-Z0-9]{3}/[A-Z0-9]{4}-\d{2}(?![A-Z0-9])"),
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
        out = texto
        for tipo in ORDEM:
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
    return [tipo for tipo in ORDEM if PADROES[tipo].search(texto)]
