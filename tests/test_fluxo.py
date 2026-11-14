"""Ciclo completo com site e IA simulados — nenhuma chamada externa."""
import csv
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from prospeccao import base as B
from prospeccao import etapas, fila, site

CFG = {
    "escritorio": {"nome": "Escritório Teste", "cidade": "Itaboraí", "crc": "CRC/RJ 000000/O",
                   "site": "https://escritorio.test", "assinatura": "Equipe Teste"},
    "regiao": ["Itaboraí RJ"],
    "whatsapp": {"teto_dia": 2, "hora_inicio": 9, "hora_fim": 18, "feriados_extras": []},
}
TERCA_10H = datetime(2026, 11, 17, 10, 0, tzinfo=fila.FUSO)

HOME = """<html><body><h1>Laboratório Vida</h1><p>Coleta nas unidades de Manilha e Centro. Atendemos convênios.</p>
<a href="/quem-somos">Quem somos</a><a href="https://wa.me/5521987654321">WhatsApp</a>
<a href="https://www.linkedin.com/company/lab-vida?x=1">in</a></body></html>"""
SOBRE = "<html><body><p>Dra. Ana Souza, sócia-diretora. Carlos Lima, analista de marketing.</p></body></html>"


def baixar_falso(url):
    return SOBRE if "quem-somos" in url else HOME


def ler_site_falso(url):
    return site.ler_site(url, baixar_fn=baixar_falso)


def ia_falsa(vimos="Vimos que o Laboratório Vida faz coleta nas unidades de Manilha e Centro e atende convênios.",
             conta="Em laboratório com convênio, a retenção de 11% do INSS (Lei 8.212/1991, art. 31) precisa ser "
                   "acompanhada mês a mês, senão o valor fica parado."):
    def ia(sistema, usuario, schema, modelo=None):
        if "pessoas" in schema["properties"]:
            return {"ativa": True, "rede_nacional": False, "subsetor": "Laboratório de análises clínicas",
                    "porte": "2 unidades", "ticket": "alto", "motivo_descarte": "",
                    "sinais": [{"sinal": "mais de uma unidade", "evidencia": "unidades de Manilha e Centro",
                                "url": "https://lab.test"}],
                    "pessoas": [{"nome": "Carlos Lima", "cargo": "analista de marketing", "url": "https://lab.test/quem-somos"},
                                {"nome": "Ana Souza", "cargo": "sócia-diretora", "url": "https://lab.test/quem-somos"}]}
        return {"dores": [{"dor": "retenção de convênio", "por_que_nesta_empresa": "atende convênios"}],
                "gancho": "Lei 8.212/1991 art. 31", "o_que_vimos": vimos, "a_conta": conta,
                "evidencias": [{"fato": "duas unidades", "url": "https://lab.test"}]}
    return ia


