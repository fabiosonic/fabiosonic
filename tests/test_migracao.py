"""Trazer configurações e dados de uma instalação anterior (outra pasta), sem alterar a antiga."""

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from nfse_itaborai import clientes, config, db, emissor, financeiro, migracao
from nfse_itaborai.tela import tratar


def _hash_pasta(p: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(p.rglob("*")):
        if f.is_file():
            h.update(str(f.relative_to(p)).encode() + f.read_bytes())
    return h.hexdigest()


@pytest.fixture
def cenario(tmp_path, monkeypatch):
    casa = tmp_path / "casa"
    antiga = casa / "Downloads" / "EmissorItaborai"
    nova = casa / "Desktop" / "Sistema"
    for p in (antiga, nova):
        (p / "nfse_itaborai").mkdir(parents=True)
        (p / "dados").mkdir()
    (antiga / ".env").write_text("ITABORAI_CNPJ=24875410000144\nITABORAI_IM=1034265\nITABORAI_CHAVE=chave-antiga\n"
                                 "ITABORAI_PROXIMO_RPS=3600\nITABORAI_AMBIENTE=producao\nITABORAI_CIENTE_IRREVERSIVEL=SIM\n",
                                 encoding="utf-8")
    (antiga / "meu-certificado.pfx").write_bytes(b"PFX")
    (antiga / "dados" / "config.json").write_text(json.dumps({
        "smtp": {"host": "smtp.gmail.com", "usuario": "escritorio@x.com", "senha": "app-pass"},
        "cobranca": {"provedor": "pix", "inter_client_id": "cli-1", "inter_client_secret": "sec", "multa_pct": 2.0},
        "empresa": {"pix_chave": "24875410000144"}, "resumo": {"email_dono": "dono@x.com"},
        "emissao": {"certificado_pfx": str(antiga / "meu-certificado.pfx"), "certificado_senha": "1234"},
        "pastas": {"xml_nfse": "~/Downloads/nfse"}, "whatsapp": {"provedor": "zapi"}}), encoding="utf-8")
    (antiga / "dados" / "clientes.json").write_text(json.dumps([
        {"cpf_cnpj": "32396063000103", "razao_social": "CLIENTE ANTIGO", "endereco": {}},
        {"cpf_cnpj": "54399432000146", "razao_social": "JA EXISTE COM OUTRO NOME", "endereco": {}}]), encoding="utf-8")
    monkeypatch.setattr(emissor, "RAIZ", emissor._Raiz(antiga))
    monkeypatch.setattr(emissor, "BASE", antiga)
    clientes.salvar({"cpf_cnpj": "54399432000146", "razao_social": "JA EXISTE COM OUTRO NOME"})
    financeiro.criar_titulo("54399432000146", "300", vencimento="2026-09-10", emitir_nfse=False)
    (nova / ".env").write_text("ITABORAI_CNPJ=24875410000144\nITABORAI_PROXIMO_RPS=3509\n", encoding="utf-8")
    monkeypatch.setattr(emissor, "RAIZ", emissor._Raiz(nova))
    monkeypatch.setattr(emissor, "BASE", nova)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: casa))
    for k in ("ITABORAI_CNPJ", "ITABORAI_IM", "ITABORAI_CHAVE", "ITABORAI_AMBIENTE", "ITABORAI_CIENTE_IRREVERSIVEL"):
        monkeypatch.delenv(k, raising=False)
    clientes.salvar({"cpf_cnpj": "54399432000146", "razao_social": "NOME CORRIGIDO NA NOVA"})
    config.salvar({"cobranca": {"multa_pct": 3.0}})
    return antiga, nova


def test_encontra_e_traz_so_o_que_falta(cenario):
    antiga, nova = cenario
    antes = _hash_pasta(antiga)
    achadas = tratar("migracao/procurar", {})
    assert [a["pasta"] for a in achadas] == [str(antiga.resolve())]
    itens = achadas[0]["itens"]
    assert {"E-mail de envio (SMTP)", "Banco Inter", "Chave PIX", "E-mail do dono", "Certificado digital"} <= set(itens)
    r = tratar("migracao/importar", {"pasta": str(antiga)})
    assert r["importado"]
    c = config.carregar()
    assert c["smtp"]["host"] == "smtp.gmail.com" and c["smtp"]["senha"] == "app-pass"
    assert c["cobranca"]["inter_client_id"] == "cli-1" and c["empresa"]["pix_chave"] == "24875410000144"
    assert c["resumo"]["email_dono"] == "dono@x.com"
    assert c["cobranca"]["multa_pct"] == 3.0                     # já preenchido aqui: não sobrescreve
    assert c["cobranca"]["provedor"] == "inter"                  # escolha da versão nova preservada
    assert c["pastas"]["xml_nfse"] == "" and "whatsapp" not in c
    # certificado copiado para dentro da empresa e utilizável
    assert c["emissao"]["certificado_pfx"] == "dados/certificados/meu-certificado.pfx"
    assert emissor.arquivo_da_empresa(c["emissao"]["certificado_pfx"]).read_bytes() == b"PFX"
    # .env: chave trazida, RPS pelo maior, produção NUNCA ligada por cópia
    assert emissor.env("ITABORAI_CHAVE") == "chave-antiga" and emissor.env("ITABORAI_PROXIMO_RPS") == "3600"
    assert not emissor.em_producao()
    # clientes: o que faltava entra, o corrigido aqui prevalece
    nomes = {c["cpf_cnpj"]: c["razao_social"] for c in clientes.listar()}
    assert nomes == {"32396063000103": "CLIENTE ANTIGO", "54399432000146": "NOME CORRIGIDO NA NOVA"}
    # financeiro: o atual estava vazio, então veio o da versão antiga
    assert len(financeiro.listar_titulos()) == 1
    # a pasta antiga não foi alterada
    assert _hash_pasta(antiga) == antes
    # depois de trazer, nada mais é oferecido; repetir não duplica nada
    assert tratar("migracao/procurar", {}) == []
    tratar("migracao/importar", {"pasta": str(antiga)})
    assert len(clientes.listar()) == 2 and len(financeiro.listar_titulos()) == 1


def test_financeiro_atual_com_dados_nao_e_substituido(cenario):
    antiga, nova = cenario
    clientes.salvar({"cpf_cnpj": "11222333000181", "razao_social": "NOVO"})
    financeiro.criar_titulo("11222333000181", "50", vencimento="2026-10-10", emitir_nfse=False)
    financeiro.criar_titulo("11222333000181", "60", vencimento="2026-10-11", emitir_nfse=False)
    migracao.importar(str(antiga))
    assert len(financeiro.listar_titulos()) == 2


def test_pasta_qualquer_e_recusada(cenario, tmp_path):
    assert "não reconhecida" in tratar("migracao/importar", {"pasta": str(tmp_path)})["erro"]
