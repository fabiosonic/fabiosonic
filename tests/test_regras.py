from datetime import date, timedelta
from decimal import Decimal

from conftest import EMPRESA, C, D, E, F, codigos, lote_de

from portal_contabil import auditar
from portal_contabil import fabrica as fb


def _res(*arqs, **kw):
    return auditar(lote_de(*arqs), **kw)


def test_inferencia_de_empresa_e_regime(venda):
    res = _res(("1.xml", fb.nfe_xml(1, D, E, C, venda)), ("2.xml", fb.nfe_xml(2, D, E, C, venda)),
               ("3.xml", fb.nfe_xml(9, D, F, E, venda, crt="3", tp_nf="1")))
    assert res.empresa.cnpj == EMPRESA and res.empresa.regime == "simples"
    assert "CFG001" in codigos(res)


def test_lacuna_e_duplicidade_de_numeracao(venda):
    res = _res(("1.xml", fb.nfe_xml(1, D, E, C, venda)), ("4.xml", fb.nfe_xml(4, D, E, C, venda)),
               ("4b.xml", fb.nfe_xml(4, D, E, C, venda, chave=fb.gerar_chave("SP", D, EMPRESA, "55", 1, 4, 999))))
    lacuna = next(a for a in res.achados if a.codigo == "DOC006")
    assert "2, 3" in lacuna.descricao
    assert "DOC005" in codigos(res)


def test_chave_invalida_e_sem_protocolo(venda):
    chave = fb.gerar_chave("SP", D, EMPRESA, "55", 1, 1)
    ruim = chave[:-1] + str((int(chave[-1]) + 1) % 10)
    res = _res(("1.xml", fb.nfe_xml(1, D, E, C, venda, chave=ruim)),
               ("2.xml", fb.nfe_xml(2, D, E, C, venda, protocolo=False)))
    assert {"DOC003", "DOC001"} <= codigos(res)


def test_totais_e_cfop(venda):
    itens = [{"cfop": "1102", "valor": "500"}, {"cfop": "6102", "valor": "300"}]
    res = _res(("1.xml", fb.nfe_xml(1, D, E, C, itens, vnf_informado="900")))
    assert {"NFE002", "NFE003", "NFE004"} <= codigos(res)


def test_crt_inconsistente():
    res = _res(("1.xml", fb.nfe_xml(1, D, E, C, [{"cfop": "5102", "valor": 10, "cst": "00"}], crt="1")),
               ("2.xml", fb.nfe_xml(2, D, E, C, [{"cfop": "5102", "valor": 10, "csosn": "102"}], crt="1")))
    assert "NFE005" in codigos(res)


def test_reforma_tributaria_regime_normal():
    itens = [{"cfop": "5102", "valor": 100, "cst": "00"}]
    res = _res(("1.xml", fb.nfe_xml(1, D, E, C, itens, crt="3")),
               ("2.xml", fb.nfe_xml(2, D, E, C, itens, crt="3", ibscbs=True)))
    ach = next(a for a in res.achados if a.codigo == "NFE007")
    assert ach.titulo.startswith("1 NF-e") and res.empresa.regime == "normal"


def test_oportunidades_monofasico_e_st():
    itens = [{"ncm": "30049099", "cfop": "5405", "valor": "800", "csosn": "500"},
             {"ncm": "84713012", "cfop": "5102", "valor": "200"}]
    res = _res(("1.xml", fb.nfe_xml(1, D, E, C, itens)))
    mono = next(a for a in res.achados if a.codigo == "SN010")
    st = next(a for a in res.achados if a.codigo == "SN011")
    assert mono.valor == 800 and st.valor == 800


def test_retencao_indevida_sobre_simples_e_iss_retido():
    xml = fb.nfse_nacional_xml(1, D, E, C, "10000", iss_retido=True, irrf="150", pis="65", cofins="300", csll="100")
    res = _res(("s.xml", xml), regime="simples")
    c = codigos(res)
    assert "NFS001" in c and "SN012" in c
    assert next(a for a in res.achados if a.codigo == "NFS001").severidade == "ALTO"


def test_aliquotas_de_retencao_e_iss_fora_da_faixa():
    xml = fb.nfse_nacional_xml(1, D, F, E, "1000", op_simples="1", aliq_iss="1.00", irrf="30",
                               pis="6.5", cofins="30", csll="10")
    res = _res(("s.xml", xml), cnpj=EMPRESA, regime="normal")
    ach = next(a for a in res.achados if a.codigo == "NFS002")
    assert "IRRF de 3,00%" in ach.descricao
    assert "NFS003" in codigos(res)


def test_tomador_sem_retencao():
    xml = fb.nfse_nacional_xml(1, D, F, E, "3000", op_simples="1")
    res = _res(("s.xml", xml), cnpj=EMPRESA, regime="normal")
    assert "NFS005" in codigos(res)


def test_limites_do_simples():
    def ano(valor):
        return [(f"{m}.xml", fb.nfe_xml(m, date(2026, m, 5), E, C, [{"cfop": "5102", "valor": valor}]))
                for m in range(1, 12)]
    res = _res(*ano("450000"))  # 4,95 mi: acima do limite, excesso <= 20%
    ach = next(a for a in res.achados if a.codigo == "SN002")
    assert ach.severidade == "CRITICO" and ach.valor == Decimal("4950000")
    assert res.apuracao[-1].rbt12 == Decimal("4500000")
    res = _res(*ano("360000"))  # 3,96 mi: acima do sublimite, excesso <= 20%
    ach = next(a for a in res.achados if a.codigo == "SN003")
    assert ach.severidade == "ALTO" and "1º de janeiro do ano seguinte" in ach.descricao


