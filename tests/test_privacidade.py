"""Garante que arquivos pessoais NUNCA sejam versionados (enviados ao GitHub)."""
import re
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
PESSOAIS = [
    "config/local.yaml", ".env", "estado/carteira_real.json", "estado/carteira_simulada.json",
    "estado/custodia_clear.json", "estado/protecoes.json", "estado/fila_ordens.json", "estado/uso_ia.json",
    "estado/carteiras_casas.json", "logs/mapa_clear.json", "logs/2026-11-07/relatorio.txt",
    ".sessao_clear/Default/Cookies", "dados_cache/pesquisa/PETR4.csv", "captura.png", "PARAR",
]


def _git(*args):
    return subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True)


@pytest.mark.skipif(not (RAIZ / ".git").exists(), reason="fora de um repositório git")
@pytest.mark.parametrize("caminho", PESSOAIS)
def test_arquivo_pessoal_e_ignorado(caminho):
    assert _git("check-ignore", "-q", caminho).returncode == 0, f"{caminho} NÃO está ignorado pelo git"


@pytest.mark.skipif(not (RAIZ / ".git").exists(), reason="fora de um repositório git")
def test_nenhum_arquivo_pessoal_versionado():
    versionados = _git("ls-files").stdout.splitlines()
    proibidos = [f for f in versionados if re.match(r"(estado|logs|\.sessao_clear|dados_cache)/|config/local\.yaml|\.env", f)]
    assert not proibidos, proibidos


def test_config_local_sobrepoe_padrao(tmp_path):
    from swingbot import config
    base = (RAIZ / "config" / "config.yaml").read_text(encoding="utf-8")
    (tmp_path / "config.yaml").write_text(base, encoding="utf-8")
    (tmp_path / "local.yaml").write_text("ia:\n  provedor: ollama\nrisco:\n  capital_teste: 1234\n", encoding="utf-8")
    cfg = config.carregar(tmp_path / "config.yaml")
    assert cfg.ia.provedor == "ollama" and cfg.risco.capital_teste == 1234
    assert cfg.risco.risco_por_operacao == 0.01   # o resto continua do padrão
