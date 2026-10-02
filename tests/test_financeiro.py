import json
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from nfse_itaborai import (asaas, automacao, clientes, cobranca, conciliacao, config, db, emissor, financeiro,
                           pix, relatorios)
from nfse_itaborai.tela import tratar
from test_emissor import Simulador, ambiente  # noqa: F401  (fixture)

CLI_A = {"cpf_cnpj": "32396063000103", "razao_social": "RPS CONSULTORIA E SERVICOS DE ENGENHARIA LTDA",
         "email": "fin@rps.com.br", "telefone": "21988887777",
         "endereco": {"tipo_logradouro": "AV", "logradouro": "PRESIDENTE VARGAS", "numero": "435", "bairro": "Centro",
                      "codigo_municipio": "3304557", "cep": "20071904"}}
CLI_B = CLI_A | {"cpf_cnpj": "54399432000146", "razao_social": "Espaco Cultivar Fonoaudiologia Ltda", "email": "",
                 "telefone": ""}


@pytest.fixture
def base(ambiente, monkeypatch):  # noqa: F811
    url, pasta = ambiente
    monkeypatch.setenv("ITABORAI_AMBIENTE", "producao")
    monkeypatch.setenv("ITABORAI_CIENTE_IRREVERSIVEL", "SIM")
    clientes.salvar(CLI_A)
    clientes.salvar(CLI_B)
    config.salvar({"empresa": {"pix_chave": "24.875.410/0001-44"}})
    # o emissor usa a URL do simulador
    from nfse_itaborai import cliente as cli_http
    orig = cli_http.postar
    monkeypatch.setattr(cli_http, "postar", lambda xml, nome, url_=None, timeout=60, **k: orig(xml, nome, url=url))
    return url, pasta


# ---------------------------------------------------------------- utilidades

@pytest.mark.parametrize("entrada,cent", [("1.234,56", 123456), ("1234.56", 123456), ("374,4", 37440), (10, 1000),
                                          ("R$ 2.000,00", 200000)])
def test_cent(entrada, cent):
    assert financeiro.cent(entrada) == cent


def test_encargos_multa_e_juros_pro_rata(base):
    t = {"status": "aberto", "vencimento": "2026-09-01", "valor_cent": 100000}
    e = financeiro.encargos(t, date(2026, 10, 1))      # 30 dias
    assert e == {"dias_atraso": 30, "multa_cent": 2000, "juros_cent": 1000, "total_cent": 103000}
    assert financeiro.encargos(t, date(2026, 9, 1))["total_cent"] == 100000
    assert financeiro.situacao(t, date(2026, 9, 2)) == "atrasado"


def test_crc16_ccitt_vetor_conhecido():
    assert pix.crc16("123456789") == "29B1"


def test_pix_payload_valido():
    p = pix.payload("24.875.410/0001-44", 37440, "MORAES & OLIVEIRA CONTABILIDADE", "Itaboraí", "T15")
    assert p.startswith("000201") and "0014br.gov.bcb.pix0114248754100001445" in p
    assert "5406374.405802BR" in p and "62070503T15" in p
    assert pix.crc16(p[:-4]) == p[-4:]
    assert pix.normalizar_chave("(21) 99999-8888") == "+5521999998888"
    assert pix.normalizar_chave("FIN@X.COM") == "fin@x.com"


# ---------------------------------------------------------------- contratos e recorrência

def test_contrato_gera_titulo_idempotente_e_ajusta_dia(base):
    k = financeiro.salvar_contrato({"cpf_cnpj": CLI_A["cpf_cnpj"], "valor": "374,40", "dia_vencimento": 31,
                                    "inicio": "2026-01"})
    assert k["valor_cent"] == 37440
    ids = financeiro.gerar_titulos("2026-02")
    assert len(ids) == 1 and financeiro.gerar_titulos("2026-02") == []
    t = financeiro.obter_titulo(ids[0])
    assert t["vencimento"] == "2026-02-28" and t["nfse_status"] == "pendente" and t["cliente_nome"].startswith("RPS")
    assert financeiro.gerar_titulos("2025-12") == []        # antes do início


