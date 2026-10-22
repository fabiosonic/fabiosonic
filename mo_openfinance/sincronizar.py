"""
Orquestração: pedir extrato quando a janela permite, recolher protocolos prontos e tratar webhooks.

Webhooks tratados (o corpo vem do provedor; nada aqui confia nele além de ids e tipos):
  TecnoSpeed: STATEMENT_OPENFINANCE (conexão ativa), STATEMENT_OPENFINANCE_REVOKED (revogada),
              STATEMENT_OPENFINANCE_PROCESSED (protocolo pronto), transaction_deleted, transactions_updated
  Pluggy:     item/created, item/updated, item/error, transactions/created, transactions/deleted
"""
import hashlib
import json
from datetime import date, timedelta


def _chave_evento(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def solicitar_extratos(banco, provedor, pagadores, hoje=None, dias_retroativos=3, quando=None):
    """Para cada conta ativa da TecnoSpeed, gera protocolo se a janela de 6 h permitir.

    Pede sempre D-`dias_retroativos` até hoje: bancos como Bradesco/Itaú/Santander lançam com atraso, e a
    deduplicação por id garante que a sobreposição não duplica nada.
    """
    hoje = hoje or date.today()
    inicio, fim = (hoje - timedelta(days=dias_retroativos)).isoformat(), hoje.isoformat()
    gerados = []
    for c in banco.contas(status="ATIVA"):
        if c["provedor"] != provedor.nome:
            continue
        if not banco.pode_solicitar(c["conta"], c["tipo"], provedor.intervalo_protocolo_horas, quando):
            continue
        uid = provedor.gerar_protocolo(pagadores[c["empresa"]], c["conta"], inicio, fim, c["tipo"], c.get("cartao"))
        banco.registrar_protocolo(uid, c["conta"], c["tipo"], inicio, fim, quando)
        gerados.append(uid)
    return gerados


def recolher_protocolos(banco, provedor, pagadores):
    """Consulta protocolos em PROCESSING (fallback do webhook) e grava as transações novas."""
    resumo = {}
    empresa_da_conta = {c["conta"]: c["empresa"] for c in banco.contas()}
    for p in banco.protocolos_pendentes():
        status, motivo, novas = provedor.consultar_protocolo(pagadores[empresa_da_conta[p["conta"]]], p["unique_id"])
        if status in ("SUCCESS", "FAILED"):
            banco.atualizar_protocolo(p["unique_id"], status, motivo)
        resumo[p["unique_id"]] = (status, banco.gravar(novas))
    return resumo


def sincronizar_periodo(banco, provedor, pagador, conta, inicio, fim, tipo="BANK"):
    """Carga inicial/ressincronização pela listagem de transações (cursor na TecnoSpeed, páginas na Pluggy)."""
    return banco.gravar(provedor.transacoes(pagador, conta, inicio, fim, tipo))


def processar_webhook(banco, payload, provedor=None, pagadores=None):
    """Aplica um webhook. Devolve um texto curto do que foi feito (para log)."""
    if not banco.evento_novo(_chave_evento(payload), str(payload.get("event") or payload.get("type")), payload):
        return "evento repetido ignorado"

    evento = payload.get("event") or payload.get("type") or ""
    dados = payload.get("data") or payload

    if evento in ("transaction_deleted", "transactions/deleted"):
        ids = dados.get("transaction_ids") or dados.get("transactionIds") or []
        estornar = banco.marcar_excluidas(ids)
        return f"{len(ids)} transação(ões) excluída(s) na origem; {len(estornar)} já contabilizada(s) irão para estorno"

    if evento in ("transactions_updated", "transactions/created"):
        # o payload só traz ids; os dados completos vêm da consulta ao provedor
        return "ressincronizar conta/protocolo: " + str(dados.get("statement_id") or dados.get("accountId") or "")

    conta = dados.get("accountHash") or dados.get("account_hash") or dados.get("itemId")
    if evento in ("STATEMENT_OPENFINANCE", "item/created") and conta:
        banco.mudar_status_conta(conta, "ATIVA")
        return f"conta {conta} ativa"
    if evento in ("STATEMENT_OPENFINANCE_REVOKED", "item/error") and conta:
        banco.mudar_status_conta(conta, "INATIVA")
        return f"conta {conta} sem consentimento: pedir nova autorização ao cliente"
    if evento == "STATEMENT_OPENFINANCE_PROCESSED" and provedor and pagadores:
        return str(recolher_protocolos(banco, provedor, pagadores))
    return f"evento {evento!r} registrado sem ação"
