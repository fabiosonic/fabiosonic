"""Motor de envio automático, webhook de respostas e painel — tudo simulado."""
import json
import tempfile
import threading
import unittest
import urllib.request
from datetime import datetime, timedelta
from http.server import ThreadingHTTPServer

from prospeccao import base as B
from prospeccao import fila, servidor
from prospeccao import whatsapp as W

CFG = {
    "escritorio": {"nome": "Escritório Teste", "cidade": "Itaboraí", "crc": "CRC/RJ 000000/O",
                   "site": "https://escritorio.test", "assinatura": "Equipe Teste"},
    "regiao": ["Itaboraí RJ"],
    "whatsapp": {"rampa": [2, 3], "teto_dia": 5, "max_por_hora": 4, "intervalo_min": [10, 10],
                 "hora_inicio": 9, "hora_fim": 18},
    "painel": {"token": "segredo"},
}
T0 = datetime(2026, 11, 17, 9, 0, tzinfo=fila.FUSO)   # terça


class ApiFalsa:
    def __init__(self, status=200, conectado=True, existe=True):
        self.status, self.on, self.tem, self.enviados = status, conectado, existe, []

    def conectado(self):
        return self.on

    def existe(self, numero):
        return self.tem

    def enviar(self, numero, texto):
        self.enviados.append((numero, texto))
        return self.status


