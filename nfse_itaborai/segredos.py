"""Proteção das senhas e chaves gravadas em disco (config.json e .env de cada empresa).

- Windows: DPAPI do usuário (CryptProtectData). Só o mesmo usuário, no mesmo computador, consegue abrir —
  o robô do Agendador roda com o mesmo usuário, então continua funcionando.
- Outros sistemas: AES-256-GCM com uma chave local aleatória (dados_locais/chave.bin, fora das empresas).
- Valores antigos em texto puro continuam aceitos e passam a ser protegidos na próxima gravação.

Se um valor protegido não puder ser aberto (ex.: pasta copiada para outro computador), devolve vazio:
a tela mostra o campo em branco e pede a senha de novo. Para levar as senhas a outro computador, use o
backup protegido por senha (ele leva as senhas dentro, criptografadas pela senha do backup).
"""

from __future__ import annotations

import base64
import os
import sys

PREFIXOS = ("dpapi:", "aesl:")


def _dpapi(dados: bytes, proteger: bool) -> bytes:  # pragma: no cover - só Windows
    import ctypes
    from ctypes import wintypes

    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    buf = ctypes.create_string_buffer(dados, len(dados))
    entrada = BLOB(len(dados), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    saida = BLOB()
    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    desc = ctypes.c_wchar_p("nfse_itaborai")
    CRYPTPROTECT_UI_FORBIDDEN = 0x01
    if proteger:
        ok = crypt32.CryptProtectData(ctypes.byref(entrada), desc, None, None, None, CRYPTPROTECT_UI_FORBIDDEN,
                                      ctypes.byref(saida))
    else:
        ok = crypt32.CryptUnprotectData(ctypes.byref(entrada), None, None, None, None, CRYPTPROTECT_UI_FORBIDDEN,
                                        ctypes.byref(saida))
    if not ok:
        raise OSError("DPAPI recusou a operação")
    try:
        return ctypes.string_at(saida.pbData, saida.cbData)
    finally:
        kernel32.LocalFree(saida.pbData)


def _chave_local() -> bytes:
    from pathlib import Path

    from . import emissor
    arq = Path(os.environ.get("NFSE_CHAVE_LOCAL") or emissor.BASE / "dados_locais" / "chave.bin")
    if not arq.exists():
        arq.parent.mkdir(parents=True, exist_ok=True)
        arq.write_bytes(os.urandom(32))
        try:
            os.chmod(arq, 0o600)
        except OSError:  # pragma: no cover
            pass
    return arq.read_bytes()


def _aes():
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError:  # sem a biblioteca: guarda como está (o sistema continua funcionando)
        return None
    return AESGCM


def usa_dpapi() -> bool:
    return sys.platform == "win32"


def protegido(valor) -> bool:
    return isinstance(valor, str) and valor.startswith(PREFIXOS)


def proteger(valor) -> str:
    if not isinstance(valor, str) or not valor or protegido(valor):
        return valor
    dados = valor.encode("utf-8")
    if usa_dpapi():  # pragma: no cover - só Windows
        try:
            return "dpapi:" + base64.b64encode(_dpapi(dados, True)).decode()
        except OSError:
            pass
    aes = _aes()
    if not aes:
        return valor
    nonce = os.urandom(12)
    return "aesl:" + base64.b64encode(nonce + aes(_chave_local()).encrypt(nonce, dados, b"nfse")).decode()


def revelar(valor) -> str:
    if not protegido(valor):
        return valor
    try:
        bruto = base64.b64decode(valor.split(":", 1)[1])
        if valor.startswith("dpapi:"):  # pragma: no cover - só Windows
            return _dpapi(bruto, False).decode("utf-8")
        aes = _aes()
        return aes(_chave_local()).decrypt(bruto[:12], bruto[12:], b"nfse").decode("utf-8") if aes else ""
    except Exception:  # noqa: BLE001 — outro computador/usuário: a tela pede a senha de novo
        return ""


# ---------------------------------------------------------------- criptografia por senha (backup)

MAGICO = b"NFSEBAK1"


def _derivar(senha: str, sal: bytes) -> bytes:
    import hashlib
    return hashlib.scrypt(senha.encode("utf-8"), salt=sal, n=2 ** 15, r=8, p=1, maxmem=64 * 1024 * 1024, dklen=32)


def cifrar_com_senha(dados: bytes, senha: str, cabecalho: bytes = b"") -> bytes:
    """MAGICO + tamanho do cabeçalho + cabeçalho (legível, autenticado) + sal + nonce + dados cifrados."""
    aes = _aes()
    if not aes:
        raise RuntimeError("Instale o pacote 'cryptography' para proteger o backup com senha.")
    if len(senha or "") < 6:
        raise ValueError("A senha do backup precisa ter ao menos 6 caracteres.")
    sal, nonce = os.urandom(16), os.urandom(12)
    ct = aes(_derivar(senha, sal)).encrypt(nonce, dados, MAGICO + cabecalho)
    return MAGICO + len(cabecalho).to_bytes(4, "big") + cabecalho + sal + nonce + ct


def cabecalho(dados: bytes) -> bytes:
    if not dados.startswith(MAGICO):
        raise ValueError("Arquivo não é um backup protegido deste sistema.")
    n = int.from_bytes(dados[8:12], "big")
    return dados[12:12 + n]


def decifrar_com_senha(dados: bytes, senha: str) -> bytes:
    aes = _aes()
    if not aes:
        raise RuntimeError("Instale o pacote 'cryptography' para abrir backups protegidos por senha.")
    cab = cabecalho(dados)
    resto = dados[12 + len(cab):]
    sal, nonce, ct = resto[:16], resto[16:28], resto[28:]
    try:
        return aes(_derivar(senha or "", sal)).decrypt(nonce, ct, MAGICO + cab)
    except Exception as ex:  # noqa: BLE001 — InvalidTag
        raise ValueError("Senha do backup incorreta (ou arquivo alterado).") from ex


# ---------------------------------------------------------------- PIN de acesso à tela

def hash_pin(pin: str, sal: bytes | None = None) -> str:
    sal = sal or os.urandom(16)
    return base64.b64encode(sal).decode() + "$" + base64.b64encode(_derivar(pin, sal)).decode()


def confere_pin(pin: str, guardado: str) -> bool:
    import hmac
    try:
        sal_b64, h = guardado.split("$", 1)
        return hmac.compare_digest(hash_pin(pin, base64.b64decode(sal_b64)).split("$", 1)[1], h)
    except (ValueError, AttributeError):
        return False
