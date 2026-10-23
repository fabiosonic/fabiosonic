"""Publicação direta no Instagram pela API de publicação de conteúdo (Graph API).

Requisitos da Meta: conta profissional (comercial ou criador), um app com a permissão
instagram_content_publish e imagens JPEG acessíveis por URL pública (o Instagram baixa a imagem).
"""
from __future__ import annotations

import time

import requests

LIMITE_LEGENDA = 2200
LIMITE_HASHTAGS = 30


class ErroInstagram(RuntimeError):
    pass


def _checar(r: requests.Response) -> dict:
    try:
        dados = r.json()
    except ValueError:
        dados = {}
    if r.status_code >= 400 or "error" in dados:
        msg = dados.get("error", {}).get("message") if isinstance(dados.get("error"), dict) else r.text[:300]
        raise ErroInstagram(f"Instagram recusou ({r.status_code}): {msg}")
    return dados


def ajustar_legenda(legenda: str) -> str:
    """Respeita os limites do Instagram: 2.200 caracteres e 30 hashtags."""
    palavras, tags = [], 0
    for palavra in legenda.split(" "):
        if palavra.startswith("#"):
            tags += 1
            if tags > LIMITE_HASHTAGS:
                continue
        palavras.append(palavra)
    return " ".join(palavras)[:LIMITE_LEGENDA]


class Instagram:
    def __init__(self, user_id: str, token: str, base: str = "https://graph.facebook.com/v21.0", espera: float = 3.0):
        self.user_id, self.token, self.base, self.espera = user_id, token, base.rstrip("/"), espera

    def _post(self, caminho: str, **dados) -> dict:
        return _checar(requests.post(f"{self.base}/{caminho}", data={**dados, "access_token": self.token}, timeout=60))

    def _aguardar(self, container: str, tentativas: int = 20) -> None:
        for _ in range(tentativas):
            r = requests.get(f"{self.base}/{container}", params={"fields": "status_code", "access_token": self.token}, timeout=30)
            status = _checar(r).get("status_code")
            if status in (None, "FINISHED", "PUBLISHED"):
                return
            if status in ("ERROR", "EXPIRED"):
                raise ErroInstagram(f"O Instagram não conseguiu processar a mídia (status {status}).")
            time.sleep(self.espera)
        raise ErroInstagram("O Instagram demorou demais para processar a mídia.")

    def publicar(self, urls_imagens: list[str], legenda: str) -> str:
        """Publica um post (1 imagem) ou carrossel (2 a 10). Devolve o ID da publicação."""
        if not urls_imagens:
            raise ErroInstagram("Nenhuma imagem para publicar.")
        if len(urls_imagens) > 10:
            raise ErroInstagram("O Instagram aceita no máximo 10 imagens por carrossel.")
        legenda = ajustar_legenda(legenda)
        if len(urls_imagens) == 1:
            container = self._post(f"{self.user_id}/media", image_url=urls_imagens[0], caption=legenda)["id"]
        else:
            filhos = [self._post(f"{self.user_id}/media", image_url=u, is_carousel_item="true")["id"] for u in urls_imagens]
            for f in filhos:
                self._aguardar(f)
            container = self._post(f"{self.user_id}/media", media_type="CAROUSEL", children=",".join(filhos), caption=legenda)["id"]
        self._aguardar(container)
        return self._post(f"{self.user_id}/media_publish", creation_id=container)["id"]