def test_reajuste_anual_no_mes_de_aniversario(base):
    financeiro.salvar_contrato({"cpf_cnpj": CLI_A["cpf_cnpj"], "valor": "1000", "inicio": "2025-01",
                                "mes_reajuste": 1, "reajuste_pct": "4,5"})
    financeiro.gerar_titulos("2025-12")
    jan = financeiro.obter_titulo(financeiro.gerar_titulos("2026-01")[0])
    assert jan["valor_cent"] == 104500
    fev = financeiro.obter_titulo(financeiro.gerar_titulos("2026-02")[0])
    assert fev["valor_cent"] == 104500                       # não reajusta duas vezes


def test_contratos_do_historico(base):
    lst = clientes.listar()
    for c in lst:
        c.update(ultimo_valor="350.00", ultima_data=financeiro.hoje().isoformat())
    clientes._gravar(lst)
    assert financeiro.contratos_do_historico(10) == 2
    assert financeiro.contratos_do_historico(10) == 0


# ---------------------------------------------------------------- títulos + NFS-e

def test_emitir_avulsa_em_producao_cria_titulo_com_nfse(base):
    r = financeiro.emitir_avulsa(CLI_A["cpf_cnpj"], "374,40")
    assert r["sucesso"]
    t = r["titulo"]
    assert t["nfse_status"] == "emitida" and t["nfse_numero"] == "202600099009999" and t["status"] == "aberto"


def test_emitir_avulsa_em_homologacao_nao_entra_no_financeiro(base, monkeypatch):
    monkeypatch.setenv("ITABORAI_AMBIENTE", "homologacao")
    r = financeiro.emitir_avulsa(CLI_A["cpf_cnpj"], "100")
    assert r["sucesso"] and financeiro.obter_titulo(r["titulo_id"])["status"] == "cancelado"


def test_erro_de_nfse_fica_registrado(base):
    Simulador.modo = "erro"
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "200")
    r = financeiro.emitir_nfse_titulo(tid)
    t = financeiro.obter_titulo(tid)
    assert not r["sucesso"] and t["nfse_status"] == "erro" and "NBS" in t["nfse_erro"]


def test_baixa_estorno_e_cancelamento(base):
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "500", vencimento="2026-01-10", emitir_nfse=False)
    t = financeiro.baixar(tid, "2026-01-12", "500,00", "pix")
    assert t["status"] == "pago" and t["valor_pago_cent"] == 50000
    financeiro.estornar(tid)
    assert financeiro.obter_titulo(tid)["status"] == "aberto"
    financeiro.cancelar_titulo(tid, "teste")
    assert financeiro.obter_titulo(tid)["status"] == "cancelado"
    with pytest.raises(ValueError):
        financeiro.baixar(tid)


# ---------------------------------------------------------------- cobrança

def test_regua_envia_email_e_enfileira_whatsapp_sem_repetir(base, monkeypatch):
    enviados = []
    monkeypatch.setattr(cobranca, "enviar_email", lambda para, assunto, texto, cfg=None: enviados.append((para, assunto, texto)))
    a = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "300", vencimento="2026-09-25", emitir_nfse=False)
    b = financeiro.criar_titulo(CLI_B["cpf_cnpj"], "300", vencimento="2026-09-25", emitir_nfse=False)
    cobranca.preparar_pagamento(a)
    r = cobranca.rodar_regua(date(2026, 9, 30))              # +5 dias
    assert r == {"email": 1, "whatsapp": 1, "sem_contato": 2, "erros": 0}
    assert enviados[0][0] == "fin@rps.com.br" and "5 dia" in enviados[0][1]
    assert "PIX copia e cola" in enviados[0][2] and "Valor atualizado" in enviados[0][2]
    assert cobranca.rodar_regua(date(2026, 9, 30)) == {"email": 0, "whatsapp": 0, "sem_contato": 0, "erros": 0}
    fila = cobranca.fila_whatsapp()
    assert len(fila) == 1 and fila[0]["detalhe"].startswith("https://wa.me/5521988887777?text=")
    cobranca.marcar_whatsapp_feito(fila[0]["id"])
    assert cobranca.fila_whatsapp() == []
    assert b


