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


def test_espera_de_cota_persiste_entre_execucoes(tmp_path):
    arq = str(tmp_path / "esperas.json")
    rel = {"t": 100.0}
    c1 = Cascata([Falso("a", erro=ErroCota("429", espera_s=600)), Falso("b", respostas=["ok"])],
                 relogio=lambda: rel["t"], arquivo_estado=arq)
    assert c1.completar("s", "t")["provedor"] == "b"
    # novo processo (próximo ciclo do Agendador): "a" continua em espera
    c2 = Cascata([Falso("a", respostas=["x"]), Falso("b", respostas=["ok2"])], relogio=lambda: rel["t"] + 60,
                 arquivo_estado=arq)
    assert [p.nome for p in c2.disponiveis()] == ["b"]
    c3 = Cascata([Falso("a", respostas=["x"])], relogio=lambda: rel["t"] + 601, arquivo_estado=arq)
    assert c3.completar("s", "t")["provedor"] == "a"


def test_montar_cascata_do_config(monkeypatch):
    from mo_autonomo.ia.cascata import montar_cascata
    c = montar_cascata({"provedores": [
        {"nome": "local", "base_url": "http://localhost:11434/v1", "modelo": "m", "local": True},
        {"nome": "off", "base_url": "https://x", "modelo": "m", "ativo": False},
        {"nome": "g", "base_url": "https://y", "modelo": "m", "chave_env": "CHAVE_TESTE_INEXISTENTE"}]})
    assert [p.nome for p in c.provedores] == ["local", "g"] and c.provedores[0].local
    monkeypatch.delenv("CHAVE_TESTE_INEXISTENTE", raising=False)
    with pytest.raises(ErroProvedor, match="não definida"):
        c.provedores[1].completar("s", "u")


def test_provedor_http_real_429_500_200():
    import json as _json
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    from mo_autonomo.ia.cascata import ProvedorOpenAICompat

    respostas = [(429, {"Retry-After": "42"}, b'{"error":"rate limit"}'), (500, {}, b"boom"),
                 (200, {}, _json.dumps({"choices": [{"message": {"content": "oi"}}]}).encode())]
    recebidos = []

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            recebidos.append((self.path, self.headers.get("Authorization"),
                              _json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
            cod, cab, corpo = respostas.pop(0)
            self.send_response(cod)
            for k, v in cab.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(corpo)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    import os
    os.environ["CHAVE_TESTE_HTTP"] = "segredo"
    try:
        p = ProvedorOpenAICompat("t", f"http://127.0.0.1:{srv.server_port}/v1", "modelo-x", "CHAVE_TESTE_HTTP", timeout=5)
        with pytest.raises(ErroCota) as exc:
            p.completar("s", "u")
        assert exc.value.espera_s == 42.0
        with pytest.raises(ErroProvedor, match="500"):
            p.completar("s", "u")
        assert p.completar("s", "u") == "oi"
        caminho, auth, corpo = recebidos[-1]
        assert caminho == "/v1/chat/completions" and auth == "Bearer segredo" and corpo["model"] == "modelo-x"
        assert corpo["temperature"] == 0.0
    finally:
        srv.shutdown()
        del os.environ["CHAVE_TESTE_HTTP"]
