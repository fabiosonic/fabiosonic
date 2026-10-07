"""Cascata de provedores de IA (gratuitos) com troca automática por cota/limite.

Ordem típica (config `ia.provedores`):
  1. ollama local      -> recebe texto bruto (local: true)
  2..n. APIs gratuitas compatíveis com OpenAI (Gemini/AI Studio, Groq, OpenRouter :free,
        Mistral, Cerebras, GitHub Models...) -> só texto MASCARADO; a cascata recusa enviar
        se detectar CPF/CNPJ/e-mail/chave.
Erro de cota/limite (HTTP 429, 402, ou corpo citando quota/rate limit) põe o provedor em
espera até `Retry-After` (ou `espera_padrao_s`) e passa para o próximo. Sem nenhum
disponível: `SemProvedorDisponivel` -> o documento vai para a fila e é reprocessado depois.
Limites dos planos gratuitos mudam: ficam no config, não no código.
"""
from __future__ import annotations

import http.client
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Callable, Protocol

from .mascaramento import Mascara, contem_dado_pessoal


class ErroCota(RuntimeError):
    def __init__(self, msg, espera_s: float | None = None):
        super().__init__(msg)
        self.espera_s = espera_s


class ErroProvedor(RuntimeError):
    pass


class SemProvedorDisponivel(RuntimeError):
    pass


class VazamentoBloqueado(RuntimeError):
    pass


class Provedor(Protocol):
    nome: str
    local: bool

    def completar(self, sistema: str, usuario: str) -> str: ...


def _post_json(url: str, corpo: dict, cabecalhos: dict, timeout: float) -> dict:
    req = urllib.request.Request(url, data=json.dumps(corpo).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **cabecalhos})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            corpo = r.read()
        try:
            return json.loads(corpo.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise ErroProvedor(f"resposta não-JSON: {corpo[:120]!r}") from exc
    except urllib.error.HTTPError as exc:
        corpo_erro = exc.read().decode(errors="replace")[:500]
        if exc.code in (402, 429) or "quota" in corpo_erro.lower() or "rate limit" in corpo_erro.lower():
            ra = exc.headers.get("Retry-After") if exc.headers else None
            espera = float(ra) if ra and ra.replace(".", "", 1).isdigit() else None
            raise ErroCota(f"HTTP {exc.code}: {corpo_erro}", espera) from exc
        raise ErroProvedor(f"HTTP {exc.code}: {corpo_erro}") from exc
    except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException) as exc:
        raise ErroProvedor(f"falha de conexão: {exc}") from exc


