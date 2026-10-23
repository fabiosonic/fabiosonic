"""Publicação: pacote para postar à mão ou agendamento pela API pública do Postiz."""
from __future__ import annotations

import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests

from avatar_contabil import config

from .db import Conteudo, Perfil
from .travas import legenda_final

# Campos mínimos de "settings" exigidos por rede na API do Postiz
CONFIG_REDE = {
    "instagram": lambda titulo: {"__type": "instagram", "post_type": "post"},
    "facebook": lambda titulo: {"__type": "facebook"},
    "linkedin": lambda titulo: {"__type": "linkedin"},
    "youtube": lambda titulo: {"__type": "youtube", "title": titulo[:95], "type": "public"},
}


def pacote(cfg: dict, perfil: Perfil, c: Conteudo, destino: Path) -> Path:
    """ZIP com as mídias e as legendas prontas, para postar manualmente."""
    dados = c.j("dados")
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for arq in c.j("arquivos"):
            caminho = config.DADOS / arq
            z.write(caminho, caminho.name)
        z.writestr("legenda.txt", legenda_final(cfg, perfil, dados, com_cta=True))
        if c.formato == "video":
            z.writestr("legenda_youtube.txt", legenda_final(cfg, perfil, dados, com_cta=False))
    return destino


class Postiz:
    def __init__(self, cfg: dict):
        self.base = cfg["studio"]["postiz"]["base_url"].rstrip("/")
        self.chave = config.segredo("POSTIZ_API_KEY")

    def _h(self) -> dict:
        return {"Authorization": self.chave}

    def enviar_midia(self, arquivo: Path) -> dict:
        with open(arquivo, "rb") as f:
            r = requests.post(f"{self.base}/upload", headers=self._h(), files={"file": (arquivo.name, f)}, timeout=300)
        r.raise_for_status()
        d = r.json()
        return {"id": d["id"], "path": d["path"]}

    def agendar(self, cfg: dict, perfil: Perfil, c: Conteudo, quando: datetime) -> list[dict]:
        canais = perfil.canais()
        if not canais:
            raise RuntimeError("Nenhum canal do Postiz configurado neste perfil.")
        dados = c.j("dados")
        arquivos = [config.DADOS / a for a in c.j("arquivos")]
        posts = []
        for rede, integracao in canais.items():
            if rede not in CONFIG_REDE:
                continue
            if c.formato == "video":
                # Instagram recebe a versão com CTA; as demais, a versão sem CTA
                escolhido = arquivos[0] if rede == "instagram" else arquivos[-1]
                midias = [self.enviar_midia(escolhido)]
            else:
                midias = [self.enviar_midia(a) for a in arquivos]
            posts.append({
                "integration": {"id": integracao},
                "value": [{"content": legenda_final(cfg, perfil, dados, com_cta=rede != "youtube"), "image": midias}],
                "settings": CONFIG_REDE[rede](dados.get("titulo", "")),
            })
        if not posts:
            raise RuntimeError("Os canais do perfil não são suportados (use instagram, facebook, linkedin ou youtube).")
        corpo = {
            "type": "schedule",
            "date": quando.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "shortLink": False,
            "tags": [],
            "posts": posts,
        }
        r = requests.post(f"{self.base}/posts", headers=self._h(), json=corpo, timeout=60)
        r.raise_for_status()
        return r.json()
