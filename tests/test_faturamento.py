"""Faturamento: gerar ou não a cobrança, e NFS-e emitida só depois do pagamento."""

from datetime import date

from nfse_itaborai import automacao, cobranca, config, db, financeiro
from nfse_itaborai.tela import tratar
from test_emissor import Simulador, ambiente  # noqa: F401  (fixture)
from test_financeiro import CLI_A, base  # noqa: F401  (fixture)


def test_sem_cobranca_emite_nota_mas_fica_fora_da_regua(base, monkeypatch):  # noqa: F811
    r = tratar("emitir", {"cpf_cnpj": CLI_A["cpf_cnpj"], "valor": "500,00", "vencimento": "2026-09-01",
                          "cobrar": False})
    assert r["sucesso"] and r["nfse"]
    t = financeiro.obter_titulo(r["titulo_id"])
    assert t["cobrar"] == 0 and t["nfse_status"] == "emitida"
    enviados = []
    monkeypatch.setattr(cobranca, "enviar_email", lambda *a, **k: enviados.append(a))
    cobranca.rodar_regua(date(2026, 10, 1))
    res = automacao.rodar(em=date(2026, 10, 1), forcar=True)
    assert not enviados and not financeiro.obter_titulo(t["id"])["pix_copia_cola"], res


def test_cobra_primeiro_e_emite_a_nota_quando_o_pagamento_entra(base):  # noqa: F811
    r = tratar("emitir", {"cpf_cnpj": CLI_A["cpf_cnpj"], "valor": "800,00", "apos_pagamento": True})
    assert r["sucesso"] and r["aguardando_pagamento"] and not r.get("nfse")
    t = financeiro.obter_titulo(r["titulo_id"])
    assert t["nfse_status"] == "apos_pagamento" and t["status"] == "aberto" and t["cobrar"] == 1
    assert t["pix_copia_cola"]                                   # cobrança gerada na hora
    automacao.rodar(em=date.today(), forcar=True)                # robô não emite antes do pagamento
    assert financeiro.obter_titulo(t["id"])["nfse_status"] == "apos_pagamento"
    pago = tratar("titulo/baixar", {"id": t["id"], "forma": "boleto"})
    assert pago["status"] == "pago" and pago["nfse_status"] == "emitida" and pago["nfse_numero"]


def test_emissao_falha_na_baixa_fica_pendente_e_o_robo_emite(base, monkeypatch):  # noqa: F811
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "300", apos_pagamento=True)
    original = financeiro.emitir_nfse_titulo
    monkeypatch.setattr(financeiro, "emitir_nfse_titulo", lambda *a, **k: (_ for _ in ()).throw(OSError("fora do ar")))
    financeiro.baixar(tid, forma="extrato")
    t = financeiro.obter_titulo(tid)
    assert t["status"] == "pago" and t["nfse_status"] == "pendente"
    monkeypatch.setattr(financeiro, "emitir_nfse_titulo", original)
    automacao.rodar(em=date.today(), forcar=True)
    assert financeiro.obter_titulo(tid)["nfse_status"] == "emitida"


def test_padrao_da_empresa_vale_para_contratos(base):  # noqa: F811
    config.salvar({"emissao": {"nfse_apos_pagamento": True}})
    tratar("contrato/salvar", {"cpf_cnpj": CLI_A["cpf_cnpj"], "valor": "1000", "dia_vencimento": 10, "inicio": "2026-01"})
    ids = financeiro.gerar_titulos("2026-11")
    assert ids and financeiro.obter_titulo(ids[0])["nfse_status"] == "apos_pagamento"
    assert db.linhas("SELECT COUNT(*) n FROM titulos WHERE nfse_status='apos_pagamento'")[0]["n"] == 1


def test_repetir_todo_mes_cria_contrato_com_as_mesmas_escolhas(base):  # noqa: F811
    r = tratar("emitir", {"cpf_cnpj": CLI_A["cpf_cnpj"], "valor": "1.200,00", "vencimento": "2026-10-15",
                          "apos_pagamento": True, "cobrar": True, "recorrente": True, "recorrente_ate": "2027-03"})
    assert r["sucesso"] and r["contrato_id"]
    k = next(c for c in financeiro.listar_contratos() if c["id"] == r["contrato_id"])
    assert (k["inicio"], k["fim"], k["dia_vencimento"], k["valor_cent"]) == ("2026-11", "2027-03", 15, 120000)
    assert k["nfse_quando"] == "pagamento" and k["cobrar"] == 1
    assert financeiro.gerar_titulos("2026-10") == []                       # o mês atual não é cobrado em dobro
    novo = financeiro.obter_titulo(financeiro.gerar_titulos("2026-11")[0])
    assert novo["nfse_status"] == "apos_pagamento" and novo["vencimento"] == "2026-11-15" and novo["cobrar"] == 1
    assert financeiro.gerar_titulos("2027-04") == []                       # depois do fim, para


def test_contrato_sem_cobranca_com_nota_na_hora(base):  # noqa: F811
    config.salvar({"emissao": {"nfse_apos_pagamento": True}})            # padrão da empresa: após pagamento
    k = tratar("contrato/salvar", {"cpf_cnpj": CLI_A["cpf_cnpj"], "valor": "90", "inicio": "2026-01",
                                   "nfse_quando": "agora", "cobrar": False})
    t = financeiro.obter_titulo(financeiro.gerar_titulos("2026-12")[0])
    assert k["cobrar"] == 0 and t["nfse_status"] == "pendente" and t["cobrar"] == 0
