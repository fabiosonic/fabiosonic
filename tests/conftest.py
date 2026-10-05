import pytest


@pytest.fixture(autouse=True)
def _chave_local(tmp_path_factory, monkeypatch):
    """A chave local que protege as senhas nunca é criada dentro do repositório durante os testes."""
    monkeypatch.setenv("NFSE_CHAVE_LOCAL", str(tmp_path_factory.getbasetemp() / "chave_local.bin"))


@pytest.fixture(autouse=True)
def _envio_sempre(monkeypatch):
    """Os testes rodam a qualquer hora: o horário comercial dos envios é testado à parte (test_horario.py)."""
    monkeypatch.setenv("NFSE_ENVIO_SEMPRE", "1")


@pytest.fixture(autouse=True)
def _licenca_liberada(request, monkeypatch):
    """Os testes rodam com a licença liberada; a licença em si é testada em test_licenca.py (marca 'licenca_real')."""
    if request.node.get_closest_marker("licenca_real"):
        return
    from nfse_itaborai import licenca
    monkeypatch.setattr(licenca, "situacao", lambda hoje=None: {"liberado": True, "status": "ativa", "mensagem": "",
                                                                 "cnpj_instalacao": "", "fornecedor": {}})


@pytest.fixture(autouse=True)
def _sem_pdf_da_nota(request, monkeypatch):
    """O PDF da NFS-e é impresso pelo Edge a partir do link oficial: nos testes, sem navegador nem internet."""
    if request.node.get_closest_marker("pdf_real"):
        return
    from nfse_itaborai import cobranca
    monkeypatch.setattr(cobranca, "pdf_nfse", lambda t: "")
