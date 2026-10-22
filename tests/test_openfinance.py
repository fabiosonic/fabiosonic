import json
import os
import tempfile
import unittest
from datetime import date, datetime
from decimal import Decimal

from mo_openfinance import contabil, sincronizar
from mo_openfinance.__main__ import exportar, importar_protocolo
from mo_openfinance.banco import Banco
from mo_openfinance.modelo import Transacao
from mo_openfinance.provedores import (Pluggy, normalizar_protocolo_tecnospeed, normalizar_transacao_pluggy,
                                       normalizar_transacao_tecnospeed)

EXEMPLOS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "exemplos", "openfinance")


def exemplo(nome):
    with open(os.path.join(EXEMPLOS, nome), encoding="utf-8") as fh:
        return json.load(fh)


def cfg():
    return contabil.Configuracao(exemplo("config_empresa.json"))


def soma_banco(linhas, conta_banco="7"):
    """Efeito líquido das partidas na conta banco (D soma, C subtrai)."""
    return sum((p.valor if p.debito == conta_banco else -p.valor) for p in linhas
               if conta_banco in (p.debito, p.credito))


class TestNormalizacao(unittest.TestCase):
    def test_protocolo_ignora_duplicadas_e_aplica_sinal(self):
        status, _, novas = normalizar_protocolo_tecnospeed(exemplo("protocolo_bank.json"))
        self.assertEqual(status, "SUCCESS")
        ids = {t.id for t in novas}
        self.assertNotIn("c0-ja-importada", ids)
        self.assertEqual(len(novas), 7)
        por_id = {t.id: t for t in novas}
        self.assertEqual(por_id["c1-pix-cliente"].valor, Decimal("1500.00"))
        self.assertEqual(por_id["d1-boleto-juros"].valor, Decimal("-100.00"))
        # entrada: contraparte é quem pagou; saída: quem recebeu
        self.assertEqual(por_id["c1-pix-cliente"].contraparte_doc, "22222222000122")
        self.assertEqual(por_id["d1-boleto-juros"].contraparte_doc, "33333333000133")
        self.assertEqual(por_id["c2-pix-socio"].contraparte_doc, "12345678900")

    def test_protocolo_em_processamento_nao_devolve_transacoes(self):
        r = {"statement": {"status": "PROCESSING", "reason": None}}
        self.assertEqual(normalizar_protocolo_tecnospeed(r), ("PROCESSING", None, []))

    def test_tecnospeed_natureza_invalida(self):
        with self.assertRaises(ValueError):
            normalizar_transacao_tecnospeed({"transactionId": "x", "transactionType": "?", "amount": "1", "date": "2026-01-01"}, "c")

    def test_pluggy(self):
        item = {"id": "p1", "accountId": "acc-1", "type": "DEBIT", "amount": -150.5, "date": "2026-10-07T03:00:00.000Z",
                "description": "Pagamento", "descriptionRaw": "PAG BOLETO FORN", "category": "Services",
                "paymentData": {"paymentMethod": "BOLETO", "receiver": {"name": "FORN", "documentNumber":
                                {"type": "CNPJ", "value": "33.333.333/0001-33"}},
                                "boletoMetadata": {"baseAmount": 150, "interestAmount": 0.5}},
                "merchant": {"cnpj": "33333333000133", "cnae": "4711302"}}
        t = normalizar_transacao_pluggy(item)
        self.assertEqual(t.valor, Decimal("-150.50"))
        self.assertEqual(t.data, "2026-10-07")
        self.assertEqual(t.descricao, "PAG BOLETO FORN")
        self.assertEqual(t.contraparte_doc, "33333333000133")
        self.assertEqual(t.boleto_juros, Decimal("0.50"))

    def test_pluggy_ignora_pendentes(self):
        p = Pluggy(client_id="x", client_secret="y")
        p._get = lambda caminho, **q: {"totalPages": 1, "results": [
            {"id": "a", "type": "CREDIT", "amount": 10, "date": "2026-10-01", "status": "POSTED"},
            {"id": "b", "type": "CREDIT", "amount": 20, "date": "2026-10-01", "status": "PENDING"}]}
        self.assertEqual([t.id for t in p.transacoes(None, "acc", "2026-10-01", "2026-10-02")], ["a"])