@dataclass
class ProvedorOpenAICompat:
    """Qualquer API compatível com /chat/completions (inclui Ollama em /v1)."""
    nome: str
    base_url: str
    modelo: str
    chave_env: str | None = None
    local: bool = False
    timeout: float = 120.0
    temperatura: float = 0.0

    def completar(self, sistema: str, usuario: str) -> str:
        cab = {}
        if self.chave_env:
            chave = os.environ.get(self.chave_env)
            if not chave:
                raise ErroProvedor(f"variável {self.chave_env} não definida")
            cab["Authorization"] = f"Bearer {chave}"
        r = _post_json(self.base_url.rstrip("/") + "/chat/completions",
                       {"model": self.modelo, "temperature": self.temperatura,
                        "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}]},
                       cab, self.timeout)
        try:
            return r["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ErroProvedor(f"resposta inesperada: {str(r)[:200]}") from exc


@dataclass
class Cascata:
    provedores: list
    espera_padrao_s: float = 3600.0
    relogio: Callable[[], float] = time.time
    _bloqueado_ate: dict = field(default_factory=dict)
    registro: list = field(default_factory=list)
    arquivo_estado: str | None = None  # persiste as esperas de cota entre execuções do Agendador

    def __post_init__(self):
        if self.arquivo_estado and os.path.exists(self.arquivo_estado):
            try:
                with open(self.arquivo_estado, encoding="utf-8") as f:
                    self._bloqueado_ate.update({k: float(v) for k, v in json.load(f).items()})
            except (OSError, ValueError):
                pass  # estado corrompido: começa sem esperas (pior caso: uma tentativa a mais)

    def _persistir(self):
        if not self.arquivo_estado:
            return
        agora = self.relogio()
        vivos = {k: v for k, v in self._bloqueado_ate.items() if v > agora}
        os.makedirs(os.path.dirname(self.arquivo_estado) or ".", exist_ok=True)
        tmp = self.arquivo_estado + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(vivos, f)
        os.replace(tmp, self.arquivo_estado)

    def disponiveis(self):
        agora = self.relogio()
        return [p for p in self.provedores if self._bloqueado_ate.get(p.nome, 0) <= agora]

    def completar(self, sistema: str, texto: str, nomes_sensiveis: list[str] | None = None) -> dict:
        """Tenta cada provedor na ordem. Devolve {texto, provedor, mascarado}."""
        mascara = Mascara()
        texto_mascarado = None
        erros = []
        for p in self.disponiveis():
            if p.local:
                envio, mascarado = texto, False
            else:
                if texto_mascarado is None:
                    texto_mascarado = mascara.mascarar(texto, nomes_sensiveis)
                    vazou = contem_dado_pessoal(texto_mascarado) + contem_dado_pessoal(sistema)
                    if vazou:
                        raise VazamentoBloqueado(f"texto ainda contém {vazou}; envio à nuvem bloqueado")
                envio, mascarado = texto_mascarado, True
            try:
                resposta = p.completar(sistema, envio)
                if not isinstance(resposta, str):
                    raise ErroProvedor(f"resposta inesperada ({type(resposta).__name__})")
            except ErroCota as exc:
                espera = exc.espera_s if exc.espera_s is not None else self.espera_padrao_s
                self._bloqueado_ate[p.nome] = self.relogio() + espera
                self._persistir()
                erros.append(f"{p.nome}: cota ({exc})")
                self.registro.append({"provedor": p.nome, "resultado": "COTA"})
                continue
            except ErroProvedor as exc:
                erros.append(f"{p.nome}: {exc}")
                self.registro.append({"provedor": p.nome, "resultado": "ERRO"})
                continue
            self.registro.append({"provedor": p.nome, "resultado": "OK"})
            return {"texto": mascara.desmascarar(resposta) if mascarado else resposta,
                    "provedor": p.nome, "mascarado": mascarado}
        raise SemProvedorDisponivel("; ".join(erros) or "todos os provedores em espera de cota")


def _host_local(url: str) -> bool:
    """`local: true` só vale para endereço da própria máquina ou da rede interna: um erro de config
    não pode mandar documento bruto para a internet (regra 11)."""
    import ipaddress
    from urllib.parse import urlparse
    host = (urlparse(url).hostname or "").lower()
    if host == "localhost":
        return True
    try:
        ips = [ipaddress.ip_address(host)]
    except ValueError:  # nome (ex.: "ollama-pc"): vale se TODOS os endereços resolvidos forem locais
        import socket
        try:
            ips = [ipaddress.ip_address(i[4][0].split("%")[0]) for i in socket.getaddrinfo(host, None)]
        except (OSError, ValueError):
            return False
    return bool(ips) and all(ip.is_loopback or ip.is_private for ip in ips)


def montar_cascata(config_ia: dict, arquivo_estado: str | None = None) -> Cascata:
    provs = []
    for p in config_ia.get("provedores", []):
        if not p.get("ativo", True):
            continue
        if p.get("local") and not _host_local(p["base_url"]):
            import logging
            logging.getLogger(__name__).warning(
                "provedor %s marcado local, mas %s não é da máquina/rede interna: tratado como NUVEM "
                "(só recebe texto mascarado)", p["nome"], p["base_url"])
        provs.append(ProvedorOpenAICompat(
            nome=p["nome"], base_url=p["base_url"], modelo=p["modelo"], chave_env=p.get("chave_env"),
            local=bool(p.get("local", False)) and _host_local(p["base_url"]), timeout=float(p.get("timeout", 120)),
        ))
    return Cascata(provs, espera_padrao_s=float(config_ia.get("espera_padrao_s", 3600)),
                   arquivo_estado=arquivo_estado)
