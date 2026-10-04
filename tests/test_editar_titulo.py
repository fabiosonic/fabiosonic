"""Editar título em aberto: valor/vencimento mudam e o boleto é refeito (antigo cancelado no Inter, novo registrado);
recorrência alterada pode levar o novo valor aos títulos em aberto já gerados."""

from datetime import date

import pytest

from nfse_itaborai import cobranca, config, db, financeiro, inter
from nfse_itaborai.tela import tratar
from test_emissor import ambiente  # noqa: F401  (fixture)
from test_financeiro import CLI_A, base  # noqa: F401  (fixture)


@pytest.fixture
def banco(monkeypatch, tmp_path):
    """Inter simulado: registra o que foi criado e cancelado."""
    reg = {"criados": [], "cancelados": []}
    config.salvar({"cobranca": {"provedor": "inter"}})
    monkeypatch.setattr(inter, "configurado", lambda cfg=None: True)

    def criar(t, cfg=None, espera=0, atualizado=None):
        reg["criados"].append((t["id"], (atualizado or t)["valor_cent"], (atualizado or t)["vencimento"]))
        n = len(reg["criados"])
        return {"banco_id": f"cod-{n}", "linha_digitavel": f"0779{n}", "pix_copia_cola": f"000201{n}", "nosso_numero": str(n)}
    monkeypatch.setattr(inter, "criar_cobranca", criar)
    monkeypatch.setattr(inter, "cancelar", lambda codigo, motivo="", cfg=None: reg["cancelados"].append((codigo, motivo)))
    pdf = tmp_path / "antigo.pdf"
    pdf.write_bytes(b"%PDF antigo")
    monkeypatch.setattr(cobranca, "salvar_boleto", lambda tid, cfg=None, refazer=False: str(pdf))
    reg["pdf"] = pdf
    return reg


def test_editar_valor_refaz_o_boleto_no_inter(base, banco):  # noqa: F811
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "10400", "HONORARIOS", vencimento="2026-10-20", competencia="2026-10",
                                  emitir_nfse=True, apos_pagamento=True)
    cobranca.preparar_pagamento(tid)
    financeiro.atualizar_titulo(tid, boleto_pdf=str(banco["pdf"]))
    t = financeiro.obter_titulo(tid)
    assert t["banco_id"] == "cod-1" and banco["criados"] == [(tid, 1040000, "2026-10-20")]
    r = tratar("titulo/editar", {"id": tid, "valor": "4.000,00", "vencimento": "2026-10-20", "competencia": "2026-10", "descricao": "HONORARIOS"})
    assert r["mudou"] == ["valor_cent"] and r["refazer"] and r["boleto_refeito"]
    t = financeiro.obter_titulo(tid)
    assert t["valor_cent"] == 400000 and t["banco_id"] == "cod-2" and t["linha_digitavel"] == "07792" and t["nosso_numero"] == "2"
    assert banco["cancelados"] == [("cod-1", "Titulo alterado")] and banco["criados"][-1] == (tid, 400000, "2026-10-20")
    assert not banco["pdf"].exists() and t["boleto_pdf"] == ""     # o PDF antigo foi apagado (o novo é baixado pelo salvar_boleto)
    assert "editado" in db.linhas("SELECT mensagem FROM log WHERE tipo='titulo' ORDER BY id DESC")[0]["mensagem"]
    # só a descrição: nada no banco
    r = tratar("titulo/editar", {"id": tid, "valor": "4.000,00", "vencimento": "2026-10-20", "descricao": "HONORARIOS OUTUBRO"})
    assert r["mudou"] == ["descricao"] and not r["refazer"] and len(banco["cancelados"]) == 1
    # nada mudou
    assert tratar("titulo/editar", {"id": tid, "valor": "4000,00"})["mudou"] == []


