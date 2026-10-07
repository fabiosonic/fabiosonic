"""Exportador no formato TXT que o escritório já importa no Domínio (leiaute aprovado em 07/10/2026)."""
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from mo_autonomo.aprovacao import lote as L
from mo_autonomo.dominio.exportador import LancamentoInvalido, gerar, historico_dominio, linha
from mo_autonomo.fluxos.ciclo import rodar_ciclo
from tests.conftest import CNPJ_A, eml_bytes, ofx_bytes
from tests.test_ponta_a_ponta import ctx_de, projeto


def test_linha_no_formato_ja_importado_pelo_escritorio():
    # mesmo desenho de uma linha real importada com sucesso (valores fictícios)
    l = linha({"data": date(2026, 1, 31), "debito": "862", "credito": "865", "valor": Decimal("5000.00"),
               "historico": "Valor transferência entre contas; Santander"})
    assert l == "31/01/2026;862;865;5000,00;VALOR TRANSFERENCIA ENTRE CONTAS SANTANDER;1;;;;;;"
    arq = gerar([{"data": "2026-02-20", "debito": "865", "credito": "432", "valor": "0.06", "historico": "Rendimento"}])
    assert arq == b"20/02/2026;865;432;0,06;RENDIMENTO;1;;;;;;\r\n"


@pytest.mark.parametrize("ruim", [
    {"debito": "1.1.1.02"}, {"credito": ""}, {"valor": "0"}, {"valor": "-5.00"},
    {"historico": " ; "}, {"credito": "862"},
])
def test_lancamento_invalido_nao_gera_arquivo(ruim):
    base = {"data": "2026-01-31", "debito": "862", "credito": "865", "valor": "10.00", "historico": "X"}
    with pytest.raises(LancamentoInvalido):
        gerar([{"data": "2026-01-31", "debito": "862", "credito": "865", "valor": "1.00", "historico": "OK"},
               {**base, **ruim}])


def test_historico_sem_acento_e_sem_quebra():
    assert historico_dominio("Pagamento\r\nde água; luz") == "PAGAMENTO DE AGUA LUZ"


def _projeto_reduzido(tmp_path, auto=False):
    base = projeto(tmp_path, auto=auto)
    dom = base / "dados" / "dominio" / "101"
    (dom / "plano_contas.csv").write_text("codigo;descricao;analitica\n862;Banco;S\n120;Clientes;S\n432;Tarifas;S\n",
                                          encoding="utf-8")
    (dom / "razao.csv").write_text(
        "data;conta_debito;conta_credito;valor;historico\n"
        "01/09/2026;862;120;10;PIX RECEBIDO CLIENTE X\n02/09/2026;862;120;10;PIX RECEBIDO CLIENTE Y\n"
        "03/09/2026;432;862;10;TARIFA BANCARIA PACOTE\n04/09/2026;432;862;10;TARIFA BANCARIA PACOTE\n",
        encoding="utf-8")
    (base / "config" / "contas_bancarias.csv").write_text(
        f"cnpj;banco;agencia;conta;conta_contabil\n{CNPJ_A};341;0001;12345;862\n", encoding="utf-8")
    return base


def test_ofx_ate_o_txt_de_importacao_do_dominio(tmp_path):
    base = _projeto_reduzido(tmp_path)
    (base / "entrada" / "1.eml").write_bytes(eml_bytes({"e.ofx": ofx_bytes()}))
    ctx = ctx_de(base)
    e = rodar_ciclo(ctx)
    l = next(x for x in e["lotes"] if x["area"] == "CONTABIL")
    lote = L.carregar(Path(l["arquivo"]))
    assert len(lote["acoes"]) == 2 and not l.get("aprovado")  # nada vai ao Domínio sem APROVADO
    assert not (ctx.dados / "_STAGING" / "IMPORTACAO_DOMINIO").exists()
    L.aprovar_humano(Path(l["arquivo"]), "APROVADO", lote["hash"], "Pessoa", ctx.trilha)
    e2 = rodar_ciclo(ctx)
    res = [r for x in e2["execucoes"] for r in x["resultado"] if r["acao"] == "lancamento_contabil"]
    assert res and res[0]["status"] == "GRAVADO" and res[0]["lancamentos"] == 2
    txt = Path(res[0]["destino"]).read_bytes()
    assert txt == (b"05/10/2026;862;120;1500,00;PIX RECEBIDO CLIENTE ALFA;1;;;;;;\r\n"
                   b"06/10/2026;432;862;320,50;TARIFA BANCARIA PACOTE;1;;;;;;\r\n")
    assert Path(res[0]["destino"]).name.startswith("Dominio-101-ALFA-341-12345-2026-10-")
    estados = {r[0] for r in ctx.trilha.con.execute("SELECT estado FROM acoes WHERE tipo='lancamento_contabil'")}
    assert estados == {"EXECUTADA"}
    assert rodar_ciclo(ctx)["execucoes"] == []  # não exporta de novo


def test_conta_nao_reduzida_bloqueia_sem_arquivo(tmp_path):
    base = projeto(tmp_path)  # plano de teste com classificação (1.1.1.02), não código reduzido
    (base / "entrada" / "1.eml").write_bytes(eml_bytes({"e.ofx": ofx_bytes()}))
    ctx = ctx_de(base)
    e = rodar_ciclo(ctx)
    l = next(x for x in e["lotes"] if x["area"] == "CONTABIL")
    lote = L.carregar(Path(l["arquivo"]))
    from mo_autonomo.fluxos.ciclo import executar_lote
    aprovado = L.aprovar_humano(Path(l["arquivo"]), "APROVADO", lote["hash"], "Pessoa", ctx.trilha)
    r = executar_lote(aprovado, ctx)
    assert r[0]["status"].startswith("ERRO") and "reduzido" in r[0]["status"]
    assert not list((ctx.dados / "_STAGING").rglob("*.txt"))
