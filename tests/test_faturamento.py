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
    # fora da régua (nenhuma cobrança, nenhum PIX/boleto) — só a própria nota fiscal vai ao cliente, uma vez
    assert [a[1] for a in enviados] == [f"Nota fiscal de serviço nº {t['nfse_numero']}"], res
    assert not financeiro.obter_titulo(t["id"])["pix_copia_cola"]


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


def test_regra_geral_e_regra_da_recorrencia_do_cliente(base):  # noqa: F811
    config.salvar({"emissao": {"nfse_quando": "baixa"}})                 # regra geral: nota na baixa
    r = tratar("emitir", {"cpf_cnpj": CLI_A["cpf_cnpj"], "valor": "100"})
    assert r["aguardando_pagamento"] and financeiro.obter_titulo(r["titulo_id"])["nfse_status"] == "apos_pagamento"
    # a recorrência do cliente com regra própria vale primeiro
    k = tratar("contrato/salvar", {"cpf_cnpj": CLI_A["cpf_cnpj"], "valor": "90", "inicio": "2026-01",
                                   "nfse_quando": "geracao"})
    r = tratar("emitir", {"cpf_cnpj": CLI_A["cpf_cnpj"], "valor": "100"})
    assert r["sucesso"] and r["nfse"] and financeiro.obter_titulo(r["titulo_id"])["nfse_status"] == "emitida"
    # "apenas lançar": conta a receber sem nota
    tratar("contrato/salvar", {"id": k["id"], "cpf_cnpj": CLI_A["cpf_cnpj"], "valor": "90", "inicio": "2026-01",
                               "nfse_quando": "lancar"})
    r = tratar("emitir", {"cpf_cnpj": CLI_A["cpf_cnpj"], "valor": "100"})
    assert r["sem_nota"] and financeiro.obter_titulo(r["titulo_id"])["nfse_status"] == "nao_emitir"
    t = financeiro.obter_titulo(financeiro.gerar_titulos("2026-12")[0])
    assert t["nfse_status"] == "nao_emitir"
    # "não emitir e não lançar": a recorrência não gera nada
    tratar("contrato/salvar", {"id": k["id"], "cpf_cnpj": CLI_A["cpf_cnpj"], "valor": "90", "inicio": "2026-01",
                               "nfse_quando": "nada"})
    assert financeiro.gerar_titulos("2027-01") == []


def test_aba_recorrencia_traz_todos_os_clientes_com_valores(base):  # noqa: F811
    from nfse_itaborai import clientes
    lst = clientes.listar()
    for c in lst:
        c.update({"ultimo_valor": "350.00", "ultima_data": "2026-09-20"} if c["cpf_cnpj"] == CLI_A["cpf_cnpj"] else {})
    clientes._gravar(lst)
    r = tratar("recorrencia", {})
    assert r["preenchidos"] == 1 and tratar("recorrencia", {})["preenchidos"] == 0          # idempotente
    a = next(l for l in r["linhas"] if l["cpf_cnpj"] == CLI_A["cpf_cnpj"])
    b = next(l for l in r["linhas"] if l["cpf_cnpj"] != CLI_A["cpf_cnpj"])
    assert a["valor_cent"] == 35000 and not a["repetir"] and a["inicio"] == "2026-10" and a["id"]
    assert b["id"] is None and b["valor_cent"] == 0
    assert financeiro.gerar_titulos("2026-10") == []                     # a confirmar: ninguém é cobrado
    tratar("recorrencia/salvar", {"linhas": [{"id": a["id"], "cpf_cnpj": a["cpf_cnpj"], "valor": "380,00",
                                              "dia_vencimento": 15, "nfse_quando": "baixa", "cobrar": True,
                                              "repetir": True},
                                             {"id": None, "cpf_cnpj": b["cpf_cnpj"], "valor": "120", "dia_vencimento": 5,
                                              "nfse_quando": "", "cobrar": False, "repetir": True}]})
    ts = {financeiro.obter_titulo(i)["cpf_cnpj"]: financeiro.obter_titulo(i) for i in financeiro.gerar_titulos("2026-11")}
    assert ts[CLI_A["cpf_cnpj"]]["valor_cent"] == 38000 and ts[CLI_A["cpf_cnpj"]]["nfse_status"] == "apos_pagamento"
    assert ts[CLI_A["cpf_cnpj"]]["vencimento"] == "2026-11-15"
    assert ts[b["cpf_cnpj"]]["cobrar"] == 0 and ts[b["cpf_cnpj"]]["nfse_status"] == "pendente"


def test_nota_sem_cobranca_e_importada_nao_entram_em_a_receber(base):  # noqa: F811
    from nfse_itaborai import relatorios
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "1130", vencimento="2026-09-01", cobrar=False)
    financeiro.atualizar_titulo(tid, nfse_status="emitida")
    p = relatorios.painel(date(2026, 10, 2))
    assert p["a_receber"] == 0 and p["atrasado"] == 0
    assert [t["id"] for t in financeiro.listar_titulos("sem_cobranca")] == [tid]
    assert financeiro.listar_titulos("a_receber") == []


def test_nota_emitida_sem_boleto_gerado_nao_e_conta_a_receber(base):  # noqa: F811
    """Caso real: notas emitidas (versão anterior marcava cobrar=1), mas nenhum boleto/PIX foi gerado."""
    from nfse_itaborai import relatorios
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "350", vencimento="2026-10-05")
    financeiro.atualizar_titulo(tid, nfse_status="emitida", nfse_numero="99003873", pix_copia_cola="")
    p = relatorios.painel(date(2026, 10, 2))
    assert p["faturado_mes"] == 35000                       # é faturamento (nota emitida)...
    assert p["a_receber"] == 0 and p["proximos_7_dias"] == []      # ...mas não é valor em cobrança
    assert financeiro.listar_titulos("a_receber") == [] and financeiro.obter_titulo(tid)["status"] == "aberto"
    assert [t["id"] for t in financeiro.listar_titulos("sem_cobranca")] == [tid]
    financeiro.atualizar_titulo(tid, banco_id="cod-inter", linha_digitavel="0019...")   # boleto registrado
    assert relatorios.painel(date(2026, 10, 2))["a_receber"] == 35000


def test_tirar_da_cobranca_mantem_a_nota_e_gerar_cobranca_volta(base):  # noqa: F811
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "400", vencimento="2026-10-05")
    financeiro.atualizar_titulo(tid, nfse_status="emitida", nfse_numero="99003875")
    assert [t["id"] for t in financeiro.listar_titulos("a_receber")] == [tid]
    tratar("titulo/sem_cobranca", {"id": tid})
    t = financeiro.obter_titulo(tid)
    assert t["status"] == "aberto" and t["nfse_status"] == "emitida" and t["cobrar"] == 0
    assert financeiro.listar_titulos("a_receber") == []
    t = tratar("titulo/gerar_cobranca", {"id": tid})
    assert t["cobrar"] == 1 and t["pix_copia_cola"].startswith("000201")
    assert [x["id"] for x in financeiro.listar_titulos("a_receber")] == [tid]
