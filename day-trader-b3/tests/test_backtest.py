"""Testes do motor de backtest e da carteira com dados sintéticos de resultado conhecido.

    python3 -m unittest discover -s tests -v
"""

import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_b3 import RAIZ, carregar  # noqa: E402

sys.path.insert(0, os.path.join(RAIZ, "b3-backtest"))
import motor  # noqa: E402
import carteira  # noqa: E402
backtest = carregar("b3-backtest", "backtest.py")
swing = carregar("b3-swing", "swing.py")

D0 = datetime.date(2020, 1, 2).toordinal()


def serie(barras):
    """barras: [(o, h, l, c)] -> ativo preparado sem sinais."""
    o, h, l, c = (list(x) for x in zip(*barras))
    n = len(c)
    return {"symbol": "TEST3", "o": o, "h": h, "l": l, "c": c, "d": list(range(D0, D0 + n)),
            "atr": [1.0] * n, "tend": [1] * n, "reg": [1] * n, "sinais": {}}


def sem_custos():
    antes = (motor.CUSTO, motor.SLIP, motor.ALUGUEL_AA)
    motor.CUSTO = motor.SLIP = motor.ALUGUEL_AA = 0.0
    return antes


class Simulacao(unittest.TestCase):
    def setUp(self):
        self.antes = sem_custos()

    def tearDown(self):
        motor.CUSTO, motor.SLIP, motor.ALUGUEL_AA = self.antes

    def barras(self, depois):
        base = [(10.0, 10.2, 9.8, 10.0)] * 10            # pregões 0..9; sinal no 9
        return serie(base + depois + [(10.0, 10.1, 9.9, 10.0)] * 40)

    def test_alvo_na_abertura_com_gap(self):
        # entrada na abertura do pregão 10 a 10; stop atr:2 = 8; alvo 1R = 12; gap para 13 no pregão 11
        t = self.barras([(10.0, 10.5, 9.9, 10.2), (13.0, 13.5, 12.8, 13.2)])
        r = motor.simular_sinal(t, 9, 1, "abertura", ("atr", 2.0))
        saida, R, dias = r[(1.0, 10)]
        self.assertEqual((saida, dias), (11, 2))
        self.assertAlmostEqual(R, 1.5)                    # saiu na abertura, acima do alvo

    def test_stop_com_gap_pior_que_1R(self):
        t = self.barras([(10.0, 10.5, 9.9, 10.2), (7.0, 7.5, 6.8, 7.2)])
        saida, R, dias = motor.simular_sinal(t, 9, 1, "abertura", ("atr", 2.0))[(2.0, 10)]
        self.assertAlmostEqual(R, -1.5)

    def test_stop_antes_do_alvo_no_mesmo_pregao(self):
        t = self.barras([(10.0, 12.5, 7.5, 10.0)])
        saida, R, dias = motor.simular_sinal(t, 9, 1, "abertura", ("atr", 2.0))[(1.0, 5)]
        self.assertAlmostEqual(R, -1.0)

    def test_prazo_sai_no_fechamento(self):
        t = self.barras([(10.0, 10.5, 9.9, 10.4)] * 3)
        saida, R, dias = motor.simular_sinal(t, 9, 1, "abertura", ("atr", 2.0))[(None, 5)]
        self.assertEqual(dias, 5)
        self.assertAlmostEqual(R, 0.0)                    # 5º pregão fecha a 10,0

    def test_gatilho_nao_disparado(self):
        t = self.barras([(9.9, 10.1, 9.7, 9.8)])         # não passa da máxima 10,2
        self.assertIsNone(motor.simular_sinal(t, 9, 1, "gatilho", ("swing", 5)))

    def test_vendido_espelhado_e_aluguel(self):
        t = self.barras([(10.0, 10.1, 9.5, 9.8), (8.5, 8.7, 8.2, 8.4)])
        R = motor.simular_sinal(t, 9, -1, "abertura", ("atr", 1.0))[(1.0, 10)][1]
        self.assertAlmostEqual(R, 1.5)                    # vendido a 10, stop 11, alvo 9, gap para 8,5
        motor.ALUGUEL_AA = 0.252
        R2 = motor.simular_sinal(t, 9, -1, "abertura", ("atr", 1.0))[(1.0, 10)][1]
        self.assertAlmostEqual(R - R2, 10 * 0.252 / 252 * 2)   # 2 pregões de aluguel em R

    def test_custos_reduzem_R(self):
        t = self.barras([(10.0, 10.5, 9.9, 10.2), (13.0, 13.5, 12.8, 13.2)])
        motor.CUSTO = 0.001
        R = motor.simular_sinal(t, 9, 1, "abertura", ("atr", 2.0))[(1.0, 10)][1]
        self.assertAlmostEqual(R, 1.5 - 0.001 * (10 + 13) / 2)


