import pytest

from mo_autonomo.ia.cascata import Cascata, ErroCota, ErroProvedor, SemProvedorDisponivel, VazamentoBloqueado
from mo_autonomo.ia.leitor import ler_nao_estruturado
from mo_autonomo.ia.mascaramento import Mascara, contem_dado_pessoal
from tests.conftest import CNPJ_A, CPF_1


class Falso:
    def __init__(self, nome, local=False, respostas=None, erro=None):
        self.nome, self.local, self.respostas, self.erro, self.recebido = nome, local, list(respostas or []), erro, []

    def completar(self, sistema, usuario):
        self.recebido.append(usuario)
        if self.erro:
            raise self.erro
        return self.respostas.pop(0)


TEXTO = f"Guia DAS da empresa ALFA COMERCIO CNPJ {CNPJ_A[:2]}.{CNPJ_A[2:5]}.{CNPJ_A[5:8]}/{CNPJ_A[8:12]}-{CNPJ_A[12:]} " \
        f"sócio CPF {CPF_1} email socio@alfa.test competência 09/2026 valor R$ 1.234,56"


def test_mascara_reversivel():
    m = Mascara()
    out = m.mascarar(TEXTO, ["ALFA COMERCIO"])
    assert "[CNPJ_1]" in out and "[CPF_" in out and "[EMAIL_" in out
    assert not contem_dado_pessoal(out) and "ALFA" not in out
    assert m.desmascarar(out) == TEXTO


def test_local_recebe_bruto_nuvem_mascarado():
    local = Falso("local", local=True, erro=ErroProvedor("ollama fora"))
    nuvem = Falso("gemini", respostas=["ok [CNPJ_1]"])
    r = Cascata([local, nuvem]).completar("sis", TEXTO, ["ALFA COMERCIO"])
    assert local.recebido[0] == TEXTO
    assert "[CNPJ_1]" in nuvem.recebido[0] and not contem_dado_pessoal(nuvem.recebido[0])
    assert r["provedor"] == "gemini" and r["mascarado"] and CNPJ_A[:2] in r["texto"]


def test_cota_estourada_passa_para_proxima_e_volta_depois():
    relogio = {"t": 0.0}
    a = Falso("a", erro=ErroCota("429", espera_s=60))
    b = Falso("b", respostas=["r1", "r2"])
    c = Cascata([a, b], relogio=lambda: relogio["t"])
    assert c.completar("s", "texto sem dados")["provedor"] == "b"
    assert [p.nome for p in c.disponiveis()] == ["b"]
    relogio["t"] = 61
    a.erro, a.respostas = None, ["volta"]
    assert c.completar("s", "texto sem dados")["provedor"] == "a"


def test_todas_esgotadas():
    c = Cascata([Falso("a", erro=ErroCota("q")), Falso("b", erro=ErroProvedor("x"))])
    with pytest.raises(SemProvedorDisponivel):
        c.completar("s", "t")
    with pytest.raises(SemProvedorDisponivel, match="espera"):
        Cascata([]).completar("s", "t")


def test_vazamento_bloqueado_no_prompt_de_sistema():
    with pytest.raises(VazamentoBloqueado):
        Cascata([Falso("n", respostas=["x"])]).completar(f"sistema com {CNPJ_A}", "t")


def json_ia(**kw):
    import json
    base = {"tipo": "GUIA_TRIBUTO", "cnpj": None, "competencia": "2026-09", "valor": "1.234,56",
            "confianca": 0.95, "resumo": "DAS"}
    base.update(kw)
    return json.dumps(base)


def test_leitor_valida_contra_texto():
    c = Cascata([Falso("n", respostas=[json_ia(cnpj="[CNPJ_1]")])])
    r = ler_nao_estruturado(TEXTO, c, nomes_sensiveis=["ALFA COMERCIO"])
    assert r["status"] == "OK" and r["cnpj"] == CNPJ_A and str(r["valor"]) == "1234.56"


def test_leitor_rejeita_invencao():
    c = Cascata([Falso("n", respostas=[json_ia(valor="9.999,99", cnpj="11222333000181")])])
    r = ler_nao_estruturado(TEXTO, c)
    assert r["status"] == "PENDENTE" and "valor" in r["motivo"] and "CNPJ" in r["motivo"]
    c = Cascata([Falso("n", respostas=[json_ia(confianca=0.3)])])
    assert "confiança" in ler_nao_estruturado(TEXTO, c)["motivo"]
    c = Cascata([Falso("n", respostas=["não sei"])])
    assert ler_nao_estruturado(TEXTO, c)["status"] == "PENDENTE"


def test_leitor_fila_quando_sem_ia():
    c = Cascata([Falso("a", erro=ErroCota("q"))])
    assert ler_nao_estruturado(TEXTO, c)["status"] == "FILA"
    assert ler_nao_estruturado("   ", c)["status"] == "PENDENTE"
