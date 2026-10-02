import json
import os
import threading
import time
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from nfse_itaborai import (automacao, clientes, cobranca, conciliacao, config, db, financeiro, importacao, lote,
                           whatsapp)
from test_emissor import Simulador, ambiente  # noqa: F401  (fixture)
from test_financeiro import CLI_A, CLI_B, base  # noqa: F401  (fixtures)

DADOS = Path(__file__).parent / "dados"


def nacional(numero: str, emissao: str, valor: str, doc="32396063000103", nome="RPS CONSULTORIA E SERVICOS DE ENGENHARIA LTDA"):
    return f"""<?xml version="1.0" encoding="UTF-8"?><NFSe xmlns="http://www.sped.fazenda.gov.br/nfse" versao="1.01">
<infNFSe><nNFSe>{numero}</nNFSe><emit><CNPJ>24875410000144</CNPJ></emit><DPS versao="1.01"><infDPS>
<dhEmi>{emissao}T10:00:00-03:00</dhEmi><dCompet>{emissao}</dCompet><prest><CNPJ>24875410000144</CNPJ></prest>
<toma><CNPJ>{doc}</CNPJ><xNome>{nome}</xNome><end><endNac><cMun>3304557</cMun><CEP>20071904</CEP></endNac>
<xLgr>AV PRESIDENTE VARGAS</xLgr><nro>435</nro><xBairro>Centro</xBairro></end></toma>
<serv><cServ><xDescServ>HONORARIOS CONTABEIS MENSAIS.</xDescServ></cServ></serv>
<valores><vServPrest><vServ>{valor}</vServ></vServPrest></valores></infDPS></DPS></infNFSe></NFSe>"""


@pytest.fixture
def auto(base, tmp_path, monkeypatch):  # noqa: F811
    xmls, extratos = tmp_path / "xmls", tmp_path / "extratos"
    xmls.mkdir()
    extratos.mkdir()
    config.salvar({"pastas": {"xml_nfse": str(xmls), "extratos": str(extratos)},
                   "automacao": {"enriquecer_contatos": False}})
    monkeypatch.setattr(clientes, "consultar_cnpj", lambda c: pytest.fail("não deveria consultar a Receita"))
    return xmls, extratos


# ---------------------------------------------------------------- XML e notas externas

def test_le_nota_nacional_e_retorno_do_webservice(auto):
    n = importacao.nota_de_xml(nacional("99003801", "2026-08-29", "374.40"), "24875410000144")
    assert n["numero"] == "99003801" and n["competencia"] == "2026-08" and n["valor_cent"] == 37440
    assert n["descricao"] == "HONORARIOS CONTABEIS MENSAIS."
    r = importacao.nota_de_xml((DADOS / "retorno_nfse_real.xml").read_text(encoding="utf-8"), "24875410000144")
    assert r["numero"] == "99003740" and r["competencia"] == "2026-08" and r["valor_cent"] == 100000
    assert importacao.numero_curto("202600099003740") == "99003740"


def test_notas_externas_viram_contas_a_receber_a_partir_do_inicio(auto):
    xmls, _ = auto
    config.salvar({"financeiro": {"inicio_financeiro": "2026-09-01"}})
    (xmls / "velha.xml").write_text(nacional("99003700", "2026-08-10", "374.40"), encoding="utf-8")
    (xmls / "nova.xml").write_text(nacional("99003863", "2026-09-26", "374.40"), encoding="utf-8")
    (xmls / "copia.xml").write_text(nacional("99003863", "2026-09-26", "374.40"), encoding="utf-8")
    r = importacao.importar_xml(date(2026, 10, 2))
    assert r["notas_lidas"] == 2 and r["contas_criadas"] == 1
    t = financeiro.listar_titulos()[0]
    assert t["nfse_numero"] == "99003863" and t["nfse_status"] == "emitida" and t["origem"] == "importado"
    assert t["vencimento"] == "2026-10-01" and t["competencia"] == "2026-09"
    assert importacao.importar_xml(date(2026, 10, 2))["contas_criadas"] == 0


def test_nota_emitida_pelo_sistema_nao_e_importada_de_novo(auto):
    xmls, _ = auto
    config.salvar({"financeiro": {"inicio_financeiro": "2026-01-01"}})
    r = financeiro.emitir_avulsa(CLI_A["cpf_cnpj"], "374,40")           # simulador devolve 202600099009999
    (xmls / "a.xml").write_text(nacional("99009999", "2026-10-02", "374.40"), encoding="utf-8")
    assert r["sucesso"] and importacao.importar_xml(date(2026, 10, 2))["contas_criadas"] == 0


