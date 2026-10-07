"""Fontes de e-mail. IMAP é SOMENTE LEITURA (regra 7): EXAMINE + BODY.PEEK, nunca STORE/MOVE/EXPUNGE."""
from __future__ import annotations

import imaplib
import re
import os
from dataclasses import dataclass
from datetime import date
from email import message_from_bytes, policy
from pathlib import Path
from typing import Iterator, Protocol

from ..util.arquivos import sha256_bytes


@dataclass
class EmailBruto:
    uid: str
    dados: bytes

    @property
    def cabecalhos(self) -> dict:
        msg = message_from_bytes(self.dados, policy=policy.default)
        return {"message_id": str(msg.get("Message-ID", "")), "remetente": str(msg.get("From", "")),
                "assunto": str(msg.get("Subject", "")), "data": str(msg.get("Date", ""))}


class FonteEmail(Protocol):
    def mensagens(self, ja_lido=None) -> Iterator[EmailBruto]: ...


class FontePastaEml:
    """Lê arquivos .eml de uma pasta (testes e reprocessamento)."""

    def __init__(self, pasta: Path | str):
        self.pasta = Path(pasta)

    def mensagens(self, ja_lido=None) -> Iterator[EmailBruto]:
        for arq in sorted(self.pasta.glob("*.eml")):
            dados = arq.read_bytes()
            yield EmailBruto(uid=f"eml:{sha256_bytes(dados)[:24]}", dados=dados)


def obter_senha(servico: str, usuario: str, variavel_ambiente: str | None = None) -> str:
    """Senha só do keyring do Windows ou de variável de ambiente (regra 11)."""
    if variavel_ambiente and os.environ.get(variavel_ambiente):
        return os.environ[variavel_ambiente]
    try:
        import keyring  # type: ignore
    except ImportError as exc:
        raise RuntimeError("instale 'keyring' ou defina a variável de ambiente da senha") from exc
    senha = keyring.get_password(servico, usuario)
    if not senha:
        raise RuntimeError(f"senha de {usuario} não encontrada no keyring (serviço {servico})")
    return senha


class OperacaoProibida(RuntimeError):
    pass


class _ImapSomenteLeitura:
    """Envoltório que bloqueia comandos que alteram a caixa."""

    PROIBIDOS = {"store", "copy", "move", "expunge", "delete", "append", "rename", "create", "uid_store"}

    def __init__(self, con):
        self._con = con

    def __getattr__(self, nome):
        if nome.lower() in self.PROIBIDOS:
            raise OperacaoProibida(f"IMAP somente leitura: comando {nome} bloqueado")
        return getattr(self._con, nome)

    def uid(self, comando, *args):
        if comando.lower() not in ("search", "fetch"):
            raise OperacaoProibida(f"IMAP somente leitura: UID {comando} bloqueado")
        if comando.lower() == "fetch" and "PEEK" not in " ".join(map(str, args)).upper():
            raise OperacaoProibida("FETCH sem BODY.PEEK marcaria a mensagem como lida")
        return self._con.uid(comando, *args)


_LISTA = re.compile(r'^\((?P<flags>[^)]*)\)\s+(?:"[^"]*"|NIL)\s+(?P<nome>.+)$')


def _nome_pasta(linha: bytes) -> tuple[str, str] | None:
    """Interpreta uma linha do LIST: devolve (nome, flags) ou None."""
    m = _LISTA.match(linha.decode("utf-8", "replace") if isinstance(linha, bytes) else str(linha))
    if not m:
        return None
    nome = m.group("nome").strip()
    if nome.startswith('"') and nome.endswith('"'):
        nome = nome[1:-1].replace('\\"', '"')
    return nome, m.group("flags")


