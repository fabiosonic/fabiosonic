"""Testes offline do day-trader-b3 com dados reais salvos (Yahoo, B3 e CVM).

    python3 -m unittest discover -s tests -v
"""

import contextlib
import csv
import datetime
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(RAIZ, "tests", "fixtures")
INTRA = os.path.join(FIX, "scanner", "intraday")
DIARIO = os.path.join(FIX, "scanner", "diario")
CVM = os.path.join(FIX, "cvm")
sys.path.insert(0, os.path.join(RAIZ, "b3-comum"))
import b3lib  # noqa: E402


def carregar(pasta, arquivo):
    spec = importlib.util.spec_from_file_location(pasta.replace("-", "_"), os.path.join(RAIZ, pasta, arquivo))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


scan = carregar("b3-scanner", "scan.py")
entrada = carregar("b3-entrada", "entry.py")
saida = carregar("b3-saida", "exit.py")
maquina = carregar("b3-maquina-do-tempo", "timemachine.py")
orcamento = carregar("b3-orcamento", "size.py")
risco = carregar("b3-risco", "check.py")
boleta = carregar("b3-boleta", "ticket.py")
alertas = carregar("b3-alertas", "alerts.py")
fiscal = carregar("b3-fiscal", "fiscal.py")
noticias = carregar("b3-noticias", "news.py")
analista = carregar("b3-analista", "facts.py")
insiders = carregar("b3-insiders", "insiders.py")

CFG = dict(b3lib.DEFAULTS, orcamento=20000)


def utc(texto):
    return b3lib.ler_agora(texto)


