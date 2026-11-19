"""Cofre de segredos (PFX, senhas de certificado, chaves de API).

- Windows: DPAPI (CryptProtectData) no escopo do USUÁRIO do serviço. Só o mesmo
  usuário Windows, na mesma máquina, consegue decifrar. Uma entropia adicional,
  gerada na instalação, é exigida para decifrar.
- Outros sistemas (desenvolvimento/testes): AES-GCM com chave mestra em arquivo
  com permissão 0600. NÃO é recomendado para produção fora do Windows sem um KMS.

O banco de dados guarda apenas a REFERÊNCIA (nome) do segredo, nunca o conteúdo.
Senhas nunca são registradas em log.
"""

from __future__ import annotations

import ctypes
import os
import re
import secrets
from pathlib import Path

_RE_NOME = re.compile(r"^[a-zA-Z0-9_.-]{1,120}$")


class ErroCofre(RuntimeError):
    pass


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob(dados: bytes) -> _DATA_BLOB:
    buf = ctypes.create_string_buffer(dados, len(dados))
    return _DATA_BLOB(len(dados), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))


def _dpapi(dados: bytes, entropia: bytes, proteger: bool) -> bytes:  # pragma: no cover - só Windows
    crypt32 = ctypes.windll.crypt32  # type: ignore[attr-defined]
    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    entrada, ent, saida = _blob(dados), _blob(entropia), _DATA_BLOB()
    CRYPTPROTECT_UI_FORBIDDEN = 0x01
    fn = crypt32.CryptProtectData if proteger else crypt32.CryptUnprotectData
    ok = fn(ctypes.byref(entrada), None, ctypes.byref(ent), None, None, CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(saida))
    if not ok:
        raise ErroCofre(f"DPAPI falhou (erro {ctypes.GetLastError()})")  # type: ignore[attr-defined]
    try:
        return ctypes.string_at(saida.pbData, saida.cbData)
    finally:
        kernel32.LocalFree(saida.pbData)


class Cofre:
    def __init__(self, pasta: Path, forcar_aesgcm: bool = False):
        self.pasta = Path(pasta)
        self.pasta.mkdir(parents=True, exist_ok=True)
        self.usa_dpapi = os.name == "nt" and not forcar_aesgcm
        self._entropia = self._carregar_ou_criar(self.pasta / ".entropia", 32)

    @property
    def mecanismo(self) -> str:
        return "Windows DPAPI (escopo do usuário)" if self.usa_dpapi else "AES-256-GCM com chave local (modo desenvolvimento)"

    def _carregar_ou_criar(self, caminho: Path, tamanho: int) -> bytes:
        if caminho.exists():
            return caminho.read_bytes()
        valor = secrets.token_bytes(tamanho)
        fd = os.open(caminho, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(valor)
        return valor

    def _caminho(self, nome: str) -> Path:
        if not _RE_NOME.match(nome):
            raise ErroCofre("nome de segredo inválido")
        return self.pasta / f"{nome}.seg"

    def _cifrar(self, dados: bytes) -> bytes:
        if self.usa_dpapi:
            return b"DPAPI1" + _dpapi(dados, self._entropia, True)
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        chave = self._carregar_ou_criar(self.pasta / ".chave-mestra", 32)
        nonce = secrets.token_bytes(12)
        return b"AESG1" + nonce + AESGCM(chave).encrypt(nonce, dados, self._entropia)

    def _decifrar(self, dados: bytes) -> bytes:
        if dados.startswith(b"DPAPI1"):
            return _dpapi(dados[6:], self._entropia, False)
        if dados.startswith(b"AESG1"):
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM

            chave = (self.pasta / ".chave-mestra").read_bytes()
            nonce, ct = dados[5:17], dados[17:]
            return AESGCM(chave).decrypt(nonce, ct, self._entropia)
        raise ErroCofre("formato de segredo desconhecido")

    def guardar(self, nome: str, valor: bytes | str) -> str:
        if isinstance(valor, str):
            valor = valor.encode("utf-8")
        caminho = self._caminho(nome)
        tmp = caminho.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(self._cifrar(valor))
        os.replace(tmp, caminho)
        return nome

    def ler(self, nome: str) -> bytes:
        caminho = self._caminho(nome)
        if not caminho.exists():
            raise ErroCofre(f"segredo '{nome}' não encontrado")
        return self._decifrar(caminho.read_bytes())

    def ler_texto(self, nome: str) -> str:
        return self.ler(nome).decode("utf-8")

    def existe(self, nome: str) -> bool:
        return self._caminho(nome).exists()

    def remover(self, nome: str) -> None:
        caminho = self._caminho(nome)
        if caminho.exists():
            # sobrescreve antes de remover (melhor esforço; SSD pode reter blocos)
            caminho.write_bytes(secrets.token_bytes(caminho.stat().st_size))
            caminho.unlink()
