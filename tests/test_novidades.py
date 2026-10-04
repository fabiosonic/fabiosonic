"""13º honorário, cobrança recorrente dos atrasados, certificado pela tela e isolamento entre empresas."""

import base64
from datetime import date

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12

from nfse_itaborai import cobranca, config, db, emissor, empresas, financeiro, inter, nacional
from nfse_itaborai.tela import tratar
from test_emissor import Simulador, ambiente  # noqa: F401  (fixture)
from test_empresas import multi  # noqa: F401  (fixture)
from test_financeiro import CLI_A, CLI_B, base  # noqa: F401  (fixture)
from test_nacional import _certificado


def _pfx(cn: str, senha: bytes = b"123") -> str:
    k, c = _certificado(cn)
    return "data:application/x-pkcs12;base64," + base64.b64encode(pkcs12.serialize_key_and_certificates(
        b"a1", k, c, None, serialization.BestAvailableEncryption(senha))).decode()


# ---------------------------------------------------------------- 13º honorário

def test_decimo_terceiro_em_duas_parcelas(base):  # noqa: F811
    financeiro.salvar_contrato({"cpf_cnpj": CLI_A["cpf_cnpj"], "valor": "1.000,00", "inicio": "2026-01", "dia_vencimento": 10})
    assert financeiro.gerar_decimo_terceiro(date(2026, 10, 30)) == []                 # outubro: nada
    nov = financeiro.gerar_decimo_terceiro(date(2026, 11, 2))
    assert len(nov) == 1 and financeiro.gerar_decimo_terceiro(date(2026, 11, 3)) == []  # idempotente
    t = financeiro.obter_titulo(nov[0])
    assert t["valor_cent"] == 50000 and t["vencimento"] == "2026-11-30" and t["competencia"] == "2026-11"
    assert t["descricao"] == "13º HONORÁRIO 2026 - PARCELA 1/2" and t["nfse_status"] == "pendente"
    dez = financeiro.gerar_decimo_terceiro(date(2026, 12, 1))
    t2 = financeiro.obter_titulo(dez[0])
    assert len(dez) == 1 and t2["valor_cent"] == 50000 and t2["vencimento"] == "2026-12-20"
    # o título mensal normal do mesmo mês continua sendo gerado (não conflita)
    assert len(financeiro.gerar_titulos("2026-12", date(2026, 12, 1))) == 1


def test_decimo_terceiro_desligado_e_parcela_vencida(base):  # noqa: F811
    financeiro.salvar_contrato({"cpf_cnpj": CLI_A["cpf_cnpj"], "valor": "900", "inicio": "2026-01"})
    config.salvar({"decimo_terceiro": {"ativo": False}})
    assert financeiro.gerar_decimo_terceiro(date(2026, 11, 2)) == []
    config.salvar({"decimo_terceiro": {"ativo": True, "parcelas": [{"percentual": 100, "vencimento": "15/12"}]}})
    # sistema parado em novembro: em 16/12 a parcela única já venceu e não é criada de surpresa
    assert financeiro.gerar_decimo_terceiro(date(2026, 12, 16)) == []
    t = financeiro.obter_titulo(financeiro.gerar_decimo_terceiro(date(2026, 12, 10))[0])
    assert t["valor_cent"] == 90000 and t["descricao"] == "13º HONORÁRIO 2026"


# ---------------------------------------------------------------- cobrança recorrente

def test_etapas_recorrentes():
    cob = {"regua_dias": [-3, 0, 1], "recorrente_ativa": True, "recorrente_apos_dias": 5, "recorrente_a_cada_dias": 7}
    assert cobranca.etapas_da_regua(40, cob) == [-3, 0, 1, 5, 12, 19, 26, 33, 40]
    assert cobranca.etapas_da_regua(3, cob) == [-3, 0, 1, 5]
    assert cobranca.etapas_da_regua(40, cob | {"recorrente_ativa": False}) == [-3, 0, 1]


def test_regua_cobra_atrasado_a_cada_periodo(base, monkeypatch):  # noqa: F811
    enviados = []
    monkeypatch.setattr(cobranca, "enviar_email", lambda para, assunto, texto, cfg=None, anexos=None, html="":
                        enviados.append(assunto))
    config.salvar({"cobranca": {"regua_dias": [0], "regua_whatsapp": False, "recorrente_apos_dias": 3,
                                "recorrente_a_cada_dias": 10}})
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "300", vencimento="2026-09-01", emitir_nfse=False)
    datas = [date(2026, 9, d) for d in range(1, 31)] + [date(2026, 10, d) for d in range(1, 10)]
    for d in datas:
        cobranca.rodar_regua(d)
    etapas = [e["etapa"] for e in cobranca.historico(tid)]
    assert etapas == [0, 3, 13, 23, 33]                              # vencimento + a cada 10 dias a partir do 3º
    financeiro.baixar(tid, "2026-10-09", "300")
    cobranca.rodar_regua(date(2026, 10, 13))
    assert [e["etapa"] for e in cobranca.historico(tid) if e["etapa"] < 1000] == [0, 3, 13, 23, 33]  # pago: para de cobrar


