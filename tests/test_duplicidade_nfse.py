"""Nota em duplicidade: resposta perdida não é reenviada sozinha; nota já emitida pode ser informada no título."""

from nfse_itaborai import automacao, financeiro, lote
from nfse_itaborai.tela import tratar
from test_emissor import ambiente  # noqa: F401  (fixture)
from test_financeiro import CLI_A, base  # noqa: F401  (fixture)


def _pendente():
    return financeiro.criar_titulo(CLI_A["cpf_cnpj"], "1100", vencimento="2026-10-30", emitir_nfse=True,
                                   apos_pagamento=False)


def _falha(monkeypatch, msg):
    monkeypatch.setattr(lote, "emitir_um", lambda *a, **k: {"sucesso": False, "erros": [msg]})


def test_sem_resposta_depois_do_envio_nao_reemite_sozinho(base, monkeypatch):  # noqa: F811
    tid = _pendente()
    _falha(monkeypatch, "Falha de comunicação: The read operation timed out")
    financeiro.emitir_nfse_titulo(tid)
    t = financeiro.obter_titulo(tid)
    assert t["nfse_status"] == "emitindo" and "confira no portal" in t["nfse_erro"]
    chamadas = []
    monkeypatch.setattr(lote, "emitir_um", lambda *a, **k: chamadas.append(1) or {"sucesso": True, "nfse": "9"})
    assert financeiro.emitir_nfse_titulo(tid)["sucesso"] is False        # reservado: não emite outra
    automacao.rodar(forcar=True)
    assert not chamadas                                                   # o robô também não


def test_servidor_fora_do_ar_antes_do_envio_continua_pendente(base, monkeypatch):  # noqa: F811
    tid = _pendente()
    _falha(monkeypatch, "Falha de comunicação: [Errno 111] Connection refused")
    financeiro.emitir_nfse_titulo(tid)
    assert financeiro.obter_titulo(tid)["nfse_status"] == "pendente"      # nada chegou: o robô tenta de novo


def test_informar_nota_ja_emitida_impede_nova_emissao(base, monkeypatch):  # noqa: F811
    tid = _pendente()
    _falha(monkeypatch, "Falha de comunicação: timed out")
    financeiro.emitir_nfse_titulo(tid)
    r = tratar("titulo/informar_nfse", {"id": tid, "numero": "99003894", "data": "2026-10-06"})
    assert r["ok"] and financeiro.obter_titulo(tid)["nfse_numero"] == "99003894"
    assert "já tem a NFS-e" in tratar("titulo/forcar_nfse", {"id": tid})["erro"]
    outro = _pendente()
    assert "já está ligada ao título" in tratar("titulo/informar_nfse", {"id": outro, "numero": "99003894"})["erro"]
    assert "número" in tratar("titulo/informar_nfse", {"id": outro, "numero": ""})["erro"]


def _emitido(comp, venc, data, numero, desc="HONORARIOS CONTABEIS MENSAIS", valor="1100"):
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], valor, desc, vencimento=venc, competencia=comp, emitir_nfse=False)
    financeiro.atualizar_titulo(tid, nfse_status="emitida", nfse_numero=numero, nfse_data=data)
    return tid


def test_caso_ngrm_segunda_nota_do_mesmo_valor_pergunta_antes(base, monkeypatch):  # noqa: F811
    """Setembro e outubro de R$ 1.100: a nota de outubro saiu; a de setembro, no mesmo dia, é parada e perguntada."""
    monkeypatch.setattr(financeiro, "hoje", lambda: __import__("datetime").date(2026, 10, 6))
    _emitido("2026-10", "2026-10-30", "2026-10-06", "99003894")
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "1100", "HONORARIOS CONTABEIS MENSAIS", vencimento="2026-10-10",
                                  competencia="2026-09", emitir_nfse=True, apos_pagamento=True)
    r = financeiro.baixar(tid, "2026-10-06", "1100")              # baixa automática: não emite, para e avisa
    t = financeiro.obter_titulo(tid)
    assert t["nfse_status"] == "duplicidade" and "99003894" in t["nfse_erro"] and "duplicidade" in r["nfse_resultado"].lower()
    emitidas = []
    monkeypatch.setattr(lote, "emitir_um", lambda *a, **k: emitidas.append(1) or {"sucesso": True, "nfse": "99003895",
                                                                                   "canal": "municipal"})
    automacao.rodar(forcar=True)
    assert not emitidas                                            # o robô não emite: espera a confirmação
    r = tratar("titulo/forcar_nfse", {"id": tid})                  # sem confirmar: pergunta de novo
    assert r["duplicidade"][0]["nfse"] == "99003894" and not emitidas
    r = tratar("titulo/forcar_nfse", {"id": tid, "confirmar_duplicidade": True})
    assert r["sucesso"] and emitidas == [1]


def test_mensalidade_normal_13o_e_servico_extra_nao_perguntam(base, monkeypatch):  # noqa: F811
    monkeypatch.setattr(financeiro, "hoje", lambda: __import__("datetime").date(2026, 10, 6))
    _emitido("2026-09", "2026-09-05", "2026-09-05", "1")              # mês passado, mesmo valor: normal
    _emitido("2026-10", "2026-10-05", "2026-10-02", "2", desc="13 HONORARIO")   # outro serviço na mesma competência
    t = {"id": 0, "cpf_cnpj": CLI_A["cpf_cnpj"], "competencia": "2026-10", "valor_cent": 110000, "nota_cent": 0,
         "descricao": "Honorários contábeis mensais."}
    assert financeiro.notas_parecidas(t) == []
    _emitido("2026-10", "2026-10-05", "2026-09-28", "3", valor="900")   # mesma competência e serviço: pergunta
    assert [d["nfse"] for d in financeiro.notas_parecidas(t)] == ["3"]


def test_emissao_avulsa_devolve_a_duplicidade_para_a_tela(base, monkeypatch):  # noqa: F811
    monkeypatch.setattr(financeiro, "hoje", lambda: __import__("datetime").date(2026, 10, 6))
    from nfse_itaborai import config
    config.salvar({"emissao": {"nfse_quando": "geracao"}})
    _emitido("2026-10", "2026-10-30", "2026-10-06", "77", desc="Consultoria")
    r = tratar("emitir", {"cpf_cnpj": CLI_A["cpf_cnpj"], "valor": "1100", "descricao": "Consultoria", "cobrar": False})
    assert not r["sucesso"] and r["duplicidade"][0]["nfse"] == "77" and r["titulo_id"]
    assert financeiro.obter_titulo(r["titulo_id"])["nfse_status"] == "duplicidade"
    assert tratar("titulo/cancelar", {"id": r["titulo_id"], "motivo": "Nota em duplicidade — não emitida"})
    assert financeiro.obter_titulo(r["titulo_id"])["status"] == "cancelado"
