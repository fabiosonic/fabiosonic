from datetime import date
from decimal import Decimal

import pytest

from mo_autonomo.contabil.lancamentos import DePara, PlanoContas, conciliar_com_notas, normalizar_historico, propor
from mo_autonomo.documentos.ofx import ler_ofx
from mo_autonomo.dominio.auditoria import RelatorioInvalido, auditar, ler_relatorio
from mo_autonomo.dp.folha import conferir, inss_progressivo, irrf_mensal
from tests.conftest import CNPJ_A, CNPJ_B, PARAMS_TESTE, catalogo_teste, ofx_bytes

PLANO = PlanoContas({"1.1.1.02": {"descricao": "Banco", "analitica": True},
                     "1.1.2.01": {"descricao": "Clientes", "analitica": True},
                     "3.1.9.01": {"descricao": "Tarifas", "analitica": True},
                     "3.1": {"descricao": "Despesas", "analitica": False}})
BANCO = "1.1.1.02"


def razao(*linhas):
    return [{"data": "", "conta_debito": d, "conta_credito": c, "valor": "1", "historico": h} for d, c, h in linhas]


def test_normalizacao():
    assert normalizar_historico("Pix recebido - Cliente Alfa 05/10") == "PIX RECEBIDO CLIENTE"
    assert normalizar_historico("TARIFA BANCÁRIA PACOTE 123") == "TARIFA BANCARIA PACOTE"


def test_propoe_lancamentos_com_historico_do_cliente():
    dp = DePara.do_razao(razao((BANCO, "1.1.2.01", "PIX RECEBIDO CLIENTE BETA"), (BANCO, "1.1.2.01", "PIX RECEBIDO CLIENTE X"),
                               ("3.1.9.01", BANCO, "TARIFA BANCARIA PACOTE SET"), ("3.1.9.01", BANCO, "TARIFA BANCARIA PACOTE AGO")), BANCO)
    r = propor(ler_ofx(ofx_bytes()), BANCO, dp, PLANO)
    assert r["pendencias"] == []
    l1, l2 = r["lancamentos"]
    assert (l1["debito"], l1["credito"], l1["valor"]) == (BANCO, "1.1.2.01", Decimal("1500.00"))
    assert (l2["debito"], l2["credito"], l2["valor"]) == ("3.1.9.01", BANCO, Decimal("320.50"))


def test_sem_historico_ambiguo_ou_conta_invalida_vira_pendencia():
    dp = DePara.do_razao(razao((BANCO, "1.1.2.01", "PIX RECEBIDO CLIENTE"), (BANCO, "9.9.9", "PIX RECEBIDO CLIENTE"),
                               ("3.1", BANCO, "TARIFA BANCARIA PACOTE"), ("3.1", BANCO, "TARIFA BANCARIA PACOTE")), BANCO)
    r = propor(ler_ofx(ofx_bytes()), BANCO, dp, PLANO)
    assert r["lancamentos"] == []
    cods = sorted(p["codigo"] for p in r["pendencias"])
    assert cods == ["CONTA_FORA_DO_PLANO", "SEM_CONTRAPARTIDA"]
    r = propor(ler_ofx(ofx_bytes()), BANCO, DePara.do_razao(razao((BANCO, "1.1.2.01", "PIX RECEBIDO CLIENTE")), BANCO), PLANO)
    assert all(p["codigo"] == "SEM_CONTRAPARTIDA" for p in r["pendencias"])  # 1 ocorrência < mínimo
    assert propor(ler_ofx(ofx_bytes()), "3.1", dp, PLANO)["pendencias"][0]["codigo"] == "CONTA_BANCO_INVALIDA"


def test_conciliacao():
    t = [{"fitid": "1", "valor": Decimal("1500.00"), "data": date(2026, 10, 5)}]
    notas = [{"chave": "K", "emissao": date(2026, 10, 2), "totais": {"vNF": Decimal("1500.00")}},
             {"chave": "L", "emissao": date(2026, 9, 1), "totais": {"vNF": Decimal("1500.00")}}]
    assert conciliar_com_notas(t, notas) == [{"fitid": "1", "chave": "K", "valor": Decimal("1500.00")}]


