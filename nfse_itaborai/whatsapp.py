"""Envio automático de WhatsApp (opcional) por Z-API ou Evolution API.

- Z-API (z-api.io, serviço pago brasileiro): POST {base}/instances/{instancia}/token/{token}/send-text
  com cabeçalho Client-Token e corpo {"phone", "message"}.
- Evolution API (código aberto, hospedado por você): POST {url}/message/sendText/{instancia}
  com cabeçalho apikey e corpo {"number", "text"}.
Sem provedor configurado, o sistema usa o link wa.me (um clique por mensagem).
"""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request

from . import clientes, config

URL_ZAPI = "https://api.z-api.io"


def automatico(cfg: dict | None = None) -> bool:
    w = (cfg or config.carregar())["whatsapp"]
    if w["provedor"] == "zapi":
        return bool(w["zapi_instancia"] and w["zapi_token"])
    if w["provedor"] == "evolution":
        return bool(w["evolution_url"] and w["evolution_instancia"] and w["evolution_apikey"])
    return False


def numero(telefone: str) -> str:
    d = clientes._digitos(telefone)
    if not d:
        return ""
    return d if d.startswith("55") and len(d) >= 12 else "55" + d


def _post(url: str, corpo: dict, cabecalhos: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(corpo).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **cabecalhos})
    try:
        with urllib.request.urlopen(req, timeout=30, context=ssl.create_default_context()) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"WhatsApp: HTTP {e.code} {e.read().decode(errors='replace')[:200]}") from e


def enviar(telefone: str, texto: str, cfg: dict | None = None) -> dict:
    cfg = cfg or config.carregar()
    w = cfg["whatsapp"]
    fone = numero(telefone)
    if not fone:
        raise RuntimeError("Cliente sem telefone.")
    if w["provedor"] == "zapi":
        base = w.get("zapi_url") or URL_ZAPI
        cab = {"Client-Token": w["zapi_client_token"]} if w.get("zapi_client_token") else {}
        return _post(f"{base}/instances/{w['zapi_instancia']}/token/{w['zapi_token']}/send-text",
                     {"phone": fone, "message": texto}, cab)
    if w["provedor"] == "evolution":
        return _post(f"{w['evolution_url'].rstrip('/')}/message/sendText/{w['evolution_instancia']}",
                     {"number": fone, "text": texto}, {"apikey": w["evolution_apikey"]})
    raise RuntimeError("Envio automático de WhatsApp não configurado.")