def test_regua_ignora_titulo_com_nota_de_teste_ou_pendente(base, monkeypatch):
    monkeypatch.setattr(cobranca, "enviar_email", lambda *a, **k: pytest.fail("não deveria enviar"))
    financeiro.criar_titulo(CLI_A["cpf_cnpj"], "300", vencimento="2026-09-30")      # nfse pendente
    assert cobranca.rodar_regua(date(2026, 9, 30))["email"] == 0


@pytest.mark.parametrize("dias,enviadas,esperada", [(-3, set(), -3), (-2, {-3}, None), (0, {-3}, 0), (6, {-3, 0, 1}, 5),
                                                    (40, set(), None), (31, {30}, None), (15, {-3, 0}, 15)])
def test_etapa_devida(dias, enviadas, esperada):
    assert cobranca.etapa_devida(dias, [-3, 0, 1, 5, 15, 30], enviadas) == esperada


class FakeAsaas(BaseHTTPRequestHandler):
    pagos: set = set()

    def _json(self, d, code=200):
        b = json.dumps(d).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):  # noqa: N802
        assert self.headers["access_token"] == "chave-teste"
        if self.path.startswith("/customers"):
            return self._json({"data": []})
        if self.path.endswith("/pixQrCode"):
            return self._json({"payload": "00020101PIXASAAS"})
        if self.path.endswith("/identificationField"):
            return self._json({"identificationField": "34191.79001 01043.510047"})
        pid = self.path.rsplit("/", 1)[-1]
        return self._json({"id": pid, "status": "RECEIVED" if pid in self.pagos else "PENDING",
                           "clientPaymentDate": "2026-10-01", "value": 300.0})

    def do_POST(self):  # noqa: N802
        corpo = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path == "/customers":
            assert corpo["cpfCnpj"] == "32396063000103"
            return self._json({"id": "cus_1"})
        assert corpo["customer"] == "cus_1" and corpo["billingType"] == "UNDEFINED" and corpo["fine"] == {"value": 2.0}
        return self._json({"id": "pay_" + corpo["externalReference"].split("-")[1], "invoiceUrl": "https://asaas/i/1"})

    def log_message(self, *a):
        pass


def test_asaas_cria_cobranca_e_baixa_automatica(base):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), FakeAsaas)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    config.salvar({"cobranca": {"provedor": "asaas", "asaas_api_key": "chave-teste",
                                "asaas_url": f"http://127.0.0.1:{srv.server_address[1]}"}})
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "300", vencimento="2026-10-05", emitir_nfse=False)
    t = cobranca.preparar_pagamento(tid)
    assert t["asaas_id"] == f"pay_{tid}" and t["pix_copia_cola"] == "00020101PIXASAAS"
    assert t["cobranca_link"] == "https://asaas/i/1" and t["linha_digitavel"].startswith("34191")
    assert cobranca.sincronizar_asaas() == 0
    FakeAsaas.pagos.add(f"pay_{tid}")
    assert cobranca.sincronizar_asaas() == 1
    t = financeiro.obter_titulo(tid)
    assert t["status"] == "pago" and t["forma_pagamento"] == "asaas" and t["data_pagamento"] == "2026-10-01"
    srv.shutdown()


# ---------------------------------------------------------------- conciliação

OFX = """OFXHEADER:100
<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><BANKTRANLIST>
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20261001120000<TRNAMT>374.40<FITID>A1<MEMO>PIX RECEBIDO T{a} RPS CONSULTORIA</STMTTRN>
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20261002<TRNAMT>350,00<FITID>A2<MEMO>PIX RECEBIDO ESPACO CULTIVAR FONOAUDIOLOGIA</STMTTRN>
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20261002<TRNAMT>999.99<FITID>A3<MEMO>TED DESCONHECIDO</STMTTRN>
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20261003<TRNAMT>-1500.00<FITID>A4<MEMO>PAGTO ALUGUEL</STMTTRN>
</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>"""


