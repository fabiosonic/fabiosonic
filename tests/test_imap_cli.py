import subprocess
import sys
from datetime import date
from pathlib import Path

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

    def response(self, codigo):
        return codigo, [b"555"] if codigo == "UIDVALIDITY" else [None]

    def store(self, *a):
        raise AssertionError("não deveria chegar aqui")

    def logout(self):
        self.chamadas.append(("logout",))


def test_imap_somente_leitura():
    falso = ImapFalso()
    f = FonteImap("h", 993, "u", "s", desde=date(2026, 10, 1), fabrica=lambda: falso)
    msgs = list(f.mensagens())
    assert len(msgs) == 2 and msgs[0].uid == "imap:u:INBOX:555:7"  # UIDVALIDITY na chave
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


def test_varias_caixas_uma_fora_do_ar_nao_para_as_outras(tmp_path):
    import yaml
    from mo_autonomo.entrada.fontes import FonteMultipla
    from mo_autonomo.fluxos.contexto import montar_fonte

    cfg = {"email": {"tipo": "imap", "host": "imap.exemplo.test", "porta": 993,
                     "caixas": [{"usuario": "fiscal@x.test"}, {"usuario": "dp@x.test"}]}}
    fonte = montar_fonte(cfg, lambda p: Path(p), date(2026, 10, 7))
    assert isinstance(fonte, FonteMultipla) and [f.usuario for f in fonte.fontes] == ["fiscal@x.test", "dp@x.test"]
    assert callable(fonte.fontes[0].senha)  # senha só é lida do cofre na hora de conectar

    ok = FonteImap("h", 993, "fiscal@x.test", lambda: "s", fabrica=lambda: ImapFalso())
    ruim = FonteImap("h", 993, "dp@x.test", lambda: (_ for _ in ()).throw(RuntimeError("senha não está no cofre")),
                     fabrica=lambda: ImapFalso())
    multi = FonteMultipla([ruim, ok])
    msgs = list(multi.mensagens())
    assert len(msgs) == 2 and all(m.uid.startswith("imap:fiscal@x.test:") for m in msgs)
    assert len(multi.erros) == 1 and multi.erros[0].startswith("dp@x.test")


def test_le_todas_as_pastas_somente_leitura():
    class Falso(ImapFalso):
        def __init__(self):
            super().__init__()
            self.abertas = []

        def list(self):
            return "OK", [b'(\\HasNoChildren) "." "INBOX"', b'(\\HasNoChildren) "." "INBOX.ALFA COMERCIO"',
                          b'(\\Noselect \\HasChildren) "." "Pai"', b'(\\HasNoChildren) "." "INBOX.Trash"',
                          b'(\\HasNoChildren) "." INBOX.BETA']

        def select(self, pasta, readonly=False):
            assert readonly, "toda pasta deve ser aberta com EXAMINE"
            self.abertas.append(pasta)
            return "OK", [b"1"]

        def uid(self, cmd, *args):
            if cmd == "search":
                return "OK", [b"7"]
            return super().uid(cmd, *args)
    f = Falso()
    fonte = FonteImap("h", 993, "contabil@x.test", "s", pasta="*", fabrica=lambda: f, ignorar=("inbox.trash",))
    msgs = list(fonte.mensagens())
    pastas = [m.uid.split(":")[2] for m in msgs]
    assert pastas == ["INBOX", "INBOX.ALFA COMERCIO", "INBOX.BETA"]
    assert '"INBOX.ALFA COMERCIO"' in f.abertas  # nome com espaço vai entre aspas
    assert all(c[:2] != ("uid", "store") for c in f.chamadas if isinstance(c, tuple))