class TestBanco(unittest.TestCase):
    def test_idempotencia(self):
        db = Banco()
        _, _, novas = normalizar_protocolo_tecnospeed(exemplo("protocolo_bank.json"))
        self.assertEqual(db.gravar(novas), 7)
        self.assertEqual(db.gravar(novas), 0)

    def test_janela_de_6h_e_virada_do_dia(self):
        db = Banco()
        db.registrar_protocolo("u1", "c", "BANK", "2026-10-01", "2026-10-02", quando=datetime(2026, 10, 2, 8, 0))
        self.assertFalse(db.pode_solicitar("c", "BANK", 6, datetime(2026, 10, 2, 13, 59)))
        self.assertTrue(db.pode_solicitar("c", "BANK", 6, datetime(2026, 10, 2, 14, 0)))
        self.assertTrue(db.pode_solicitar("c", "CREDIT_CARD", 6, datetime(2026, 10, 2, 9, 0)))
        db.registrar_protocolo("u2", "c", "BANK", "x", "y", quando=datetime(2026, 10, 2, 22, 0))
        self.assertTrue(db.pode_solicitar("c", "BANK", 6, datetime(2026, 10, 3, 0, 5)))   # contador zera às 00h
        db.atualizar_protocolo("u2", "FAILED")
        self.assertTrue(db.pode_solicitar("c", "BANK", 6, datetime(2026, 10, 2, 22, 30)))  # falha não consome janela

    def test_exclusao_so_estorna_o_que_ja_foi_exportado(self):
        db = Banco()
        _, _, novas = normalizar_protocolo_tecnospeed(exemplo("protocolo_bank.json"))
        db.gravar(novas)
        db.marcar_exportadas(["d3-tarifa"])
        self.assertEqual(db.marcar_excluidas(["d3-tarifa", "d4-sem-regra", "inexistente"]), ["d3-tarifa"])
        self.assertEqual([t.id for t in db.a_estornar()], ["d3-tarifa"])
        self.assertNotIn("d4-sem-regra", [t.id for t in db.a_exportar()])


class TestContabil(unittest.TestCase):
    def setUp(self):
        _, _, novas = normalizar_protocolo_tecnospeed(exemplo("protocolo_bank.json"))
        self.t = {t.id: t for t in novas}
        self.cfg = cfg()

    def test_partidas_fecham_com_o_extrato(self):
        for t in self.t.values():
            self.assertEqual(soma_banco(contabil.partidas(t, self.cfg)), t.valor, t.id)

    def test_cliente_por_documento(self):
        (p,) = contabil.partidas(self.t["c1-pix-cliente"], self.cfg)
        self.assertEqual((p.debito, p.credito, p.pendente), ("7", "1201", ""))

    def test_socio_sempre_pendente(self):
        (p,) = contabil.partidas(self.t["c2-pix-socio"], self.cfg)
        self.assertEqual(p.credito, "999")
        self.assertIn("sócio", p.pendente)

    def test_transferencia_propria(self):
        (p,) = contabil.partidas(self.t["c3-ted-propria"], self.cfg)
        self.assertEqual((p.debito, p.credito, p.pendente), ("7", "998", ""))

    def test_boleto_com_juros_desdobra(self):
        linhas = contabil.partidas(self.t["d1-boleto-juros"], self.cfg)
        self.assertEqual([(p.debito, p.credito, p.valor) for p in linhas],
                         [("2101", "7", Decimal("90.00")), ("4301", "7", Decimal("10.00"))])

    def test_boleto_com_desconto_baixa_titulo_cheio(self):
        linhas = contabil.partidas(self.t["d2-boleto-desconto"], self.cfg)
        fornecedor = sum(p.valor for p in linhas if p.debito == "211")
        self.assertEqual(fornecedor, Decimal("200.00"))
        self.assertIn(("211", "3301", Decimal("10.00")), [(p.debito, p.credito, p.valor) for p in linhas])

    def test_boleto_que_nao_fecha_nao_desdobra(self):
        t = self.t["d1-boleto-juros"]
        t.boleto_juros = Decimal("7.00")
        (p,) = contabil.partidas(t, self.cfg)
        self.assertEqual(p.valor, Decimal("100.00"))
        self.assertIn("não fecha", p.pendente)

    def test_regra_por_texto_e_transitoria(self):
        (tarifa,) = contabil.partidas(self.t["d3-tarifa"], self.cfg)
        self.assertEqual(tarifa.debito, "4310")
        (sem,) = contabil.partidas(self.t["d4-sem-regra"], self.cfg)
        self.assertEqual((sem.debito, sem.pendente), ("999", "sem regra para esta transação"))

    def test_estorno_inverte(self):
        (p,) = contabil.partidas(self.t["d3-tarifa"], self.cfg, estorno=True)
        self.assertEqual((p.debito, p.credito), ("7", "4310"))
        self.assertTrue(p.complemento.startswith("ESTORNO"))

    def test_conta_sem_mapeamento(self):
        t = Transacao(id="x", conta="outra", tipo_extrato="BANK", data="2026-10-01", valor=Decimal("1"))
        with self.assertRaises(KeyError):
            contabil.partidas(t, self.cfg)

    def test_fechamento(self):
        self.assertFalse(contabil.fechamento_liberado("2026-09", date(2026, 10, 7)))
        self.assertTrue(contabil.fechamento_liberado("2026-09", date(2026, 10, 8)))
        self.assertTrue(contabil.fechamento_liberado("2026-02", date(2026, 3, 8)))


