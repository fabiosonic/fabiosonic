"""Revisão 11: CPF/CNPJ com vírgula e CNPJ alfanumérico picado com qualquer rótulo; provedor local
fixado no IP e sem proxy; base64 curto."""
import base64
import socket

import pytest

from mo_autonomo.ia import cascata as C
from mo_autonomo.ia.mascaramento import Mascara, contem_dado_pessoal

CASOS = ["Tomador 123,456,789,09", "C.P.F.: 123,456,789,09", "CNPJ/MF: 12,345,678/0001-95",
         "C.N.P.J.: 12,345,678/0001-95", "Inscrição: 12,345,678/0001-95", "CPF nº 123,456,789,09",
         "CPF: 123, 456, 789, 09", "C.N.P.J. 12 ABC 345 01DE 35", "CNPJ do tomador 12 ABC 345 01DE 35",
         "Inscrição 12 ABC 345 01DE 35", "CNPJ/MF nº 12 ABC 345 01DE 35", "tomador 12 ABC 345 01DE 35",
         "anexo " + base64.b64encode(b"CPF 123.456.789-09 joao@x.com.br").decode()]


@pytest.mark.parametrize("texto", CASOS)
def test_guarda_pega(texto):
    assert contem_dado_pessoal(texto)


@pytest.mark.parametrize("texto", CASOS[:7])
def test_virgula_e_mascarada_e_volta(texto):
    m = Mascara()
    out = m.mascarar(texto)
    assert not contem_dado_pessoal(out) and m.desmascarar(out) == texto


def test_quantidade_com_tres_casas_continua_intacta():
    t = "Item 10,000 150,000 123,456 789,012 total 1.500,00"
    assert Mascara().mascarar(t) == t and not contem_dado_pessoal(t)


def test_local_fixado_no_ip_resolvido(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda h, *a: [(0, 0, 0, "", ("192.168.0.10", 0))])
    c = C.montar_cascata({"provedores": [{"nome": "o", "base_url": "http://ollama-pc:11434/v1", "modelo": "m", "local": True}]})
    p = c.provedores[0]
    assert p.local and p.base_url == "http://192.168.0.10:11434/v1"  # o envio não resolve o nome de novo


def test_local_nao_passa_pelo_proxy(monkeypatch):
    usados = []

    class R:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def read(self): return b'{"choices":[{"message":{"content":"ok"}}]}'
    monkeypatch.setattr(C._SEM_PROXY, "open", lambda req, timeout: usados.append("direto") or R())
    monkeypatch.setattr(C.urllib.request, "urlopen", lambda req, timeout: usados.append("proxy") or R())
    p = C.ProvedorOpenAICompat(nome="o", base_url="http://127.0.0.1:11434/v1", modelo="m", local=True)
    p.completar("s", "u")
    assert usados == ["direto"]
