"""Testes offline do swing trade comprado e vendido.

    python3 -m unittest discover -s tests -v
"""

import csv
import datetime
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_b3 import (CFG, ComPasta, FIX, RAIZ, b3lib, boleta, carregar, orcamento, risco, rodar,  # noqa: E402
                     scan, utc)

swing = carregar("b3-swing", "swing.py")
SW = os.path.join(FIX, "swing")
AGORA = "2026-10-26 09:00"
CFG_V = dict(CFG, permitir_vendido=True, max_perda_por_operacao=200, orcamento=30000)
APURACAO = os.path.join(os.path.dirname(RAIZ), ".claude", "skills", "traders", "scripts", "apuracao_mensal.py")


def dias(sym):
    return swing.pregoes_diarios(b3lib.obter_chart(sym, offline=SW), utc(AGORA), CFG)


class SetupsDeVenda(unittest.TestCase):
    def test_espelhos(self):
        tags, _ = scan.setups([10.0] * 30 + [9.0])
        self.assertIn("perdeu_20d", tags)
        tags, _ = scan.setups([10.0] * 20 + [10 + 0.2 * i for i in range(1, 12)])
        self.assertIn("sobrecomprado", tags)
        self.assertEqual({scan.LADO_SETUP[t] for t in ("perdeu_20d", "sobrecomprado")}, {"venda"})

    def test_filtro_de_lado(self):
        rc, out = rodar(scan, ["diario", "--lado", "venda", "--symbols", "B3SA3,PETR4", "--offline",
                               os.path.join(FIX, "scanner", "diario"), "--now", AGORA, "--no-write", "--json"])
        self.assertEqual(rc, 0)
        self.assertIn("B3SA3", out)
        self.assertNotIn('"PETR4"', out)


class Plano(unittest.TestCase):
    def test_vendido_gatilho_na_minima(self):
        d = dias("B3SA3")
        p = swing.montar_plano("B3SA3", "venda", d, CFG_V)
        self.assertEqual(p["entrada"], round(d[-1]["l"] - 0.01, 2))
        self.assertGreater(p["stop"], p["entrada"])
        self.assertLess(p["alvo"], p["entrada"])
        self.assertEqual(p["tipo_entrada"], "stop")
        self.assertEqual((p["dia"], p["prazo_ate"]), ("2026-10-26", "2026-11-16"))  # 15 pregões, 02/11 é feriado
        self.assertIn("sobrecomprado", p["setups"])

    def test_comprado_atr(self):
        p = swing.montar_plano("WEGE3", "compra", dias("WEGE3"), CFG, stop_txt="atr:2", alvo_txt="3R")
        self.assertLess(p["stop"], p["entrada"])
        self.assertAlmostEqual(p["risco_retorno"], 3.0, places=1)

    def test_aviso_sem_permissao_de_vendido(self):
        p = swing.montar_plano("B3SA3", "venda", dias("B3SA3"), CFG)
        self.assertTrue(any("permitir_vendido" in a for a in p["avisos"]))

    def test_stop_do_lado_errado(self):
        with self.assertRaises(b3lib.B3Erro):
            swing.montar_plano("PETR4", "venda", dias("PETR4"), CFG_V, stop_txt="preco:1")


