"""Mascaramento reversível de dados pessoais antes de enviar texto à IA na nuvem (regra 11)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# quebra de linha só conta como separador depois de pontuação ("123.456.\n789-09", PDF quebrado);
# quebra solta não junta o fim de um valor ("1.234,56") com a linha numérica seguinte
_SEP = r"[ \t./_\-\u2013\u2014]{0,3}(?:(?<=[./\-])\r?\n[ \t]?)?"
_DATA = re.compile(r"(?<!\d)\d{2}/\d{2}/\d{4}(?!\d)|(?<!\d)\d{2}/\d{4}(?!\d)")
PADROES = {
    # CNPJ alfanumérico (com ou sem pontuação; exige ao menos uma letra) — numérico cai em DOC_NUM
    # sem exigir fronteira à esquerda: o texto extraído de PDF cola o rótulo no número ("CNPJ12ABC...")
    "CNPJ": re.compile(r"(?:(?<![A-Z0-9])|(?<=CNPJ)|(?<=CPF))(?=[A-Z0-9./_-]{0,20}?[A-Z])"
                       r"[A-Z0-9]{2}[._]?[A-Z0-9]{3}[._]?[A-Z0-9]{3}[/_]?[A-Z0-9]{4}[_-]?\d{2}(?![A-Z0-9])",
                       re.IGNORECASE),
    "EMAIL": re.compile(r"[\w.+-]+\s*(?:@|\\u0040|&#64;|\(at\)|\[at\])\s*[\w-]+(?:\s*\.\s*[\w-]+)+", re.IGNORECASE),
    "TELEFONE": re.compile(r"(?<!\d)(?:\(?\d{2}\)?\s?)?9?\d{4}[\s.-]?\d{4}(?!\d)"),
    # CPF/CNPJ separado por vírgula (OCR): só no desenho exato, para não engolir valores "1.500,00"
    # só logo após o rótulo CPF/CNPJ, para não engolir quantidade/preço com 3 casas ("10,000 150,000")
    "DOC_VIRGULA": re.compile(r"(?<=CPF|PJ:|PF:|NPJ)[\s:]{0,3}\d{2,3}(?:[,_ ]\d{3}){2}[,_ /]\d{2,4}(?:[,_ -]\d{2})?(?!\d)",
                              re.IGNORECASE),
    # qualquer sequência de 11+ dígitos, mesmo com espaço/ponto/barra/hífen entre eles:
    # cobre CPF, CNPJ, chave de acesso impressa em grupos, PIS, contas.
    "DOC_NUM": re.compile(r"(?<!\d)\d(?:" + _SEP + r"\d){10,}(?!\d)"),
}
ORDEM = ("EMAIL", "CNPJ", "DOC_NUM", "DOC_VIRGULA", "TELEFONE")
_BASE64 = re.compile(r"[A-Za-z0-9+/]{60,}={0,2}")


def _parece_base64(texto: str) -> bool:
    """Bloco codificado: longo E misturando maiúsculas, minúsculas e dígitos (texto colado sem espaço,
    autenticação hexadecimal e linhas de '////' não são)."""
    for m in _BASE64.finditer(texto):
        s = m.group(0)
        if any(c.isupper() for c in s) and any(c.islower() for c in s) and any(c.isdigit() for c in s):
            return True
    return False


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


def _dv_alfa(base: str) -> str:
    """Dígitos verificadores do CNPJ (o alfanumérico usa o valor ASCII − 48 de cada caractere)."""
    def dv(s):
        pesos = list(range(len(s) - 7, 1, -1)) + list(range(9, 1, -1))
        r = sum((ord(c) - 48) * p for c, p in zip(s, pesos)) % 11
        return "0" if r < 2 else str(11 - r)
    d1 = dv(base)
    return d1 + dv(base + d1)


def _cnpj_alfa_escondido(texto: str) -> bool:
    """CNPJ alfanumérico picado por espaços/pontuação ("12 ABC 345 01DE 35"): junta tudo e procura
    janela de 14 caracteres com letra cujos dígitos verificadores batem."""
    # só logo depois do rótulo CNPJ/CPF e com pedaços inteiros: juntar palavras quaisquer ("RECEBIDO" +
    # número) acerta o dígito verificador por acaso ~1 vez em 100 e travaria a nuvem em todo extrato
    pedacos = re.findall(r"[A-Z0-9]+", texto.upper())
    inicios = {j for k, p in enumerate(pedacos) if re.fullmatch(r"(?:CPF|CNPJ|CPFCNPJ)", p)
               for j in range(k + 1, k + 3)}
    for i in sorted(x for x in inicios if x < len(pedacos)):
        s = ""
        for p in pedacos[i:i + 6]:
            s += p
            if len(s) > 14:
                break
            if (len(s) == 14 and s[12:].isdigit() and not s[:12].isdigit() and any(c.isdigit() for c in s[:12])
                    and _dv_alfa(s[:12]) == s[12:]):
                return True
    return False


def contem_dado_pessoal(texto: str) -> list[str]:
    """Guarda final antes da nuvem: checa o texto e também a versão sem espaços/pontuação."""
    sem_datas = _DATA.sub(" ", texto)
    achados = [tipo for tipo in ORDEM if PADROES[tipo].search(sem_datas)]
    compacto = re.sub(r"(?<=[0-9A-Za-z])[\s./_\-\u2013\u2014]+(?=[0-9])", "", sem_datas)
    if "DOC_NUM" not in achados and re.search(r"\d{11,}", compacto):
        achados.append("DOC_NUM")
    if "CNPJ" not in achados and _cnpj_alfa_escondido(sem_datas):
        achados.append("CNPJ")
    if _parece_base64(sem_datas):  # conteúdo codificado não dá para inspecionar: não sai para a nuvem
        achados.append("BASE64")
    return achados
