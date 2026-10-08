"""Atualização pelo ZIP: troca só o programa, nunca os dados; faz backup antes e guarda a versão anterior."""

import io
import zipfile

import pytest

from nfse_itaborai import __version__, atualizacao, backup, clientes, emissor
from nfse_itaborai.tela import tratar
from test_empresas import multi  # noqa: F401  (fixture)


def _zip(versao="9.9.9", extra=None, prefixo="EmissorItaborai/"):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr(prefixo + "nfse_itaborai/__init__.py", f'__version__ = "{versao}"\n')
        z.writestr(prefixo + "nfse_itaborai/novo_modulo.py", "X = 1\n")
        z.writestr(prefixo + "INICIAR.bat", "@echo nova\r\n")
        z.writestr(prefixo + "README.md", "novo")
        # o que NUNCA pode ser trocado por uma atualização
        z.writestr(prefixo + ".env", "ITABORAI_CHAVE=roubada\n")
        z.writestr(prefixo + "dados/config.json", "{}")
        z.writestr(prefixo + "empresas.json", "{}")
        for k, v in (extra or {}).items():
            z.writestr(prefixo + k, v)
    return b.getvalue()


def _programa(base):
    (base / "nfse_itaborai").mkdir(exist_ok=True)
    (base / "nfse_itaborai" / "__init__.py").write_text(f'__version__ = "{__version__}"\n', encoding="utf-8")
    (base / "nfse_itaborai" / "velho.py").write_text("V = 1\n", encoding="utf-8")
    (base / "INICIAR.bat").write_text("@echo velha\r\n", encoding="utf-8")


def test_analisa_o_zip(multi):  # noqa: F811
    a = atualizacao.analisar(_zip())
    assert a["versao_nova"] == "9.9.9" and a["mais_nova"] and a["arquivos"] == 4
    assert not atualizacao.analisar(_zip("1.0.0", prefixo=""))["mais_nova"]
    with pytest.raises(ValueError, match="não é do Sistema"):
        b = io.BytesIO()
        with zipfile.ZipFile(b, "w") as z:
            z.writestr("outro/arquivo.txt", "x")
        atualizacao.analisar(b.getvalue())
    with pytest.raises(ValueError, match="caminhos inválidos"):
        atualizacao.analisar(_zip(extra={"../fora.py": "x"}))


def test_atualiza_so_o_programa(multi):  # noqa: F811
    _programa(multi)
    env_antes = (multi / ".env").read_text(encoding="utf-8")
    r = tratar("atualizacao/aplicar", {"arquivo": "data:application/zip;base64," + __import__("base64").b64encode(_zip()).decode(),
                                       "reiniciar": False})
    assert r["ok"] and r["versao_nova"] == "9.9.9" and r["backups"]
    assert (multi / "nfse_itaborai" / "novo_modulo.py").exists() and not (multi / "nfse_itaborai" / "velho.py").exists()
    assert (multi / "INICIAR.bat").read_bytes() == b"@echo nova\r\n"
    assert (multi / ".env").read_text(encoding="utf-8") == env_antes                      # dados intactos
    assert (multi / "dados" / "config.json").read_text(encoding="utf-8") != "{}"
    assert not (multi / "empresas.json").exists() or (multi / "empresas.json").read_text(encoding="utf-8") != "{}"
    assert [c["razao_social"] for c in clientes.listar()] == ["CLIENTE DA MORAES"]
    assert any(b["motivo"] == "antes_da_atualizacao" for b in backup.listar())
    v = atualizacao.versoes_guardadas()
    assert v and v[0]["versao"] == __version__
    # voltar para a versão guardada
    atualizacao.voltar(v[0]["nome"])
    assert (multi / "nfse_itaborai" / "velho.py").exists() and not (multi / "nfse_itaborai" / "novo_modulo.py").exists()


def test_versao_anterior_so_com_confirmacao(multi):  # noqa: F811
    _programa(multi)
    with pytest.raises(ValueError, match="não é mais nova"):
        atualizacao.aplicar(_zip("1.0.0"))
    assert atualizacao.aplicar(_zip("1.0.0"), permitir_anterior=True)["ok"]


def test_nao_atualiza_com_robo_rodando(multi, monkeypatch):  # noqa: F811
    import os
    from nfse_itaborai import parada
    _programa(multi)
    monkeypatch.setattr(atualizacao, "ESPERA_PARADA_SEG", 2)
    (multi / "dados" / "robo.lock").write_text(str(os.getpid()), encoding="utf-8")   # robô vivo que não termina
    with pytest.raises(ValueError, match="robô parar"):
        atualizacao.aplicar(_zip())
    assert not parada.pedida()                       # desistiu: o robô volta a trabalhar
    assert (multi / "nfse_itaborai" / "velho.py").exists()
    assert emissor.BASE == multi


def test_pacote_com_caminho_fora_da_pasta_e_recusado(multi):  # noqa: F811
    """Zip-slip: nome de arquivo com '..' no pacote não escreve fora da pasta do programa (nem ao analisar, nem ao aplicar)."""
    _programa(multi)
    pacote = _zip(extra={"nfse_itaborai/../../fora.py": "print('fora')\n"})
    with pytest.raises(ValueError, match="inválid"):
        atualizacao.aplicar(pacote)
    assert not (multi.parent / "fora.py").exists() and not (multi / "fora.py").exists()
    assert (multi / "nfse_itaborai" / "velho.py").exists()                      # nada foi alterado