def rodar(mod, args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        rc = mod.main(args)
    return rc, out.getvalue()


class ComPasta(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self._antes = b3lib.PASTA
        b3lib.PASTA = self.dir

    def tearDown(self):
        b3lib.PASTA = self._antes
        shutil.rmtree(self.dir)

    def gravar(self, nome, doc):
        b3lib.gravar_json(os.path.join(self.dir, nome), doc)


class Calendario(unittest.TestCase):
    def test_feriados_2026_conferem_com_oficio_041(self):
        uteis = sorted(d.isoformat() for d in b3lib.feriados(2026) if d.weekday() < 5)
        self.assertEqual(uteis, ["2026-01-01", "2026-02-16", "2026-02-17", "2026-04-03", "2026-04-21",
                                 "2026-05-01", "2026-06-04", "2026-09-07", "2026-10-12", "2026-11-02",
                                 "2026-11-20", "2026-12-24", "2026-12-25", "2026-12-31"])

    def test_horario_segue_verao_americano(self):
        d = datetime.date
        self.assertEqual(b3lib.sessao(d(2026, 3, 6))[1], datetime.time(17, 55))
        self.assertEqual(b3lib.sessao(d(2026, 3, 9))[1], datetime.time(16, 55))   # OC 005/2026
        self.assertEqual(b3lib.sessao(d(2026, 10, 30))[1], datetime.time(16, 55))
        self.assertEqual(b3lib.sessao(d(2026, 11, 3))[1], datetime.time(17, 55))  # OC 050/2026
        self.assertIsNone(b3lib.sessao(d(2026, 11, 2)))

    def test_quarta_de_cinzas_abre_13h(self):
        self.assertEqual(b3lib.sessao(datetime.date(2026, 2, 18))[0], datetime.time(13, 0))
        self.assertEqual(b3lib.quarta_de_cinzas(2027), datetime.date(2027, 2, 10))

    def test_config_sobrescreve_dia(self):
        cfg = dict(CFG, sessoes={"2026-10-26": ["10:00", "13:00"], "2026-10-27": []})
        self.assertEqual(b3lib.sessao(datetime.date(2026, 10, 26), cfg)[1], datetime.time(13, 0))
        self.assertIsNone(b3lib.sessao(datetime.date(2026, 10, 27), cfg))

    def test_janela_de_entradas(self):
        antes, depois, zerar = b3lib.janela_entradas(datetime.date(2026, 10, 23), CFG)
        self.assertEqual((b3lib.hm(antes), b3lib.hm(depois), b3lib.hm(zerar)), ("10:15", "16:15", "16:45"))


class Tickers(unittest.TestCase):
    def test_validacao(self):
        for ok in ("PETR4", "B3SA3", "petr4f", "TAEE11", "AAPL34", "VALE3.SA"):
            self.assertTrue(b3lib.valido(ok), ok)
        for ruim in ("PETRK420", "AAPL", "PETR", "PETR4FF"):
            self.assertFalse(b3lib.valido(ruim), ruim)

    def test_tipos(self):
        self.assertEqual(b3lib.tipo_ativo("PETR4"), "ACAO")
        self.assertEqual(b3lib.tipo_ativo("AAPL34"), "BDR")
        self.assertIsNone(b3lib.tipo_ativo("BOVA11"))
        self.assertEqual(b3lib.tipo_ativo("HGLG11", {"tipos": {"HGLG11": "FII"}}), "FII")
        self.assertEqual(b3lib.sem_fracionario("PETR4F"), "PETR4")

    def test_reais(self):
        self.assertEqual(b3lib.reais(1234567.891), "R$ 1.234.567,89")
        self.assertEqual(b3lib.reais(-5), "-R$ 5,00")


class Scanner(ComPasta):
    def test_ifr_e_setups(self):
        c = [10.0] * 20 + [10 - 0.2 * i for i in range(1, 12)]
        tags, n = scan.setups(c)
        self.assertIn("sobrevendido", tags)
        self.assertLess(n["ifr"], 30)
        tags, _ = scan.setups([10.0] * 30 + [11.0])
        self.assertIn("rompimento_20d", tags)

    def test_universo_ibra(self):
        rc, out = rodar(scan, ["universo", "--offline", os.path.join(FIX, "scanner", "ibra.json.gz")])
        self.assertEqual(rc, 0)
        self.assertIn("148 ativos do IBRA", out)

    def test_orb_real_23_10(self):
        rc, _ = rodar(scan, ["orb", "--symbols", "PETR4,VALE3,ITUB4", "--offline", INTRA, "--now", "2026-10-23 11:00"])
        self.assertEqual(rc, 0)
        doc = b3lib.ler_json(os.path.join(self.dir, "watchlist.json"))
        hits = {h["symbol"]: h for h in doc["hits"]}
        self.assertEqual(hits["PETR4"]["hora"], "10:25")
        self.assertEqual(hits["PETR4"]["faixa_max"], 58.53)

    def test_orb_antes_da_faixa_recusa(self):
        with self.assertRaises(b3lib.B3Erro):
            scan.janela_orb(utc("2026-10-23 10:12"), None, 15, CFG)

    def test_diario(self):
        rc, _ = rodar(scan, ["diario", "--symbols", "PETR4,VALE3,WEGE3", "--offline", DIARIO, "--now", "2026-10-26 09:00"])
        self.assertEqual(rc, 0)
        doc = b3lib.ler_json(os.path.join(self.dir, "watchlist.json"))
        self.assertIn("sobrevendido", {h["symbol"]: h for h in doc["hits"]}["VALE3"]["setups"])


class Entrada(unittest.TestCase):
    def chart(self, s):
        return b3lib.obter_chart(s, offline=INTRA)

    def test_orb_dispara(self):
        r = entrada.avaliar(self.chart("PETR4"), utc("2026-10-23 10:40"), cfg=CFG)
        self.assertEqual(r["status"], "disparou")
        self.assertEqual((r["sinal"]["hora"], r["sinal"]["preco"]), ("10:25", 58.57))

    def test_aguardando_faixa(self):
        r = entrada.avaliar(self.chart("VALE3"), utc("2026-10-23 10:07"), cfg=CFG)
        self.assertEqual(r["status"], "aguardando")

    def test_fim_de_semana(self):
        self.assertEqual(entrada.avaliar(self.chart("PETR4"), utc("2026-10-25 11:00"), cfg=CFG)["status"], "sem-dados")

    def test_nivel(self):
        r = entrada.avaliar(self.chart("PETR4"), utc("2026-10-23 16:30"), setup="nivel", nivel=99.0, cfg=CFG)
        self.assertEqual(r["status"], "expirado")


class Saida(unittest.TestCase):
    def test_or_mid_2r(self):
        r = saida.calcular(58.57, "or_mid", None, "r", saida.D(2), 58.53, 58.01)
        self.assertEqual((float(r["stop"]), float(r["alvo"])), (58.27, 59.17))

    def test_recusas(self):
        with self.assertRaises(b3lib.B3Erro):
            saida.calcular(62.10, "preco", saida.D("62.09"), "r", saida.D(2))
        with self.assertRaises(b3lib.B3Erro):
            saida.calcular(62.10, "preco", saida.D("63"), "r", saida.D(2))


class Maquina(unittest.TestCase):
    PLANO = {"symbol": "PETR4", "dia": "2026-10-23", "entrada": 58.57, "stop": 58.27, "alvo": 59.17,
             "hora_entrada": "10:25", "zerar_ate": "16:45",
             "regra": {"stop": "or_mid", "stop_param": 0, "alvo_r": 2.0, "or_minutes": 15}}

    def setUp(self):
        self.chart = b3lib.obter_chart("PETR4", offline=os.path.join(FIX, "maquina", "PETR4.json.gz"))

    def test_deterministico(self):
        a = maquina.rodar(self.chart, self.PLANO, CFG, replays=2000)
        b = maquina.rodar(self.chart, self.PLANO, CFG, replays=2000)
        self.assertEqual(a["simulacao"], b["simulacao"])
        s = a["simulacao"]
        self.assertAlmostEqual(s["p_alvo"] + s["p_stop"] + s["p_nenhum"], 1.0, places=6)
        self.assertGreaterEqual(a["pregoes_usados"], 20)
        self.assertFalse(a["proporcional"])

    def test_dia_de_inverno_usa_proporcional(self):
        plano = dict(self.PLANO, dia="2026-11-03", hora_entrada="10:30", zerar_ate="17:45")
        doc = maquina.rodar(self.chart, plano, CFG, replays=500)
        self.assertTrue(doc["proporcional"])

    def test_veredito(self):
        self.assertTrue(maquina.veredito({"p_alvo": 0.5, "p_stop": 0.5, "r_alvo": 1.0}).startswith("Perto do empate"))
        self.assertTrue(maquina.veredito({"p_alvo": 0.6, "p_stop": 0.3, "r_alvo": 1.0}).startswith("Forte para o alvo"))


class Orcamento(unittest.TestCase):
    PLANO = {"symbol": "PETR4", "entrada": 58.57, "stop": 58.27, "alvo": 59.17, "zerar_ate": "16:45", "dia": "2026-10-23"}

    def test_lote_e_fracionario(self):
        s = orcamento.dimensionar(self.PLANO, CFG)
        self.assertEqual((s["qtd"], s["lote"], s["fracionario"], s["limitante"]), (256, 200, 56, "posição máxima"))
        self.assertLessEqual(s["perda_no_stop"], CFG["max_perda_por_operacao"])
        o = orcamento.ordens(s, self.PLANO)
        self.assertEqual([x["codigo"] for x in o], ["PETR4", "PETR4F"])

    def test_sem_fracionario(self):
        s = orcamento.dimensionar(self.PLANO, dict(CFG, permitir_fracionario=False))
        self.assertEqual((s["qtd"], s["fracionario"]), (200, 0))

    def test_perda_maxima_limita_com_custos(self):
        s = orcamento.dimensionar(self.PLANO, dict(CFG, max_perda_por_operacao=30))
        self.assertLessEqual(s["perda_no_stop"], 30)
        self.assertEqual(s["limitante"], "perda máxima")

    def test_zero_acoes(self):
        with self.assertRaises(b3lib.B3Erro):
            orcamento.dimensionar(dict(self.PLANO, stop=10.0), dict(CFG, max_perda_por_operacao=5))


class Risco(unittest.TestCase):
    def ordens(self):
        s = orcamento.dimensionar(Orcamento.PLANO, CFG)
        return orcamento.ordens(s, Orcamento.PLANO)

    def test_aprova_no_horario(self):
        r = risco.checar(self.ordens(), CFG, agora_utc=utc("2026-10-23 10:26"))
        self.assertEqual(r["aprovadas"], 2)

    def test_bloqueia_fora_do_horario_e_feriado(self):
        r = risco.checar(self.ordens(), CFG, agora_utc=utc("2026-10-23 16:30"))
        self.assertIn("horário", r["ordens"][0]["motivos"][0])
        r = risco.checar(self.ordens(), CFG, agora_utc=utc("2026-11-02 11:00"))
        self.assertIn("Finados", r["ordens"][0]["motivos"][0])

    def test_formato_lote(self):
        o = dict(self.ordens()[0], qtd=150)
        r = risco.checar([o], CFG, agora_utc=utc("2026-10-23 10:26"))
        self.assertTrue(any("múltiplo" in m for m in r["ordens"][0]["motivos"]))

    def test_saida_sempre_possivel(self):
        venda = {"symbol": "PETR4", "codigo": "PETR4", "mercado": "lote", "lado": "venda", "qtd": 200,
                 "tipo": "mercado", "validade": "dia"}
        cart = {"caixa": 0, "posicoes": {"PETR4": {"qtd": 200, "custo": 11714}}}
        r = risco.checar([venda], CFG, cart, agora_utc=utc("2026-10-23 16:50"))
        self.assertEqual(r["ordens"][0]["veredito"], "APROVADA")

    def test_vendido_bloqueado(self):
        venda = {"symbol": "PETR4", "codigo": "PETR4", "mercado": "lote", "lado": "venda", "qtd": 100,
                 "tipo": "mercado", "validade": "dia"}
        r = risco.checar([venda], CFG, agora_utc=utc("2026-10-23 11:00"))
        self.assertTrue(any(m.startswith("vendido") for m in r["ordens"][0]["motivos"]))


class Boleta(unittest.TestCase):
    O = {"codigo": "PETR4", "symbol": "PETR4", "qtd": 200}

    def test_aceita_sim_explicito(self):
        for ok in ("sim", "Sim!", "sim, 200 PETR4", "s"):
            self.assertTrue(boleta.aceitar_sim(ok, self.O)[0], ok)

    def test_recusa(self):
        for ruim in ("ok", "pode ser", "sim para todas", "sim, VALE3", "sim 300", "sim, mas espera", "não"):
            self.assertFalse(boleta.aceitar_sim(ruim, self.O)[0], ruim)


class FluxoCompleto(ComPasta):
    def test_entrada_ate_darf(self):
        agora = "2026-10-23 10:26"
        self.gravar("config.json", {"orcamento": 20000})
        self.assertEqual(rodar(entrada, ["check", "PETR4", "--offline", INTRA, "--now", "2026-10-23 10:40", "--write"])[0], 0)
        self.assertEqual(rodar(saida, ["plan", "--write"])[0], 0)
        self.assertEqual(rodar(orcamento, ["--limit", "--write", "--now", agora])[0], 0)
        self.assertEqual(rodar(risco, ["--now", agora])[0], 0)
        self.assertEqual(rodar(boleta, ["approve", "--index", "1", "--reply", "sim para todas", "--now", agora])[0], 1)
        self.assertEqual(rodar(boleta, ["approve", "--index", "1", "--reply", "sim", "--now", agora])[0], 0)
        self.assertEqual(rodar(boleta, ["result", "--index", "1", "--status", "enviada", "--id", "1", "--now", agora])[0], 0)
        rodar(boleta, ["fill", "--codigo", "PETR4", "--lado", "compra", "--qtd", "200", "--preco", "58.57", "--custos", "3.51", "--now", agora])
        rodar(boleta, ["fill", "--codigo", "PETR4", "--lado", "venda", "--qtd", "200", "--preco", "59.17", "--custos", "3.55", "--now", "2026-10-23 11:40"])
        # a mesma compra não pode ser repetida no dia
        r = risco.checar(b3lib.ler_json(os.path.join(self.dir, "ordens.json"))["ordens"][:1], b3lib.ler_config(),
                         estado=b3lib.ler_json(os.path.join(self.dir, "estado", "boleta.json")), agora_utc=utc("2026-10-23 10:30"))
        self.assertTrue(any(m.startswith("duplicada") for m in r["ordens"][0]["motivos"]))
        rc, _ = rodar(fiscal, ["exportar"])
        self.assertEqual(rc, 0)
        with open(os.path.join(self.dir, "operacoes_ir.csv"), encoding="utf-8") as f:
            linhas = list(csv.DictReader(f))
        self.assertEqual([l["modalidade"] for l in linhas], ["DT", "DT"])


class Fiscal(unittest.TestCase):
    def test_classifica_dt_e_st(self):
        execs = [{"data": "2026-10-26", "hora": "10:30", "codigo": "VALE3", "lado": "compra", "quantidade": "300", "preco": "62", "custos": "5.58"},
                 {"data": "2026-10-26", "hora": "11:10", "codigo": "VALE3F", "lado": "compra", "quantidade": "50", "preco": "62.1", "custos": "0.93"},
                 {"data": "2026-10-26", "hora": "15:00", "codigo": "VALE3", "lado": "venda", "quantidade": "200", "preco": "62.8", "custos": "3.77"}]
        l = fiscal.classificar(execs, CFG)
        self.assertEqual([(x["modalidade"], x["operacao"], x["quantidade"]) for x in l],
                         [("DT", "C", 200), ("ST", "C", 100), ("ST", "C", 50), ("DT", "V", 200)])
        self.assertEqual(l[0]["custos"], "3.72")

    def test_tipo_ambiguo_exige_config(self):
        e = [{"data": "2026-10-26", "codigo": "BOVA11", "lado": "compra", "quantidade": "1", "preco": "130", "custos": "0"}]
        with self.assertRaises(b3lib.B3Erro):
            fiscal.classificar(e, CFG)
        self.assertEqual(fiscal.classificar(e, dict(CFG, tipos={"BOVA11": "ETF"}))[0]["tipo"], "ETF")


class Alertas(unittest.TestCase):
    def test_status(self):
        self.assertEqual(alertas.status_mercado(utc("2026-10-23 16:57"), CFG)["fase"], "call de fechamento")
        self.assertEqual(alertas.status_mercado(utc("2026-11-03 09:50"), CFG)["fase"], "pré-abertura")
        self.assertEqual(alertas.status_mercado(utc("2026-11-20 11:00"), CFG)["fase"], "sem pregão")

    def test_avaliar(self):
        als = [alertas.novo("PETR4", "acima", 58.0), alertas.novo("PETR4", "abaixo", 50.0)]
        st = alertas.status_mercado(utc("2026-10-23 12:00"), CFG)
        tocou = alertas.avaliar(als, {"PETR4": {"preco": 58.68}}, st, utc("2026-10-23 12:00"))
        self.assertEqual([t["tipo"] for t in tocou], ["acima"])
        self.assertEqual(alertas.avaliar(als, {"PETR4": {"preco": 58.68}}, st, utc("2026-10-23 12:05")), [])


class Cvm(ComPasta):
    def test_noticias(self):
        rc, out = rodar(noticias, ["--symbols", "DXCO3,VALE3", "--dias", "10", "--offline", CVM, "--sem-precos",
                                   "--now", "2026-10-26 09:00"])
        self.assertEqual(rc, 0)
        self.assertIn("Fato Relevante: Encerramento das atividades", out)
        rc, out = rodar(noticias, ["--symbols", "DXCO3,VALE3", "--dias", "10", "--offline", CVM, "--sem-precos",
                                   "--now", "2026-10-26 09:00"])
        self.assertEqual(rc, 1)  # já visto
        self.assertIn("nenhum documento novo", out)

    def test_analista_deriva_4t(self):
        rc, out = rodar(analista, ["WEGE3,ITUB4", "--offline", CVM, "--ano", "2026", "--json"])
        self.assertEqual(rc, 0)
        res = json.loads(out)["resultados"]
        tri = {t["trimestre"]: t for t in res["WEGE3"]["trimestres"]}
        self.assertTrue(tri["4T25"]["derivado"])
        self.assertEqual(round(tri["3T26"]["receita"] / 1e6), 10861)
        self.assertIsNone({t["trimestre"]: t for t in res["ITUB4"]["trimestres"]}["2T26"]["ebit"])

    def test_insiders(self):
        rc, out = rodar(insiders, ["WEGE3", "--offline", CVM, "--now", "2026-10-26 09:00", "--json"])
        self.assertEqual(rc, 0)
        res = json.loads(out)["resumo"]
        on = res["84.429.695/0001-11 ON"]
        self.assertLess(on["liquido_vol"], 0)
        rc, out = rodar(insiders, ["--ranking", "--offline", CVM, "--now", "2026-10-26 09:00", "--json"])
        self.assertEqual(json.loads(out)["mes"], "2026-09")


class Repositorio(unittest.TestCase):
    def test_cada_skill_tem_skill_md(self):
        skills = [d for d in os.listdir(RAIZ) if d.startswith("b3-") and d != "b3-comum"]
        self.assertEqual(len(skills), 13)
        for d in skills:
            with open(os.path.join(RAIZ, d, "SKILL.md"), encoding="utf-8") as f:
                texto = f.read()
            self.assertTrue(texto.startswith("---\nname: %s\n" % d), d)

    def test_manifesto(self):
        with open(os.path.join(RAIZ, ".claude-plugin", "plugin.json"), encoding="utf-8") as f:
            m = json.load(f)
        self.assertEqual(m["name"], "day-trader-b3")


if __name__ == "__main__":
    unittest.main()
