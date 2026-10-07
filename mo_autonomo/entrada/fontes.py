"""Fontes de e-mail. IMAP é SOMENTE LEITURA (regra 7): EXAMINE + BODY.PEEK, nunca STORE/MOVE/EXPUNGE."""
from __future__ import annotations

import imaplib
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
    def mensagens(self) -> Iterator[EmailBruto]: ...


class FontePastaEml:
    """Lê arquivos .eml de uma pasta (testes e reprocessamento)."""

    def __init__(self, pasta: Path | str):
        self.pasta = Path(pasta)

    def mensagens(self) -> Iterator[EmailBruto]:
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


class FonteImap:
    def __init__(self, host: str, porta: int, usuario: str, senha: str, pasta: str = "INBOX",
                 desde: date | None = None, ssl: bool = True, fabrica=None):
        self.host, self.porta, self.usuario, self.senha = host, porta, usuario, senha
        self.pasta, self.desde, self.ssl = pasta, desde, ssl
        self._fabrica = fabrica
        self.uidvalidity = "0"

    def _conectar(self):
        if self._fabrica:
            con = self._fabrica()
        elif self.ssl:
            con = imaplib.IMAP4_SSL(self.host, self.porta, timeout=60)
        else:
            con = imaplib.IMAP4(self.host, self.porta, timeout=60)
        con.login(self.usuario, self.senha)
        tipo, _ = con.select(self.pasta, readonly=True)  # EXAMINE
        if tipo != "OK":
            raise RuntimeError(f"não foi possível abrir {self.pasta}")
        # UID só é único dentro do UIDVALIDITY (RFC 3501): entra na chave do e-mail
        try:
            _, val = con.response("UIDVALIDITY")
            self.uidvalidity = (val[0].decode() if val and val[0] else "0")
        except Exception:  # noqa: BLE001
            self.uidvalidity = "0"
        return _ImapSomenteLeitura(con)

    def testar(self) -> dict:
        con = self._conectar()
        try:
            tipo, dados = con.uid("search", None, "ALL")
            total = len(dados[0].split()) if tipo == "OK" and dados and dados[0] else 0
            return {"ok": True, "pasta": self.pasta, "mensagens": total}
        finally:
            con.logout()

    def mensagens(self) -> Iterator[EmailBruto]:
        con = self._conectar()
        try:
            criterio = f'SINCE {self.desde.strftime("%d-%b-%Y")}' if self.desde else "ALL"
            tipo, dados = con.uid("search", None, criterio)
            if tipo != "OK":
                raise RuntimeError("falha na busca IMAP")
            for uid in (dados[0].split() if dados and dados[0] else []):
                tipo, partes = con.uid("fetch", uid, "(BODY.PEEK[])")
                if tipo != "OK":
                    continue
                for p in partes:
                    if isinstance(p, tuple):
                        yield EmailBruto(uid=f"imap:{self.pasta}:{self.uidvalidity}:{uid.decode()}", dados=p[1])
        finally:
            try:
                con.logout()
            except Exception:  # noqa: BLE001
                pass