def test_inss_progressivo_e_irrf_com_redutor():
    f = PARAMS_TESTE["TABELA_INSS_SEGURADO"]["faixas"]
    assert inss_progressivo(Decimal("1500.00"), f) == Decimal("200.00")  # 100 + 100
    assert inss_progressivo(Decimal("5000.00"), f) == Decimal("300.00")  # teto
    p = PARAMS_TESTE["TABELA_IRRF_MENSAL"]
    assert irrf_mensal(Decimal("1900.00"), 0, p) == Decimal("0.00")
    assert irrf_mensal(Decimal("2400.00"), 0, p) == Decimal("0.00")      # zerado pelo redutor
    # 2800: imposto 80; redução 300 - 0,10*2800 = 20 -> 60
    assert irrf_mensal(Decimal("2800.00"), 0, p) == Decimal("60.00")
    # 4000 com 1 dependente: base 3900 -> 190; acima da faixa do redutor
    assert irrf_mensal(Decimal("4000.00"), 1, p) == Decimal("190.00")


def folha(**kw):
    l = {"cpf": "00000000191", "nome": "Empregado Teste", "competencia": "2026-09",
         "salario_contribuicao": Decimal("1500.00"), "inss_descontado": Decimal("200.00"),
         "base_irrf": Decimal("2800.00"), "dependentes": 0, "irrf_descontado": Decimal("60.00")}
    l.update(kw)
    return [l]


def test_conferencia_folha():
    cat = catalogo_teste()
    assert conferir(folha(), CNPJ_A, cat)["achados"] == []
    r = conferir(folha(inss_descontado=Decimal("150.00"), irrf_descontado=Decimal("0.00")), CNPJ_A, cat)
    assert sorted(a.regra for a in r["achados"]) == ["DP_INSS_DIVERGENTE", "DP_IRRF_DIVERGENTE"]
    assert r["achados"][0].natureza == "APONTAMENTO"
    inativo = conferir(folha(inss_descontado=Decimal("1.00")), CNPJ_A, catalogo_teste(conferidas=[], pendentes_com_param=True))
    assert inativo["achados"] == [] and len(inativo["inativas"]) == 2


def test_fgts(tmp_path):
    cat = catalogo_teste()
    ok = folha(remuneracao_fgts=Decimal("1500.00"), fgts_depositado=Decimal("75.00"))
    assert conferir(ok, CNPJ_A, cat)["achados"] == []
    r = conferir(folha(remuneracao_fgts=Decimal("1500.00"), fgts_depositado=Decimal("70.00")), CNPJ_A, cat)
    assert [a.regra for a in r["achados"]] == ["DP_FGTS_DIVERGENTE"] and r["achados"][0].valor == Decimal("-5.00")
    sem = conferir(ok, CNPJ_A, catalogo_teste(conferidas=["TABELA_INSS_SEGURADO", "TABELA_IRRF_MENSAL"]))
    assert sem["achados"] == [] and any("FGTS" in i for i in sem["inativas"])
    from mo_autonomo.dp.folha import ler_folha
    arq = tmp_path / "f.csv"
    arq.write_text("cpf;nome;competencia;salario_contribuicao;inss_descontado;base_irrf;dependentes;irrf_descontado;"
                   "remuneracao_fgts;fgts_depositado\n00000000191;X;2026-09;1500,00;200,00;2800,00;0;60,00;1500,00;75,00\n",
                   encoding="utf-8")
    assert conferir(ler_folha(arq), CNPJ_A, cat)["achados"] == []


def test_auditoria_dominio(tmp_path):
    rel = tmp_path / "rel.csv"
    rel.write_text("Chave;Valor Contábil;CNPJ Empresa\nK1;100,00;" + CNPJ_A + "\nK2;55,00;" + CNPJ_A +
                   "\nK9;10,00;" + CNPJ_A + "\nK1;1,00;" + CNPJ_B + "\n", encoding="latin-1")
    cols = {"chave": "Chave", "valor": "Valor Contábil", "cnpj": "CNPJ Empresa"}
    linhas = ler_relatorio(rel, cols)
    docs = [{"chave": "K1", "totais": {"vNF": Decimal("100.00")}}, {"chave": "K2", "totais": {"vNF": Decimal("50.00")}},
            {"chave": "K3", "totais": {"vServ": Decimal("1.00")}}]
    a = auditar(docs, linhas, CNPJ_A, "2026-10")
    assert sorted(x.regra for x in a) == ["DOMINIO_NAO_IMPORTADO", "DOMINIO_SEM_DOCUMENTO", "DOMINIO_VALOR_DIVERGENTE"]
    with pytest.raises(RelatorioInvalido, match="mapeamento"):
        ler_relatorio(rel, {})
    with pytest.raises(RelatorioInvalido, match="ausentes"):
        ler_relatorio(rel, {**cols, "chave": "Inexistente"})
