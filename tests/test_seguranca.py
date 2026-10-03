"""Segurança: senhas protegidas no disco, backup cifrado com senha e PIN de acesso à tela."""

import base64
import json
import shutil

import pytest

from nfse_itaborai import backup, clientes, config, emissor, empresas, segredos
from nfse_itaborai.tela import tratar
from test_empresas import multi  # noqa: F401  (fixture)


# ---------------------------------------------------------------- senhas protegidas

def test_senhas_nunca_ficam_legiveis_no_disco(multi):  # noqa: F811
    config.salvar({"smtp": {"senha": "senha-do-email"}, "cobranca": {"inter_client_secret": "segredo-inter"},
                   "emissao": {"certificado_senha": "senha-pfx"}})
    bruto = (multi / "dados" / "config.json").read_text(encoding="utf-8")
    assert "senha-do-email" not in bruto and "segredo-inter" not in bruto and "senha-pfx" not in bruto
    cfg = config.carregar()
    assert cfg["smtp"]["senha"] == "senha-do-email" and cfg["emissao"]["certificado_senha"] == "senha-pfx"
    assert config.publico()["smtp"]["senha"] == "••••••"


def test_senha_antiga_em_texto_continua_valendo(multi):  # noqa: F811
    arq = multi / "dados" / "config.json"
    d = json.loads(arq.read_text(encoding="utf-8"))
    d["smtp"]["senha"] = "texto-puro"
    arq.write_text(json.dumps(d), encoding="utf-8")
    assert config.carregar()["smtp"]["senha"] == "texto-puro"
    config.salvar({})                                   # próxima gravação protege
    assert "texto-puro" not in arq.read_text(encoding="utf-8")


def test_chave_do_webservice_protegida_no_env(multi):  # noqa: F811
    empresas.salvar_credenciais({"chave": "chave-secreta-123"})
    assert "chave-secreta-123" not in (multi / ".env").read_text(encoding="utf-8")
    assert emissor.env("ITABORAI_CHAVE") == "chave-secreta-123"
    assert empresas.credenciais()["chave"] == empresas.SEGREDO


def test_valor_protegido_em_outro_computador_vira_vazio(multi, monkeypatch, tmp_path):  # noqa: F811
    v = segredos.proteger("abc")
    monkeypatch.setenv("NFSE_CHAVE_LOCAL", str(tmp_path / "outra_chave.bin"))
    assert segredos.revelar(v) == ""


# ---------------------------------------------------------------- backup com senha

def test_backup_protegido_por_senha(multi):  # noqa: F811
    config.salvar({"smtp": {"senha": "senha-do-email"}, "seguranca": {"backup_senha": "minha-senha"}})
    empresas.salvar_credenciais({"chave": "chave-ws"})
    b = tratar("backup/criar", {})
    assert b["nome"].endswith(".protegido") and b["protegido"] and b["cnpj"] == empresas.ativa()["cnpj"]
    bruto = (backup.pasta_backups() / b["nome"]).read_bytes()
    assert b"PK" not in bruto[:200] and b"CLIENTE DA MORAES" not in bruto and b"senha-do-email" not in bruto
    assert backup.listar()[0]["protegido"] and backup.listar()[0]["valido"]
    clientes.salvar({"cpf_cnpj": "54399432000146", "razao_social": "CLIENTE NOVO"})
    with pytest.raises(ValueError, match="incorreta"):
        backup.restaurar(backup.arquivo(b["nome"]), senha="errada")
    r = tratar("backup/restaurar", {"nome": b["nome"]})          # usa a senha configurada
    assert r["senhas_restauradas"] >= 2
    assert [c["razao_social"] for c in clientes.listar()] == ["CLIENTE DA MORAES"]


def test_backup_protegido_em_computador_novo_volta_com_as_senhas(multi, monkeypatch, tmp_path):  # noqa: F811
    config.salvar({"smtp": {"senha": "senha-do-email"}, "seguranca": {"backup_senha": "minha-senha"}})
    empresas.salvar_credenciais({"chave": "chave-ws"})
    dados = (backup.pasta_backups() / backup.criar("manual")["nome"]).read_bytes()
    # computador novo: outra chave local (as senhas protegidas do disco antigo não abrem aqui)
    monkeypatch.setenv("NFSE_CHAVE_LOCAL", str(tmp_path / "pc_novo.bin"))
    shutil.rmtree(multi / "dados")
    (multi / ".env").write_text("ITABORAI_CNPJ=24875410000144\n", encoding="utf-8")
    b64 = base64.b64encode(dados).decode()
    from nfse_itaborai import tela
    with pytest.raises(ValueError, match="senha"):
        tela._restaurar_arquivo({"arquivo": b64})
    assert not list(backup.pasta_backups().glob("backup_enviado_*"))   # tentativa sem senha não deixa lixo
    r = tratar("backup/restaurar_arquivo", {"arquivo": b64, "senha": "minha-senha"})
    assert r["empresa_id"] and config.carregar()["smtp"]["senha"] == "senha-do-email"
    assert emissor.env("ITABORAI_CHAVE") == "chave-ws"


