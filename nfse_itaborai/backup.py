"""Backup e restauração completos de cada empresa.

O backup é um .zip com tudo o que é da empresa: banco de dados (cópia consistente), clientes, configurações,
serviços, numeração, credenciais (.env), certificados e os XML/notas enviados (saida/). Fica em dados/backup da
própria empresa (nunca misturado com outra) e, se configurado, também é copiado para uma segunda pasta
(pendrive, HD externo, pasta sincronizada com a nuvem).

Restauração com segurança:
- só restaura backup da mesma empresa (CNPJ do manifesto = CNPJ da empresa);
- antes de restaurar, faz um backup do estado atual (dá para desfazer);
- a numeração do RPS/DPS nunca volta atrás (evita repetir número já enviado à prefeitura/Sefin);
- o ambiente (homologação/produção) continua o atual: restauração nunca liga a produção;
- só aceita caminhos conhecidos dentro do .zip (nada fora da pasta da empresa).
"""

from __future__ import annotations

import base64
import json
import re
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath

from . import __version__, emissor
from .xml_rps import so_digitos

ARQUIVOS_RAIZ = (".env", "servicos.json", "servico_padrao.json")
PASTAS = ("dados", "saida")
MANIFESTO = "backup.json"
MANTER_AUTOMATICOS = 30
CHAVES_PRESERVADAS_ENV = ("ITABORAI_AMBIENTE", "ITABORAI_CIENTE_IRREVERSIVEL")


def pasta_backups(raiz: Path | None = None) -> Path:
    p = (raiz or emissor.raiz()) / "dados" / "backup"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _cnpj(raiz: Path | None = None) -> str:
    with emissor.usar_empresa(raiz or emissor.raiz()):
        return so_digitos(emissor.env("ITABORAI_CNPJ"))


def _nome_empresa(raiz: Path) -> str:
    try:
        return json.loads((raiz / "dados" / "config.json").read_text(encoding="utf-8"))["empresa"].get("nome", "")
    except (OSError, ValueError, KeyError):
        return ""


def _arquivos(raiz: Path):
    """Arquivos da empresa que entram no backup (caminho relativo com /)."""
    for nome in ARQUIVOS_RAIZ:
        if (raiz / nome).is_file():
            yield nome
    for pasta in PASTAS:
        base = raiz / pasta
        if not base.is_dir():
            continue
        for arq in sorted(base.rglob("*")):
            rel = arq.relative_to(raiz).as_posix()
            if not arq.is_file() or rel.startswith("dados/backup/") or rel == "dados/sistema.db" \
                    or rel.endswith(("-journal", "-wal", "-shm")):
                continue
            yield rel


def criar(motivo: str = "manual", raiz: Path | None = None) -> dict:
    """Gera o .zip do backup da empresa e devolve as informações dele."""
    raiz = raiz or emissor.raiz()
    agora = datetime.now(emissor.FUSO)
    cnpj = _cnpj(raiz)
    destino = pasta_backups(raiz) / f"backup_{cnpj or 'empresa'}_{agora:%Y-%m-%d_%H%M%S}_{motivo}.zip"
    manifesto = {"sistema": "nfse_itaborai", "versao_backup": 1, "versao_sistema": __version__, "cnpj": cnpj,
                 "empresa": _nome_empresa(raiz), "criado_em": agora.strftime("%Y-%m-%d %H:%M:%S"), "motivo": motivo}
    with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        banco = raiz / "dados" / "sistema.db"
        if banco.exists():   # cópia consistente mesmo com o sistema aberto
            copia = Path(tmp) / "sistema.db"
            with sqlite3.connect(banco) as origem, sqlite3.connect(copia) as dst:
                origem.backup(dst)
            z.write(copia, "dados/sistema.db")
        arquivos = list(_arquivos(raiz))
        for rel in arquivos:
            z.write(raiz / rel, rel)
        manifesto["arquivos"] = len(arquivos) + banco.exists()
        z.writestr(MANIFESTO, json.dumps(manifesto, indent=2, ensure_ascii=False))
    copia_extra = _copiar_para_pasta_extra(destino, raiz)
    _limpar_antigos(raiz)
    return _info(destino) | {"copia": copia_extra}