# ---------------------------------------------------------------- certificado e isolamento

def test_certificado_pela_tela(multi):  # noqa: F811
    r = tratar("certificado/enviar", {"arquivo": _pfx("MORAES:24875410000144"), "senha": "123"})
    assert r["cnpj"] == "24875410000144" and not r["vencido"]
    assert (multi / "dados" / "certificados" / "certificado-a1.pfx").exists()
    assert config.carregar()["emissao"]["certificado_pfx"] == "dados/certificados/certificado-a1.pfx"
    assert nacional.carregar_certificado().cnpj == "24875410000144"
    assert "Senha incorreta" in tratar("certificado/enviar", {"arquivo": _pfx("X:24875410000144"), "senha": "errada"})["erro"]
    assert "é do CNPJ 11222333000181" in tratar("certificado/enviar", {"arquivo": _pfx("OUTRA:11222333000181"),
                                                                       "senha": "123"})["erro"]


def test_certificado_fora_da_pasta_da_empresa_e_recusado(multi, tmp_path_factory):  # noqa: F811
    fora = tmp_path_factory.mktemp("downloads") / "cert.pfx"
    fora.write_bytes(base64.b64decode(_pfx("MORAES:24875410000144").split(",")[1]))
    config.salvar({"emissao": {"certificado_pfx": str(fora), "certificado_senha": "123"}})
    with pytest.raises(nacional.ErroCertificado, match="guardado nesta empresa"):
        nacional.carregar_certificado()


def test_empresas_nao_compartilham_credenciais(multi, monkeypatch):  # noqa: F811
    pfx = _pfx("MORAES:24875410000144")
    tratar("certificado/enviar", {"arquivo": pfx, "senha": "123"})
    tratar("config/salvar", {"empresa": {"pix_chave": "pix@moraes.com"}, "cobranca": {"inter_client_id": "cli-moraes"}})
    crt = "data:;base64," + base64.b64encode(b"-----BEGIN CERTIFICATE-----\nAAA\n-----END CERTIFICATE-----\n").decode()
    tratar("inter/arquivo", {"tipo": "crt", "arquivo": crt})
    empresas.criar({"nome": "PADARIA BOM PAO LTDA", "cnpj": "11222333000181"})
    # nada da Moraes aparece na padaria
    c = config.carregar()
    assert c["empresa"]["pix_chave"] == "" and c["cobranca"]["inter_client_id"] == ""
    assert c["emissao"]["certificado_pfx"] == "" and c["cobranca"]["inter_certificado"] == ""
    with pytest.raises(nacional.ErroCertificado):
        nacional.carregar_certificado()
    # e a padaria não pode reutilizar as credenciais da Moraes
    assert "já pertence à empresa MORAES" in tratar("config/salvar", {"empresa": {"pix_chave": "PIX@moraes.com"}})["erro"]
    assert "já pertence" in tratar("config/salvar", {"cobranca": {"inter_client_id": "cli-moraes"}})["erro"]
    assert "já está cadastrado na empresa" in tratar("inter/arquivo", {"tipo": "crt", "arquivo": crt})["erro"]
    # nem apontar para o arquivo guardado na pasta da Moraes
    config.salvar({"cobranca": {"inter_client_id": "cli-padaria", "inter_client_secret": "s",
                                "inter_certificado": str(multi / "dados" / "certificados" / "inter.crt"),
                                "inter_chave": str(multi / "dados" / "certificados" / "inter.crt")}})
    with pytest.raises(inter.ErroInter, match="guardado nesta empresa"):
        inter.token()


def test_empresa_adicional_nao_herda_variaveis_do_computador(multi, monkeypatch):  # noqa: F811
    empresas.criar({"nome": "PADARIA BOM PAO LTDA", "cnpj": "11222333000181"})
    monkeypatch.setenv("ITABORAI_CHAVE", "chave-do-computador")
    assert emissor.env("ITABORAI_CHAVE") == ""
    empresas.ativar("24875410000144")
    (multi / ".env").write_text("ITABORAI_CNPJ=24875410000144\n", encoding="utf-8")
    assert emissor.env("ITABORAI_CHAVE") == "chave-do-computador"          # só a empresa original
