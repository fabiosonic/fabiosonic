"""Atualização do sistema: o robô é parado num ponto seguro e uma trava abandonada não segura a atualização."""

import os
import threading
import time
from datetime import date

from nfse_itaborai import atualizacao, automacao, db, emissor, parada
from test_empresas import multi  # noqa: F401  (fixture)


def test_pedido_de_parada_faz_o_robo_nao_comecar_e_parar_entre_etapas(multi, monkeypatch):  # noqa: F811
    parada.pedir()
    r = automacao.rodar_todas(date(2026, 10, 8), forcar=True)
    assert all(not v["executado"] for v in r.values())
    parada.liberar()
    assert not parada.pedida()
    # pedido no meio da rodada: a etapa seguinte não roda
    feitas = []
    real = automacao.financeiro.gerar_despesas_recorrentes
    def despesas(em):
        feitas.append("despesas"); parada.pedir(); return real(em)
    monkeypatch.setattr(automacao.financeiro, "gerar_despesas_recorrentes", despesas)
    monkeypatch.setattr(automacao.financeiro, "gerar_titulos", lambda **k: feitas.append("titulos") or [])
    r = automacao.rodar_todas(date(2026, 10, 8), forcar=True)
    assert feitas == ["despesas"] and "parado" in str(r)
    parada.liberar()


def test_trava_de_processo_morto_e_ignorada_e_robo_vivo_e_esperado(multi, monkeypatch):  # noqa: F811
    trava = emissor.raiz() / "dados" / "robo.lock"
    trava.parent.mkdir(parents=True, exist_ok=True)
    trava.write_text("999999999", encoding="utf-8")            # processo que não existe
    assert not atualizacao._robo_rodando() and not trava.exists()
    trava.write_text(str(os.getpid()), encoding="utf-8")       # robô vivo: solta a trava em 1 s
    threading.Timer(1.0, lambda: trava.unlink()).start()
    t0 = time.time()
    assert atualizacao.parar_robo(espera_seg=10) and 0.8 < time.time() - t0 < 8
    assert parada.pedida()
    trava.write_text(str(os.getpid()), encoding="utf-8")       # não solta: desiste e não atualiza
    assert not atualizacao.parar_robo(espera_seg=2)
    trava.unlink()
    parada.liberar()


def test_processo_com_versao_antiga_na_memoria_se_reabre(monkeypatch):
    from nfse_itaborai import tela
    chamadas = []
    monkeypatch.setattr(atualizacao, "versao_no_disco", lambda: "99.0.0")
    monkeypatch.setattr(atualizacao, "reiniciar", lambda espera=1.0: chamadas.append(espera))
    monkeypatch.setattr(atualizacao, "_reiniciando", threading.Event())
    monkeypatch.setattr(atualizacao.db if hasattr(atualizacao, "db") else db, "registrar", lambda *a: None)
    r = tela.tratar("despesa/estornar", {"id": 1})
    assert r["reabrindo"] and "99.0.0" in r["erro"] and chamadas == [2.0]
    tela.tratar("despesas", {})
    assert chamadas == [2.0]                                  # uma reabertura só
