"""Envio automático: o boleto sai assim que a cobrança é gerada; pago, o cliente recebe o agradecimento e a NFS-e."""

from datetime import date

from nfse_itaborai import clientes, cobranca, config, db, financeiro
from test_emissor import ambiente  # noqa: F401  (fixture)
from test_financeiro import CLI_A, base  # noqa: F401  (fixture)


def _cap(monkeypatch):
    env = []
    monkeypatch.setattr(cobranca, "enviar_email", lambda para, assunto, texto, cfg=None, anexos=None, **k:
                        env.append((para, assunto, texto, anexos or [])))
    return env


def test_boleto_sai_quando_a_cobranca_e_gerada(base, monkeypatch):  # noqa: F811
    env = _cap(monkeypatch)
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "500", vencimento="2026-10-20", emitir_nfse=False)
    cobranca.preparar_pagamento(tid)
    r = cobranca.rodar_regua(date(2026, 10, 1))                 # 19 dias antes: nenhuma etapa da régua ainda
    assert r["email"] == 1 and r["whatsapp"] == 1 and env[0][1] == "Boleto dos honorários — vencimento 20/10/2026"
    assert "Segue a cobrança dos honorários de R$ 500,00" in env[0][2]
    fila = cobranca.fila_whatsapp()
    assert len(fila) == 1 and fila[0]["etapa"] == cobranca.ETAPA_BOLETO
    assert cobranca.rodar_regua(date(2026, 10, 2))["email"] == 0  # não repete
    assert cobranca.rodar_regua(date(2026, 10, 17))["email"] == 1  # o lembrete de 3 dias continua


def test_titulo_vencido_importado_recebe_a_cobranca_uma_vez(base, monkeypatch):  # noqa: F811
    env = _cap(monkeypatch)
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "400", vencimento="2026-07-10", emitir_nfse=False)
    cobranca.preparar_pagamento(tid)
    cobranca.rodar_regua(date(2026, 10, 1))
    assert len(env) == 1 and "10/07/2026" in env[0][2]
    assert cobranca.rodar_regua(date(2026, 10, 2))["email"] == 0


def test_desligado_nao_manda_ao_gerar(base, monkeypatch):  # noqa: F811
    env = _cap(monkeypatch)
    config.salvar({"cobranca": {"enviar_ao_gerar": False}})
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "500", vencimento="2026-10-20", emitir_nfse=False)
    cobranca.preparar_pagamento(tid)
    assert cobranca.rodar_regua(date(2026, 10, 1))["email"] == 0 and env == []


def test_pago_agradece_e_depois_manda_a_nota(base, monkeypatch, tmp_path):  # noqa: F811
    env = _cap(monkeypatch)
    antigo = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "100", vencimento="2026-08-10", emitir_nfse=False)
    financeiro.baixar(antigo, "2026-08-10", "100", "pix")      # pago antes de ligar: não recebe nada
    cobranca.rodar_regua(date(2026, 9, 30))                     # liga o recurso (agradecer_desde = 30/09)
    env.clear()
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "374,40", vencimento="2026-10-10", emitir_nfse=False)
    financeiro.atualizar_titulo(tid, nfse_status="apos_pagamento", pix_copia_cola="000201x")
    financeiro.baixar(tid, "2026-10-08", "374,40", "extrato")   # baixa (nota ainda não emitida)
    financeiro.atualizar_titulo(tid, nfse_status="pendente")    # a emissão após o pagamento ainda não saiu
    cobranca.rodar_regua(date(2026, 10, 8))
    assert [e[1] for e in env] == ["Pagamento recebido — obrigado! (R$ 374,40)"]
    assert "Recebemos o seu pagamento de R$ 374,40 em 08/10/2026" in env[0][2] and "pontualidade" in env[0][2]
    pasta = financeiro.emissor.raiz() / "saida" / "2026-10" / "RPS_9"
    pasta.mkdir(parents=True)
    (pasta / "NFSe_202600000123.xml").write_text("<NFSe/>", encoding="utf-8")
    financeiro.atualizar_titulo(tid, nfse_status="emitida", nfse_numero="202600000123", nfse_link="https://nfse.exemplo/123")
    cobranca.rodar_regua(date(2026, 10, 9))
    assert env[1][1] == "Nota fiscal de serviço nº 202600000123" and "https://nfse.exemplo/123" in env[1][2]
    assert env[1][3] and env[1][3][0].endswith("NFSe_202600000123.xml")
    fila = cobranca.fila_whatsapp()
    assert [e["etapa"] for e in fila] == [cobranca.ETAPA_PAGO, cobranca.ETAPA_NFSE]   # WhatsApp: na mesma ordem
    cobranca.rodar_regua(date(2026, 10, 10))
    assert len(env) == 2                                          # nada repete
    assert not db.linhas("SELECT 1 FROM eventos_cobranca WHERE titulo_id=?", (antigo,))


