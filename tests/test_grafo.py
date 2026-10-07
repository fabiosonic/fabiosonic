import pytest

from mo_autonomo.grafo.motor import FIM, ErroGrafo, Grafo
from mo_autonomo.trilha.auditoria import Trilha


def g_simples():
    g = Grafo("t")
    g.no("a", lambda e, c: {"x": 1})
    g.no("b", lambda e, c: {"y": e["x"] + 1})
    g.no("c", lambda e, c: {"z": "par"})
    g.no("d", lambda e, c: {"z": "impar"})
    g.ligar("a", "b")
    g.rotear("b", lambda e: "c" if e["y"] % 2 == 0 else "d", ("c", "d"))
    g.ligar("c", FIM)
    g.ligar("d", FIM)
    return g


def test_execucao_condicional():
    e = g_simples().executar({})
    assert e["z"] == "par" and e["_historico"] == ["a", "b", "c"]


def test_validacao_no_sem_saida_e_inalcancavel():
    g = Grafo("t")
    g.no("a", lambda e, c: {})
    with pytest.raises(ErroGrafo, match="sem saída"):
        g.validar()
    g.ligar("a", FIM)
    g.no("solto", lambda e, c: {})
    g.ligar("solto", FIM)
    with pytest.raises(ErroGrafo, match="inalcançáveis"):
        g.validar()


def test_roteador_destino_nao_declarado():
    g = Grafo("t")
    g.no("a", lambda e, c: {})
    g.no("b", lambda e, c: {})
    g.rotear("a", lambda e: "x", ("b",))
    g.ligar("b", FIM)
    with pytest.raises(ErroGrafo, match="não declarado"):
        g.executar({})


def test_excecao_desvia_e_registra():
    g = Grafo("t")
    g.no("a", lambda e, c: 1 / 0)
    g.no("falha", lambda e, c: {"tratado": True})
    g.ligar("a", FIM)
    g.ligar("falha", FIM)
    g.excecao("falha")
    t = Trilha(":memory:")
    e = g.executar({}, trilha=t, run_id="r1")
    assert e["tratado"] and e["_erros"][0]["no"] == "a"
    assert [p[2] for p in t.passos("r1")] == ["ERRO", "OK"]


def test_tentativas():
    cont = {"n": 0}

    def instavel(e, c):
        cont["n"] += 1
        if cont["n"] < 3:
            raise RuntimeError("instável")
        return {"ok": True}
    g = Grafo("t")
    g.no("a", instavel, tentativas=3)
    g.ligar("a", FIM)
    assert g.executar({})["ok"] and cont["n"] == 3


def test_sem_no_excecao_propaga():
    g = Grafo("t")
    g.no("a", lambda e, c: 1 / 0)
    g.ligar("a", FIM)
    with pytest.raises(ErroGrafo, match="ZeroDivisionError"):
        g.executar({})


def test_retomar_do_checkpoint():
    estado = {"quebrar": True}

    def b(e, c):
        if estado["quebrar"]:
            raise RuntimeError("queda de energia")
        return {"b": True}
    g = Grafo("t")
    g.no("a", lambda e, c: {"a": True})
    g.no("b", b)
    g.ligar("a", "b")
    g.ligar("b", FIM)
    t = Trilha(":memory:")
    with pytest.raises(ErroGrafo):
        g.executar({}, trilha=t, run_id="r2")
    estado["quebrar"] = False
    e = g.retomar("r2", t)
    assert e["a"] and e["b"]
    assert [p[1] for p in t.passos("r2")] == ["a", "b", "b"]  # trilha preserva a falha


def test_mermaid():
    m = g_simples().mermaid()
    assert "a --> b" in m and "b -.-> c" in m


def test_no_devolve_tipo_errado():
    g = Grafo("t")
    g.no("a", lambda e, c: [1])
    g.ligar("a", FIM)
    with pytest.raises(ErroGrafo, match="esperado dict"):
        g.executar({})