class Fluxo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = B.Base(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _lead(self, **k):
        dados = {"empresa": "Laboratório Vida", "municipio": "Itaboraí", "site": "https://lab.test",
                 "fonte_lead": "https://maps.test/1", **k}
        return self.base.adicionar(dados)

    def test_contato_so_vale_celular_publicado(self):
        self.assertTrue(B.eh_celular("+55 (21) 98765-4321"))
        self.assertFalse(B.eh_celular("(21) 2645-1234"))
        leitura = ler_site_falso("https://lab.test")
        self.assertEqual(leitura["whatsapp"], "21987654321")
        self.assertEqual(leitura["fonte_whatsapp"], "https://lab.test")
        self.assertEqual(leitura["linkedin"], "https://www.linkedin.com/company/lab-vida")

    def test_decisor_por_cargo(self):
        self.assertEqual(etapas.nivel_decisor("Sócia-diretora"), "A")
        self.assertEqual(etapas.nivel_decisor("Gerente Financeiro"), "B")
        self.assertEqual(etapas.nivel_decisor("Analista de RH"), "")
        self.assertEqual(etapas.nivel_decisor("Diretor comercial e sócio"), "A")

    def test_dedupe_e_concorrente(self):
        self._lead()
        self.assertEqual(self._lead()[1], "já está na base")
        conta = {"entraram": 0, "descartes": {}}
        etapas._entrar(self.base, {"empresa": "Silva Contabilidade", "fonte_lead": "x"}, conta)
        self.assertEqual(conta["descartes"], {"concorrente": 1})

    def test_importar_csv_do_scraper(self):
        arq = Path(self.tmp.name, "gmaps.csv")
        with arq.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["title", "category", "website", "phone", "link"])
            w.writerow(["Clínica Sorriso", "Dentista", "https://sorriso.test", "(21) 99999-0000", "https://maps.test/2"])
            w.writerow(["Padaria Fixa", "Padaria", "", "(21) 2222-0000", "https://maps.test/3"])
        self.assertEqual(etapas.importar(self.base, str(arq), setor="Saúde")["entraram"], 2)
        self.assertEqual(self.base.leads[0]["whatsapp"], "21999990000")
        self.assertEqual(self.base.leads[1]["whatsapp"], "")  # fixo não vira WhatsApp

    def test_ciclo_ate_a_fila(self):
        self._lead()
        self.assertEqual(etapas.qualificar(CFG, self.base, ler_site=ler_site_falso, ia=ia_falsa())["qualificados"], 1)
        lead = self.base.leads[0]
        self.assertEqual((lead["decisor_nome"], lead["decisor_nivel"], lead["prioridade"]), ("Ana Souza", "A", "A"))
        self.assertEqual(etapas.material(CFG, self.base, ler_site=ler_site_falso, ia=ia_falsa())["prontos"], 1)

        out = fila.gerar(CFG, self.base, TERCA_10H)
        self.assertEqual(len(out["fila"]), 1)
        texto = lead["texto_enviado"]
        self.assertTrue(texto.startswith("Bom dia, Ana. Aqui é da Escritório Teste, de Itaboraí."))
        self.assertIn("CRC/RJ 000000/O", texto)
        self.assertIn("não enviaremos mais mensagens", texto)
        pagina = Path(out["arquivo"]).read_text(encoding="utf-8")
        self.assertIn("web.whatsapp.com/send?phone=5521987654321", pagina)

        fila.marcar_enviado(self.base, lead["id"], TERCA_10H)
        self.assertEqual(fila.enviados_hoje(self.base, TERCA_10H.date()), 1)
        fila.registrar_resultado(self.base, lead["id"], "optout", "pediu para parar")
        self.assertEqual(lead["status"], B.REMOVIDO)
        self.assertEqual(self._lead(empresa="Laboratorio Vida LTDA")[1], "pediu remoção")

    def test_checklist_barra_texto_proibido(self):
        casos = {
            "trabalho gratuito": "Fazemos um diagnóstico gratuito, sem compromisso.",
            "recuperação de crédito": "O recolhido a maior dos últimos cinco anos ainda é recuperável.",
            "ataque ao colega": "Seu contador atual provavelmente não faz essa conta.",
            "norma revogada": "O CPC 17 define a receita da obra.",
            "norma fora da base conferida: 12.345": "A Lei 12.345/2030 mudou a regra.",
        }
        for alerta, conta in casos.items():
            self._lead(empresa=alerta)
            lead = self.base.leads[-1]
            lead.update(o_que_vimos="Vimos as duas unidades.", a_conta=conta, evidencias='[{"fato":"x","url":"y"}]')
            self.assertIn(alerta, etapas.revisar(lead), conta)

    def test_texto_com_alerta_nao_entra_na_fila(self):
        self._lead()
        etapas.qualificar(CFG, self.base, ler_site=ler_site_falso, ia=ia_falsa())
        r = etapas.material(CFG, self.base, ler_site=ler_site_falso, ia=ia_falsa(conta="Vocês vão economizar 30%!"))
        self.assertEqual(r, {"prontos": 0, "com_alerta": 1})
        self.assertEqual(fila.gerar(CFG, self.base, TERCA_10H)["fila"], [])

    def test_janela_e_teto(self):
        self.assertFalse(fila.janela_aberta(CFG, datetime(2026, 11, 14, 11, 0, tzinfo=fila.FUSO))[0])  # sábado
        self.assertFalse(fila.janela_aberta(CFG, datetime(2026, 11, 17, 20, 0, tzinfo=fila.FUSO))[0])  # 20h
        self.assertFalse(fila.janela_aberta(CFG, datetime(2026, 11, 20, 10, 0, tzinfo=fila.FUSO))[0])  # feriado
        self.assertFalse(fila.janela_aberta(CFG, datetime(2026, 4, 3, 10, 0, tzinfo=fila.FUSO))[0])    # Sexta Santa
        self.assertTrue(fila.janela_aberta(CFG, TERCA_10H)[0])
        for n in range(4):
            lead, _ = self._lead(empresa=f"Empresa {n}", whatsapp=f"2198765000{n}", fonte_whatsapp="https://e.test")
            lead.update(status=B.PRONTO, o_que_vimos=f"Vimos {n}.", a_conta="x", evidencias="[]", dor="[]")
        self.assertEqual(len(fila.gerar(CFG, self.base, TERCA_10H)["fila"]), 2)  # teto_dia = 2
        for l in [l for l in self.base.leads if l["status"] == B.NA_FILA]:
            fila.marcar_enviado(self.base, l["id"], TERCA_10H)
        self.assertEqual(fila.gerar(CFG, self.base, TERCA_10H)["motivo"], "teto diário atingido")


if __name__ == "__main__":
    unittest.main()