def test_whatsapp_so_para_quem_e_marcado(base, monkeypatch):  # noqa: F811
    _cap(monkeypatch)
    clientes.salvar(clientes.obter(CLI_A["cpf_cnpj"]) | {"whatsapp_cobranca": False})
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "200", vencimento="2026-10-10", emitir_nfse=False)
    cobranca.rodar_regua(date(2026, 10, 1))
    financeiro.baixar(tid, "2026-10-02", "200", "pix")
    cobranca.rodar_regua(date(2026, 10, 2))
    assert cobranca.fila_whatsapp() == []


def test_titulos_do_mesmo_cliente_vao_num_unico_email(base, monkeypatch):  # noqa: F811
    env = []
    monkeypatch.setattr(cobranca, "enviar_email", lambda para, assunto, texto, cfg=None, anexos=None, html="", **k:
                        env.append((para, assunto, texto, html)))
    ids = [financeiro.criar_titulo(CLI_A["cpf_cnpj"], v, vencimento=d, emitir_nfse=False)
           for v, d in (("400", "2026-07-10"), ("500", "2026-08-10"), ("600", "2026-10-20"))]
    for tid in ids:
        financeiro.atualizar_titulo(tid, pix_copia_cola=f"000201pix{tid}")
    r = cobranca.rodar_regua(date(2026, 10, 1))
    assert r["email"] == 1 and len(env) == 1
    para, assunto, texto, html = env[0]
    assert assunto.startswith("Honorários em aberto — 3 títulos (total atualizado R$ ")
    assert texto.index("10/07/2026") < texto.index("10/08/2026") < texto.index("20/10/2026")   # por vencimento
    assert all(f"000201pix{tid}" in texto and f"000201pix{tid}" in html for tid in ids)
    assert "R$ 600,00" in texto and "dia(s) em atraso" in html
    ev = db.linhas("SELECT titulo_id, etapa, status FROM eventos_cobranca WHERE canal='email' ORDER BY titulo_id")
    assert [e["titulo_id"] for e in ev] == ids and {e["status"] for e in ev} == {"enviado"}
    assert cobranca.rodar_regua(date(2026, 10, 2))["email"] == 0   # nada repete


def test_email_cobra_tudo_que_o_cliente_tem_em_aberto_mesmo_quando_so_um_vence_hoje(base, monkeypatch):  # noqa: F811
    """Caso real (Espaço Acolher): o cliente tinha vários débitos e a mensagem cobrava só o título cuja etapa venceu
    naquele dia. Agora a mensagem traz todos os títulos em aberto, somados e com o valor atualizado."""
    env = _cap(monkeypatch)
    velho = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "400", vencimento="2026-07-10", emitir_nfse=False)
    novo = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "500", vencimento="2026-10-20", emitir_nfse=False)
    for tid in (velho, novo):
        financeiro.atualizar_titulo(tid, pix_copia_cola=f"000201pix{tid}")
    with db.conexao() as con:                                     # o título novo já recebeu o boleto; etapa dele não vence hoje
        con.execute("INSERT INTO eventos_cobranca (titulo_id, etapa, canal, data, status, detalhe) VALUES (?,?,?,?,?,?)",
                    (novo, cobranca.ETAPA_BOLETO, "email", "2026-09-20", "enviado", "x"))
    r = cobranca.rodar_regua(date(2026, 10, 1))
    assert r["email"] == 1 and len(env) == 1
    _, assunto, texto, _ = env[0]
    assert "2 títulos" in assunto and "10/07/2026" in texto and "20/10/2026" in texto
    assert "Total: R$" in texto and "dia(s) em atraso" in texto                    # soma e valor atualizado
    assert all(f"000201pix{tid}" in texto for tid in (velho, novo))
    ev = db.linhas("SELECT titulo_id FROM eventos_cobranca WHERE canal='email' AND data='2026-10-01'")
    assert [e["titulo_id"] for e in ev] == [velho]                               # só a etapa do título da vez é registrada