def test_conciliacao_ofx(base):
    a = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "374,40", vencimento="2026-10-05", emitir_nfse=False)
    b = financeiro.criar_titulo(CLI_B["cpf_cnpj"], "350", vencimento="2026-10-05", emitir_nfse=False)
    financeiro.criar_titulo(CLI_A["cpf_cnpj"], "350", vencimento="2026-10-05", emitir_nfse=False)  # mesmo valor de b
    financeiro.salvar_despesa({"descricao": "Aluguel", "valor": "1500", "vencimento": "2026-10-05"})
    r = conciliacao.importar(OFX.format(a=a))
    assert r == {"lancamentos": 4, "novos": 4, "titulos": 2, "despesas": 1}
    assert financeiro.obter_titulo(a)["status"] == "pago"
    assert financeiro.obter_titulo(b)["status"] == "pago"          # nome desempata valores iguais
    pend = conciliacao.nao_conciliados()
    assert [p["descricao"] for p in pend] == ["TED DESCONHECIDO"]
    assert conciliacao.importar(OFX.format(a=a))["novos"] == 0      # reimportar não duplica


# ---------------------------------------------------------------- relatórios

def test_aliquota_anexo3_e_rbt12():
    assert relatorios.aliquota_efetiva_anexo3(100_000_00, iss_fixo=False) == 6.0
    assert relatorios.aliquota_efetiva_anexo3(500_000_00, iss_fixo=False) == 9.97
    assert relatorios.aliquota_efetiva_anexo3(500_000_00, iss_fixo=True) == 6.73


def test_painel_aging_clientes_fluxo_dre_csv(base):
    em = date(2026, 10, 2)
    financeiro.salvar_contrato({"cpf_cnpj": CLI_A["cpf_cnpj"], "valor": "1000", "inicio": "2026-09", "dia_vencimento": 10})
    financeiro.gerar_titulos("2026-09")
    atrasado = financeiro.listar_titulos()[0]["id"]
    financeiro.atualizar_titulo(atrasado, nfse_status="emitida")
    pago = financeiro.criar_titulo(CLI_B["cpf_cnpj"], "500", vencimento="2026-09-20", competencia="2026-09", emitir_nfse=False)
    financeiro.baixar(pago, "2026-10-01", "500")
    financeiro.salvar_despesa({"descricao": "Aluguel", "valor": "800", "vencimento": "2026-10-15", "categoria": "Aluguel"})
    p = relatorios.painel(em)
    assert p["faturado_mes"] == 0 and p["recebido_mes"] == 50000 and p["atrasado"] == 100000
    assert p["atrasado_qtd"] == 1 and p["mrr"] == 100000 and p["a_pagar"] == 80000
    assert p["inadimplencia_pct"] == 66.7 and len(p["serie"]) == 12
    ag = relatorios.aging(em)
    assert ag["faixas"]["1_30"] == 100000
    pc = {c["cpf_cnpj"]: c for c in relatorios.por_cliente(em)}
    assert pc[CLI_A["cpf_cnpj"]]["faixa"] == "atenção" and pc[CLI_B["cpf_cnpj"]]["score"] == 84
    assert pc[CLI_A["cpf_cnpj"]]["score"] == 57 and pc[CLI_A["cpf_cnpj"]]["media_atraso"] == 22
    fluxo = relatorios.fluxo_caixa(em, 60)
    assert sum(s["entradas"] for s in fluxo) == 100000 + 100000 * 2   # atrasado + out/nov do contrato
    assert sum(s["saidas"] for s in fluxo) == 80000
    d = relatorios.dre(2026, em)
    set_ = d["meses"][8]
    assert set_["receita"] == 150000 and d["categorias"] == ["Aluguel"]
    assert "RPS CONSULTORIA" in relatorios.csv_titulos(em)


