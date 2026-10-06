"""Botão "Emitir NFS-e" (forçar emissão) no Contas a receber."""

from nfse_itaborai import financeiro
from nfse_itaborai.tela import tratar
from test_emissor import ambiente  # noqa: F401  (fixture)
from test_financeiro import CLI_A, base  # noqa: F401  (fixture)


def _titulo(**k):
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "1000", vencimento="2026-10-10", emitir_nfse=False)
    financeiro.atualizar_titulo(tid, **k)
    return tid


def test_pago_sem_nfse_emite_ao_forcar_e_nao_emite_duas_vezes(base):  # noqa: F811
    """Caso da tela: título pago (R$ 1.000,00) marcado "Sem NFS-e"."""
    tid = _titulo(nfse_status="nao_emitir")
    financeiro.baixar(tid, "2026-09-30", "1000")
    r = tratar("titulo/forcar_nfse", {"id": tid})
    assert r["sucesso"] and r["anterior"] == "nao_emitir", r
    t = financeiro.obter_titulo(tid)
    assert t["nfse_status"] == "emitida" and t["nfse_numero"] and t["status"] == "pago"
    assert "já tem a NFS-e" in tratar("titulo/forcar_nfse", {"id": tid})["erro"]


def test_apos_pagamento_e_erro_tambem_emitem(base):  # noqa: F811
    for sit in ("apos_pagamento", "erro"):
        tid = _titulo(nfse_status=sit, nfse_erro="E999 falha" if sit == "erro" else "")
        r = tratar("titulo/forcar_nfse", {"id": tid})
        assert r["sucesso"] and financeiro.obter_titulo(tid)["nfse_erro"] == ""


def test_travado_em_emissao_exige_conferir_no_portal(base):  # noqa: F811
    tid = _titulo(nfse_status="emitindo")
    assert "Confira no portal" in tratar("titulo/forcar_nfse", {"id": tid})["erro"]
    assert financeiro.obter_titulo(tid)["nfse_status"] == "emitindo"          # nada mudou
    assert tratar("titulo/forcar_nfse", {"id": tid, "conferido_portal": True})["sucesso"]


def test_cancelado_nao_emite(base):  # noqa: F811
    tid = _titulo(nfse_status="nao_emitir")
    financeiro.cancelar_titulo(tid, "teste")
    assert "cancelado" in tratar("titulo/forcar_nfse", {"id": tid})["erro"]
