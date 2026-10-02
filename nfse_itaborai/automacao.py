"""Robô financeiro: rotina idempotente que pode rodar a cada hora (tela aberta) e 1x/dia (Agendador do Windows).

Ordem: backup → XML (clientes, notas externas, contratos detectados) → contatos pela Receita
       → despesas recorrentes → títulos do mês (contratos) → NFS-e → cobrança (PIX/Asaas)
       → baixa automática (Asaas) → extratos OFX da pasta → régua de cobrança → resumo diário por e-mail.
Cada etapa é isolada: uma falha não impede as demais e fica registrada no log.
"""

from __future__ import annotations

import contextlib
import os
import threading
import time
from datetime import date

from . import cobranca, config, db, emissor, financeiro, importacao


TRAVA_MAX_SEG = 2 * 3600


@contextlib.contextmanager
def _trava():
    """Só um robô por vez (tela aberta + Agendador do Windows podem coincidir)."""
    arq = db.caminho().parent / "robo.lock"
    arq.parent.mkdir(parents=True, exist_ok=True)
    if arq.exists() and time.time() - arq.stat().st_mtime > TRAVA_MAX_SEG:
        arq.unlink(missing_ok=True)                    # trava abandonada (queda de energia etc.)
    try:
        fd = os.open(arq, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        yield False
        return
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        yield True
    finally:
        arq.unlink(missing_ok=True)


def rodar(em: date | None = None, forcar: bool = False, url: str | None = None) -> dict:
    with _trava() as livre:
        if not livre:
            return {"executado": False, "motivo": "Outra execução do robô está em andamento."}
        return _rodar(em, forcar, url)


def _rodar(em: date | None = None, forcar: bool = False, url: str | None = None) -> dict:
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
    etapa("importacao_xml", auto.get("importar_xml"), lambda: importacao.importar_xml(em))
    etapa("contatos_completados", auto.get("enriquecer_contatos"), importacao.enriquecer_contatos)
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
    etapa("boletos_pdf", auto.get("baixar_boletos", True) and cfg["cobranca"]["provedor"] == "asaas",
          lambda: cobranca.baixar_boletos(cfg=cfg))
    etapa("extratos", auto.get("importar_extratos"), importacao.importar_extratos)
    etapa("regua", auto["regua"], lambda: cobranca.rodar_regua(em, cfg))
    etapa("resumo", auto.get("resumo_diario"), lambda: importacao.resumo_diario(res, em))
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
