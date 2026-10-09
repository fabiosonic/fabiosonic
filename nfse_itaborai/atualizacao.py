"""Atualização do sistema pelo botão: recebe o ZIP da versão nova e troca só os arquivos do programa.

Nunca toca nos dados: .env, dados/, saida/, empresas/, empresas.json, dados_locais/, IMPORTAR XML/, serviços
e exemplos ficam como estão. Antes de trocar, faz um backup de cada empresa e guarda uma cópia do programa
atual (dados_locais/versoes/) para voltar, se precisar. Depois reinicia o sistema sozinho.
"""

from __future__ import annotations

import io
import os
import re
import subprocess
import sys
import threading
import time
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath

from . import __version__, emissor, parada

PASTAS_PROGRAMA = ("nfse_itaborai", "schemas", "docs")
ARQUIVOS_PROGRAMA = ("README.md", "MANUAL.html", "MANUAL.pdf", "pyproject.toml", ".gitattributes", ".gitignore")
EXTENSOES_RAIZ = (".bat", ".vbs")
MAX_BYTES = 50 * 1024 * 1024


def _versao(v: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v or "0")[:3])


def _do_programa(rel: str) -> bool:
    p = PurePosixPath(rel)
    if not p.parts or "__pycache__" in p.parts or rel.endswith((".pyc", "/")):
        return False
    if len(p.parts) == 1:
        return rel in ARQUIVOS_PROGRAMA or p.suffix.lower() in EXTENSOES_RAIZ
    return p.parts[0] in PASTAS_PROGRAMA


def _abrir(dados: bytes) -> tuple[zipfile.ZipFile, str, str]:
    if len(dados) > MAX_BYTES or not dados.startswith(b"PK"):
        raise ValueError("Selecione o arquivo .zip da versão nova do sistema.")
    z = zipfile.ZipFile(io.BytesIO(dados))
    for n in z.namelist():
        p = PurePosixPath(n)
        if p.is_absolute() or ".." in p.parts or "\\" in n:
            raise ValueError("ZIP com caminhos inválidos; atualização recusada.")
    alvo = next((n for n in z.namelist() if n.endswith("nfse_itaborai/__init__.py")), None)
    if not alvo:
        raise ValueError("Este ZIP não é do Sistema Financeiro e NFS-e.")
    prefixo = alvo[: -len("nfse_itaborai/__init__.py")]
    m = re.search(r'__version__\s*=\s*"([^"]+)"', z.read(alvo).decode("utf-8", "replace"))
    return z, prefixo, (m.group(1) if m else "0")


def analisar(dados: bytes) -> dict:
    z, prefixo, nova = _abrir(dados)
    arquivos = [n[len(prefixo):] for n in z.namelist() if n.startswith(prefixo) and _do_programa(n[len(prefixo):])]
    return {"versao_atual": __version__, "versao_nova": nova, "arquivos": len(arquivos),
            "mais_nova": _versao(nova) > _versao(__version__), "mesma": _versao(nova) == _versao(__version__)}


def _robo_rodando() -> bool:
    """Alguma empresa com o robô trabalhando? Trava de processo que não existe mais (queda, janela fechada no
    meio) é apagada aqui mesmo — ela não segura a atualização."""
    from . import empresas
    for e in empresas.listar():
        trava = empresas.pasta(e) / "dados" / "robo.lock"
        try:
            idade = time.time() - trava.stat().st_mtime
            pid = int((trava.read_text(encoding="utf-8").strip() or "0"))
        except (OSError, ValueError):
            continue
        if idade >= 2 * 3600 or not parada.pid_vivo(pid):
            trava.unlink(missing_ok=True)
            continue
        return True
    return False


ESPERA_PARADA_SEG = 180


def parar_robo(espera_seg: int | None = None) -> bool:
    """Pede para o robô parar e espera ele chegar a um ponto seguro (fim da etapa/título em andamento)."""
    parada.pedir()
    limite = time.time() + (ESPERA_PARADA_SEG if espera_seg is None else espera_seg)
    while _robo_rodando():
        if time.time() >= limite:
            return False
        time.sleep(2)
    return True


