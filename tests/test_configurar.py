"""Assistente de configuração inicial (configurar.bat / INICIAR.bat): Emissor Nacional não pede chave webservice."""

import builtins
import getpass

from nfse_itaborai import __main__ as cli, config, emissor


def _rodar(monkeypatch, tmp_path, respostas, ocultas=()):
    monkeypatch.setattr(emissor, "RAIZ", tmp_path)
    monkeypatch.setattr(emissor, "BASE", tmp_path)
    r = iter(respostas)
    monkeypatch.setattr(builtins, "input", lambda *a: next(r))
    o = iter(ocultas)
    monkeypatch.setattr(getpass, "getpass", lambda *a: next(o))
    return cli.configurar()


def test_emissor_nacional_sem_chave_webservice(monkeypatch, tmp_path):
    # opção 1 (Nacional), CNPJ, IM em branco, município IBGE, Simples
    assert _rodar(monkeypatch, tmp_path, ["1", "59.165.665/0001-06", "", "3304557", "S"]) == 0
    env = emissor.ler_env(tmp_path / ".env")
    assert env["ITABORAI_CNPJ"] == "59165665000106" and "ITABORAI_CHAVE" not in env
    e = config.carregar()["emissao"]
    assert e["canal"] == "nacional" and e["municipio_emissor"] == "3304557"
    monkeypatch.delenv("ITABORAI_CHAVE", raising=False)
    monkeypatch.delenv("ITABORAI_IM", raising=False)
    assert emissor.prestador_do_ambiente().cnpj == "59165665000106"     # não exige a chave no canal Nacional


def test_webservice_municipal_continua_pedindo_a_chave(monkeypatch, tmp_path):
    assert _rodar(monkeypatch, tmp_path, ["2", "59165665000106", "155656964", "1", "S"], ocultas=[""]) == 2
    assert not (tmp_path / ".env").exists()
    assert _rodar(monkeypatch, tmp_path, ["2", "59165665000106", "155656964", "1", "S"], ocultas=["minha-chave"]) == 0
    env = emissor.ler_env(tmp_path / ".env")
    assert env["ITABORAI_CHAVE"] == "minha-chave" and env["ITABORAI_IM"] == "155656964"
    assert config.carregar()["emissao"]["canal"] == "municipal"