def test_regras_da_edicao(base, banco):  # noqa: F811
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "300", vencimento="2026-10-20", competencia="2026-10", emitir_nfse=True)
    financeiro.atualizar_titulo(tid, nfse_status="emitida", nfse_numero="123")
    with pytest.raises(ValueError, match="já foi emitida"):
        financeiro.editar_titulo(tid, valor="250")
    with pytest.raises(ValueError, match="competência"):
        financeiro.editar_titulo(tid, competencia="2026-11")
    r = financeiro.editar_titulo(tid, vencimento="2026-10-25")              # vencimento pode mudar mesmo com nota
    assert r["mudou"] == ["vencimento"] and r["refazer"]
    with pytest.raises(ValueError, match="inválido"):
        financeiro.editar_titulo(tid, vencimento="25/10/2026")
    with pytest.raises(ValueError, match="maior que zero"):
        financeiro.editar_titulo(tid, valor="0")
    financeiro.baixar(tid, "2026-10-21", "300", "pix")
    with pytest.raises(ValueError, match="em aberto"):
        financeiro.editar_titulo(tid, valor="250")
    # cobrança dispensada (PIX do escritório) continua sem boleto depois de editar
    d = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "500", vencimento="2026-07-10", emitir_nfse=True, apos_pagamento=True)
    financeiro.atualizar_titulo(d, boleto_situacao="dispensado")
    r = tratar("titulo/editar", {"id": d, "valor": "450"})
    t = financeiro.obter_titulo(d)
    assert t["valor_cent"] == 45000 and t["boleto_situacao"] == "dispensado" and not t["banco_id"] and not r["boleto_refeito"]
    assert banco["criados"] == []


def test_recorrencia_alterada_aplica_aos_titulos_em_aberto(base, banco, monkeypatch):  # noqa: F811
    monkeypatch.setattr(financeiro, "hoje", lambda: date(2026, 10, 4))
    k = financeiro.salvar_contrato({"cpf_cnpj": CLI_A["cpf_cnpj"], "valor": "10400", "dia_vencimento": 20, "inicio": "2026-10",
                                    "descricao": "HONORARIOS CONTABEIS MENSAIS"})
    with db.conexao() as con:
        con.execute("UPDATE contratos SET confirmado=1")
    monkeypatch.setattr(financeiro, "emitir_nfse_titulo", lambda tid, url=None: {"sucesso": True, "erros": [], "titulo": financeiro.obter_titulo(tid)})
    [tid] = financeiro.gerar_titulos("2026-10", date(2026, 10, 4))
    cobranca.preparar_pagamento(tid)
    antigo = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "10400", vencimento="2026-09-20", competencia="2026-09", emitir_nfse=False)
    financeiro.atualizar_titulo(antigo, contrato_id=k["id"])
    assert financeiro.obter_titulo(tid)["banco_id"] == "cod-1"
    # salvar pela aba Recorrência com o novo valor e "aplicar aos abertos"
    r = financeiro.salvar_recorrencia([{"id": k["id"], "cpf_cnpj": CLI_A["cpf_cnpj"], "valor_cent": 400000, "dia_vencimento": 20,
                                        "repetir": True, "servico_id": "", "nfse_quando": "", "cobrar": True}], aplicar_abertos=True)
    assert r["salvos"] == 1 and r["titulos_ajustados"] == [tid]                 # só deste mês em diante
    t = financeiro.obter_titulo(tid)
    assert t["valor_cent"] == 400000 and t["banco_id"] == "cod-2" and banco["cancelados"] == [("cod-1", "Valor da recorrencia alterado")]
    assert financeiro.obter_titulo(antigo)["valor_cent"] == 1040000             # competência passada não muda
    assert financeiro.titulos_abertos_do_contrato(k["id"]) == []
    assert tratar("contrato/abertos", {"id": k["id"]})["titulos"] == []
    # sem o 'aplicar', os títulos ficam como estão (e a tela oferece depois)
    financeiro.salvar_recorrencia([{"id": k["id"], "cpf_cnpj": CLI_A["cpf_cnpj"], "valor_cent": 350000, "dia_vencimento": 20, "repetir": True}])
    assert financeiro.obter_titulo(tid)["valor_cent"] == 400000
    assert [x["id"] for x in tratar("contrato/abertos", {"id": k["id"]})["titulos"]] == [tid]
    assert tratar("contrato/aplicar_abertos", {"id": k["id"]}) == {"titulos": [tid], "boletos": 1}
    assert financeiro.obter_titulo(tid)["valor_cent"] == 350000 and financeiro.obter_titulo(tid)["banco_id"] == "cod-3"
