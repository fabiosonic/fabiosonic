"""Varredura das telas num navegador de verdade (tests/ui). Demorada: roda com NFSE_TESTE_TELA=1
(e no CI), desde que haja Node.js com Playwright."""

import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

import pytest

UI = Path(__file__).parent / "ui"


def _playwright_ok() -> bool:
    if not shutil.which("node"):
        return False
    return subprocess.run(["node", "-e", "require('playwright')"], cwd=UI, capture_output=True).returncode == 0


@pytest.mark.skipif(os.environ.get("NFSE_TESTE_TELA") != "1" or not _playwright_ok(),
                    reason="varredura de tela: defina NFSE_TESTE_TELA=1 (precisa de Node.js + Playwright)")
def test_varredura_das_telas(tmp_path):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        porta = s.getsockname()[1]
    srv = subprocess.Popen([sys.executable, str(UI / "servidor.py"), str(tmp_path / "sistema"), str(porta)],
                           stdout=subprocess.PIPE, text=True)
    try:
        assert srv.stdout.readline().strip() == "pronto"
        r = subprocess.run(["node", str(UI / "varredura.js"), str(porta)], cwd=UI, capture_output=True, text=True,
                           timeout=900)
        assert r.returncode == 0 and "SEM PROBLEMAS" in r.stdout, r.stdout + r.stderr
    finally:
        srv.terminate()


@pytest.mark.skipif(os.environ.get("NFSE_TESTE_TELA") != "1" or not _playwright_ok(),
                    reason="teste funcional: defina NFSE_TESTE_TELA=1 (precisa de Node.js + Playwright)")
def test_funcional_de_ponta_a_ponta(tmp_path):
    """Todas as funções pela tela, com prefeitura, Sefin, Inter e e-mail simulados (tests/ui/funcional.js)."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        porta = s.getsockname()[1]
    pasta = tmp_path / "sistema"
    srv = subprocess.Popen([sys.executable, str(UI / "servidor_completo.py"), str(pasta), str(porta)],
                           stdout=subprocess.PIPE, text=True)
    try:
        assert srv.stdout.readline().strip() == "pronto"
        r = subprocess.run(["node", str(UI / "funcional.js"), str(porta), str(pasta)], cwd=UI, capture_output=True,
                           text=True, timeout=1500)
        assert r.returncode == 0, r.stdout[-4000:] + r.stderr[-2000:]
    finally:
        srv.terminate()