def test_senha_do_backup_curta_e_recusada(multi):  # noqa: F811
    r = tratar("config/salvar", {"seguranca": {"backup_senha": "123"}})
    assert r["sucesso"] is False and "6 caracteres" in r["erro"]


# ---------------------------------------------------------------- PIN de acesso

@pytest.fixture
def servidor(multi):  # noqa: F811
    import threading
    from http.server import ThreadingHTTPServer

    from nfse_itaborai import acesso, tela
    acesso._SESSOES.clear()
    acesso._ERROS.update(n=0, ate=0.0)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), tela._Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def _post(url, rota, corpo=None, cookie=""):
    import urllib.request
    req = urllib.request.Request(f"{url}/api/{rota}", data=json.dumps(corpo or {}).encode(), method="POST",
                                 headers={"Cookie": cookie} if cookie else {})
    with urllib.request.urlopen(req) as r:
        ck = (r.headers.get("Set-Cookie") or "").split(";")[0]
        return json.loads(r.read()), ck


def _get(url, caminho, cookie=""):
    import urllib.error
    import urllib.request
    try:
        with urllib.request.urlopen(urllib.request.Request(url + caminho, headers={"Cookie": cookie} if cookie else {})) as r:
            return r.status
    except urllib.error.HTTPError as ex:
        return ex.code


def test_sem_pin_tudo_aberto(servidor):
    assert _post(servidor, "acesso/estado")[0] == {"ativo": False, "logado": True, "minutos": 240}
    assert "clientes" in _post(servidor, "estado")[0]


def test_pin_bloqueia_api_e_downloads(servidor, multi):  # noqa: F811
    r, ck = _post(servidor, "acesso/definir", {"novo": "4321", "minutos": 30})
    assert r["ativo"] and ck.startswith("nfse_sessao=")          # quem definiu continua dentro
    assert "clientes" in _post(servidor, "estado", cookie=ck)[0]
    # outro navegador, sem sessão
    assert _post(servidor, "estado")[0]["bloqueado"]
    assert _get(servidor, "/export/titulos.csv") == 401 and _get(servidor, "/") == 200 and _get(servidor, "/app.js") == 200
    assert _post(servidor, "acesso/entrar", {"pin": "0000"})[0]["erro"] == "PIN incorreto."
    r, ck2 = _post(servidor, "acesso/entrar", {"pin": "4321"})
    assert r["ok"] and _get(servidor, "/export/titulos.csv", ck2) == 200
    _post(servidor, "acesso/sair", cookie=ck2)
    assert _post(servidor, "estado", cookie=ck2)[0]["bloqueado"]
    # PIN guardado só como hash
    assert "4321" not in (multi / "dados_locais" / "acesso.json").read_text(encoding="utf-8")
    # trocar/remover exige o PIN atual
    assert "incorreto" in _post(servidor, "acesso/definir", {"atual": "9999", "novo": ""}, ck)[0]["erro"]
    assert _post(servidor, "acesso/definir", {"atual": "4321", "novo": ""}, ck)[0]["ativo"] is False
    assert "clientes" in _post(servidor, "estado")[0]


def test_tentativas_erradas_bloqueiam(servidor):
    from nfse_itaborai import acesso
    acesso.definir("", "1234")
    for _ in range(acesso.MAX_ERROS):
        _post(servidor, "acesso/entrar", {"pin": "0000"})
    assert "Aguarde" in _post(servidor, "acesso/entrar", {"pin": "1234"})[0]["erro"]


def test_pin_so_numeros(multi):  # noqa: F811
    from nfse_itaborai import acesso
    with pytest.raises(ValueError, match="4 a 8"):
        acesso.definir("", "12ab")


def test_senhas_antigas_protegidas_ao_abrir(multi):  # noqa: F811
    arq = multi / "dados" / "config.json"
    d = json.loads(arq.read_text(encoding="utf-8"))
    d["smtp"]["senha"] = "antiga"
    arq.write_text(json.dumps(d), encoding="utf-8")
    assert empresas.proteger_senhas() == 2                  # config.json + chave do .env ("abc")
    assert "antiga" not in arq.read_text(encoding="utf-8") and "=abc" not in (multi / ".env").read_text(encoding="utf-8")
    assert emissor.env("ITABORAI_CHAVE") == "abc" and config.carregar()["smtp"]["senha"] == "antiga"
    assert empresas.proteger_senhas() == 0
