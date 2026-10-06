"""Pagamento estornado (cliente pagou o boleto errado): a NFS-e volta a aguardar o pagamento."""

from datetime import date

from nfse_itaborai import config, db, financeiro
from nfse_itaborai.tela import tratar
from test_emissor import ambiente  # noqa: F401  (fixture)
from test_financeiro import CLI_A, base  # noqa: F401  (fixture)


def _apos_pagamento():
    config.salvar({"emissao": {"nfse_quando": "baixa"}})
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "1100", vencimento="2026-10-30", emitir_nfse=True,
                                  apos_pagamento=True)
    assert financeiro.obter_titulo(tid)["nfse_status"] == "apos_pagamento"
    return tid


def test_estorno_devolve_a_nota_para_apos_o_pagamento(base, monkeypatch):  # noqa: F811
    tid = _apos_pagamento()
    monkeypatch.setattr(financeiro, "emitir_nfse_titulo", lambda *a, **k: {"sucesso": False, "erros": ["fora do ar"],
                                                                            "titulo": financeiro.obter_titulo(tid)})
    financeiro.baixar(tid, "2026-10-07", "1100")                  # baixa: a nota fica pendente (prefeitura fora)
    assert financeiro.obter_titulo(tid)["nfse_status"] == "pendente"
    tratar("titulo/estornar", {"id": tid})                        # pagou o boleto errado: estorno
    t = financeiro.obter_titulo(tid)
    assert t["status"] == "aberto" and t["nfse_status"] == "apos_pagamento"
    # o robô não emite nota de título em aberto que aguarda o pagamento
    assert t["id"] not in [x["id"] for x in financeiro.listar_titulos("sem_nfse")
                           if x["status"] == "aberto" and x["nfse_status"] in ("pendente", "teste")]


def test_estorno_com_regra_na_geracao_e_nota_emitida_nao_mudam(base):  # noqa: F811
    config.salvar({"emissao": {"nfse_quando": "geracao"}})
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "500", vencimento="2026-10-30", emitir_nfse=True)
    financeiro.baixar(tid, "2026-10-07", "500")
    financeiro.atualizar_titulo(tid, nfse_status="pendente", nfse_numero="")
    financeiro.estornar(tid)
    assert financeiro.obter_titulo(tid)["nfse_status"] == "pendente"         # regra geral: emite na geração
    financeiro.atualizar_titulo(tid, nfse_status="emitida", nfse_numero="123")
    financeiro.baixar(tid, "2026-10-07", "500")
    financeiro.estornar(tid)
    assert financeiro.obter_titulo(tid)["nfse_status"] == "emitida"


def test_correcao_unica_dos_titulos_ja_estornados(base):  # noqa: F811
    tid = _apos_pagamento()
    outro = _apos_pagamento()
    with db.conexao() as con:                                     # situação antiga: estornado e "pendente"
        con.execute("UPDATE titulos SET nfse_status='pendente' WHERE id IN (?,?)", (tid, outro))
        con.execute("INSERT INTO log (quando, tipo, mensagem) VALUES (?,?,?)",
                    ("2026-10-07 10:00:00", "baixa", f"Título {tid} (RPS) pago R$ 1.100,00 via boleto"))
        db._corrigir_estornados(con)
    assert financeiro.obter_titulo(tid)["nfse_status"] == "apos_pagamento"
    assert financeiro.obter_titulo(outro)["nfse_status"] == "pendente"      # nunca baixado: não mexe
