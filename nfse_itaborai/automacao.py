"""Robô financeiro: rotina idempotente que pode rodar a cada hora (tela aberta) e 1x/dia (Agendador do Windows).

Ordem: backup → despesas recorrentes → títulos do mês (contratos) → NFS-e → cobrança (PIX/Asaas)
       → baixa automática (Asaas) → régua de cobrança.
Cada etapa é isolada: uma falha não impede as demais e fica registrada no log.
"""

from __future__ import annotations

import threading
import time
from datetime import date

from . import cobranca, config, db, emissor, financeiro


def rodar(em: date | None = None, forcar: bool = False, url: str | None = None) -> dict:
    em = em or financeiro.hoje()
    cfg = config.carregar()
    auto = cfg["automacao"]
    if not auto["ativa"] and not forcar:
        return {"executado": False, "motivo": "Automação desligada (Configurações > Robô)."}
    res: dict = {"executado": True, "data": em.isoformat()}

    def etapa(nome, ligado, func):
        if not ligado:
            return
        try:
            res[nome] = func()
        except Exception as ex:  # noqa: BLE001 — o robô nunca para por causa de uma etapa
            res[nome] = f"erro: {ex}"
            db.registrar("robo_erro", f"{nome}: {ex}")

    etapa("backup", auto["backup"], lambda: str(db.backup()))
    etapa("despesas_recorrentes", auto["despesas_recorrentes"], lambda: financeiro.gerar_despesas_recorrentes(em))
    etapa("titulos_gerados", auto["gerar_titulos"] and em.day >= int(cfg["financeiro"]["dia_geracao"]),
          lambda: len(financeiro.gerar_titulos(em=em)))

    def nfse():
        if not emissor.em_producao():
            return "ambiente de homologação: o robô só emite NFS-e em produção"
        ok = erro = 0
        for t in financeiro.listar_titulos("sem_nfse", em=em):
            if t["nfse_status"] not in ("pendente", "teste") or t["status"] != "aberto":
                continue                      # erros ficam para revisão humana, sem reenvio infinito
            r = financeiro.emitir_nfse_titulo(t["id"], url=url)
            ok, erro = ok + bool(r["sucesso"]), erro + (not r["sucesso"])
        return {"emitidas": ok, "erros": erro}
    etapa("nfse", auto["emitir_nfse"], nfse)

    def cobrancas():
        n = 0
        for t in db.linhas("SELECT * FROM titulos WHERE status='aberto' AND pix_copia_cola='' AND asaas_id=''"):
            if t["nfse_status"] in ("pendente", "erro", "teste"):
                continue                      # cobra junto com a nota válida
            financeiro_t = cobranca.preparar_pagamento(t["id"], cfg)
            n += bool(financeiro_t["pix_copia_cola"] or financeiro_t["asaas_id"])
        return n
    etapa("cobrancas_criadas", auto["criar_cobranca"] and cfg["cobranca"]["provedor"] != "nenhum", cobrancas)
    etapa("baixas_asaas", auto["sincronizar_asaas"] and cfg["cobranca"]["provedor"] == "asaas",
          lambda: cobranca.sincronizar_asaas(cfg))
    etapa("regua", auto["regua"], lambda: cobranca.rodar_regua(em, cfg))
    db.registrar("robo", f"Rotina executada: { {k: v for k, v in res.items() if k not in ('executado', 'data')} }")
    return res


_thread: threading.Thread | None = None


def iniciar_em_segundo_plano(intervalo_min: int = 60) -> None:
    """Enquanto a tela estiver aberta, roda a rotina ao abrir e depois a cada hora."""
    global _thread
    if _thread and _thread.is_alive():
        return

    def laco():
        while True:
            try:
                rodar()
            except Exception as ex:  # noqa: BLE001
                db.registrar("robo_erro", str(ex))
            time.sleep(intervalo_min * 60)

    _thread = threading.Thread(target=laco, daemon=True, name="robo-financeiro")
    _thread.start()
