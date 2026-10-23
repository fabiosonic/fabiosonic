"""Etapa 9: publicação no YouTube (sem CTA) e no Instagram Reels (com CTA)."""
from __future__ import annotations

import time
from pathlib import Path

import requests

from . import config


def youtube(cfg: dict, video: Path, titulo: str, descricao: str, tags: list[str]) -> str:
    """Envia o vídeo pela YouTube Data API v3 e devolve a URL."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    opc = cfg["publicacao"]["youtube"]
    escopos = ["https://www.googleapis.com/auth/youtube.upload"]
    token = config.RAIZ / opc["token"]
    cred = Credentials.from_authorized_user_file(str(token), escopos) if token.exists() else None
    if cred and cred.expired and cred.refresh_token:
        cred.refresh(Request())
    if not cred or not cred.valid:
        fluxo = InstalledAppFlow.from_client_secrets_file(str(config.RAIZ / opc["client_secrets"]), escopos)
        cred = fluxo.run_local_server(port=0)
        token.parent.mkdir(parents=True, exist_ok=True)
        token.write_text(cred.to_json())

    api = build("youtube", "v3", credentials=cred)
    corpo = {
        "snippet": {
            "title": f"{titulo[:90]} #shorts",
            "description": descricao,
            "tags": tags[:15],
            "categoryId": opc.get("categoria_id", "27"),
            "defaultLanguage": "pt-BR",
        },
        "status": {
            "privacyStatus": opc.get("privacidade", "private"),
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": True,  # rótulo obrigatório de conteúdo gerado por IA
        },
    }
    req = api.videos().insert(part="snippet,status", body=corpo, media_body=MediaFileUpload(str(video), resumable=True))
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    return f"https://youtube.com/shorts/{resp['id']}"


def instagram(cfg: dict, video: Path, legenda: str, espera_max: int = 600) -> str:
    """Publica um Reel. O arquivo precisa estar acessível em url_publica_base."""
    opc = cfg["publicacao"]["instagram"]
    base = opc.get("url_publica_base", "").rstrip("/")
    if not base:
        raise RuntimeError("Defina publicacao.instagram.url_publica_base (o Instagram só aceita vídeo por URL).")
    rel = video.resolve().relative_to(config.DADOS.resolve()).as_posix()
    api = f"https://graph.facebook.com/{opc.get('graph_versao', 'v21.0')}"
    usuario = config.segredo("INSTAGRAM_USER_ID")
    token = config.segredo("INSTAGRAM_ACCESS_TOKEN")

    cont = requests.post(
        f"{api}/{usuario}/media",
        data={"media_type": "REELS", "video_url": f"{base}/{rel}", "caption": legenda[:2200], "access_token": token},
        timeout=60,
    )
    cont.raise_for_status()
    cont_id = cont.json()["id"]

    inicio = time.time()
    while time.time() - inicio < espera_max:
        st = requests.get(f"{api}/{cont_id}", params={"fields": "status_code", "access_token": token}, timeout=30)
        st.raise_for_status()
        codigo = st.json().get("status_code")
        if codigo == "FINISHED":
            break
        if codigo == "ERROR":
            raise RuntimeError("Instagram recusou o vídeo (status ERROR).")
        time.sleep(10)
    else:
        raise TimeoutError("Instagram não terminou de processar o vídeo.")

    pub = requests.post(f"{api}/{usuario}/media_publish", data={"creation_id": cont_id, "access_token": token}, timeout=60)
    pub.raise_for_status()
    return f"instagram media id {pub.json()['id']}"
