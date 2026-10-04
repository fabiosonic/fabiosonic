"""Licença de uso por período (mensalidade).

Como funciona:
- O fornecedor gera a chave de licença com o Gerador de Licenças (fica só com ele, com a chave PRIVADA). A chave
  traz cliente, CNPJ, validade e quantidade de empresas, assinada digitalmente (RSA 2048, SHA-256).
- O sistema só tem a chave PÚBLICA: confere a assinatura, mas não consegue criar licenças. Alterar a validade ou o
  CNPJ dentro da chave invalida a assinatura.
- A licença vale para o CNPJ da empresa principal da instalação.
- Sem licença: período de avaliação. Vencida: alguns dias de carência com aviso e, depois, o sistema bloqueia as
  funções (emissão, cobrança, robô). Consulta, backup e a própria ativação continuam disponíveis.
- Relógio atrasado de propósito (para "voltar no tempo") é detectado: o sistema guarda a maior data já vista.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import date, timedelta
from pathlib import Path

from . import emissor

PREFIXO = "NFSE1"
TESTE_DIAS = 15          # avaliação sem licença
CARENCIA_DIAS = 5        # depois do vencimento: funciona com aviso
AVISO_DIAS = 10          # antes do vencimento: aviso no painel

# Chave pública do fornecedor (a privada fica só no Gerador de Licenças)
CHAVE_PUBLICA = {"e": 65537, "n": int(
    "2760369966245183318331634153624312371174686283207248233892411061109556478399703398691811665506713854"
    "3111705012971226178548786844686881887534587102076568589329407156010208272000296222487003884283008590"
    "6758329035053767137184295016889422786436325459833106888859231688947667185079181080113069987093323766"
    "7857386539541400029212570448581855270040726058829337787065012437901878414161774743234405129348802209"
    "7677983971696533407236337762905612722527518790529945062490285433626107812610333087498625682966671181"
    "9600619630184957243152978485096634348905320843655294060250290451948626584489232065478871706430856811"
    "47927131458211319"
)}

# Contato exibido na tela de licença: arquivo fornecedor.json na pasta do programa (o fornecedor preenche antes de
# distribuir): {"nome": "...", "whatsapp": "...", "email": "..."}
FORNECEDOR: dict = {}


def fornecedor() -> dict:
    if FORNECEDOR:
        return FORNECEDOR
    d = _ler_json(emissor.BASE / "fornecedor.json")
    return {k: str(d.get(k) or "") for k in ("nome", "whatsapp", "email")}

# rotas que funcionam mesmo com a licença bloqueada (ver dados, guardar backup, ativar a licença, sair)
ROTAS_LIVRES = {"estado", "licenca/status", "licenca/ativar", "sistema/encerrar", "backup/criar", "backup/listar",
                "backup/abrir_pasta", "painel"}

_SHA256_DER = bytes.fromhex("3031300d060960864801650304020105000420")


# ---------------------------------------------------------------- criptografia (só biblioteca padrão)

def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _em(msg: bytes, k: int) -> bytes:
    """EMSA-PKCS1-v1_5 (RFC 8017, 9.2) com SHA-256."""
    t = _SHA256_DER + hashlib.sha256(msg).digest()
    if k < len(t) + 11:
        raise ValueError("chave curta demais")
    return b"\x00\x01" + b"\xff" * (k - len(t) - 3) + b"\x00" + t


def _primo_provavel(n: int, rodadas: int = 40) -> bool:
    if n < 2:
        return False
    for p in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        if n % p == 0:
            return n == p
    d, r = n - 1, 0
    while d % 2 == 0:
        d //= 2
        r += 1
    for _ in range(rodadas):
        x = pow(secrets.randbelow(n - 3) + 2, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(r - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def _primo(bits: int, e: int) -> int:
    while True:
        p = secrets.randbits(bits) | (1 << (bits - 1)) | (1 << (bits - 2)) | 1
        if p % e != 1 and _primo_provavel(p):
            return p


def gerar_chaves(bits: int = 2048) -> tuple[dict, dict]:
    """(pública, privada). Usado pelo Gerador de Licenças e pelos testes."""
    e = 65537
    while True:
        p, q = _primo(bits // 2, e), _primo(bits // 2, e)
        n = p * q
        if p != q and n.bit_length() == bits:
            break
    d = pow(e, -1, (p - 1) * (q - 1))
    return {"e": e, "n": n}, {"e": e, "n": n, "d": d}


def emitir(dados: dict, privada: dict) -> str:
    """Chave de licença assinada (texto para copiar e colar)."""
    payload = json.dumps(dados, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    k = (privada["n"].bit_length() + 7) // 8
    s = pow(int.from_bytes(_em(payload, k), "big"), privada["d"], privada["n"])
    return f"{PREFIXO}-{_b64e(payload)}.{_b64e(s.to_bytes(k, 'big'))}"


def ler(chave: str, publica: dict | None = None) -> dict:
    """Confere a assinatura e devolve os dados da licença; chave alterada ou de outro fornecedor -> ValueError."""
    pub = publica or CHAVE_PUBLICA
    txt = "".join(str(chave or "").split())
    if not txt.startswith(PREFIXO + "-") or "." not in txt:
        raise ValueError("Chave de licença inválida (formato).")
    try:
        p64, s64 = txt[len(PREFIXO) + 1:].split(".", 1)
        payload, sig = _b64d(p64), _b64d(s64)
    except (ValueError, TypeError):
        raise ValueError("Chave de licença inválida (formato).") from None
    k = (pub["n"].bit_length() + 7) // 8
    if len(sig) != k or pub["n"] < 2 ** 1000:
        raise ValueError("Chave de licença inválida (assinatura).")
    m = pow(int.from_bytes(sig, "big"), pub["e"], pub["n"])
    if not hmac.compare_digest(m.to_bytes(k, "big"), _em(payload, k)):
        raise ValueError("Chave de licença inválida: a assinatura não confere (chave alterada ou de outro fornecedor).")
    dados = json.loads(payload.decode())
    if not dados.get("validade"):
        raise ValueError("Chave de licença sem validade.")
    date.fromisoformat(dados["validade"])
    return dados


# ---------------------------------------------------------------- estado da instalação

def _arquivo() -> Path:
    return emissor.BASE / "dados" / "licenca.json"


def _espelho() -> Path:
    """Cópia do controle fora da pasta do programa (apagar dados/licenca.json não reinicia a avaliação)."""
    chave = hashlib.sha256(str(Path(emissor.BASE).resolve()).lower().encode()).hexdigest()[:16]
    return Path(os.environ.get("APPDATA") or Path.home()) / ".emissor_nfse" / f"{chave}.json"


def _ler_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _estado() -> dict:
    a, b = _ler_json(_arquivo()), _ler_json(_espelho())
    inicio = min(x for x in (a.get("teste_inicio"), b.get("teste_inicio")) if x) if (a.get("teste_inicio") or b.get("teste_inicio")) else ""
    maior = max((a.get("maior_data") or ""), (b.get("maior_data") or ""))
    return {"chave": a.get("chave") or b.get("chave") or "", "teste_inicio": inicio, "maior_data": maior}


def _gravar(est: dict) -> None:
    for p in (_arquivo(), _espelho()):
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(est, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass


def _hoje() -> date:
    from . import horario
    return horario.agora().date()


def cnpj_instalacao() -> str:
    """CNPJ da empresa principal (a da pasta do programa)."""
    return emissor.so_digitos(emissor.ler_env(emissor.BASE / ".env").get("ITABORAI_CNPJ", ""))


def situacao(hoje: date | None = None) -> dict:
    """Situação da licença: liberado (bool), status (ativa | aviso | carencia | teste | bloqueada) e a mensagem."""
    hoje = hoje or _hoje()
    est = _estado()
    mudou = False
    if est["maior_data"] and hoje < date.fromisoformat(est["maior_data"]) - timedelta(days=1):
        return {"liberado": False, "status": "bloqueada", "relogio": True, "cnpj_instalacao": cnpj_instalacao(),
                "fornecedor": fornecedor(),
                "mensagem": f"A data do computador ({hoje:%d/%m/%Y}) está anterior ao último uso do sistema "
                            f"({date.fromisoformat(est['maior_data']):%d/%m/%Y}). Acerte a data e a hora do Windows."}
    if hoje.isoformat() > est["maior_data"]:
        est["maior_data"], mudou = hoje.isoformat(), True
    base = {"cnpj_instalacao": cnpj_instalacao(), "fornecedor": fornecedor()}
    lic, erro = None, ""
    if est["chave"]:
        try:
            lic = ler(est["chave"])
            cnpj = emissor.so_digitos(lic.get("cnpj", ""))
            if cnpj and base["cnpj_instalacao"] and cnpj != base["cnpj_instalacao"]:
                erro = (f"A licença é do CNPJ {_fmt(cnpj)}, mas esta instalação é do CNPJ "
                        f"{_fmt(base['cnpj_instalacao'])}.")
                lic = None
        except ValueError as ex:
            erro, lic = str(ex), None
    if lic:
        validade = date.fromisoformat(lic["validade"])
        dias = (validade - hoje).days
        dados = base | {"cliente": lic.get("cliente", ""), "cnpj": lic.get("cnpj", ""), "validade": lic["validade"],
                        "empresas": int(lic.get("empresas") or 0), "id": lic.get("id", ""), "dias": dias}
        if mudou:
            _gravar(est)
        if dias >= 0:
            return dados | {"liberado": True, "status": "aviso" if dias <= AVISO_DIAS else "ativa",
                            "mensagem": f"Licença válida até {validade:%d/%m/%Y}"
                                        + (f" — faltam {dias} dia(s): renove para não interromper." if dias <= AVISO_DIAS else ".")}
        if dias >= -CARENCIA_DIAS:
            return dados | {"liberado": True, "status": "carencia",
                            "mensagem": f"Licença vencida em {validade:%d/%m/%Y}. O sistema bloqueia em "
                                        f"{CARENCIA_DIAS + dias + 1} dia(s): renove a licença."}
        return dados | {"liberado": False, "status": "bloqueada",
                        "mensagem": f"Licença vencida em {validade:%d/%m/%Y}. Ative uma nova chave para continuar."}
    if not est["teste_inicio"]:
        est["teste_inicio"], mudou = hoje.isoformat(), True
    if mudou:
        _gravar(est)
    resta = TESTE_DIAS - (hoje - date.fromisoformat(est["teste_inicio"])).days
    if resta > 0:
        return base | {"liberado": True, "status": "teste", "dias": resta, "erro_chave": erro,
                       "mensagem": f"Período de avaliação: {resta} dia(s) restante(s)." + (f" {erro}" if erro else "")}
    return base | {"liberado": False, "status": "bloqueada", "erro_chave": erro,
                   "mensagem": (erro + " " if erro else "") + "O período de avaliação terminou. Ative a chave de licença."}


def _fmt(c: str) -> str:
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}" if len(c) == 14 else c


def ativar(chave: str) -> dict:
    """Grava a chave (depois de conferida) e devolve a nova situação."""
    lic = ler(chave)
    cnpj, inst = emissor.so_digitos(lic.get("cnpj", "")), cnpj_instalacao()
    if cnpj and inst and cnpj != inst:
        raise ValueError(f"Esta licença é do CNPJ {_fmt(cnpj)}; esta instalação é do CNPJ {_fmt(inst)}.")
    if date.fromisoformat(lic["validade"]) < _hoje() - timedelta(days=CARENCIA_DIAS):
        raise ValueError(f"Esta chave já venceu em {date.fromisoformat(lic['validade']):%d/%m/%Y}.")
    est = _estado()
    est["chave"] = "".join(str(chave).split())
    _gravar(est)
    from . import db
    try:
        db.registrar("licenca", f"Licença ativada: {lic.get('cliente', '')} até {lic['validade']}")
    except Exception:  # noqa: BLE001 — registrar no log é secundário
        pass
    return situacao()


def liberado() -> bool:
    return situacao()["liberado"]


def limite_empresas() -> int:
    """0 = sem limite (ou em avaliação)."""
    s = situacao()
    return int(s.get("empresas") or 0) if s.get("status") not in ("teste",) else 0