class Indicadores(unittest.TestCase):
    def test_sinais_iguais_ao_scanner(self):
        import random
        rng = random.Random(3)
        c = [20.0]
        for _ in range(399):
            c.append(max(1.5, c[-1] * (1 + rng.gauss(0, 0.02))))
        tk = {"symbol": "X", "d": list(range(D0, D0 + 400)), "c": c, "o": c, "h": [x * 1.01 for x in c],
              "l": [x * 0.99 for x in c], "v": [10 ** 7] * 400}
        prep = motor.preparar(tk, {})
        scan = carregar("b3-scanner", "scan.py")
        for i in (150, 220, 333, 399):
            esperado, _ = scan.setups(c[:i + 1])
            achado = [k for k, v in prep["sinais"].items() if i in v]
            # o IFR do motor usa o histórico inteiro; os setups de preço têm de bater sempre
            preco = {"rompimento_20d", "perdeu_20d", "bandeira_alta", "bandeira_baixa", "retomou_mm20", "perdeu_mm20"}
            self.assertEqual(sorted(set(esperado) & preco), sorted(set(achado) & preco), i)


class WalkForward(unittest.TestCase):
    def test_escolhe_no_treino_e_mede_no_teste(self):
        bom, ruim = ("abertura", ("atr", 3.0), 2.0, 15, "nenhum"), motor.PADRAO
        st = {bom: {}, ruim: {}}
        for ano in range(2001, 2027):
            st[bom][ano] = [200, 40.0, 200 * 1.2, 110, 120.0, 80.0, 2000]     # média 0,2R, dp ~1
            st[ruim][ano] = [200, -10.0, 200 * 1.0, 90, 90.0, 100.0, 2000]
        janelas, total = backtest.walk_forward(st, 2001, 2026)
        self.assertEqual(janelas[0]["treino"], "2001-2008")
        self.assertTrue(all(j["combo"] == bom for j in janelas))
        self.assertAlmostEqual(motor.metricas(total)["R_medio"], 0.2)

    def test_nada_passa_sem_vantagem(self):
        st = {motor.PADRAO: {a: [200, -10.0, 200.0, 90, 90.0, 100.0, 2000] for a in range(2001, 2027)}}
        combo, m = backtest.escolher(st, range(2001, 2009))
        self.assertIsNone(combo)


class Carteira(unittest.TestCase):
    def op(self, ent, sai, sym, R, risco=0.05):
        return {"entrada": D0 + ent, "saida": D0 + sai, "symbol": sym, "R": R, "reg": 1, "setup_lado": 1,
                "mom": 0.0, "atr_pct": 0.02, "risco_pct": risco, "dias": sai - ent + 1}

    def test_limite_de_posicoes_e_um_ativo_por_vez(self):
        ops = [self.op(0, 5, "A", 1.0), self.op(0, 5, "B", 1.0), self.op(0, 5, "C", 1.0), self.op(1, 3, "A", 1.0)]
        m = carteira.simular(ops, max_pos=2, risco=0.01, ordem="baixa_vol")
        self.assertEqual(m["operacoes"], 2)
        self.assertAlmostEqual(m["retorno_total"], 0.02)

    def test_tamanho_limitado_sem_alavancagem(self):
        # risco 1% com stop a 0,1% pediria 1000% do patrimônio: limita a 1/max_pos
        m = carteira.simular([self.op(0, 2, "A", -1.0, risco=0.001)], max_pos=5, risco=0.01)
        self.assertAlmostEqual(m["retorno_total"], -0.2 * 0.001)

    def test_cdi_no_caixa_livre(self):
        cdi = {(2020, 1): 1.0, (2020, 2): 1.0}
        m = carteira.simular([self.op(0, 1, "A", 0.0), self.op(40, 41, "B", 0.0)], max_pos=5, risco=0.01, cdi=cdi)
        self.assertGreater(m["retorno_total"], 0.01)
        self.assertLess(m["retorno_total"], 0.02)


