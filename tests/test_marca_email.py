"""Aparência dos e-mails: logo da empresa embutida (cid), cores, rodapé e saudação pelo primeiro nome."""

import base64
import struct
import zlib
from datetime import date

import pytest

from nfse_itaborai import clientes, cobranca, config, emissor, financeiro, marca
from nfse_itaborai.tela import tratar
from test_emissor import ambiente  # noqa: F401  (fixture)
from test_financeiro import CLI_A, base  # noqa: F401  (fixture)
from test_mensagens import smtp  # noqa: F401  (fixture)


def png(w=4, h=2):
    """PNG sintético mínimo (sem dependências)."""
    bruto = b"".join(b"\x00" + b"\x10\x80\xff" * w for _ in range(h))
    pedaco = lambda tipo, d: struct.pack(">I", len(d)) + tipo + d + struct.pack(">I", zlib.crc32(tipo + d))  # noqa: E731
    return (b"\x89PNG\r\n\x1a\n" + pedaco(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + pedaco(b"IDAT", zlib.compress(bruto)) + pedaco(b"IEND", b""))


def b64(d):
    return "data:image/png;base64," + base64.b64encode(d).decode()


def _partes(msg):
    return list(msg.walk())


def test_logo_vai_embutida_no_email_de_cobranca(smtp):  # noqa: F811
    tratar("marca/logo", {"arquivo": b64(png()), "fundo": "#000f26", "cor": "#0a83b4"})
    assert (emissor.raiz() / "dados" / "logo_email.png").read_bytes() == png()
    cfg = config.carregar()
    assert cfg["empresa"]["logo_fundo"] == "#000f26" and cfg["empresa"]["cor_email"] == "#0a83b4"
    config.salvar({"empresa": {"whatsapp": "(21)99880-6423", "site": "moraeseoliveira.com.br"}})
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "500", vencimento="2026-10-20", emitir_nfse=False)
    cobranca.preparar_pagamento(tid)
    cobranca.rodar_regua(date(2026, 10, 1))
    msg = smtp.enviados[0]
    html = next(p for p in _partes(msg) if p.get_content_type() == "text/html").get_content()
    imgs = [p for p in _partes(msg) if p.get_content_type() == "image/png"]
    assert 'src="cid:logo"' in html and len(imgs) == 1 and imgs[0]["Content-ID"] == "<logo>"
    assert imgs[0].get_payload(decode=True) == png()
    assert "#000f26" in html and "#0a83b4" in html and "https://wa.me/5521998806423" in html
    assert "moraeseoliveira.com.br" in html and "R$ 500,00" in html


def test_sem_logo_cabecalho_com_nome_e_mensagem_de_texto_ganha_moldura(smtp):  # noqa: F811
    config.salvar({"empresa": {"nome": "ESCRITORIO TESTE LTDA"}})
    cobranca.enviar_email("x@y.com", "Pagamento recebido", "Olá, Fulano!\n\nRecebemos o seu pagamento.\n\n"
                          "Atenciosamente,\nESCRITORIO", ref={"tipo": "Agradecimento"})
    msg = smtp.enviados[0]
    html = next(p for p in _partes(msg) if p.get_content_type() == "text/html").get_content()
    assert "cid:logo" not in html and "ESCRITORIO TESTE LTDA" in html
    assert "PAGAMENTO RECEBIDO" in html and "Recebemos o seu pagamento." in html
    assert "Atenciosamente" not in html                     # a assinatura vai no rodapé
    assert not [p for p in _partes(msg) if p.get_content_type() == "image/png"]
    assert "Recebemos o seu pagamento." in next(p for p in _partes(msg) if p.get_content_type() == "text/plain").get_content()


def test_logo_invalida_e_remocao(base):  # noqa: F811
    with pytest.raises(ValueError):
        marca.salvar_logo(b64(b"GIF89a....."))
    marca.salvar_logo(b64(png()))
    assert tratar("marca/info", {})["tem_logo"]
    assert not tratar("marca/remover", {})["tem_logo"]


def test_cor_invalida_nao_entra_no_html(base):  # noqa: F811
    config.salvar({"empresa": {"cor_email": "red;background:url(x)", "logo_fundo": "javascript:1"}})
    html = marca.casca(config.carregar(), "A", "<p>x</p>")
    assert "url(x)" not in html and "javascript" not in html and marca.COR_PADRAO in html


def test_saudacao_pelo_primeiro_nome_so_para_pessoa():
    assert cobranca.saudacao({"cpf_cnpj": "11914266706", "cliente_nome": "BRUNO YOSHIHISA SILVA OKAMURA"},
                             "Bruno Yoshihisa Silva Okamura") == "Bruno"
    assert cobranca.saudacao({"cpf_cnpj": "61773639000100", "cliente_nome": "61.773.639 Oscar Chagas Matozinhos"},
                             "61.773.639 Oscar Chagas Matozinhos") == "Oscar"
    assert cobranca.saudacao({"cpf_cnpj": "32396063000103", "cliente_nome": "RPS CONSULTORIA LTDA"},
                             "RPS Consultoria LTDA") == "RPS Consultoria LTDA"


def test_previa_mostra_a_logo_sem_enviar(base):  # noqa: F811
    marca.salvar_logo(b64(png()))
    financeiro.criar_titulo(CLI_A["cpf_cnpj"], "300", vencimento="2026-10-20", emitir_nfse=False)
    r = tratar("marca/previa", {})
    assert "data:image/png;base64," in r["html"] and "cid:logo" not in r["html"] and r["titulo_id"]


def test_logo_de_uma_empresa_nao_aparece_na_outra(base, tmp_path, monkeypatch):  # noqa: F811
    marca.salvar_logo(b64(png()))
    outra = tmp_path / "outra_empresa"
    (outra / "dados").mkdir(parents=True)
    monkeypatch.setattr(emissor, "RAIZ", outra)
    assert marca.logo() == b"" and not marca.info()["tem_logo"]