def test_despesas_recorrentes(base):
    financeiro.salvar_despesa({"descricao": "Sistema", "valor": "99,90", "vencimento": "2026-09-15", "recorrente": True})
    assert financeiro.gerar_despesas_recorrentes(date(2026, 10, 2)) == 1
    assert financeiro.gerar_despesas_recorrentes(date(2026, 10, 3)) == 0
    assert [d["vencimento"] for d in financeiro.listar_despesas()] == ["2026-09-15", "2026-10-15"]


# ---------------------------------------------------------------- robô

def test_robo_ponta_a_ponta(base, monkeypatch):
    enviados = []
    monkeypatch.setattr(cobranca, "enviar_email", lambda para, assunto, texto, cfg=None: enviados.append(assunto))
    config.salvar({"automacao": {"ativa": True}})
    financeiro.salvar_contrato({"cpf_cnpj": CLI_A["cpf_cnpj"], "valor": "374,40", "inicio": "2026-10", "dia_vencimento": 5})
    r = automacao.rodar(date(2026, 10, 2))
    assert r["titulos_gerados"] == 1 and r["nfse"] == {"emitidas": 1, "erros": 0} and r["cobrancas_criadas"] == 1
    assert r["regua"]["email"] == 1 and enviados == ["Lembrete: honorários vencem em 05/10/2026"]
    t = financeiro.listar_titulos()[0]
    assert t["nfse_status"] == "emitida" and t["pix_copia_cola"].startswith("000201")
    again = automacao.rodar(date(2026, 10, 2))
    assert again["titulos_gerados"] == 0 and again["nfse"] == {"emitidas": 0, "erros": 0}
    assert (db.caminho().parent / "backup").exists()


def test_robo_desligado_nao_faz_nada(base):
    assert automacao.rodar()["executado"] is False


def test_robo_em_homologacao_nao_emite(base, monkeypatch):
    monkeypatch.setenv("ITABORAI_AMBIENTE", "homologacao")
    config.salvar({"automacao": {"ativa": True}})
    financeiro.salvar_contrato({"cpf_cnpj": CLI_A["cpf_cnpj"], "valor": "100", "inicio": "2026-10"})
    r = automacao.rodar(date(2026, 10, 2))
    assert "homologação" in r["nfse"] and Simulador.recebidos == []


# ---------------------------------------------------------------- API da tela

def test_rotas_da_tela(base):
    assert tratar("estado", {})["config"]["smtp"]["senha"] == ""
    config.salvar({"smtp": {"senha": "segredo"}})
    assert tratar("config", {})["smtp"]["senha"] == "••••••"
    tratar("config/salvar", {"smtp": {"senha": "••••••", "host": "smtp.x"}})
    assert config.carregar()["smtp"]["senha"] == "segredo"
    r = tratar("emitir", {"cpf_cnpj": CLI_A["cpf_cnpj"], "valor": "374,40"})
    assert r["sucesso"] and r["titulo_id"]
    assert tratar("titulos", {"filtro": "a_receber"})[0]["id"] == r["titulo_id"]
    assert tratar("painel", {})["a_receber"] == 37440
    assert tratar("titulo/baixar", {"id": r["titulo_id"]})["status"] == "pago"
    assert "erro" in tratar("contrato/salvar", {"cpf_cnpj": "000", "valor": "1"})
    assert tratar("rota/inexistente", {}) == {"erro": "Rota inválida"}


def test_conciliacao_mesmo_cliente_quita_o_mais_antigo(base):
    velho = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "374,40", vencimento="2026-08-10", emitir_nfse=False)
    novo = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "374,40", vencimento="2026-09-10", emitir_nfse=False)
    ofx = ("<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20260912<TRNAMT>374.40<FITID>Z1"
           "<MEMO>PIX RECEBIDO RPS CONSULTORIA</STMTTRN></BANKTRANLIST>")
    assert conciliacao.importar(ofx)["titulos"] == 1
    assert financeiro.obter_titulo(velho)["status"] == "pago" and financeiro.obter_titulo(novo)["status"] == "aberto"
