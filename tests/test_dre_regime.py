"""DRE conforme o regime: MEI, Lucro Presumido e Lucro Real."""

from datetime import date

from nfse_itaborai import config, contabil, financeiro
from test_emissor import Simulador, ambiente  # noqa: F401  (fixture)
from test_financeiro import CLI_A, base  # noqa: F401  (fixture)

EM = date(2026, 10, 2)


def _receita(valor="100000"):
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], valor, vencimento="2026-09-10", competencia="2026-09")
    financeiro.atualizar_titulo(tid, nfse_status="emitida")
    financeiro.salvar_despesa({"descricao": "Aluguel", "valor": "10000", "vencimento": "2026-09-10", "categoria": "Aluguel",
                               "competencia": "2026-09"})
    financeiro.salvar_despesa({"descricao": "DARF PIS/COFINS", "valor": "3650", "vencimento": "2026-09-25",
                               "categoria": "Impostos", "competencia": "2026-09"})


def _linha(d, nome):
    return next(l for l in d["linhas"] if l["conta"].startswith(nome))


def test_presumido(base):  # noqa: F811
    config.salvar({"fiscal": {"regime": "presumido"}})
    _receita()
    d = contabil.dre(2026, EM)
    assert _linha(d, "PIS")["total"] == -65000 and _linha(d, "COFINS")["total"] == -300000
    # IRPJ: 32% de 100.000 = 32.000 → 15% = 4.800 + 10% sobre 12.000 = 1.200; CSLL 9% de 32.000 = 2.880
    assert _linha(d, "IRPJ")["total"] == -600000 and _linha(d, "CSLL")["total"] == -288000
    assert "Impostos" not in [l["conta"] for l in d["linhas"]]           # o DARF não é deduzido de novo
    assert d["regime"] == "presumido" and "Presumido" in d["nota"]


def test_real_e_mei(base):  # noqa: F811
    config.salvar({"fiscal": {"regime": "real"}})
    _receita()
    d = contabil.dre(2026, EM)
    assert _linha(d, "PIS")["total"] == -165000 and _linha(d, "COFINS")["total"] == -760000
    lair = _linha(d, "(=) RESULTADO ANTES")["total"]
    assert _linha(d, "CSLL")["total"] == -round(lair * 0.09)
    config.salvar({"fiscal": {"regime": "mei"}, "financeiro": {"das_mei_mensal": "81,05"}})
    d = contabil.dre(2026, EM)
    assert _linha(d, "DAS-MEI")["total"] == -8105 and not any(l["conta"].startswith("IRPJ") for l in d["linhas"])
    assert contabil.carga_sobre_receita_pct(0) == 0.0
