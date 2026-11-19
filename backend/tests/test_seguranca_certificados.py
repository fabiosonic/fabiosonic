import ssl
from datetime import UTC, datetime, timedelta

import pytest

from moxml import servicos
from moxml.certificados.a1 import SenhaIncorreta, carregar_pfx, impedimentos_bloqueantes, validar_para_empresa
from moxml.seguranca.cofre import Cofre
from moxml.simulador import gerador

CNPJ = "99000001000101"


def test_certificado_valido_identifica_cnpj():
    pfx, _, _ = gerador.gerar_certificado_teste(CNPJ, "EMPRESA X")
    c = carregar_pfx(pfx, "teste")
    assert c.info.cnpj == CNPJ and c.info.titular == "EMPRESA X" and c.info.status == "VALIDO"
    assert validar_para_empresa(c, CNPJ) == []


def test_certificado_vencido():
    pfx, _, _ = gerador.gerar_certificado_teste(CNPJ, "EMPRESA X", dias_validade=10,
                                                inicio=datetime.now(UTC) - timedelta(days=30))
    c = carregar_pfx(pfx, "teste")
    assert c.info.status == "VENCIDO"
    assert impedimentos_bloqueantes(validar_para_empresa(c, CNPJ))


def test_senha_incorreta():
    pfx, _, _ = gerador.gerar_certificado_teste(CNPJ, "EMPRESA X")
    with pytest.raises(SenhaIncorreta):
        carregar_pfx(pfx, "errada")


def test_cnpj_incompativel():
    pfx, _, _ = gerador.gerar_certificado_teste("99000002000148", "OUTRA")
    c = carregar_pfx(pfx, "teste")
    assert any("difere" in p for p in impedimentos_bloqueantes(validar_para_empresa(c, CNPJ)))


def test_contexto_ssl_exige_verificacao_do_servidor():
    pfx, _, _ = gerador.gerar_certificado_teste(CNPJ, "EMPRESA X")
    ctx = carregar_pfx(pfx, "teste").contexto_ssl()
    assert ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname


def test_cliente_soap_recusa_tls_desabilitado():
    from moxml.sefaz.transporte import ClienteSoap
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with pytest.raises(ValueError, match="não pode ser desabilitada"):
        ClienteSoap(ctx)


def test_cofre_cifra_e_nao_grava_texto_puro(tmp_path):
    cofre = Cofre(tmp_path / "cofre", forcar_aesgcm=True)
    cofre.guardar("senha-x", "S3nh@Secreta")
    bruto = (tmp_path / "cofre" / "senha-x.seg").read_bytes()
    assert b"S3nh@Secreta" not in bruto
    assert cofre.ler_texto("senha-x") == "S3nh@Secreta"
    cofre.remover("senha-x")
    assert not cofre.existe("senha-x")


def test_cadastro_certificado_exige_autorizacao_e_guarda_no_cofre(app, empresa):
    pfx, _, _ = gerador.gerar_certificado_teste(CNPJ, "EMPRESA X")
    with pytest.raises(servicos.ErroNegocio, match="autorização"):
        servicos.cadastrar_certificado(app, empresa.id, pfx, "teste", "", "")
    c = servicos.cadastrar_certificado(app, empresa.id, pfx, "teste", "Fulano (sócio)", "Contrato 12/2026")
    assert app.cofre.ler(c.referencia_armazenamento_seguro) == pfx
    assert app.cofre.ler_texto(c.referencia_senha) == "teste"
    # nada sensível no banco
    assert "teste" not in (c.referencia_senha, c.referencia_armazenamento_seguro)


def test_log_mascara_segredos():
    from moxml.motor.logs import mascarar
    assert "abc123" not in mascarar("Authorization: Bearer abc123 senha=abc123")


@pytest.mark.parametrize("cnpj,ok", [("99000001000101", True), ("99000001000102", False), ("12ABC34501DE35", True),
                                     ("11111111111111", False)])
def test_validar_cnpj(cnpj, ok):
    if ok:
        assert servicos.validar_cnpj(cnpj) == cnpj
    else:
        with pytest.raises(servicos.ErroNegocio):
            servicos.validar_cnpj(cnpj)
