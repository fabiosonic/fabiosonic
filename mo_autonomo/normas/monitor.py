"""Monitor de mudança do texto oficial e ficha de conferência assistida.

- `monitorar`: baixa a `fonte_url` de cada norma, normaliza o texto, compara o sha256 com
  `hash_texto`. Texto de norma CONFERIDA que mudou entra em `alteradas.json`: o catálogo
  passa a tratá-la como NÃO conferida (regras dependentes ficam inativas) até a reconferência.
- `ficha_conferencia`: prepara para a PESSOA conferir (texto salvo + dispositivos + bloco YAML
  a preencher). Nunca altera o YAML nem marca CONFERIDO.
"""
from __future__ import annotations

import html
import json
import re
import urllib.request
from datetime import date
from pathlib import Path

from ..util.arquivos import escrever_atomico, sha256_bytes
from .catalogo import Catalogo, url_oficial


def baixar(url: str, timeout: float = 60) -> bytes:
    if not url_oficial(url):
        raise ValueError(f"URL não oficial recusada: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "mo_autonomo-monitor/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def texto_normalizado(bruto: bytes) -> str:
    for enc in ("utf-8", "latin-1"):
        try:
            t = bruto.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", t)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    t = html.unescape(t)
    return re.sub(r"\s+", " ", t).strip()


def _salvar_texto(pasta: Path, nid: str, texto: str, h: str) -> Path:
    destino = Path(pasta) / nid / f"{date.today():%Y%m%d}_{h[:12]}.txt"
    if not destino.exists():
        escrever_atomico(destino, texto.encode("utf-8"))
    return destino


def monitorar(catalogo: Catalogo, pasta_textos: Path, buscar=baixar, trilha=None) -> list[dict]:
    resultado, alteradas = [], set(carregar_alteradas(pasta_textos))
    for n in sorted(catalogo.normas.values(), key=lambda x: x.id):
        if not n.fonte_url:
            resultado.append({"id": n.id, "situacao": "SEM_URL"})
            continue
        try:
            texto = texto_normalizado(buscar(n.fonte_url))
        except Exception as exc:  # noqa: BLE001 — site fora do ar não derruba o monitor
            resultado.append({"id": n.id, "situacao": "ERRO", "erro": str(exc)})
            continue
        h = sha256_bytes(texto.encode("utf-8"))
        arquivo = _salvar_texto(pasta_textos, n.id, texto, h)
        if not n.hash_texto:
            sit = "SEM_HASH_REGISTRADO"
            if n.status == "CONFERIDO":  # não dá para saber se mudou: reconferir
                alteradas.add(n.id)
        elif n.hash_texto == h:
            sit = "IGUAL"
            alteradas.discard(n.id)
        else:
            sit = "MUDOU"
            if n.status == "CONFERIDO":
                alteradas.add(n.id)
        resultado.append({"id": n.id, "situacao": sit, "hash": h, "arquivo": str(arquivo)})
        if trilha and sit == "MUDOU":
            trilha.evento("NORMA_ALTERADA", n.id, {"hash_novo": h, "hash_conferido": n.hash_texto})
    escrever_atomico(Path(pasta_textos) / "alteradas.json", json.dumps(sorted(alteradas)).encode())
    return resultado


def carregar_alteradas(pasta_textos: Path) -> list[str]:
    arq = Path(pasta_textos) / "alteradas.json"
    if not arq.exists():
        return []
    return list(json.loads(arq.read_text(encoding="utf-8")))


def ficha_conferencia(catalogo: Catalogo, nid: str, pasta_saida: Path, buscar=baixar) -> Path:
    n = catalogo.get(nid)
    if n is None:
        raise KeyError(f"norma {nid} não está no catálogo")
    url = n.fonte_url or n.fonte_url_sugerida
    linhas = [f"# Ficha de conferência — {n.id}", "", f"**{n.titulo}**", "",
              f"- Status atual: **{n.status}**", f"- URL: {url or 'NÃO LOCALIZADA — localizar no site oficial'}",
              f"- Dispositivos declarados: {', '.join(n.dispositivos) or '—'}", ""]
    h = None
    if url and url_oficial(url):
        try:
            texto = texto_normalizado(buscar(url))
            h = sha256_bytes(texto.encode("utf-8"))
            arq = _salvar_texto(Path(pasta_saida) / "textos", n.id, texto, h)
            linhas += [f"- Texto salvo: `{arq}` (sha256 `{h}`)", ""]
            for d in n.dispositivos:
                chave = re.escape(d.split()[0] + " " + d.split()[1]) if len(d.split()) > 1 else re.escape(d)
                m = re.search(chave, texto, re.IGNORECASE)
                trecho = texto[m.start(): m.start() + 600] if m else "(dispositivo não localizado no texto — conferir manualmente)"
                linhas += [f"### {d}", "", f"> {trecho}", ""]
        except Exception as exc:  # noqa: BLE001
            linhas += [f"- Não foi possível baixar: {exc}", ""]
    elif url:
        linhas += ["- URL não é de domínio oficial: não serve como fonte.", ""]
    linhas += ["## Para concluir (ato humano)", "",
               "Confira cada parâmetro com o trecho literal acima e preencha no YAML da norma:", "", "```yaml",
               f"  status: CONFERIDO", f"  fonte_url: {url or '<url oficial>'}", "  conferido_por: <seu nome>",
               f"  conferido_em: {date.today():%Y-%m-%d}", f"  hash_texto: {h or '<sha256 do texto conferido>'}",
               "  parametros:", "    # <nome>: <valor>   # dispositivo + trecho literal que sustenta", "```"]
    destino = Path(pasta_saida) / f"{n.id}.md"
    escrever_atomico(destino, "\n".join(linhas).encode("utf-8"))
    return destino