class Automatico(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = B.Base(self.tmp.name)
        for n in range(8):
            lead, _ = self.base.adicionar({"empresa": f"Empresa {n}", "whatsapp": f"2198765000{n}", "setor": "Saúde",
                                           "fonte_whatsapp": "https://e.test", "fonte_lead": "https://m.test"})
            lead.update(status=B.PRONTO, o_que_vimos=f"Vimos a unidade {n}.", a_conta="A conta.", gancho="LC 123/2006")
        self.base.salvar()

    def tearDown(self):
        self.tmp.cleanup()

    def passo(self, api, agora):
        return W.passo(CFG, B.Base(self.tmp.name), api, agora, sorteio=lambda a, b: a)

    def test_intervalo_teto_e_rampa(self):
        api = ApiFalsa()
        self.assertTrue(self.passo(api, T0).startswith("enviado"))
        self.assertEqual(self.passo(api, T0 + timedelta(minutes=5)), "aguardando intervalo entre envios")
        self.assertTrue(self.passo(api, T0 + timedelta(minutes=11)).startswith("enviado"))
        self.assertEqual(self.passo(api, T0 + timedelta(minutes=30)), "teto de hoje atingido (2)")   # dia 1 da rampa
        amanha = T0 + timedelta(days=1)
        for m in (0, 11, 22):
            self.assertTrue(self.passo(api, amanha + timedelta(minutes=m)).startswith("enviado"))
        self.assertEqual(self.passo(api, amanha + timedelta(minutes=40)), "teto de hoje atingido (3)")
        self.assertEqual(len(api.enviados), 5)
        self.assertEqual(len({t for _, t in api.enviados}), 5)          # nenhum texto repetido
        self.assertIn("não enviaremos mais mensagens", api.enviados[0][1])

    def test_nao_envia_fora_da_janela(self):
        api = ApiFalsa()
        self.assertIn("aguardando janela", self.passo(api, T0.replace(hour=20)))
        self.assertIn("aguardando janela", self.passo(api, T0 - timedelta(days=2)))   # domingo
        self.assertEqual(api.enviados, [])

    def test_falhas_em_serie_pausam_o_motor(self):
        api = ApiFalsa(status=403)
        self.passo(api, T0)
        self.passo(api, T0 + timedelta(minutes=1))
        est = W.ler_estado(B.Base(self.tmp.name))
        self.assertTrue(est["pausado"])
        self.assertTrue(self.passo(ApiFalsa(), T0 + timedelta(hours=1)).startswith("pausado"))
        self.assertTrue(all(l["status"] == B.PRONTO for l in B.Base(self.tmp.name).leads))   # nada marcado como enviado

    def test_numero_sem_whatsapp_e_descartado(self):
        api = ApiFalsa(existe=False)
        self.assertIn("descartado", self.passo(api, T0))
        self.assertEqual(api.enviados, [])

    def test_pouca_resposta_pausa(self):
        base = B.Base(self.tmp.name)
        for n in range(20):
            lead, _ = base.adicionar({"empresa": f"Antiga {n}", "whatsapp": f"2197000{n:04d}", "fonte_lead": "x"})
            lead.update(status=B.ENVIADO, canal_usado="whatsapp", data_1="2026-11-10", resultado="sem_resposta")
        base.salvar()
        self.assertEqual(self.passo(ApiFalsa(), T0), "pausado por taxa de resposta")

    def _msg(self, numero, texto):
        return {"event": "messages.upsert", "data": {"key": {"remoteJid": f"55{numero}@s.whatsapp.net", "fromMe": False},
                                                      "message": {"conversation": texto}}}

    def test_respostas_pelo_webhook(self):
        api = ApiFalsa()
        self.passo(api, T0)
        numero = api.enviados[0][0]
        base = B.Base(self.tmp.name)
        self.assertEqual(W.receber(CFG, base, api, self._msg(numero, "Bom dia, podem mandar a proposta?")), "resposta registrada")
        lead = next(l for l in B.Base(self.tmp.name).leads if l["whatsapp"] == numero)
        self.assertEqual((lead["status"], lead["resultado"]), (B.EM_CONVERSA, "respondeu"))
        # número sem o nono dígito no identificador do WhatsApp também casa
        self.passo(api, T0 + timedelta(minutes=11))
        n2 = api.enviados[1][0]
        base = B.Base(self.tmp.name)
        self.assertEqual(W.receber(CFG, base, api, self._msg(n2[:2] + n2[3:], "Não me mandem mais mensagem")), "removido a pedido")
        lead2 = next(l for l in B.Base(self.tmp.name).leads if l["whatsapp"] == n2)
        self.assertEqual(lead2["status"], B.REMOVIDO)
        self.assertTrue(B.Base(self.tmp.name).esta_removido(lead2))
        self.assertIn("Retiramos o contato", api.enviados[-1][1])
        self.assertEqual(W.receber(CFG, base, api, self._msg("21911112222", "oi")), "mensagem de quem não está na prospecção")

    def test_sessao_encerrada_pelo_whatsapp_pausa(self):
        base = B.Base(self.tmp.name)
        W.receber(CFG, base, None, {"event": "CONNECTION_UPDATE", "data": {"state": "close", "statusReason": 401}})
        self.assertTrue(W.ler_estado(base)["pausado"])

    def test_gravacoes_concorrentes_nao_se_perdem(self):
        a, b = B.Base(self.tmp.name), B.Base(self.tmp.name)
        a.leads[0]["status"] = B.ENVIADO
        b.leads[1]["dor"] = "nova dor"
        a.salvar(); b.salvar()
        final = B.Base(self.tmp.name).leads
        self.assertEqual((final[0]["status"], final[1]["dor"]), (B.ENVIADO, "nova dor"))

    def test_painel_http(self):
        api = ApiFalsa()
        self.passo(api, T0)
        srv = ThreadingHTTPServer(("127.0.0.1", 0), servidor.criar_handler(CFG, self.tmp.name, api))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{srv.server_port}"
        try:
            with self.assertRaises(urllib.error.HTTPError):
                urllib.request.urlopen(url + "/api/painel")                      # sem token
            d = json.load(urllib.request.urlopen(url + "/api/painel?t=segredo"))
            self.assertEqual(d["totais"]["enviados"], 1)
            self.assertEqual(d["funil"][0]["n"], 8)
            urllib.request.urlopen(urllib.request.Request(url + "/api/pausar?t=segredo", data=b"{}"))
            self.assertTrue(json.load(urllib.request.urlopen(url + "/api/painel?t=segredo"))["motor"]["pausado"])
            corpo = json.dumps(self._msg(api.enviados[0][0], "parar")).encode()
            r = json.load(urllib.request.urlopen(urllib.request.Request(url + "/webhook/segredo", data=corpo)))
            self.assertEqual(r["ok"], "removido a pedido")
            self.assertIn(b"Painel", urllib.request.urlopen(url + "/?t=segredo").read())
        finally:
            srv.shutdown()


if __name__ == "__main__":
    unittest.main()