def _copiar_para_pasta_extra(arq: Path, raiz: Path) -> str:
    try:
        cfg = json.loads((raiz / "dados" / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    extra = str(cfg.get("pastas", {}).get("backup_copia") or "").strip()
    if not extra:
        return ""
    try:
        destino = Path(extra).expanduser() / (_cnpj(raiz) or "empresa")
        destino.mkdir(parents=True, exist_ok=True)
        shutil.copy2(arq, destino / arq.name)
        return str(destino / arq.name)
    except OSError as ex:  # pendrive fora, pasta sem permissão: o backup local continua valendo
        from . import db
        db.registrar("backup", f"Cópia extra não feita em {extra}: {ex}")
        return ""


def _limpar_antigos(raiz: Path) -> None:
    autos = sorted(pasta_backups(raiz).glob("backup_*_automatico.zip"))
    for velho in autos[:-MANTER_AUTOMATICOS]:
        velho.unlink()


def automatico(raiz: Path | None = None) -> str:
    """Robô: um backup completo por dia."""
    raiz = raiz or emissor.raiz()
    hoje = datetime.now(emissor.FUSO).strftime("%Y-%m-%d")
    feito = next(pasta_backups(raiz).glob(f"backup_*_{hoje}_*_automatico.zip"), None)
    return feito.name if feito else criar("automatico", raiz)["nome"]


def _info(arq: Path) -> dict:
    try:
        with zipfile.ZipFile(arq) as z:
            m = json.loads(z.read(MANIFESTO))
    except (OSError, KeyError, ValueError, zipfile.BadZipFile):
        m = {}
    return {"nome": arq.name, "tamanho": arq.stat().st_size, "criado_em": m.get("criado_em", ""),
            "motivo": m.get("motivo", ""), "cnpj": m.get("cnpj", ""), "empresa": m.get("empresa", ""),
            "versao_sistema": m.get("versao_sistema", ""), "valido": bool(m)}


def listar() -> list[dict]:
    return [_info(a) for a in sorted(pasta_backups().glob("backup_*.zip"), reverse=True)]


def arquivo(nome: str) -> Path:
    """Caminho de um backup desta empresa pelo nome (sem permitir sair da pasta)."""
    if not re.fullmatch(r"[\w.-]+\.zip", nome or ""):
        raise ValueError("Nome de backup inválido.")
    p = pasta_backups() / nome
    if not p.is_file():
        raise ValueError("Backup não encontrado.")
    return p


def _caminho_permitido(nome: str) -> bool:
    p = PurePosixPath(nome)
    if p.is_absolute() or ".." in p.parts or "\\" in nome or nome.endswith("/"):
        return False
    if nome in ARQUIVOS_RAIZ or nome == MANIFESTO:
        return True
    return p.parts[0] in PASTAS and not nome.startswith("dados/backup/")


def ler_manifesto(zip_path: Path) -> dict:
    try:
        with zipfile.ZipFile(zip_path) as z:
            m = json.loads(z.read(MANIFESTO))
            nomes = z.namelist()
    except (KeyError, ValueError, zipfile.BadZipFile) as ex:
        raise ValueError("Arquivo não é um backup deste sistema.") from ex
    if m.get("sistema") != "nfse_itaborai":
        raise ValueError("Arquivo não é um backup deste sistema.")
    ruins = [n for n in nomes if not _caminho_permitido(n)]
    if ruins:
        raise ValueError(f"Backup com arquivos fora do padrão ({ruins[0]}); restauração recusada.")
    return m


def _numeros(raiz: Path) -> dict:
    """Numerações atuais (RPS, lote, DPS) — a restauração nunca as faz voltar."""
    out: dict = {}
    seq = raiz / "dados" / "sequencia.json"
    if seq.exists():
        try:
            out.update({k: int(v) for k, v in json.loads(seq.read_text(encoding="utf-8")).items()
                        if str(v).isdigit()})
        except ValueError:
            pass
    env = emissor.ler_env(raiz / ".env")
    for var, chave in (("ITABORAI_PROXIMO_RPS", "proximo_rps"), ("ITABORAI_PROXIMO_LOTE", "proximo_lote")):
        if env.get(var, "").isdigit():
            out[chave] = max(out.get(chave, 0), int(env[var]))
    try:
        dps = json.loads((raiz / "dados" / "config.json").read_text(encoding="utf-8"))["emissao"].get("proximo_dps")
        out["proximo_dps"] = max(out.get("proximo_dps", 0), int(dps or 0))
    except (OSError, ValueError, KeyError):
        pass
    return out


def _gravar_env(raiz: Path, valores: dict) -> None:
    arq = raiz / ".env"
    linhas = arq.read_text(encoding="utf-8").splitlines() if arq.exists() else []
    linhas = [l for l in linhas if l.split("=", 1)[0].strip() not in valores]
    arq.write_text("\n".join(linhas + [f"{k}={v}" for k, v in valores.items()]) + "\n", encoding="utf-8")


def restaurar(zip_path: Path, raiz: Path | None = None) -> dict:
    """Volta a empresa ao estado do backup (com backup prévio do estado atual)."""
    raiz = raiz or emissor.raiz()
    m = ler_manifesto(zip_path)
    atual = _cnpj(raiz)
    if atual and m.get("cnpj") and m["cnpj"] != atual:
        raise ValueError(f"Este backup é da empresa {m.get('empresa') or ''} (CNPJ {m['cnpj']}) e não pode ser "
                         f"restaurado na empresa em uso (CNPJ {atual}). Os dados de uma empresa nunca vão para outra.")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(tmp)   # caminhos já validados em ler_manifesto
        banco = tmp / "dados" / "sistema.db"
        if banco.exists():
            with sqlite3.connect(banco) as con:
                if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError("O banco de dados deste backup está corrompido; restauração recusada.")
        antes = criar("antes_da_restauracao", raiz) if (raiz / "dados").exists() else None
        numeros = _numeros(raiz)
        env_atual = emissor.ler_env(raiz / ".env")
        # dados/: o estado (banco, clientes, configurações...) passa a ser o do backup; certificados e pastas
        # que não vieram no backup continuam; backups ficam intactos.
        dados = raiz / "dados"
        dados.mkdir(parents=True, exist_ok=True)
        for arq in dados.iterdir():
            if arq.is_file() and not (tmp / "dados" / arq.name).exists():
                arq.unlink()
        for arq in sorted(tmp.rglob("*")):
            rel = arq.relative_to(tmp).as_posix()
            if arq.is_dir() or rel == MANIFESTO:
                continue
            alvo = raiz / rel
            alvo.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(arq, alvo)
    # numeração nunca volta; ambiente continua o atual (homologação se não havia nada)
    seq = dados / "sequencia.json"
    salvo = json.loads(seq.read_text(encoding="utf-8")) if seq.exists() else {}
    for k, v in numeros.items():
        salvo[k] = max(int(salvo.get(k, 0) or 0), v)
    if salvo:
        seq.write_text(json.dumps(salvo, indent=2), encoding="utf-8")
    env_novo = {k: env_atual.get(k) or ("homologacao" if k == "ITABORAI_AMBIENTE" else "NAO")
                for k in CHAVES_PRESERVADAS_ENV}
    restaurado = emissor.ler_env(raiz / ".env")
    for var, chave in (("ITABORAI_PROXIMO_RPS", "proximo_rps"), ("ITABORAI_PROXIMO_LOTE", "proximo_lote")):
        if chave in salvo:
            env_novo[var] = str(max(int(salvo[chave]), int(restaurado.get(var, "0") or 0)))
    _gravar_env(raiz, env_novo)
    cfg = dados / "config.json"
    if cfg.exists() and "proximo_dps" in salvo:
        c = json.loads(cfg.read_text(encoding="utf-8"))
        c.setdefault("emissao", {})["proximo_dps"] = max(int(c["emissao"].get("proximo_dps", 1) or 1), salvo["proximo_dps"])
        cfg.write_text(json.dumps(c, indent=2, ensure_ascii=False), encoding="utf-8")
    from . import db
    db.registrar("backup", f"Restaurado o backup de {m.get('criado_em')} ({zip_path.name})")
    return {"restaurado": zip_path.name, "criado_em": m.get("criado_em"), "empresa": m.get("empresa"),
            "backup_anterior": antes["nome"] if antes else ""}


def decodificar(arquivo_b64: str) -> bytes:
    dados = base64.b64decode(arquivo_b64.split(",")[-1] or b"")
    if not dados.startswith(b"PK"):
        raise ValueError("Selecione o arquivo .zip do backup.")
    return dados


def manifesto_de_bytes(dados: bytes) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "b.zip"
        p.write_bytes(dados)
        return ler_manifesto(p)


def receber(dados: bytes) -> Path:
    """Guarda na pasta de backups da empresa em uso um .zip enviado pela tela."""
    stamp = datetime.now(emissor.FUSO).strftime("%Y-%m-%d_%H%M%S")
    destino = pasta_backups() / f"backup_enviado_{stamp}_arquivo.zip"
    destino.write_bytes(dados)
    try:
        ler_manifesto(destino)
    except ValueError:
        destino.unlink()
        raise
    return destino
