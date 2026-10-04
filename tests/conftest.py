import pytest


@pytest.fixture(autouse=True)
def _chave_local(tmp_path_factory, monkeypatch):
    """A chave local que protege as senhas nunca é criada dentro do repositório durante os testes."""
    monkeypatch.setenv("NFSE_CHAVE_LOCAL", str(tmp_path_factory.getbasetemp() / "chave_local.bin"))


@pytest.fixture(autouse=True)
def _envio_sempre(monkeypatch):
    """Os testes rodam a qualquer hora: o horário comercial dos envios é testado à parte (test_horario.py)."""
    monkeypatch.setenv("NFSE_ENVIO_SEMPRE", "1")
