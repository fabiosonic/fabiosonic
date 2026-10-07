"""Motor de grafo de estados (graph engineering).

- Nó: função `f(estado, ctx) -> dict` com as atualizações do estado.
- Aresta fixa (`ligar`) ou condicional (`rotear`, função que devolve o nome do próximo nó).
- Cada passo é gravado na trilha (checkpoint): uma execução interrompida é retomada do ponto
  em que parou com `retomar(run_id)`.
- Falha após as tentativas configuradas desvia para o nó de exceção (se houver), nunca é
  engolida em silêncio.
"""
from __future__ import annotations

import time
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

FIM = "__FIM__"

FuncNo = Callable[[dict, Any], dict | None]
Roteador = Callable[[dict], str]


class ErroGrafo(RuntimeError):
    pass


@dataclass
class No:
    nome: str
    funcao: FuncNo
    tentativas: int = 1
    descricao: str = ""


@dataclass
class Grafo:
    nome: str
    nos: dict[str, No] = field(default_factory=dict)
    arestas: dict[str, str] = field(default_factory=dict)
    roteadores: dict[str, tuple[Roteador, tuple[str, ...]]] = field(default_factory=dict)
    inicio: str | None = None
    no_excecao: str | None = None
    max_passos: int = 500

    def no(self, nome: str, funcao: FuncNo, tentativas: int = 1, descricao: str = "") -> "Grafo":
        if nome in self.nos or nome == FIM:
            raise ErroGrafo(f"nó duplicado ou reservado: {nome}")
        self.nos[nome] = No(nome, funcao, tentativas, descricao or (funcao.__doc__ or "").strip().split("\n")[0])
        if self.inicio is None:
            self.inicio = nome
        return self

    def ligar(self, origem: str, destino: str) -> "Grafo":
        if origem in self.roteadores:
            raise ErroGrafo(f"{origem} já tem roteador condicional")
        self.arestas[origem] = destino
        return self

    def rotear(self, origem: str, roteador: Roteador, destinos: tuple[str, ...]) -> "Grafo":
        if origem in self.arestas:
            raise ErroGrafo(f"{origem} já tem aresta fixa")
        self.roteadores[origem] = (roteador, tuple(destinos))
        return self

    def excecao(self, nome: str) -> "Grafo":
        self.no_excecao = nome
        return self

    # ------------------------------------------------------------------
    def validar(self) -> None:
        if not self.inicio:
            raise ErroGrafo("grafo vazio")
        validos = set(self.nos) | {FIM}
        for o, d in self.arestas.items():
            if o not in self.nos or d not in validos:
                raise ErroGrafo(f"aresta inválida {o} -> {d}")
        for o, (_, ds) in self.roteadores.items():
            if o not in self.nos:
                raise ErroGrafo(f"roteador em nó inexistente: {o}")
            for d in ds:
                if d not in validos:
                    raise ErroGrafo(f"destino inválido {o} -> {d}")
        if self.no_excecao and self.no_excecao not in self.nos:
            raise ErroGrafo(f"nó de exceção inexistente: {self.no_excecao}")
        for nome in self.nos:
            if nome not in self.arestas and nome not in self.roteadores:
                raise ErroGrafo(f"nó sem saída: {nome} (ligue a FIM explicitamente)")
        # alcançabilidade
        vistos, pilha = set(), [self.inicio]
        if self.no_excecao:
            pilha.append(self.no_excecao)
        while pilha:
            n = pilha.pop()
            if n in vistos or n == FIM:
                continue
            vistos.add(n)
            if n in self.arestas:
                pilha.append(self.arestas[n])
            if n in self.roteadores:
                pilha.extend(self.roteadores[n][1])
        soltos = set(self.nos) - vistos
        if soltos:
            raise ErroGrafo(f"nós inalcançáveis: {sorted(soltos)}")

    def _proximo(self, atual: str, estado: dict) -> str:
        if atual in self.arestas:
            return self.arestas[atual]
        roteador, destinos = self.roteadores[atual]
        d = roteador(estado)
        if d not in destinos:
            raise ErroGrafo(f"roteador de {atual} devolveu destino não declarado: {d}")
        return d

    def mermaid(self) -> str:
        linhas = ["flowchart TD"]
        def ident(n):
            return "FIM((FIM))" if n == FIM else n
        for o, d in self.arestas.items():
            linhas.append(f"    {o} --> {ident(d)}")
        for o, (_, ds) in self.roteadores.items():
            for d in ds:
                linhas.append(f"    {o} -.-> {ident(d)}")
        if self.no_excecao:
            linhas.append(f"    classDef exc fill:#fdd,stroke:#c00\n    class {self.no_excecao} exc")
        return "\n".join(linhas)

    # ------------------------------------------------------------------
    def executar(self, estado: dict, ctx: Any = None, trilha=None, run_id: str | None = None,
                 _inicio: str | None = None, _passo: int = 0) -> dict:
        self.validar()
        run_id = run_id or uuid.uuid4().hex
        estado = dict(estado)
        estado.setdefault("_run_id", run_id)
        estado.setdefault("_historico", [])
        atual = _inicio or self.inicio
        passo = _passo
        while atual != FIM:
            passo += 1
            if passo > self.max_passos:
                raise ErroGrafo(f"limite de passos excedido em {self.nome} (ciclo?)")
            no = self.nos[atual]
            t0 = time.monotonic()
            erro = None
            for tentativa in range(1, no.tentativas + 1):
                try:
                    atualizacao = no.funcao(estado, ctx) or {}
                    if not isinstance(atualizacao, dict):
                        raise ErroGrafo(f"nó {atual} devolveu {type(atualizacao).__name__}, esperado dict")
                    estado.update(atualizacao)
                    erro = None
                    break
                except Exception as exc:  # noqa: BLE001 — registrado e desviado
                    erro = f"{type(exc).__name__}: {exc}"
                    estado["_ultimo_traceback"] = traceback.format_exc(limit=5)
            ms = int((time.monotonic() - t0) * 1000)
            if erro:
                estado.setdefault("_erros", []).append({"no": atual, "erro": erro})
                if self.no_excecao and atual != self.no_excecao:
                    proximo = self.no_excecao
                else:
                    if trilha:
                        # checkpoint aponta para o próprio nó: `retomar` tenta de novo a partir dele
                        trilha.registrar_passo(run_id, self.nome, passo, atual, "ERRO", ms, erro, atual, estado)
                    raise ErroGrafo(f"{self.nome}.{atual}: {erro}")
                status = "ERRO"
            else:
                proximo = self._proximo(atual, estado)
                status = "OK"
            estado["_historico"].append(atual)
            if trilha:
                trilha.registrar_passo(run_id, self.nome, passo, atual, status, ms, erro, proximo, estado)
            atual = proximo
        return estado

    def retomar(self, run_id: str, trilha, ctx: Any = None) -> dict:
        ultimo = trilha.ultimo_passo(run_id)
        if ultimo is None:
            raise ErroGrafo(f"execução {run_id} não encontrada")
        if ultimo["proximo"] == FIM:
            return ultimo["estado"]
        return self.executar(ultimo["estado"], ctx, trilha, run_id, _inicio=ultimo["proximo"], _passo=ultimo["passo"])
