#!/usr/bin/env python3
"""Agente coletor do M&O XML Captador — roda na ORIGEM (PC/servidor do cliente).

Vigia as pastas onde o ERP/PDV grava os XMLs de NF-e/NFC-e e envia, sozinho e
continuamente, cada arquivo NOVO para o servidor do escritório, por HTTPS.

Características:
- **100% autônomo**: uma vez instalado, não precisa de ninguém. Sem CAPTCHA, sem login.
- **Somente biblioteca padrão do Python** (urllib): instala em qualquer Windows sem pip.
- **Incremental**: guarda em estado local o que já enviou (caminho + tamanho + mtime + SHA-256);
  reenvia apenas o que mudou. Arquivos recém-gravados (ainda sendo escritos) ficam para a próxima volta.
- **Resiliente**: se o servidor estiver fora do ar, tenta de novo no próximo ciclo; nada se perde.
- **Nunca altera nem apaga** os XMLs de origem; só lê.

Configuração em ``agente.ini`` (ao lado deste arquivo ou em --config). Não guarde senhas:
o token do servidor é o único segredo e fica no .ini com permissão restrita.
"""

from __future__ import annotations

import argparse
import configparser
import hashlib
import io
import json
import logging
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
import zipfile
from pathlib import Path

LOG = logging.getLogger("moxml.agente")
IDADE_MINIMA = 60  # s: arquivo mexido há menos que isso pode estar sendo gravado
TAMANHO_MAXIMO = 50 * 1024 * 1024
LOTE = 20  # XMLs por requisição


def sha256(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()


class Estado:
    """Registro local do que já foi enviado (JSON simples, resiliente a quedas)."""

    def __init__(self, caminho: Path):
        self.caminho = caminho
        self.vistos: dict[str, list] = {}
        if caminho.exists():
            try:
                self.vistos = json.loads(caminho.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                LOG.warning("estado ilegível; recomeçando o controle local")

    def ja_enviado(self, chave: str, tamanho: int, mtime: float) -> bool:
        v = self.vistos.get(chave)
        return bool(v) and v[0] == tamanho and abs(v[1] - mtime) < 1

    def marcar(self, chave: str, tamanho: int, mtime: float, h: str) -> None:
        self.vistos[chave] = [tamanho, mtime, h]

    def salvar(self) -> None:
        tmp = self.caminho.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.vistos), encoding="utf-8")
        os.replace(tmp, self.caminho)


def coletar(pastas: list[Path], recursivo: bool, estado: Estado):
    """Gera (nome_exibicao, bytes) dos XMLs novos. Expande .zip no próprio cliente."""
    for base in pastas:
        if not base.exists():
            LOG.warning("pasta inexistente: %s", base)
            continue
        for p in sorted(base.rglob("*") if recursivo else base.glob("*")):
            if not p.is_file() or p.suffix.lower() not in (".xml", ".zip"):
                continue
            try:
                st = p.stat()
            except OSError:
                continue
            if time.time() - st.st_mtime < IDADE_MINIMA or st.st_size > TAMANHO_MAXIMO:
                continue
            if estado.ja_enviado(str(p), st.st_size, st.st_mtime):
                continue
            try:
                dados = p.read_bytes()
            except OSError:
                continue
            if p.stat().st_size != len(dados):  # mudou enquanto lia
                continue
            if p.suffix.lower() == ".zip":
                try:
                    with zipfile.ZipFile(io.BytesIO(dados)) as z:
                        for info in z.infolist():
                            if info.filename.lower().endswith(".xml") and info.file_size <= TAMANHO_MAXIMO:
                                yield f"{p.name}!{info.filename}", z.read(info)
                except zipfile.BadZipFile:
                    continue
            else:
                yield p.name, dados
            estado.marcar(str(p), st.st_size, st.st_mtime, sha256(dados))