class ParametrosNaSkill(unittest.TestCase):
    PARAMS = {"gerado_em": "teste", "setups": {
        "rompimento_20d": {"ativo": True, "entrada": "abertura", "stop": "atr:3", "alvo_r": 3.0, "prazo": 20,
                           "filtro": "nenhum", "oos": {"R_medio": 0.12, "acerto": 0.52, "n": 100}},
        "bandeira_alta": {"ativo": True, "entrada": "abertura", "stop": "atr:3", "alvo_r": None, "prazo": 15,
                          "filtro": "tendencia", "oos": {"R_medio": 0.15, "acerto": 0.52, "n": 100}}}}

    def test_escolhe_o_melhor_setup_ativo(self):
        t, p = swing.escolher_parametros(["rompimento_20d", "bandeira_alta"], self.PARAMS)
        self.assertEqual(t, "bandeira_alta")
        self.assertEqual(swing.escolher_parametros(["sobrevendido"], self.PARAMS), (None, None))

    def test_plano_sem_alvo(self):
        dias = [{"data": datetime.date(2025, 1, 1) + datetime.timedelta(days=i), "o": 10 + i * 0.05,
                 "h": 10.3 + i * 0.05, "l": 9.8 + i * 0.05, "c": 10 + i * 0.05, "v": 1} for i in range(220)]
        cfg = dict(carregar("b3-orcamento", "size.py").b3lib.DEFAULTS, orcamento=20000)
        p = swing.montar_plano("TEST3", "compra", dias, cfg, params=self.PARAMS, hoje=dias[-1]["data"],
                               entrada_txt="abertura", stop_txt="atr:3", alvo_txt="nenhum", prazo=15, filtro="tendencia")
        self.assertIsNone(p["alvo"])
        self.assertTrue(p["filtro_ok"])
        self.assertEqual(p["tipo_entrada"], "mercado")


if __name__ == "__main__":
    unittest.main()


class CarteiraComCustosEIR(unittest.TestCase):
    def op(self, ent, sai, R, risco=0.05):
        return {"entrada": D0 + ent, "saida": D0 + sai, "symbol": "A", "R": R, "reg": 1, "setup_lado": 1,
                "mom": 0.0, "atr_pct": 0.02, "risco_pct": risco, "dias": sai - ent + 1}

    def test_corretagem_por_ordem(self):
        m = carteira.simular([self.op(0, 2, 0.0)], max_pos=5, risco=0.01, capital=10000, corretagem=5.0)
        self.assertAlmostEqual(m["final"], 10000 - 10.0)

    def test_isencao_ate_20_mil_no_mes(self):
        # vendas de R$ 2 mil no mês com lucro: isento
        m = carteira.simular([self.op(0, 2, 2.0)], max_pos=5, risco=0.01, capital=10000, ir=True, fim=D0 + 90)
        self.assertEqual(m["custos"]["ir_swing"], 0.0)

    def test_ir_15_quando_vendas_passam_de_20_mil(self):
        # patrimônio de R$ 1 milhão: venda de R$ 200 mil no mês, lucro de R$ 20 mil -> IR de R$ 3 mil
        m = carteira.simular([self.op(0, 2, 2.0)], max_pos=5, risco=0.01, capital=1e6, ir=True, fim=D0 + 90)
        self.assertAlmostEqual(m["custos"]["ir_swing"], 3000.0)

    def test_cdi_antes_da_primeira_operacao(self):
        cdi = {(2020, m): 1.0 for m in range(1, 13)}
        m = carteira.simular([], capital=10000, cdi=cdi, inicio=D0, fim=D0 + 365, ir=True)
        self.assertGreater(m["final"], 10000 * 1.09)     # ~12,7% bruto, 15% de IR
        self.assertLess(m["final"], 10000 * 1.115)
