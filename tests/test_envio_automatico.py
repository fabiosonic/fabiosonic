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