def _multipart(itens: list[tuple[str, bytes]], origem: str) -> tuple[bytes, str]:
    fronteira = f"----moxml{uuid.uuid4().hex}"
    buf = io.BytesIO()

    def w(txt: str) -> None:
        buf.write(txt.encode("utf-8"))

    for nome, dados in itens:
        seguro = os.path.basename(nome).replace('"', "_")
        w(f"--{fronteira}\r\n")
        w(f'Content-Disposition: form-data; name="arquivos"; filename="{seguro}"\r\n')
        w(f"Content-Type: {mimetypes.guess_type(seguro)[0] or 'application/xml'}\r\n\r\n")
        buf.write(dados)
        w("\r\n")
    w(f"--{fronteira}\r\n")
    w('Content-Disposition: form-data; name="origem"\r\n\r\n')
    w(origem)
    w(f"\r\n--{fronteira}--\r\n")
    return buf.getvalue(), f"multipart/form-data; boundary={fronteira}"


def enviar(url: str, token: str | None, itens: list[tuple[str, bytes]], origem: str, timeout: float) -> dict:
    corpo, ctype = _multipart(itens, origem)
    req = urllib.request.Request(url.rstrip("/") + "/api/ingestao", data=corpo, method="POST")
    req.add_header("Content-Type", ctype)
    if token:
        req.add_header("x-api-token", token)
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 - URL do próprio escritório, via config
        return json.loads(r.read().decode("utf-8"))


def ciclo(cfg: dict, estado: Estado) -> dict:
    total = {"recebidos": 0, "novos": 0, "duplicados": 0, "rejeitados": 0}
    lote: list[tuple[str, bytes]] = []

    def despachar() -> None:
        if not lote:
            return
        r = enviar(cfg["url"], cfg["token"], lote, cfg["origem"], cfg["timeout"])
        for k in total:
            total[k] += r.get(k, 0)
        for d in r.get("detalhes", []):
            LOG.info("%s: %s %s", d.get("arquivo"), d.get("resultado"), d.get("mensagem", ""))
        lote.clear()

    for nome, dados in coletar(cfg["pastas"], cfg["recursivo"], estado):
        lote.append((nome, dados))
        if len(lote) >= LOTE:
            despachar()
            estado.salvar()  # confirma o envio antes de marcar como visto
    despachar()
    estado.salvar()
    return total


def carregar_config(caminho: Path) -> dict:
    cp = configparser.ConfigParser()
    if not caminho.exists():
        raise SystemExit(f"configuração não encontrada: {caminho} (copie agente.ini.modelo)")
    cp.read(caminho, encoding="utf-8")
    s = cp["agente"]
    pastas = [Path(x.strip()) for x in s.get("pastas", "").splitlines() if x.strip()] or \
             [Path(x.strip()) for x in s.get("pastas", "").split(";") if x.strip()]
    if not pastas or not s.get("url"):
        raise SystemExit("defina 'url' e 'pastas' no agente.ini")
    return {
        "url": s["url"].strip(),
        "token": (s.get("token") or "").strip() or None,
        "pastas": pastas,
        "recursivo": s.getboolean("recursivo", fallback=True),
        "intervalo": s.getint("intervalo_segundos", fallback=300),
        "origem": (s.get("origem") or "agente_coletor").strip(),
        "timeout": s.getfloat("timeout_segundos", fallback=60),
        "estado": Path(s.get("estado") or (caminho.parent / "estado.json")),
    }


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Agente coletor do M&O XML Captador")
    ap.add_argument("--config", default=str(Path(__file__).with_name("agente.ini")))
    ap.add_argument("--uma-vez", action="store_true", help="executa um ciclo e sai (para teste/tarefa agendada)")
    a = ap.parse_args(argv)
    cfg = carregar_config(Path(a.config))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(),
                                  logging.FileHandler(Path(cfg["estado"]).with_name("agente.log"), encoding="utf-8")])
    estado = Estado(cfg["estado"])
    LOG.info("agente iniciado — servidor %s — %d pasta(s) — intervalo %ds",
             cfg["url"], len(cfg["pastas"]), cfg["intervalo"])
    while True:
        try:
            r = ciclo(cfg, estado)
            if r["recebidos"]:
                LOG.info("ciclo: %s", r)
        except urllib.error.URLError as e:
            LOG.warning("servidor indisponível (%s); nova tentativa no próximo ciclo", e)
        except Exception as e:  # noqa: BLE001 - agente nunca deve morrer
            LOG.exception("falha no ciclo: %s", e)
        if a.uma_vez:
            break
        time.sleep(cfg["intervalo"])


if __name__ == "__main__":
    sys.exit(main())