class Simulacao(unittest.TestCase):
    def test_gap_executa_na_abertura(self):
        self.assertEqual(swing.um_dia(9.0, 9.5, 8.8, 9.2, 9.5, 12.0, 1), (9.0, "stop"))     # comprado, gap abaixo
        self.assertEqual(swing.um_dia(11.0, 11.2, 10.9, 11.0, 10.5, 8.0, -1), (11.0, "stop"))  # vendido, gap acima
        self.assertEqual(swing.um_dia(10.0, 10.6, 9.4, 10.0, 9.5, 10.5, 1), (9.5, "stop"))  # toca os dois: stop

    def test_deterministico_e_completo(self):
        p = swing.montar_plano("B3SA3", "venda", dias("B3SA3"), CFG_V)
        ch = b3lib.obter_chart("B3SA3", offline=SW)
        a = swing.rodar_simulacao(ch, p, CFG_V, utc(AGORA), replays=2000)
        b = swing.rodar_simulacao(ch, p, CFG_V, utc(AGORA), replays=2000)
        self.assertEqual(a["simulacao"], b["simulacao"])
        mc = a["simulacao"]
        self.assertAlmostEqual(mc["p_alvo"] + mc["p_stop"] + mc["p_prazo"], 1.0, places=6)
        self.assertGreater(mc["p_gap_no_stop"], 0)
        self.assertGreater(a["historico"]["operacoes"], 0)

    def test_aluguel_reduz_r_do_vendido(self):
        pool = [(1.0, 1.0, 1.0, 1.0)]
        mc = swing.simular(pool, 10.0, 11.0, 8.0, "venda", 10, replays=10, aluguel_dia=0.01)
        self.assertAlmostEqual(mc["R_medio"], -0.1, places=3)


class OrcamentoVendido(unittest.TestCase):
    def setUp(self):
        self.plano = swing.montar_plano("B3SA3", "venda", dias("B3SA3"), CFG_V)

    def test_lote_aluguel_e_ordem_stop(self):
        s = orcamento.dimensionar(self.plano, CFG_V)
        self.assertEqual((s["lote"], s["fracionario"]), (s["qtd"], 0))
        self.assertGreater(s["aluguel_estimado"], 0)
        self.assertLessEqual(s["perda_no_stop"], 200)
        self.assertLess(s["preco_ref"], self.plano["entrada"])  # limite abaixo do gatilho na venda
        o = orcamento.ordens(s, self.plano)[0]
        self.assertEqual((o["lado"], o["tipo"], o["vendido"], o["estrategia"]), ("venda", "stop", True, "swing"))
        self.assertIn("garantia", s["tetos"])


class RiscoVendido(unittest.TestCase):
    def ordem(self, **kw):
        p = swing.montar_plano("B3SA3", "venda", dias("B3SA3"), CFG_V)
        o = orcamento.ordens(orcamento.dimensionar(p, CFG_V), p)[0]
        o.update(kw)
        return o

    def test_aprova_no_pregao(self):
        r = risco.checar([self.ordem()], CFG_V, {"caixa": 30000, "posicoes": {}}, agora_utc=utc("2026-10-26 10:05"))
        self.assertEqual(r["ordens"][0]["veredito"], "APROVADA")
        self.assertTrue(r["ordens"][0]["vendido"])

    def test_bloqueios(self):
        cfg = dict(CFG_V, permitir_vendido=False)
        r = risco.checar([self.ordem()], cfg, agora_utc=utc("2026-10-26 10:05"))
        self.assertTrue(any(m.startswith("vendido") for m in r["ordens"][0]["motivos"]))
        r = risco.checar([self.ordem()], CFG_V, {"caixa": 2000, "posicoes": {}}, agora_utc=utc("2026-10-26 10:05"))
        self.assertTrue(any(m.startswith("garantia") for m in r["ordens"][0]["motivos"]))
        r = risco.checar([self.ordem(stop=10.0)], CFG_V, agora_utc=utc("2026-10-26 10:05"))
        self.assertTrue(any(m.startswith("stop") for m in r["ordens"][0]["motivos"]))
        r = risco.checar([self.ordem()], CFG_V, agora_utc=utc("2026-10-26 17:00"))
        self.assertTrue(any("entradas de swing" in m for m in r["ordens"][0]["motivos"]))

    def test_zerar_vendido_sempre_passa(self):
        cobre = {"symbol": "B3SA3", "codigo": "B3SA3", "mercado": "lote", "lado": "compra", "qtd": 100,
                 "tipo": "mercado", "validade": "dia"}
        cart = {"caixa": 0, "posicoes": {"B3SA3": {"qtd": -100, "custo": -2261.32}}}
        r = risco.checar([cobre], dict(CFG, permitir_vendido=False), cart, agora_utc=utc("2026-10-26 17:30"))
        self.assertEqual(r["ordens"][0]["veredito"], "APROVADA")
        self.assertFalse(r["ordens"][0]["entrada"])

    def test_limite_de_posicoes_swing(self):
        cart = {"caixa": 30000, "posicoes": {s: {"qtd": 100, "custo": 1000} for s in ("PETR4", "VALE3")}}
        r = risco.checar([self.ordem()], dict(CFG_V, swing_max_posicoes=2), cart, agora_utc=utc("2026-10-26 10:05"))
        self.assertTrue(any(m.startswith("posições") for m in r["ordens"][0]["motivos"]))


