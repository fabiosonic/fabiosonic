"""Cobrança jurídica: ENVIAR PARA O JURÍDICO suspende a cobrança na hora (e-mail, WhatsApp, régua, robô); o valor
continua registrado na aba 'Jurídico' do contas a receber, com multa e juros, e a baixa funciona normalmente."""

from datetime import date

import pytest

from nfse_itaborai import automacao, cobranca, db, financeiro, relatorios, whatsapp_web
from nfse_itaborai.tela import tratar
from test_emissor import ambiente  # noqa: F401  (fixture)
from test_financeiro import CLI_A, CLI_B, base  # noqa: F401  (fixture)


def _titulos():
    ids = [financeiro.criar_titulo(CLI_A["cpf_cnpj"], v, vencimento=d, emitir_nfse=True, apos_pagamento=True)
           for v, d in (("400", "2026-07-10"), ("500", "2026-08-10"), ("600", "2026-10-20"))]
    for tid in ids:
        financeiro.atualizar_titulo(tid, banco_id=f"inter-{tid}", linha_digitavel=f"0779{tid}", pix_copia_cola=f"000201pix{tid}")
    outro = financeiro.criar_titulo(CLI_B["cpf_cnpj"], "300", vencimento="2026-07-10", emitir_nfse=False)
    financeiro.atualizar_titulo(outro, pix_copia_cola="000201outro")
    return ids, outro


def test_enviar_para_o_juridico_suspende_a_cobranca_na_hora(base, monkeypatch):  # noqa: F811
    env = []
    monkeypatch.setattr(cobranca, "enviar_email", lambda para, *a, **k: env.append(para))
    ids, outro = _titulos()
    cobranca.rodar_regua(date(2026, 10, 1))                                # régua já deixou WhatsApp pendente
    assert len(cobranca.fila_whatsapp()) == 3 and env == [CLI_A["email"]]
    env.clear()
    r = tratar("titulo/juridico", {"id": ids[0], "obs": "Dr. Silva — processo 0001", "todos": True})
    assert r["titulos"] == 3 and r["suspensos"] == 3 and sorted(r["ids"]) == sorted(ids)
    assert cobranca.fila_whatsapp() == []                                  # mensagens pendentes suspensas
    assert {e["status"] for e in db.linhas("SELECT status FROM eventos_cobranca WHERE canal='whatsapp' AND titulo_id IN (?,?,?)", tuple(ids))} == {"suspenso"}
    for tid in ids:
        t = financeiro.enriquecer(financeiro.obter_titulo(tid), date(2026, 10, 1))
        assert t["situacao"] == "juridico" and t["juridico_em"] == financeiro.hoje().isoformat() and t["juridico_obs"].startswith("Dr. Silva")
        assert financeiro.tem_cobranca(t) and t["total_cent"] >= t["valor_cent"]      # continua devido, com encargos
    # régua, recorrente e robô: nada mais sai para esses títulos; o outro cliente segue normal
    cobranca.rodar_regua(date(2026, 10, 15))
    assert all(x["titulo_id"] == outro for x in db.linhas(
        "SELECT titulo_id FROM eventos_cobranca WHERE data='2026-10-15'")) and len(env) <= 1
    assert cobranca.todos_do_cliente(CLI_A["cpf_cnpj"], []) == []
    assert ids[0] not in [t["id"] for t in db.linhas("SELECT id FROM titulos WHERE " + financeiro.SQL_COBRADO)]
    with pytest.raises(ValueError, match="jurídico"):
        cobranca.cobrar_agora(ids[0])
    assert whatsapp_web.enviar_fila()["pendentes"] == 0


def test_aba_juridico_painel_e_baixa(base, monkeypatch):  # noqa: F811
    monkeypatch.setattr(cobranca, "enviar_email", lambda *a, **k: None)
    monkeypatch.setattr(financeiro, "hoje", lambda: date(2026, 10, 1))
    ids, outro = _titulos()
    tratar("titulo/juridico", {"id": ids[1], "obs": "", "todos": False})   # só um título
    lst = {f: [t["id"] for t in financeiro.listar_titulos(f, em=date(2026, 10, 1))]
           for f in ("juridico", "a_receber", "atrasado", "todos")}
    assert lst["juridico"] == [ids[1]] and ids[1] not in lst["a_receber"] and ids[1] not in lst["atrasado"]
    assert sorted(lst["todos"]) == sorted(ids + [outro])
    p = relatorios.painel(date(2026, 10, 1))
    assert p["juridico_qtd"] == 1 and p["clientes_juridico"] == 1 and p["juridico"] > 50000
    assert p["atrasado_qtd"] == 2 and p["inadimplencia_pct"] > 0           # jurídico fora do 'em atraso', dentro da inadimplência
    # robô não gera boleto para quem está no jurídico
    financeiro.atualizar_titulo(ids[1], banco_id="", linha_digitavel="", pix_copia_cola="")
    gerados = []
    monkeypatch.setattr(cobranca, "preparar_pagamento", lambda tid, cfg=None: gerados.append(tid) or financeiro.obter_titulo(tid))
    automacao.rodar(date(2026, 10, 1), forcar=True)
    assert ids[1] not in gerados
    # voltar do jurídico: retoma a cobrança
    tratar("titulo/juridico_voltar", {"id": ids[1]})
    t = financeiro.enriquecer(financeiro.obter_titulo(ids[1]), date(2026, 10, 1))
    assert t["situacao"] == "atrasado" and t["juridico_em"] == "" and t["juridico_obs"] == ""
    with pytest.raises(ValueError, match="não está no jurídico"):
        financeiro.voltar_do_juridico(ids[1])
    # baixa de um título no jurídico: funciona e a nota (após o pagamento) sai pelo valor pago
    tratar("titulo/juridico", {"id": ids[0], "obs": "acordo", "todos": False})
    emitidas = []
    monkeypatch.setattr(financeiro, "emitir_nfse_titulo", lambda tid, url=None: emitidas.append(tid) or
                        {"sucesso": True, "erros": [], "titulo": financeiro.obter_titulo(tid)})
    from nfse_itaborai import emissor
    monkeypatch.setattr(emissor, "em_producao", lambda: True)
    financeiro.baixar(ids[0], "2026-10-01", "450", "pix")
    assert financeiro.obter_titulo(ids[0])["status"] == "pago" and emitidas == [ids[0]]
    with pytest.raises(ValueError, match="em aberto"):
        financeiro.enviar_juridico(ids[0])