def test_detecta_contrato_recorrente_e_so_cobra_apos_confirmacao(auto):
    xmls, _ = auto
    for i, d in enumerate(["2026-07-05", "2026-08-05", "2026-09-05"]):
        (xmls / f"{i}.xml").write_text(nacional(f"9900370{i}", d, "374.40"), encoding="utf-8")
    (xmls / "b.xml").write_text(nacional("99003799", "2026-09-10", "350.00", CLI_B["cpf_cnpj"], "Espaco"), encoding="utf-8")
    r = importacao.importar_xml(date(2026, 10, 2))
    assert r["contratos_detectados"] == 1
    k = financeiro.listar_contratos()[0]
    assert k["confirmado"] == 0 and k["origem"] == "detectado" and k["valor_cent"] == 37440 and k["inicio"] == "2026-10"
    assert financeiro.gerar_titulos("2026-10") == []                  # aguardando confirmação
    assert importacao.confirmar_contratos() == 1
    assert len(financeiro.gerar_titulos("2026-10")) == 1
    assert importacao.importar_xml(date(2026, 10, 2))["contratos_detectados"] == 0


def test_valores_diferentes_nao_viram_contrato(auto):
    xmls, _ = auto
    for i, (d, v) in enumerate([("2026-07-05", "100.00"), ("2026-08-05", "250.00"), ("2026-09-05", "900.00")]):
        (xmls / f"{i}.xml").write_text(nacional(f"9900370{i}", d, v), encoding="utf-8")
    assert importacao.importar_xml(date(2026, 10, 2))["contratos_detectados"] == 0


# ---------------------------------------------------------------- extratos e despesas

EXTRATO = """<OFX><BANKTRANLIST>
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20261002<TRNAMT>374.40<FITID>B1<MEMO>PIX RECEBIDO RPS CONSULTORIA</STMTTRN>
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20261002<TRNAMT>-45.90<FITID>B2<MEMO>TARIFA PACOTE SERVICOS</STMTTRN>
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20261002<TRNAMT>-612.33<FITID>B3<MEMO>PAGAMENTO DAS SIMPLES NACIONAL</STMTTRN>
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20261002<TRNAMT>-80.00<FITID>B4<MEMO>COMPRA PAPELARIA CENTRO</STMTTRN>
</BANKTRANLIST></OFX>"""


def test_pasta_de_extratos_importada_uma_vez_e_despesas_classificadas(auto):
    _, extratos = auto
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "374,40", vencimento="2026-10-05", emitir_nfse=False)
    (extratos / "extrato.ofx").write_text(EXTRATO, encoding="cp1252")
    r = importacao.importar_extratos()
    assert r == {"arquivos": 1, "titulos": 1, "despesas": 3}
    assert financeiro.obter_titulo(tid)["status"] == "pago"
    cats = {d["descricao"]: (d["categoria"], d["status"]) for d in financeiro.listar_despesas()}
    assert cats["TARIFA PACOTE SERVICOS"] == ("Bancárias", "pago")
    assert cats["PAGAMENTO DAS SIMPLES NACIONAL"] == ("Impostos", "pago")
    assert cats["COMPRA PAPELARIA CENTRO"] == ("Outras", "pago")
    assert importacao.importar_extratos()["arquivos"] == 0
    time.sleep(0.01)
    os.utime(extratos / "extrato.ofx")                                 # arquivo baixado de novo
    assert importacao.importar_extratos() == {"arquivos": 1, "titulos": 0, "despesas": 0}


def test_despesas_do_extrato_desligado(auto):
    config.salvar({"automacao": {"despesas_do_extrato": False}})
    conciliacao.importar(EXTRATO)
    assert financeiro.listar_despesas() == []


# ---------------------------------------------------------------- contatos, resumo, reenvio

def test_completa_contato_pela_receita(auto, monkeypatch):
    config.salvar({"automacao": {"enriquecer_contatos": True}})
    consultas = []
    monkeypatch.setattr(clientes, "consultar_cnpj", lambda c: consultas.append(c) or {
        "email": "contato@cultivar.com", "telefone": "2133334444", "endereco": {"complemento": "SALA 2"}})
    assert importacao.enriquecer_contatos() == 1
    c = clientes.obter(CLI_B["cpf_cnpj"])
    assert c["email"] == "contato@cultivar.com" and c["telefone"] == "2133334444"
    assert c["endereco"]["complemento"] == "SALA 2" and c["endereco"]["numero"] == "435"
    assert consultas == [CLI_B["cpf_cnpj"]]                            # CLI_A já tinha contato
    assert importacao.enriquecer_contatos() == 0 and len(consultas) == 1   # não repete no mesmo mês


def test_resumo_diario_uma_vez_por_dia(auto, monkeypatch):
    enviados = []
    monkeypatch.setattr(cobranca, "enviar_email", lambda para, assunto, texto, cfg=None, anexos=None: enviados.append((para, texto)))
    assert importacao.resumo_diario({}) == "sem e-mail do dono ou SMTP"
    config.salvar({"resumo": {"email_dono": "fabio@x.com"}, "smtp": {"host": "smtp.x"}})
    financeiro.criar_titulo(CLI_A["cpf_cnpj"], "300", vencimento="2026-09-01", emitir_nfse=False)
    assert importacao.resumo_diario({"nfse": {"emitidas": 2}}, date(2026, 10, 2)) == "enviado para fabio@x.com"
    assert "A receber: R$ 300,00" in enviados[0][1] and "nfse: {'emitidas': 2}" in enviados[0][1]
    assert importacao.resumo_diario({}, date(2026, 10, 2)) == "já enviado hoje" and len(enviados) == 1