def test_devolucao_reduz_receita():
    res = _res(("v.xml", fb.nfe_xml(1, D, E, C, [{"cfop": "5102", "valor": "1000"}])),
               ("d.xml", fb.nfe_xml(77, D, C, E, [{"cfop": "5202", "valor": "300"}], crt="3")))
    assert res.contexto.receita_mensal == {"2026-03": Decimal("700")}


def test_fator_r_abaixo_de_28():
    arqs = [(f"{m}.xml", fb.nfse_nacional_xml(m, date(2025, m, 10), E, C, "20000")) for m in range(1, 13)]
    folha = fb.folha_csv([(f"{m:02d}/2025", 0, 2000, 0) for m in range(1, 13)])
    arqs.append(("jan26.xml", fb.nfse_nacional_xml(13, date(2026, 1, 10), E, C, "20000")))
    res = _res(*arqs, ("folha.csv", folha))
    ach = next(a for a in res.achados if a.codigo == "SN005")
    assert ach.severidade == "MEDIO"
    # 28% de 240.000 = 67.200; folha de 24.000 -> faltam 43.200
    assert ach.valor == Decimal("43200.00")


def test_conciliacao_bancaria():
    n1 = fb.nfe_xml(1, D, E, C, [{"cfop": "5102", "valor": "1000"}])
    n2 = fb.nfe_xml(2, D, E, C, [{"cfop": "5102", "valor": "2000"}])
    n3 = fb.nfe_xml(3, D, E, C, [{"cfop": "5102", "valor": "500"}])
    extrato = fb.ofx([
        (D - timedelta(days=1), "-12.90", "TARIFA PACOTE"),
        (D + timedelta(days=3), "1000.00", "PIX RECEBIDO CLIENTE ALFA"),
        (D + timedelta(days=20), "1985.00", "LIQUIDACAO BOLETO"),     # tarifa de R$ 15
        (D + timedelta(days=5), "7000.00", "DEPOSITO DINHEIRO"),      # sem nota
        (D + timedelta(days=6), "10000.00", "RESGATE APLICACAO CDB"),  # não operacional
        (D + timedelta(days=7), "-300.00", "PAGTO FORNECEDOR"),
        (D + timedelta(days=45), "-12.90", "TARIFA PACOTE"),
    ])
    res = _res(("1.xml", n1), ("2.xml", n2), ("3.xml", n3), ("ext.ofx", extrato))
    conc = res.conciliacao
    assert len(conc.conciliados) == 2
    assert [l.valor for l in conc.creditos_sem_nota] == [Decimal("7000.00")]
    assert [d.numero for d in conc.notas_sem_recebimento] == ["3"]
    c = codigos(res)
    assert {"CON001", "CON002", "CON004", "CON005"} <= c
    assert next(a for a in res.achados if a.codigo == "CON001").severidade == "CRITICO"


def test_nfse_conciliada_pelo_valor_liquido():
    xml = fb.nfse_nacional_xml(1, D, E, C, "10000", op_simples="1", irrf="150", pis="65", cofins="300", csll="100")
    extrato = fb.ofx([(D + timedelta(days=10), "9385.00", "TED CLIENTE ALFA")])
    res = _res(("s.xml", xml), ("e.ofx", extrato), regime="normal")
    assert len(res.conciliacao.conciliados) == 1 and not res.conciliacao.creditos_sem_nota


def test_documentos_de_terceiros(venda):
    outro = (fb.gerar_cnpj("444333220001"), "Outra Empresa", "SP")
    res = _res(("1.xml", fb.nfe_xml(1, D, E, C, venda)), ("2.xml", fb.nfe_xml(2, D, E, C, venda)),
               ("x.xml", fb.nfe_xml(5, D, outro, F, venda)), cnpj=EMPRESA)
    assert "DOC008" in codigos(res)


def test_mei_acima_do_limite():
    arqs = [(f"{m}.xml", fb.nfe_xml(m, date(2026, m, 5), E, C, [{"cfop": "5102", "valor": "9000"}], crt="4"))
            for m in range(1, 11)]
    res = _res(*arqs)
    assert res.empresa.regime == "mei"
    ach = next(a for a in res.achados if a.codigo == "SN001")
    assert ach.severidade == "ALTO"


def test_nota_recente_fica_no_prazo():
    n1 = fb.nfe_xml(1, D, E, C, [{"cfop": "5102", "valor": "1000"}])
    extrato = fb.ofx([(D - timedelta(days=2), "-5.00", "TARIFA"), (D + timedelta(days=10), "-5.00", "TARIFA")])
    res = _res(("1.xml", n1), ("e.ofx", extrato))
    assert "CON006" in codigos(res) and "CON004" not in codigos(res)


def test_consolidacao_de_achados_repetidos():
    arqs = [(f"{n}.xml", fb.nfse_nacional_xml(n, D, E, C, "1000", irrf="15")) for n in range(1, 6)]
    res = _res(*arqs, regime="simples")
    nfs001 = [a for a in res.achados if a.codigo == "NFS001"]
    assert len(nfs001) == 1 and nfs001[0].ocorrencias == 5 and nfs001[0].valor == Decimal("75.00")
    assert nfs001[0].titulo.startswith("5 NFS-e")
    assert len([a for a in res.achados_detalhados if a.codigo == "NFS001"]) == 5
