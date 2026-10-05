"""Monta o pacote COMPLETO para Windows (uso do fornecedor; esta pasta não vai para o cliente).

Resultado: EmissorItaborai_<versão>_completo.zip com o programa, o manual e a pasta python\\ — Python 3.12 oficial
(pacote "python" da Python Software Foundation no NuGet) já com lxml, cryptography, playwright e pypdf instalados.
O cliente não precisa de internet nem instalar nada: o INSTALAR.bat usa esse Python.

Uso (Linux/macOS/Windows com git e pip):  python ferramentas/montar_pacote_windows.py <pasta_saida> [MANUAL.pdf]
"""

from __future__ import annotations

import hashlib
import io
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

PYTHON_VERSAO = "3.12.10"
NUGET = f"https://api.nuget.org/v3-flatcontainer/python/{PYTHON_VERSAO}/python.{PYTHON_VERSAO}.nupkg"
COMPONENTES = ["lxml", "cryptography", "playwright", "pypdf"]
FORA_DO_PACOTE = ("tests", ".github", "ferramentas", "exemplos/xml_para_validar.xml")
SECOES_FORA = ("## Validar o XML", "## Testes")
RAIZ = Path(__file__).resolve().parents[1]


def _baixar(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=300) as r:
        return r.read()


def _programa(destino: Path) -> str:
    dados = subprocess.run(["git", "archive", "--prefix=EmissorItaborai/", "HEAD"], cwd=RAIZ, check=True,
                           capture_output=True).stdout
    tarfile.open(fileobj=io.BytesIO(dados)).extractall(destino)
    pasta = destino / "EmissorItaborai"
    for item in FORA_DO_PACOTE:
        alvo = pasta / item
        if alvo.is_dir():
            shutil.rmtree(alvo)
        elif alvo.exists():
            alvo.unlink()
    for g in pasta.rglob(".gitkeep"):
        g.unlink()
    readme = pasta / "README.md"
    partes = re.split(r"(?m)^(?=## )", readme.read_text(encoding="utf-8"))
    readme.write_text("".join(p for p in partes if not p.startswith(SECOES_FORA)), encoding="utf-8")
    return re.search(r'__version__ = "([^"]+)"', (pasta / "nfse_itaborai" / "__init__.py").read_text()).group(1)


def _python(pasta: Path) -> None:
    pkg = _baixar(NUGET)
    (pasta.parent / "python.nupkg.sha256").write_text(hashlib.sha256(pkg).hexdigest() + "\n")
    alvo = pasta / "python"
    with zipfile.ZipFile(io.BytesIO(pkg)) as z:
        for nome in z.namelist():
            if nome.startswith("tools/") and not nome.endswith("/"):
                dest = alvo / nome[len("tools/"):]
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(z.read(nome))
    site = alvo / "Lib" / "site-packages"
    site.mkdir(parents=True, exist_ok=True)
    rodas = pasta.parent / "rodas"
    subprocess.run([sys.executable, "-m", "pip", "download", "--quiet", "--only-binary=:all:", "--platform", "win_amd64",
                    "--python-version", "3.12", "--implementation", "cp", "--abi", "cp312", "--abi", "abi3",
                    "--abi", "none", "-d", str(rodas), *COMPONENTES], check=True)
    rodas_pip = list((alvo / "Lib" / "ensurepip" / "_bundled").glob("pip-*.whl"))
    for roda in sorted(rodas.glob("*.whl")) + rodas_pip:
        with zipfile.ZipFile(roda) as z:
            for nome in z.namelist():
                partes = nome.split("/")
                if partes[0].endswith(".data"):          # <pacote>.data/purelib|platlib/... vai para site-packages
                    if len(partes) > 2 and partes[1] in ("purelib", "platlib"):
                        nome_final = "/".join(partes[2:])
                    else:
                        continue                         # scripts/headers: não são usados
                else:
                    nome_final = nome
                if nome_final.endswith("/"):
                    continue
                dest = site / nome_final
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(z.read(nome))
        print("  componente:", roda.name)


def main() -> int:
    saida = Path(sys.argv[1]).resolve()
    manual_pdf = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else None
    trabalho = saida / "montagem"
    if trabalho.exists():
        shutil.rmtree(trabalho)
    trabalho.mkdir(parents=True)
    versao = _programa(trabalho)
    pasta = trabalho / "EmissorItaborai"
    if manual_pdf and manual_pdf.exists():
        shutil.copy2(manual_pdf, pasta / "MANUAL.pdf")
    _python(pasta)
    proibido = re.compile(rb"moraes|24875410|oliveira contab", re.I)
    for f in pasta.rglob("*"):
        if f.is_file() and "python" not in f.relative_to(pasta).parts[:1] and proibido.search(f.read_bytes()):
            raise SystemExit(f"Referência ao escritório em {f}: pacote NÃO gerado.")
    arq = saida / f"EmissorItaborai_{versao}_completo.zip"
    if arq.exists():
        arq.unlink()
    with zipfile.ZipFile(arq, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in sorted(pasta.rglob("*")):
            if f.is_file() and "__pycache__" not in f.parts:
                z.write(f, f.relative_to(trabalho))
    print(f"OK: {arq} ({arq.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
