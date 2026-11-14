"""Confere tudo o que precisa estar no lugar antes de ligar o modo automático."""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import requests

from . import base as B
from . import fila, site
from . import whatsapp as W


def rodar(cfg: dict, pasta: str, ler_site=site.ler_site, api=None, imprimir=print) -> bool:
    """Imprime uma linha por item e devolve True quando nada impede o envio automático."""
    impeditivos = 0

    def item(ok: bool, texto: str, impede: bool = True) -> None:
        nonlocal impeditivos
        impeditivos += (not ok) and impede
        imprimir(f"[{'ok' if ok else 'FALTA' if impede else 'aviso'}] {texto}")

    e = cfg.get("escritorio", {})
    item(all(e.get(k) for k in ("nome", "cidade", "crc", "assinatura")), "dados do escritório (nome, cidade, CRC, assinatura)")
    leitura = ler_site(e.get("site", ""))
    item(leitura["vivo"], f"site do escritório abre: {e.get('site', '(vazio)')}")
    item(bool(cfg.get("regiao")), "região de busca definida")
    item(bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")),
         "credencial da Anthropic no ambiente (ANTHROPIC_API_KEY)")
    item(bool(os.environ.get("GOOGLE_MAPS_API_KEY")),
         "GOOGLE_MAPS_API_KEY — sem ela a busca automática não roda; use 'importar' com CSV", impede=False)
    item((Path(pasta) / "nichos.json").exists(), "nichos já definidos (senão o servidor define na 1ª rodada)", impede=False)

    token = cfg.get("painel", {}).get("token", "")
    item(len(token) >= 16 and not token.startswith("troque"), "painel.token com 16+ caracteres, trocado do exemplo")
    ev = cfg.get("evolution", {})
    item(all(ev.get(k) for k in ("url", "instancia", "apikey")) and not ev.get("apikey", "").startswith("SUA-"),
         "Evolution API configurada (url, instancia, apikey)")
    try:
        conectado = (api or W.Evolution(cfg)).conectado()
        item(conectado, "instância da Evolution conectada ao WhatsApp (estado 'open')")
    except (requests.RequestException, KeyError) as erro:
        item(False, f"Evolution API responde ({type(erro).__name__})")

    op = W.opcoes(cfg)
    item(op["teto_dia"] <= 30, f"teto diário de {op['teto_dia']} — acima de 30 primeiros contatos por dia o risco de bloqueio sobe muito", impede=False)
    base = B.Base(pasta)
    est = W.ler_estado(base)
    item(not est["pausado"], f"motor não está pausado{': ' + est['motivo'] if est['pausado'] else ''}", impede=False)
    aberta, motivo = fila.janela_aberta(cfg, datetime.now(fila.FUSO))
    item(aberta, f"janela comercial aberta agora{'' if aberta else ' (' + motivo + ') — o servidor espera sozinho'}", impede=False)
    prontos = sum(l["status"] == B.PRONTO for l in base.leads)
    imprimir(f"\n{len(base.leads)} empresa(s) na base, {prontos} com texto aprovado.")
    imprimir("Pode ligar: python -m prospeccao servidor" if not impeditivos else f"{impeditivos} item(ns) impedem o modo automático.")
    return not impeditivos