class CarteiraComVendido(ComPasta):
    def test_abrir_virar_e_zerar(self):
        boleta.aplicar_execucao("B3SA3", "venda", 100, 22.62, 0.68)
        pos = b3lib.ler_json(os.path.join(self.dir, "carteira.json"))["posicoes"]["B3SA3"]
        self.assertEqual((pos["qtd"], pos["custo"]), (-100, -2261.32))
        boleta.aplicar_execucao("B3SA3", "compra", 150, 20.0, 0.9)   # zera 100 e fica comprado em 50
        pos = b3lib.ler_json(os.path.join(self.dir, "carteira.json"))["posicoes"]["B3SA3"]
        self.assertEqual((pos["qtd"], pos["custo"]), (50, 1000.3))
        boleta.aplicar_execucao("B3SA3", "venda", 50, 21.0, 0.3)
        self.assertEqual(b3lib.ler_json(os.path.join(self.dir, "carteira.json"))["posicoes"], {})

    def test_acompanhar_vendido(self):
        p = swing.montar_plano("B3SA3", "venda", dias("B3SA3"), CFG_V)
        pos = {"qtd": -100, "custo": -2261.32}
        r = swing.avaliar_posicao("B3SA3", pos, dict(p, dia="2026-10-20"), dias("B3SA3"), datetime.date(2026, 10, 23), CFG_V)
        self.assertEqual(r["lado"], "vendido")
        self.assertIn("aluguel_acumulado", r)
        self.assertLess(r["resultado"], 0)   # B3SA3 subiu de 22,61 para 23,65

    def test_mover_stop_so_a_favor(self):
        p = swing.montar_plano("B3SA3", "venda", dias("B3SA3"), CFG_V)
        b3lib.gravar_json(os.path.join(self.dir, "swing", "planos.json"), {"B3SA3": p})
        self.assertEqual(rodar(swing, ["mover-stop", "B3SA3", "%.2f" % (p["stop"] + 1)])[0], 1)
        self.assertEqual(rodar(swing, ["mover-stop", "B3SA3", "%.2f" % (p["stop"] - 0.5)])[0], 0)


@unittest.skipUnless(os.path.exists(APURACAO), "skill traders não está no repositório")
class ApuracaoVendido(unittest.TestCase):
    def test_resultado_no_mes_da_recompra(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="") as f:
            w = csv.writer(f)
            w.writerow(["data", "ativo", "tipo", "modalidade", "operacao", "quantidade", "preco", "custos"])
            w.writerow(["2026-10-26", "B3SA3", "ACAO", "ST", "V", 100, "22.62", "0.68"])
            w.writerow(["2026-11-05", "B3SA3", "ACAO", "ST", "C", 100, "20.10", "0.60"])
        out = subprocess.run([sys.executable, APURACAO, f.name, "--json"], capture_output=True, text=True).stdout
        os.unlink(f.name)
        import json
        meses = {m["periodo"]: m for m in json.loads(out)["meses"]}
        self.assertEqual(meses["10/2026"]["imposto_devido"], "0.00")
        self.assertEqual(meses["11/2026"]["resultado_comum"], "250.72")
        self.assertEqual(meses["11/2026"]["darf"], "37.61")


if __name__ == "__main__":
    unittest.main()