def test_nota_emitida_vai_ao_cliente_mesmo_sem_cobranca_e_sem_pagamento(base, monkeypatch):  # noqa: F811
    """NFS-e emitida (regra 'emitir na geração', ou faturamento sem cobrança) também é enviada ao cliente,
    uma vez só; notas emitidas antes do recurso não são reenviadas em massa."""
    env = _cap(monkeypatch)
    velha = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "90", vencimento="2026-09-10", emitir_nfse=False)
    financeiro.atualizar_titulo(velha, nfse_status="emitida", nfse_numero="1", nfse_data="2026-09-01")
    cobranca.rodar_regua(date(2026, 10, 1))                      # liga o recurso em 01/10
    env.clear()
    sem_cob = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "350", vencimento="2026-10-20", emitir_nfse=False)
    financeiro.atualizar_titulo(sem_cob, cobrar=0, nfse_status="emitida", nfse_numero="202600000777",
                                nfse_data="2026-10-02", nfse_link="https://nfse.exemplo/777")
    r = cobranca.enviar_pos_pagamento(date(2026, 10, 2))
    assert r["email"] == 1 and env[0][1] == "Nota fiscal de serviço nº 202600000777"
    assert "no valor de R$ 350,00" in env[0][2] and "https://nfse.exemplo/777" in env[0][2]
    assert [e["etapa"] for e in cobranca.fila_whatsapp() if e["titulo_id"] == sem_cob] == [cobranca.ETAPA_NFSE]
    assert cobranca.enviar_pos_pagamento(date(2026, 10, 2))["email"] == 0          # não repete
    assert not db.linhas("SELECT 1 FROM eventos_cobranca WHERE titulo_id=? AND etapa=?", (velha, cobranca.ETAPA_NFSE))
    # botão "Enviar ao cliente": reenvia na hora
    from nfse_itaborai.tela import tratar
    monkeypatch.setattr(cobranca.horario, "comercial", lambda **k: True)
    config.salvar({"smtp": {"host": "smtp.exemplo"}})
    x = tratar("titulo/enviar_nfse", {"id": sem_cob})
    assert x["email"] == CLI_A["email"] and len(env) == 2


def test_anexo_xml_vai_como_xml_e_nao_como_pdf(base, monkeypatch, tmp_path):  # noqa: F811
    enviados = []

    class SMTP:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def starttls(self, **k): pass
        def login(self, *a): pass
        def send_message(self, msg): enviados.append(msg)
    monkeypatch.setattr(cobranca.smtplib, "SMTP", SMTP)
    config.salvar({"smtp": {"host": "smtp.exemplo", "porta": 587, "usuario": "a@b.com", "senha": "x"}})
    arq = tmp_path / "NFSe_1.xml"
    arq.write_text("<NFSe/>", encoding="utf-8")
    cobranca.enviar_email("c@d.com", "t", "x", anexos=[str(arq)], teste=True)
    tipos = [p.get_content_type() for p in enviados[0].iter_attachments()]
    assert tipos == ["application/xml"]


def test_rotina_rapida_envia_a_nota_sem_esperar_o_robo(base, monkeypatch):  # noqa: F811
    from nfse_itaborai import automacao
    env = _cap(monkeypatch)
    hoje = financeiro.hoje()
    cobranca.enviar_pos_pagamento(hoje)                           # liga o recurso hoje
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "500", vencimento="2026-12-20", emitir_nfse=False)
    financeiro.atualizar_titulo(tid, nfse_status="emitida", nfse_numero="55", nfse_data=hoje.isoformat())
    r = automacao.rodar_pagamentos()
    assert any(v.get("envio_notas", {}).get("email") == 1 for v in r.values() if isinstance(v, dict))
    assert [e[1] for e in env] == ["Nota fiscal de serviço nº 55"] and automacao.AGENDA["ultima"]
    assert config.carregar()["automacao"]["intervalo_extrato_min"] == 15