class TestFluxo(unittest.TestCase):
    def test_ponta_a_ponta_com_webhooks(self):
        pasta = tempfile.mkdtemp()
        db = Banco(os.path.join(pasta, "of.db"))
        importar_protocolo(db, os.path.join(EXEMPLOS, "protocolo_bank.json"))
        txt = os.path.join(pasta, "l.txt")
        self.assertIn("9 partida(s)", exportar(db, cfg(), txt, os.path.join(pasta, "p.csv")))
        with open(txt, encoding="cp1252") as fh:
            linhas = fh.read().splitlines()
        self.assertEqual(linhas[0], "05/10/2026;7;1201;1500,00;1;CLIENTE ALFA LTDA")
        # nada novo na segunda exportação
        self.assertIn("0 partida(s)", exportar(db, cfg(), txt))

        evento = exemplo("webhook_transaction_deleted.json")
        self.assertIn("1 já contabilizada", sincronizar.processar_webhook(db, evento))
        self.assertEqual(sincronizar.processar_webhook(db, evento), "evento repetido ignorado")
        self.assertIn("1 estorno(s)", exportar(db, cfg(), txt))
        self.assertIn("0 estorno(s)", exportar(db, cfg(), txt))

    def test_status_da_conexao(self):
        db = Banco()
        db.registrar_conta("acc-1", "EMP", "pluggy", item="item-9")
        self.assertIn("ativa", sincronizar.processar_webhook(db, {"event": "item/created", "itemId": "item-9"}))
        self.assertEqual(db.contas("ATIVA")[0]["conta"], "acc-1")
        db.registrar_conta("hash", "EMP", "tecnospeed", status="ATIVA")
        msg = sincronizar.processar_webhook(db, {"event": "STATEMENT_OPENFINANCE_REVOKED", "data": {"accountHash": "hash"}})
        self.assertIn("nova autorização", msg)
        self.assertEqual([c["conta"] for c in db.contas("INATIVA")], ["hash"])

    def test_solicitar_e_recolher_com_provedor_falso(self):
        class Falso:
            nome, intervalo_protocolo_horas = "tecnospeed", 6

            def __init__(self):
                self.pedidos = []

            def gerar_protocolo(self, pagador, conta, inicio, fim, tipo, cartao):
                self.pedidos.append((pagador, conta, inicio, fim, tipo))
                return f"u{len(self.pedidos)}"

            def consultar_protocolo(self, pagador, uid):
                return normalizar_protocolo_tecnospeed(exemplo("protocolo_bank.json"))

        db, prov, pag = Banco(), Falso(), {"EMP": "11111111000111"}
        db.registrar_conta("gDyriq_q39", "EMP", "tecnospeed", status="ATIVA")
        db.registrar_conta("pendente", "EMP", "tecnospeed")
        manha = datetime(2026, 10, 22, 7, 0)
        self.assertEqual(sincronizar.solicitar_extratos(db, prov, pag, date(2026, 10, 22), quando=manha), ["u1"])
        self.assertEqual(prov.pedidos[0], ("11111111000111", "gDyriq_q39", "2026-10-19", "2026-10-22", "BANK"))
        self.assertEqual(sincronizar.solicitar_extratos(db, prov, pag, date(2026, 10, 22),
                                                        quando=datetime(2026, 10, 22, 9, 0)), [])
        self.assertEqual(sincronizar.recolher_protocolos(db, prov, pag), {"u1": ("SUCCESS", 7)})
        self.assertEqual(db.protocolos_pendentes(), [])


if __name__ == "__main__":
    unittest.main()