def test_falha_de_rede_fica_pendente_para_nova_tentativa(auto, monkeypatch):
    monkeypatch.setattr(lote, "emitir_um", lambda *a, **k: {"sucesso": False, "erros": ["Falha de comunicação: timed out"]})
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "300")
    financeiro.emitir_nfse_titulo(tid)
    t = financeiro.obter_titulo(tid)
    assert t["nfse_status"] == "pendente" and "timed out" in t["nfse_erro"]


# ---------------------------------------------------------------- WhatsApp automático

class FakeZap(BaseHTTPRequestHandler):
    recebidos: list = []

    def do_POST(self):  # noqa: N802
        corpo = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeZap.recebidos.append((self.path, {k.lower(): v for k, v in self.headers.items()}, corpo))
        b = b'{"zaapId":"1"}'
        self.send_response(200)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, *a):
        pass


@pytest.fixture
def zap():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), FakeZap)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    FakeZap.recebidos = []
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_zapi_e_evolution(auto, zap):
    config.salvar({"whatsapp": {"provedor": "zapi", "zapi_instancia": "INST", "zapi_token": "TOK",
                                "zapi_client_token": "CT", "zapi_url": zap}})
    assert whatsapp.automatico()
    whatsapp.enviar("(21) 98888-7777", "oi")
    path, cab, corpo = FakeZap.recebidos[-1]
    assert path == "/instances/INST/token/TOK/send-text" and cab["client-token"] == "CT"
    assert corpo == {"phone": "5521988887777", "message": "oi"}
    config.salvar({"whatsapp": {"provedor": "evolution", "evolution_url": zap + "/", "evolution_instancia": "escritorio",
                                "evolution_apikey": "K"}})
    whatsapp.enviar("5521988887777", "ola")
    path, cab, corpo = FakeZap.recebidos[-1]
    assert path == "/message/sendText/escritorio" and cab["apikey"] == "K"
    assert corpo == {"number": "5521988887777", "text": "ola"}


def test_regua_envia_whatsapp_automatico(auto, zap, monkeypatch):
    monkeypatch.setattr(cobranca, "enviar_email", lambda *a, **k: None)
    config.salvar({"whatsapp": {"provedor": "zapi", "zapi_instancia": "I", "zapi_token": "T", "zapi_url": zap}})
    financeiro.criar_titulo(CLI_A["cpf_cnpj"], "300", vencimento="2026-10-05", emitir_nfse=False)
    r = cobranca.rodar_regua(date(2026, 10, 2))
    assert r["whatsapp"] == 1 and len(FakeZap.recebidos) == 1
    assert FakeZap.recebidos[0][2]["message"].startswith("Olá, RPS CONSULTORIA")
    assert cobranca.fila_whatsapp() == []                               # nada para clicar
    ev = db.linhas("SELECT status FROM eventos_cobranca WHERE canal='whatsapp'")
    assert ev == [{"status": "enviado"}]


# ---------------------------------------------------------------- robô completo

def test_robo_com_todas_as_etapas(auto, monkeypatch):
    xmls, extratos = auto
    monkeypatch.setattr(cobranca, "enviar_email", lambda *a, **k: None)
    config.salvar({"financeiro": {"inicio_financeiro": "2026-09-20"}, "resumo": {"email_dono": "f@x.com"},
                   "smtp": {"host": "smtp.x"}})
    for i, d in enumerate(["2026-07-05", "2026-08-05", "2026-09-25"]):
        (xmls / f"{i}.xml").write_text(nacional(f"9900370{i}", d, "374.40"), encoding="utf-8")
    (extratos / "e.ofx").write_text(EXTRATO, encoding="utf-8")
    r = automacao.rodar(date(2026, 10, 2))
    assert r["importacao_xml"] == {"clientes_novos": 0, "notas_lidas": 3, "contas_criadas": 1, "contratos_detectados": 1}
    assert r["titulos_gerados"] == 0                                   # contrato detectado aguarda confirmação
    assert r["extratos"] == {"arquivos": 1, "titulos": 1, "despesas": 3}   # PIX quitou a nota externa
    assert r["resumo"] == "enviado para f@x.com"


def test_nfse_nao_e_emitida_duas_vezes(auto):
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "300")
    financeiro.atualizar_titulo(tid, nfse_status="emitindo")            # outro processo emitindo
    r = financeiro.emitir_nfse_titulo(tid)
    assert not r["sucesso"] and "já está sendo emitida" in r["erros"][0] and Simulador.recebidos == []


def test_trava_impede_dois_robos_simultaneos(auto):
    config.salvar({"automacao": {"ativa": True}})
    with automacao._trava() as livre:
        assert livre
        assert automacao.rodar()["motivo"] == "Outra execução do robô está em andamento."
    assert automacao.rodar(date(2026, 10, 2))["executado"] is True
    trava = db.caminho().parent / "robo.lock"
    trava.write_text("1")
    os.utime(trava, (time.time() - 3 * 3600,) * 2)                     # trava abandonada
    assert automacao.rodar(date(2026, 10, 2))["executado"] is True
