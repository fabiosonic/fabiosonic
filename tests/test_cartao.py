"""Cartão de crédito pela InfinitePay (simulada): taxa repassada, link na cobrança, "Pago no cartão" com conferência
pelo comprovante, taxa lançada como despesa, NFS-e pelo valor pago e cancelamento do boleto."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from nfse_itaborai import automacao, cartao, cobranca, config, financeiro
from nfse_itaborai.tela import tratar
from test_emissor import Simulador, ambiente  # noqa: F401  (fixture)
from test_financeiro import CLI_A, base  # noqa: F401  (fixture)


class FakeInfinitePay(BaseHTTPRequestHandler):
    links: list = []
    pagos: dict = {}            # (order_nsu, transaction_nsu, slug) -> valor pago (centavos)

    def log_message(self, *a):
        pass

    def _json(self, d, code=200):
        b = json.dumps(d).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_POST(self):  # noqa: N802
        js = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if js.get("handle") != "moraes_contab":
            return self._json({"message": "handle inválido"}, 422)
        if self.path == "/links":
            if "customer" in js and not js["customer"]["phone_number"].startswith("+55"):
                return self._json({"message": "telefone inválido"}, 422)
            FakeInfinitePay.links.append(js)
            return self._json({"url": f"https://checkout.infinitepay.io/moraes_contab?lenc={js['order_nsu']}"}, 201)
        if self.path == "/payment_check":
            v = FakeInfinitePay.pagos.get((js["order_nsu"], js["transaction_nsu"], js["slug"]))
            return self._json({"success": True, "paid": bool(v), "amount": v or 0, "paid_amount": v or 0,
                               "installments": 1, "capture_method": "credit_card"})
        self._json({}, 404)


@pytest.fixture
def infinite(base):  # noqa: F811
    srv = ThreadingHTTPServer(("127.0.0.1", 0), FakeInfinitePay)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    FakeInfinitePay.links, FakeInfinitePay.pagos = [], {}
    config.salvar({"cobranca": {"provedor": "pix", "cartao_provedor": "infinitepay", "cartao_infinitepay_tag": "$moraes_contab",
                                "cartao_taxa_1x": 4.20, "cartao_infinitepay_url": f"http://127.0.0.1:{srv.server_address[1]}"}})
    yield
    srv.shutdown()


def test_taxa_repassada_mantem_o_honorario_cheio():
    cfg = {"cobranca": {"cartao_repassar": True, "cartao_taxa_1x": 4.20, "cartao_taxa_2a6": 7.5, "cartao_taxa_7a12": 12.4,
                        "cartao_taxa_fixa": 0, "cartao_parcelas_max": 12}}
    v = cartao.valor_no_cartao(100000, 1, cfg)
    assert v["total_cent"] == 104385 and v["acrescimo_cent"] == 4385          # 1000 / (1 - 4,20%)
    assert 0 <= v["total_cent"] * (1 - 0.042) - 100000 < 1                       # sobra o honorário cheio
    assert cartao.valor_no_cartao(100000, 10, cfg)["taxa_pct"] == 12.4
    cfg["cobranca"]["cartao_repassar"] = False
    assert cartao.valor_no_cartao(100000, 1, cfg)["acrescimo_cent"] == 0


def test_link_na_cobranca_e_pago_no_cartao(infinite):
    config.salvar({"emissao": {"nfse_quando": "baixa"}})
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "1000,00", "HONORARIOS OUTUBRO", vencimento="2026-10-10",
                                  emitir_nfse=True, apos_pagamento=True)
    cobranca.preparar_pagamento(tid)                                           # PIX + link do cartão
    t = financeiro.obter_titulo(tid)
    pedido = FakeInfinitePay.links[0]
    assert pedido["handle"] == "moraes_contab" and pedido["items"][0]["price"] == 104385
    assert pedido["order_nsu"] == f"T{tid}-1" and pedido["customer"]["phone_number"].startswith("+55")
    assert t["cartao_link"].startswith("https://checkout.infinitepay.io/") and t["cartao_status"] == "aberto"
    _, texto = cobranca.mensagem(t, -3)
    assert "Prefere pagar com cartão" in texto and "R$ 1.043,85" in texto and "sem acréscimo" in texto
    assert cartao.gerar_link(tid)["reaproveitado"]
    r = tratar("titulo/pago_cartao", {"id": tid, "data": "2026-10-12"})
    assert r["ok"] and not r["conferido"]
    t = financeiro.obter_titulo(tid)
    assert t["status"] == "pago" and t["forma_pagamento"] == "cartao" and t["valor_pago_cent"] == 104385
    assert t["valor_cent"] == 104385 and t["nfse_status"] == "emitida"        # NFS-e pelo valor pago no cartão
    taxa = [d for d in financeiro.listar_despesas("pago") if "Taxa do cartão" in d["descricao"]]
    assert taxa and taxa[0]["valor_cent"] == 4384 and taxa[0]["categoria"] == "Bancárias"


def test_conferencia_pelo_comprovante(infinite):
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "500", vencimento="2026-10-10", emitir_nfse=False)
    cartao.gerar_link(tid)
    order = financeiro.obter_titulo(tid)["cartao_id"]
    recibo = f"https://exemplo/retorno?order_nsu={order}&slug=abc123&transaction_nsu=9f1c2d3e-0000-4000-8000-123456789abc"
    with pytest.raises(cartao.ErroCartao, match="não confirmou"):
        cartao.confirmar_pagamento(tid, comprovante=recibo)
    FakeInfinitePay.pagos[(order, "9f1c2d3e-0000-4000-8000-123456789abc", "abc123")] = 52193
    r = cartao.confirmar_pagamento(tid, comprovante=recibo)
    assert r["conferido"] and financeiro.obter_titulo(tid)["valor_pago_cent"] == 52193
    with pytest.raises(cartao.ErroCartao, match="código da transação"):
        cartao.confirmar_pagamento(financeiro.criar_titulo(CLI_A["cpf_cnpj"], "10", vencimento="2026-10-10",
                                                          emitir_nfse=False), comprovante="texto qualquer")


def test_pago_por_pix_encerra_o_link_e_rotas(infinite):
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "600", vencimento="2026-10-10", emitir_nfse=False)
    r = tratar("titulo/cartao", {"id": tid, "parcelas": 1})
    assert r["link"] and r["acrescimo_cent"] > 0
    financeiro.baixar(tid, "2026-10-09", "600", "pix")
    res = automacao.rodar(forcar=True)
    assert res["cartao_links_encerrados"] == 1 and financeiro.obter_titulo(tid)["cartao_status"] == "encerrado"
    assert "Prefere pagar com cartão" not in cobranca.mensagem(financeiro.obter_titulo(tid), 1)[1]
    assert tratar("cartao/testar", {})["ok"]


def test_tag_errada(infinite):
    config.salvar({"cobranca": {"cartao_infinitepay_tag": "outra"}})
    r = tratar("cartao/testar", {})
    assert r["sucesso"] is False and "handle" in r["erro"]