def _guardar_programa_atual(base: Path) -> Path:
    destino = base / "dados_locais" / "versoes"
    destino.mkdir(parents=True, exist_ok=True)
    arq = destino / f"programa_{__version__}_{datetime.now(emissor.FUSO):%Y-%m-%d_%H%M%S}.zip"
    with zipfile.ZipFile(arq, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(base.rglob("*")):
            rel = p.relative_to(base).as_posix()
            if p.is_file() and _do_programa(rel):
                z.write(p, f"EmissorItaborai/{rel}")
    for velho in sorted(destino.glob("programa_*.zip"))[:-5]:      # guarda as 5 últimas
        velho.unlink()
    return arq


def aplicar(dados: bytes, permitir_anterior: bool = False) -> dict:
    info = analisar(dados)
    if not info["mais_nova"] and not permitir_anterior:
        raise ValueError(f"O ZIP é da versão {info['versao_nova']}, que não é mais nova que a instalada "
                         f"({info['versao_atual']}). Para voltar de versão, confirme a opção na tela.")
    if not parar_robo():
        parada.liberar()
        raise ValueError("Pedi para o robô parar, mas ele ainda está terminando um envio ao banco ou à prefeitura "
                         "(cortar no meio poderia gerar boleto ou nota em dobro). Tente de novo em 2 ou 3 minutos — "
                         "nada foi alterado.")
    try:
        return _aplicar(dados)
    except Exception:
        parada.liberar()                       # deu errado: o robô volta a trabalhar
        raise


def _aplicar(dados: bytes) -> dict:
    from . import backup, db, empresas
    base = Path(emissor.BASE)
    backups = []
    for e in empresas.listar():                                  # dados de cada empresa protegidos antes
        backups.append(backup.criar("antes_da_atualizacao", empresas.pasta(e))["nome"])
    copia = _guardar_programa_atual(base)
    z, prefixo, nova = _abrir(dados)
    novos = set()
    for n in z.namelist():
        rel = n[len(prefixo):] if n.startswith(prefixo) else ""
        if not rel or not _do_programa(rel):
            continue
        if ".." in Path(rel).parts or Path(rel).is_absolute() or "\\" in rel:
            raise ValueError(f"Pacote inválido: caminho fora da pasta do programa ({rel}).")
        novos.add(rel)
        alvo = (base / rel).resolve()
        if base.resolve() not in alvo.parents:
            raise ValueError(f"Pacote inválido: caminho fora da pasta do programa ({rel}).")
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_bytes(z.read(n))
    # módulos que deixaram de existir na versão nova saem (evita código velho sendo importado)
    removidos = 0
    for p in (base / "nfse_itaborai").rglob("*"):
        rel = p.relative_to(base).as_posix()
        if p.is_file() and _do_programa(rel) and rel not in novos:
            p.unlink()
            removidos += 1
    db.registrar("atualizacao", f"Sistema atualizado de {__version__} para {nova} ({len(novos)} arquivos; "
                                f"cópia da versão anterior em {copia.name})")
    return {"ok": True, "versao_anterior": __version__, "versao_nova": nova, "arquivos": len(novos),
            "removidos": removidos, "backups": backups, "copia_programa": str(copia)}


def versoes_guardadas() -> list[dict]:
    pasta = Path(emissor.BASE) / "dados_locais" / "versoes"
    return [{"nome": a.name, "versao": a.name.split("_")[1]} for a in sorted(pasta.glob("programa_*.zip"), reverse=True)]


def voltar(nome: str) -> dict:
    if not re.fullmatch(r"programa_[\w.-]+\.zip", nome or ""):
        raise ValueError("Versão inválida.")
    arq = Path(emissor.BASE) / "dados_locais" / "versoes" / nome
    if not arq.is_file():
        raise ValueError("Cópia da versão não encontrada.")
    return aplicar(arq.read_bytes(), permitir_anterior=True)


def versao_no_disco() -> str:
    """Versão dos arquivos do programa instalados agora (pode ser mais nova que a que está rodando)."""
    try:
        m = re.search(r'__version__\s*=\s*"([^"]+)"', (Path(__file__).parent / "__init__.py").read_text(encoding="utf-8"))
        return m.group(1) if m else __version__
    except OSError:
        return __version__


def desatualizado() -> bool:
    """Os arquivos foram atualizados mas este processo ainda roda a versão anterior?"""
    return versao_no_disco() != __version__


_reiniciando = threading.Event()


def reiniciar_se_desatualizado() -> bool:
    """Chamado pela tela e por um vigia a cada 30 s: o sistema velho na memória se troca sozinho pelo novo."""
    if not desatualizado() or _reiniciando.is_set():
        return _reiniciando.is_set()
    _reiniciando.set()
    from . import db
    try:
        db.registrar("atualizacao", f"Reabrindo: rodava a versão {__version__}, mas os arquivos já são da {versao_no_disco()}")
    except Exception:  # noqa: BLE001
        pass
    reiniciar(espera=2.0)
    return True


def reiniciar(espera: float = 1.0) -> None:
    """Fecha este processo e abre o sistema de novo (já com os arquivos novos)."""
    base = Path(emissor.BASE)
    if sys.platform == "win32":  # pragma: no cover - só Windows
        # "timeout" não funciona sem janela (sai na hora e o sistema velho continuava aberto): ping espera ~3 s
        cmd = ["cmd", "/c", f'ping -n 4 127.0.0.1 >nul & wscript.exe "{base / "SISTEMA.vbs"}"']
        subprocess.Popen(cmd, cwd=base, creationflags=0x08000000 | 0x00000008)   # sem janela, desvinculado
    else:
        subprocess.Popen([sys.executable, "-c", "import time, subprocess, sys; time.sleep(3); "
                          "subprocess.Popen([sys.executable, '-m', 'nfse_itaborai', 'tela'])"], cwd=base,
                         start_new_session=True)
    threading.Timer(espera, lambda: os._exit(0)).start()
