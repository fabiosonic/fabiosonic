"""Revisão 12: localhost no Windows (IPv4 primeiro), 'Inscrição Municipal' sem falso positivo,
hífen tipográfico, vírgula com espaço e OCR com letra no lugar de dígito."""
import socket

import pytest

from mo_autonomo.ia import cascata as C
from mo_autonomo.ia.mascaramento import Mascara, contem_dado_pessoal


def test_localhost_prefere_ipv4(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda h, *a: [(0, 0, 0, "", ("::1", 0, 0, 0)), (0, 0, 0, "", ("127.0.0.1", 0))])
    c = C.montar_cascata({"provedores": [{"nome": "o", "base_url": "http://localhost:11434/v1", "modelo": "m", "local": True}]})
    assert c.provedores[0].base_url == "http://127.0.0.1:11434/v1"


@pytest.mark.parametrize("texto", ["Inscrição Municipal: 4.029.875-4", "Inscrição Estadual: 32.226.48-6",
                                   "Inscricao Municipal 0.123.456-7 Inscricao Estadual 12.345.67-8"])
def test_inscricao_nao_bloqueia(texto):
    assert not contem_dado_pessoal(texto)


@pytest.mark.parametrize("texto", ["CPF 529.982.247‐25", "CPF 529.982.247­25", "CPF 529.982.247−25",
                                   "CPF 529.982.247－25", "CPF 529, 982, 247 - 25", "CNPJ 11, 222, 333 / 0001 - 81",
                                   "CPF 529.982.247-2O", "CPF 5Z9.982.247-25"])
def test_formatos_de_pdf_e_ocr_sao_mascarados(texto):
    out = Mascara().mascarar(texto)
    assert not contem_dado_pessoal(out) and not any(c.isdigit() for c in out.replace("_1]", ""))
