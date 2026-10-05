"""Licença de uso por período: assinatura, avaliação, vencimento, carência, bloqueio, relógio e CNPJ."""

from datetime import date, timedelta

import pytest

from nfse_itaborai import automacao, emissor, licenca
from nfse_itaborai.tela import tratar

pytestmark = pytest.mark.licenca_real

CNPJ = "11222333000181"
_CHAVES = {}


def _chaves():
    if not _CHAVES:
        _CHAVES["pub"], _CHAVES["priv"] = licenca.gerar_chaves(1024)
    return _CHAVES["pub"], _CHAVES["priv"]


@pytest.fixture
def inst(tmp_path, monkeypatch):
    """Instalação limpa numa pasta temporária, com a chave pública de teste."""
    pub, priv = _chaves()
    monkeypatch.setattr(emissor, "BASE", tmp_path)
    monkeypatch.setattr(licenca, "CHAVE_PUBLICA", pub)
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    (tmp_path / ".env").write_text(f"ITABORAI_CNPJ={CNPJ}\n", encoding="utf-8")
    hoje = {"d": date(2026, 10, 4)}
    monkeypatch.setattr(licenca, "_hoje", lambda: hoje["d"])
    return {"pasta": tmp_path, "priv": priv, "hoje": hoje}


def _chave(priv, validade, cnpj=CNPJ, **k):
    return licenca.emitir({"id": "L-1", "cliente": "ESCRITORIO X", "cnpj": cnpj, "validade": validade} | k, priv)


def test_chave_assinada_confere_e_adulterada_e_recusada(inst):
    ch = _chave(inst["priv"], "2026-11-30")
    assert licenca.ler(ch)["validade"] == "2026-11-30"
    payload, sig = ch[len("NFSE1-"):].split(".")
    import base64
    import json
    dados = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    dados["validade"] = "2099-12-31"                                      # cliente tenta estender a validade
    falsa = "NFSE1-" + licenca._b64e(json.dumps(dados, sort_keys=True, separators=(",", ":")).encode()) + "." + sig
    with pytest.raises(ValueError, match="assinatura"):
        licenca.ler(falsa)
    _, outra_priv = licenca.gerar_chaves(1024)                             # chave de outro "fornecedor"
    with pytest.raises(ValueError, match="assinatura"):
        licenca.ler(_chave(outra_priv, "2099-12-31"))
    with pytest.raises(ValueError, match="formato"):
        licenca.ler("qualquer coisa")


def test_avaliacao_vencimento_carencia_e_bloqueio(inst, monkeypatch):
    monkeypatch.setattr(licenca, "TESTE_DIAS", 15)                          # fornecedor que dá avaliação
    h = inst["hoje"]
    s = licenca.situacao()
    assert s["liberado"] and s["status"] == "teste" and s["dias"] == licenca.TESTE_DIAS
    h["d"] += timedelta(days=licenca.TESTE_DIAS)
    assert licenca.situacao()["status"] == "bloqueada"
    r = tratar("titulos", {"filtro": "todos"})
    assert r["licenca_bloqueada"] and "avaliação terminou" in r["erro"]
    assert "licenca" in tratar("estado", {})                               # tela abre para ativar
    assert automacao.rodar_todas()["executado"] is False                   # robô parado
    s = tratar("licenca/ativar", {"chave": _chave(inst["priv"], (h["d"] + timedelta(days=30)).isoformat())})
    assert s["liberado"] and s["status"] == "ativa" and s["cliente"] == "ESCRITORIO X"
    h["d"] += timedelta(days=25)
    assert licenca.situacao()["status"] == "aviso"                          # faltam 5 dias
    h["d"] += timedelta(days=7)
    s = licenca.situacao()
    assert s["liberado"] and s["status"] == "carencia"                      # vencida há 2 dias
    h["d"] += timedelta(days=licenca.CARENCIA_DIAS)
    assert not licenca.situacao()["liberado"]


def test_licenca_de_outro_cnpj_e_recusada(inst):
    with pytest.raises(ValueError, match="CNPJ"):
        licenca.ativar(_chave(inst["priv"], "2027-01-31", cnpj="99888777000166"))


def test_relogio_atrasado_bloqueia(inst):
    h = inst["hoje"]
    licenca.ativar(_chave(inst["priv"], "2026-12-31"))
    h["d"] = date(2026, 12, 20)
    assert licenca.situacao()["liberado"]
    h["d"] = date(2026, 11, 1)                                              # "voltou no tempo"
    s = licenca.situacao()
    assert not s["liberado"] and s.get("relogio")


def test_apagar_o_arquivo_nao_reinicia_a_avaliacao(inst, monkeypatch):
    monkeypatch.setattr(licenca, "TESTE_DIAS", 15)
    h = inst["hoje"]
    licenca.situacao()
    h["d"] += timedelta(days=licenca.TESTE_DIAS + 1)
    (inst["pasta"] / "dados" / "licenca.json").unlink()
    assert not licenca.situacao()["liberado"]                               # o controle espelhado continua valendo


def test_limite_de_empresas(inst, monkeypatch):
    licenca.ativar(_chave(inst["priv"], "2027-12-31", empresas=1))
    from nfse_itaborai import empresas
    monkeypatch.setattr(empresas, "listar", lambda: [{"id": "principal"}])
    r = tratar("empresa/criar", {"nome": "OUTRA", "cnpj": "99888777000166"})
    assert "permite 1 empresa" in r["erro"]


def test_serial_obrigatorio_ja_na_instalacao(inst):
    """Padrão: sem avaliação. Instalação nova fica bloqueada até informar o serial; o serial grava o CNPJ."""
    (inst["pasta"] / ".env").unlink()
    s = licenca.situacao()
    assert not s["liberado"] and s["status"] == "sem_licenca" and "serial" in s["mensagem"]
    assert tratar("titulos", {"filtro": "todos"})["licenca_bloqueada"]
    s = licenca.ativar(_chave(inst["priv"], "2026-11-04", plano="mensal"))
    assert s["liberado"] and s["plano"] == "mensal" and s["plano_nome"] == "Mensalidade"
    assert "Mensalidade" in s["mensagem"]
    assert emissor.ler_env(inst["pasta"] / ".env")["ITABORAI_CNPJ"] == CNPJ        # instalação já sabe o CNPJ


def test_plano_anual_e_licenca_antiga_sem_plano(inst):
    s = licenca.ativar(_chave(inst["priv"], "2027-10-04", plano="anual"))
    assert (s["plano"], s["plano_nome"]) == ("anual", "Anuidade")
    assert licenca.plano({"validade": "2027-10-04", "emitida": "2026-10-04"}) == "anual"
    assert licenca.plano({"validade": "2026-11-04", "emitida": "2026-10-04"}) == "mensal"


def test_fornecedor_pode_dar_dias_de_teste(inst, monkeypatch):
    (inst["pasta"] / "fornecedor.json").write_text('{"nome": "X", "dias_de_teste": 7}', encoding="utf-8")
    s = licenca.situacao()
    assert s["liberado"] and s["status"] == "teste" and s["dias"] == 7


def test_instalacao_pede_o_serial(inst, monkeypatch, capsys):
    from nfse_itaborai import __main__ as cli
    respostas = iter(["serial-errado", _chave(inst["priv"], "2027-10-04", plano="anual")])
    monkeypatch.setattr("builtins.input", lambda *_: next(respostas))
    assert cli.pedir_serial()
    out = capsys.readouterr().out
    assert "inválida" in out and "Anuidade" in out
    assert licenca.situacao()["plano"] == "anual"