class FonteImap:
    """Uma caixa IMAP. `pasta="*"` lê TODAS as pastas (ex.: INBOX.<empresa>), sempre em EXAMINE."""

    def __init__(self, host: str, porta: int, usuario: str, senha, pasta: str = "INBOX",
                 desde: date | None = None, ssl: bool = True, fabrica=None, ignorar: tuple = ()):
        self.host, self.porta, self.usuario, self.senha = host, porta, usuario, senha
        self.pasta, self.desde, self.ssl = pasta, desde, ssl
        self._fabrica = fabrica
        self.ignorar = tuple(x.lower() for x in ignorar)
        self.uidvalidity = "0"

    def _login(self):
        if self._fabrica:
            con = self._fabrica()
        elif self.ssl:
            con = imaplib.IMAP4_SSL(self.host, self.porta, timeout=60)
        else:
            con = imaplib.IMAP4(self.host, self.porta, timeout=60)
        senha = self.senha() if callable(self.senha) else self.senha  # senha lida do keyring só na hora
        con.login(self.usuario, senha)
        return con

    def _examinar(self, con, pasta: str) -> str:
        """Abre a pasta só para leitura (EXAMINE) e devolve o UIDVALIDITY (RFC 3501)."""
        nome = f'"{pasta}"' if " " in pasta and not pasta.startswith('"') else pasta
        tipo, _ = con.select(nome, readonly=True)
        if tipo != "OK":
            raise RuntimeError(f"não foi possível abrir {pasta}")
        try:
            _, val = con.response("UIDVALIDITY")
            return val[0].decode() if val and val[0] else "0"
        except Exception:  # noqa: BLE001
            return "0"

    def _conectar(self):
        con = self._login()
        self.uidvalidity = self._examinar(con, "INBOX" if self.pasta == "*" else self.pasta)
        return _ImapSomenteLeitura(con)

    def pastas(self, con) -> list[str]:
        if self.pasta != "*":
            return [self.pasta]
        tipo, linhas = con.list()
        if tipo != "OK":
            raise RuntimeError("falha ao listar pastas IMAP")
        out = []
        for l in linhas or []:
            r = _nome_pasta(l)
            if not r or "\\noselect" in r[1].lower():
                continue
            if any(r[0].lower().startswith(x) for x in self.ignorar):
                continue
            out.append(r[0])
        return out or ["INBOX"]

    def testar(self) -> dict:
        con = self._conectar()
        try:
            pastas = self.pastas(con)
            total = 0
            for pasta in pastas:
                self._examinar(con, pasta)
                tipo, dados = con.uid("search", None, "ALL")
                total += len(dados[0].split()) if tipo == "OK" and dados and dados[0] else 0
            return {"ok": True, "pastas": len(pastas), "mensagens": total}
        finally:
            con.logout()

    def mensagens(self, ja_lido=None) -> Iterator[EmailBruto]:
        """`ja_lido(chave)`: pula o FETCH de e-mails já registrados na trilha (não baixa o mês toda hora)."""
        con = self._conectar()
        try:
            criterio = f'SINCE {self.desde.strftime("%d-%b-%Y")}' if self.desde else "ALL"
            for pasta in self.pastas(con):
                validade = self._examinar(con, pasta)
                self.uidvalidity = validade
                tipo, dados = con.uid("search", None, criterio)
                if tipo != "OK":
                    raise RuntimeError(f"falha na busca IMAP em {pasta}")
                for uid in (dados[0].split() if dados and dados[0] else []):
                    chave = f"imap:{self.usuario.lower()}:{pasta}:{validade}:{uid.decode()}"
                    if ja_lido is not None and ja_lido(chave):
                        continue
                    tipo, partes = con.uid("fetch", uid, "(BODY.PEEK[])")
                    if tipo != "OK":
                        continue
                    for p in partes:
                        if isinstance(p, tuple):
                            yield EmailBruto(uid=chave, dados=p[1])
        finally:
            try:
                con.logout()
            except Exception:  # noqa: BLE001
                pass


class FonteMultipla:
    """Lê várias caixas (fiscal@, moraes@, contabil@, dp@...). Uma caixa com problema não para as outras:
    o erro fica em `erros` e o ciclo transforma em pendência dizendo qual caixa falhou."""

    def __init__(self, fontes: list):
        self.fontes = fontes
        self.erros: list[str] = []

    def mensagens(self, ja_lido=None) -> Iterator[EmailBruto]:
        self.erros = []
        for f in self.fontes:
            nome = getattr(f, "usuario", None) or getattr(f, "pasta", "?")
            try:
                yield from f.mensagens(ja_lido=ja_lido)
            except Exception as exc:  # noqa: BLE001
                self.erros.append(f"{nome}: {type(exc).__name__}: {exc}")

    def testar(self) -> list[dict]:
        out = []
        for f in self.fontes:
            try:
                out.append({"caixa": f.usuario, **f.testar()})
            except Exception as exc:  # noqa: BLE001
                out.append({"caixa": getattr(f, "usuario", "?"), "ok": False, "erro": f"{type(exc).__name__}: {exc}"})
        return out