def test_atraso_cobrado_3_dias_apos_o_vencimento_e_depois_a_cada_7(base, monkeypatch):  # noqa: F811
    """Venceu e o pagamento não foi reconhecido: 1ª cobrança 3 dias depois, e depois a cada 7 dias."""
    env = _cap(monkeypatch)
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "500", vencimento="2026-10-05", emitir_nfse=False)
    cobranca.preparar_pagamento(tid)
    dias = [d for d in range(1, 31) if cobranca.rodar_regua(date(2026, 10, d))["email"]]
    assert dias == [1, 2, 5, 8, 15, 22, 29]          # boleto, lembrete (-3), vence hoje, +3, +10, +17, +24
    assert "em aberto há 3 dia(s)" in env[3][1]


def test_mesmo_cliente_atrasado_so_e_cobrado_a_cada_7_dias(base, monkeypatch):  # noqa: F811
    """Caso real: título atrasado (venc. 10/09) e título novo (venc. 10/10). Os avisos do título no prazo (boleto,
    lembrete, vence hoje) não cobram o atrasado; o atrasado é cobrado uma vez por semana."""
    env = _cap(monkeypatch)
    velho = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "500", vencimento="2026-09-10", emitir_nfse=False)
    cobranca.preparar_pagamento(velho)
    cobranca.rodar_regua(date(2026, 9, 28))                     # cobrança do atrasado em 28/09
    novo = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "500", vencimento="2026-10-10", emitir_nfse=False)
    cobranca.preparar_pagamento(novo)
    env.clear()
    por_dia = {}
    for d in range(5, 27):
        n = len(env)
        cobranca.rodar_regua(date(2026, 10, d))
        if len(env) > n:
            por_dia[d] = env[-1]
    assert sorted(por_dia) == [5, 7, 10, 12, 19, 26]
    assert "2 títulos" in por_dia[5][1]                          # 05/10: boleto novo + a cobrança semanal do atrasado
    for d in (7, 10):                                           # lembrete e vence hoje: só o título no prazo
        assert "10/09/2026" not in por_dia[d][2] and "10/10/2026" in por_dia[d][1] + por_dia[d][2]
    datas_wa = sorted({e["data"] for e in db.linhas(
        "SELECT data FROM eventos_cobranca WHERE canal='whatsapp' AND data>='2026-10-05'")})
    assert datas_wa == ["2026-10-05", "2026-10-07", "2026-10-10", "2026-10-12", "2026-10-19", "2026-10-26"]


def test_aviso_de_suspensao_aos_90_dias(base, monkeypatch):  # noqa: F811
    env = _cap(monkeypatch)
    t1 = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "500", vencimento="2026-07-10", emitir_nfse=False)
    t2 = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "300", vencimento="2026-08-10", emitir_nfse=False)
    for t in (t1, t2):
        cobranca.preparar_pagamento(t)
    cobranca.rodar_regua(date(2026, 10, 7))                     # 89 dias: só a cobrança de atraso
    assert not [e for e in env if "suspensão" in e[1].lower()]
    env.clear()
    cobranca.rodar_regua(date(2026, 10, 8))                     # 90 dias: aviso de suspensão, uma vez
    avisos = [e for e in env if "suspensão" in e[1].lower()]
    assert len(avisos) == 1 and len(env) == 1                   # conta como a cobrança da semana
    assert "2 título(s)" in avisos[0][2] and "18/10/2026" in avisos[0][2]   # prazo de 10 dias
    for d in range(9, 31):
        cobranca.rodar_regua(date(2026, 10, d))
    assert len([e for e in env if "suspensão" in e[1].lower()]) == 1
    assert [e["etapa"] for e in cobranca.fila_whatsapp() if e["etapa"] == cobranca.ETAPA_SUSPENSAO]
