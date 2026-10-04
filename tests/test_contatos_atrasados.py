"""Importação de e-mail/WhatsApp, inadimplentes sem boleto em Atrasados e recorrência que começa no meio do mês."""

from datetime import date

from nfse_itaborai import clientes, config, contatos, db, financeiro
from test_emissor import ambiente  # noqa: F401  (fixture)
from test_financeiro import CLI_A, base  # noqa: F401  (fixture)

CSV = ("CPF/CNPJ;Nome / Razão social;Celular;E-mail\r\n"
       "{a};CLIENTE A;(21) 9 8242-4959;Financeiro@ClienteA.com.br\r\n"
       "{a2};CLIENTE NOVO QUE NAO EXISTE;(21) 9 7664-8052;novo@novo.com.br\r\n"
       "{b};CLIENTE B;(21) 1 1111-1111;aguardando@aguardando.com\r\n").encode("utf-8-sig")


def test_importa_so_clientes_existentes_e_ignora_enfeites(base):  # noqa: F811
    b = "11444777000161"
    clientes.salvar({"cpf_cnpj": b, "razao_social": "CLIENTE B", "email": "b@b.com.br", "telefone": "2126271130"})
    clientes.salvar(clientes.obter(CLI_A["cpf_cnpj"]) | {"email": "", "telefone": ""})
    config.salvar({"smtp": {"usuario": "moraes@escritorio.com.br"}})
    dados = CSV.decode("utf-8-sig").format(a=CLI_A["cpf_cnpj"], a2="45309710000136", b=b).encode("utf-8-sig")
    a = contatos.analisar(dados)
    assert [i["cpf_cnpj"] for i in a["itens"]] == [CLI_A["cpf_cnpj"]]          # B: só enfeites, nada muda
    assert [f["cpf_cnpj"] for f in a["fora_do_cadastro"]] == ["45309710000136"]  # não é cadastrado
    r = contatos.aplicar(dados)
    assert r == {"clientes": 1, "emails": 1, "whatsapp": 1, "fora_do_cadastro": 1}
    c = clientes.obter(CLI_A["cpf_cnpj"])
    assert (c["email"], c["telefone"]) == ("financeiro@clientea.com.br", "21982424959")
    assert clientes.obter("45309710000136") is None
    assert clientes.obter(b)["email"] == "b@b.com.br"


def test_celular_fixo_troca_e_email_do_escritorio_e_ignorado(base):  # noqa: F811
    clientes.salvar(clientes.obter(CLI_A["cpf_cnpj"]) | {"email": "", "telefone": "2126271130"})   # fixo
    config.salvar({"smtp": {"usuario": "moraes@escritorio.com.br"}})
    dados = ("CPF/CNPJ;Celular;E-mail\r\n" + CLI_A["cpf_cnpj"] + ";+1 21986275344;moraes@escritorio.com.br\r\n").encode()
    contatos.aplicar(dados)
    c = clientes.obter(CLI_A["cpf_cnpj"])
    assert c["telefone"] == "21986275344" and c["email"] == ""      # o e-mail do escritório não vira do cliente
    assert contatos.celular("(99) 9 1111-2111") == "" and contatos.provisorio("acerto@acerto.com")


def test_inadimplente_sem_boleto_aparece_em_atrasados(base):  # noqa: F811
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "400", vencimento="2026-07-15", emitir_nfse=False)
    financeiro.atualizar_titulo(tid, cobranca_erro="pagador sem endereço")
    t = next(x for x in financeiro.listar_titulos("atrasado", em=date(2026, 10, 5)) if x["id"] == tid)
    assert t["situacao"] == "atrasado" and t["total_cent"] > 40000
    nota = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "100", vencimento="2026-07-15", emitir_nfse=False, cobrar=False)
    assert financeiro.obter_titulo(nota) and nota not in [x["id"] for x in financeiro.listar_titulos("atrasado", em=date(2026, 10, 5))]


def test_recorrencia_no_meio_do_mes_nao_nasce_vencida_nem_duplica(base):  # noqa: F811
    k = financeiro.salvar_contrato({"cpf_cnpj": CLI_A["cpf_cnpj"], "valor": "500", "dia_vencimento": 1, "inicio": "2026-10"})
    with db.conexao() as con:
        con.execute("UPDATE contratos SET confirmado=1")
    pago = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "500", "HONORÁRIOS CONTABEIS MENSAIS.", vencimento="2026-10-01",
                                   competencia="2026-10", emitir_nfse=False, cobrar=False)
    financeiro.baixar(pago, "2026-10-01", "500", "pix")
    assert financeiro.gerar_titulos("2026-10", date(2026, 10, 4)) == []          # outubro já lançado (pago por PIX)
    assert financeiro.obter_titulo(pago)["contrato_id"] == k["id"]
    b = "11444777000161"
    clientes.salvar({"cpf_cnpj": b, "razao_social": "CLIENTE B", "email": "b@b.com.br"})
    financeiro.salvar_contrato({"cpf_cnpj": b, "valor": "300", "dia_vencimento": 1, "inicio": "2026-10"})
    with db.conexao() as con:
        con.execute("UPDATE contratos SET confirmado=1")
    novo = financeiro.gerar_titulos("2026-10", date(2026, 10, 4))
    assert [financeiro.obter_titulo(t)["vencimento"] for t in novo] == ["2026-10-01"]   # vencimento nunca é prorrogado


def test_inadimplencia_do_nitrus_segue_cobrada_sem_boleto(base, monkeypatch):  # noqa: F811
    from nfse_itaborai import automacao, cobranca, inter
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "400", "HONORÁRIOS CONTABEIS MENSAIS.", vencimento="2026-07-15",
                                  emitir_nfse=True, apos_pagamento=True)
    monkeypatch.setattr(config, "CNPJ_REGRA_BAIXA", {config._cnpj_da_pasta()})
    with db.conexao() as con:
        con.execute("PRAGMA user_version=3")
        db._migrar(con)
    assert financeiro.obter_titulo(tid)["boleto_situacao"] == "dispensado"
    monkeypatch.setattr(inter, "configurado", lambda cfg=None: True)
    monkeypatch.setattr(inter, "criar_cobranca", lambda *a, **k: (_ for _ in ()).throw(AssertionError("não gera boleto")))
    config.salvar({"cobranca": {"provedor": "inter"}, "empresa": {"pix_chave": "24875410000144"}})
    assert cobranca.preparar_pagamento(tid)["banco_id"] == ""
    env = []
    monkeypatch.setattr(cobranca, "enviar_email", lambda para, assunto, texto, cfg=None, anexos=None, **k: env.append(texto))
    cobranca.rodar_regua(date(2026, 10, 5))
    assert len(env) == 1 and "use o PIX abaixo" in env[0] and "expirou" not in env[0] and "br.gov.bcb.pix" in env[0].lower()
    assert "15/07/2026" in env[0]                                         # vencimento original mantido
    assert automacao is not None


def test_recorrencias_da_moraes_comecam_em_outubro(base, monkeypatch):  # noqa: F811
    k = financeiro.salvar_contrato({"cpf_cnpj": CLI_A["cpf_cnpj"], "valor": "500", "dia_vencimento": 10, "inicio": "2026-11"})
    monkeypatch.setattr(config, "CNPJ_REGRA_BAIXA", {config._cnpj_da_pasta()})
    with db.conexao() as con:
        con.execute("PRAGMA user_version=3")
        db._migrar(con)
    assert db.linhas("SELECT inicio FROM contratos WHERE id=?", (k["id"],))[0]["inicio"] == "2026-10"
