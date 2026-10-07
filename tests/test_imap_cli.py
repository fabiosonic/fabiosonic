import subprocess
import sys
from datetime import date

import pytest

from mo_autonomo.entrada.fontes import FonteImap, OperacaoProibida, _ImapSomenteLeitura
from tests.conftest import eml_bytes, nfe_xml


class ImapFalso:
    def __init__(self):
        self.chamadas = []

    def login(self, u, s):
        self.chamadas.append(("login", u))

    def select(self, pasta, readonly=False):
        self.chamadas.append(("select", pasta, readonly))
        return "OK", [b"1"]

    def uid(self, cmd, *args):
        self.chamadas.append(("uid", cmd) + args)
        if cmd == "search":
            return "OK", [b"7 8"]
        return "OK", [(b"7 (BODY[] {10}", eml_bytes({"a.xml": nfe_xml()})), b")"]

    def store(self, *a):
        raise AssertionError("não deveria chegar aqui")

    def logout(self):
        self.chamadas.append(("logout",))


def test_imap_somente_leitura():
    falso = ImapFalso()
    f = FonteImap("h", 993, "u", "s", desde=date(2026, 10, 1), fabrica=lambda: falso)
    msgs = list(f.mensagens())
    assert len(msgs) == 2 and msgs[0].uid == "imap:INBOX:7"
    assert ("select", "INBOX", True) in falso.chamadas
    assert ("uid", "search", None, "SINCE 01-Oct-2026") in falso.chamadas
    assert all("PEEK" in c[3] for c in falso.chamadas if c[:2] == ("uid", "fetch"))
    ro = _ImapSomenteLeitura(falso)
    for proibido in ("store", "expunge", "copy", "move", "delete", "append"):
        with pytest.raises(OperacaoProibida):
            getattr(ro, proibido)
    with pytest.raises(OperacaoProibida):
        ro.uid("store", b"7", "+FLAGS", "\\Deleted")
    with pytest.raises(OperacaoProibida, match="PEEK"):
        ro.uid("fetch", b"7", "(RFC822)")
    assert f.testar()["mensagens"] == 2


def rodar(*args):
    return subprocess.run([sys.executable, "-m", "mo_autonomo", *args], capture_output=True, text=True, check=False)


def test_cli_normas_e_grafo():
    r = rodar("normas", "cobertura")
    assert r.returncode == 0 and "INATIVA" in r.stdout and "NFE_SOMA_ITENS" in r.stdout
    r = rodar("grafo", "desenhar")
    assert r.returncode == 0 and "capturar --> processar_documentos" in r.stdout
