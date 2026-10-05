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


@pytest.fixture
def outra_empresa(tmp_path, monkeypatch):
    """Duas instalações no mesmo computador: a do escritório (Desktop) e a de um cliente (Downloads, outro CNPJ)."""
    casa = tmp_path / "casa"
    cliente = casa / "Downloads" / "EmissorItaborai_limpo" / "EmissorItaborai"
    escritorio = casa / "Desktop" / "Escritorio"
    for p in (cliente, escritorio):
        (p / "nfse_itaborai").mkdir(parents=True)
        (p / "dados" / "certificados").mkdir(parents=True)
    (cliente / ".env").write_text("ITABORAI_CNPJ=59165665000106\nITABORAI_IE=999\n", encoding="utf-8")
    (cliente / "dados" / "certificados" / "certificado-cliente.pfx").write_bytes(b"PFX-CLIENTE")
    (cliente / "dados" / "config.json").write_text(json.dumps({
        "empresa": {"nome": "CLINICA DE PSICOLOGIA LTDA", "assinatura": "CLINICA DE PSICOLOGIA LTDA"},
        "emissao": {"canal": "nacional", "municipio_emissor": "3304557", "op_simp_nac": "3"},
        "financeiro": {"aliquota_simples_pct": 6.0}}), encoding="utf-8")
    (cliente / "dados" / "clientes.json").write_text(json.dumps([
        {"cpf_cnpj": "52998224725", "razao_social": "PACIENTE DA CLINICA", "endereco": {}}]), encoding="utf-8")
    monkeypatch.setattr(emissor, "RAIZ", emissor._Raiz(escritorio))
    monkeypatch.setattr(emissor, "BASE", escritorio)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: casa))
    for k in ("ITABORAI_CNPJ", "ITABORAI_IM", "ITABORAI_CHAVE", "ITABORAI_IE"):
        monkeypatch.delenv(k, raising=False)
    (escritorio / ".env").write_text("ITABORAI_CNPJ=24875410000144\nITABORAI_IM=1034265\nITABORAI_CHAVE=minha\n", encoding="utf-8")
    config.salvar({"empresa": {"nome": "ESCRITORIO CONTABIL LTDA", "assinatura": "Escritório Contábil"},
                   "emissao": {"canal": "municipal", "municipio_emissor": "3301900"}})
    clientes.salvar({"cpf_cnpj": "32396063000103", "razao_social": "CLIENTE DO ESCRITORIO"})
    return cliente, escritorio


def test_instalacao_de_outra_empresa_nunca_e_oferecida_nem_importada(outra_empresa):
    cliente, escritorio = outra_empresa
    assert cliente in migracao.localizar()                       # ela existe no computador…
    assert tratar("migracao/procurar", {}) == []                  # …mas nunca é oferecida
    r = tratar("migracao/importar", {"pasta": str(cliente)})
    assert "outra empresa" in r["erro"]
    assert config.carregar()["empresa"]["nome"] == "ESCRITORIO CONTABIL LTDA"
    assert [c["razao_social"] for c in clientes.listar()] == ["CLIENTE DO ESCRITORIO"]
    assert not (escritorio / "dados" / "certificados" / "certificado-cliente.pfx").exists()


def test_reparo_desfaz_o_que_veio_da_outra_empresa(outra_empresa, monkeypatch):
    """Caso real: instalação de um cliente trazida pela versão antiga (sem conferir o CNPJ). O reparo volta nome,
    canal, município e regras do backup anterior, tira os clientes e o certificado da outra empresa e mantém o que
    o escritório mudou depois."""
    from nfse_itaborai import backup
    cliente, escritorio = outra_empresa
    b = backup.criar("automatico")                               # backup automático de antes
    import time
    time.sleep(1.1)
    monkeypatch.setattr(migracao, "mesma_empresa", lambda p: True)      # como a versão antiga fazia
    monkeypatch.setitem(config.PADRAO["empresa"], "nome", "ESCRITORIO CONTABIL LTDA")   # nome de fábrica = do escritório
    monkeypatch.setitem(config.PADRAO["empresa"], "assinatura", "Escritório Contábil")
    migracao.importar(str(cliente))
    c = config.carregar()
    assert c["empresa"]["nome"] == "CLINICA DE PSICOLOGIA LTDA" and c["emissao"]["canal"] == "nacional"   # o estrago
    assert clientes.obter("52998224725") and emissor.ler_env(escritorio / ".env").get("ITABORAI_IE") == "999"
    config.salvar({"cobranca": {"multa_pct": 2.5}})              # algo que o escritório mudou depois
    monkeypatch.undo()
    monkeypatch.setattr(emissor, "RAIZ", emissor._Raiz(escritorio))
    monkeypatch.setattr(emissor, "BASE", escritorio)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: cliente.parents[2]))
    assert [m["cnpj"] for m in tratar("migracao/misturas", {})] == ["59165665000106"]
    r = tratar("migracao/reparar", {})
    assert r["conferir"] == [] and any("empresa.nome" in x for x in r["desfeito"])
    c = config.carregar()
    assert (c["empresa"]["nome"], c["empresa"]["assinatura"]) == ("ESCRITORIO CONTABIL LTDA", "Escritório Contábil")
    assert (c["emissao"]["canal"], c["emissao"]["municipio_emissor"]) == ("municipal", "3301900")
    assert c["cobranca"]["multa_pct"] == 2.5                     # mudança posterior preservada
    assert not clientes.obter("52998224725") and clientes.obter("32396063000103")
    assert "ITABORAI_IE" not in emissor.ler_env(escritorio / ".env")
    assert emissor.ler_env(escritorio / ".env")["ITABORAI_CNPJ"] == "24875410000144"
    assert not (escritorio / "dados" / "certificados" / "certificado-cliente.pfx").exists()
    assert tratar("migracao/misturas", {}) == []                 # não oferece de novo
    assert b["nome"]


def test_reparo_sem_backup_traz_os_dados_certos_de_outras_fontes(outra_empresa, monkeypatch):
    """Sem backup anterior (a versão antiga não fazia): o nome, o canal e o município CERTOS vêm de outra instalação
    do mesmo CNPJ e das notas autorizadas; o que identifica a outra empresa e não tem fonte fica vazio, nunca dela."""
    from nfse_itaborai import backup
    cliente, escritorio = outra_empresa
    cfg_cli = json.loads((cliente / "dados" / "config.json").read_text(encoding="utf-8"))
    cfg_cli["empresa"]["pix_chave"] = "clinica@exemplo.com"
    (cliente / "dados" / "config.json").write_text(json.dumps(cfg_cli), encoding="utf-8")
    # versão mais antiga do próprio escritório, mesmo CNPJ, em outra pasta
    antiga = escritorio.parent / "EmissorAntigo"
    (antiga / "nfse_itaborai").mkdir(parents=True)
    (antiga / "dados").mkdir()
    (antiga / ".env").write_text("ITABORAI_CNPJ=24875410000144\n", encoding="utf-8")
    (antiga / "dados" / "config.json").write_text(json.dumps({"empresa": {"nome": "ESCRITORIO CONTABIL LTDA"}}),
                                                  encoding="utf-8")
    # nota autorizada pela prefeitura (canal municipal) emitida por este CNPJ
    nota = escritorio / "saida" / "2026-09" / "RPS_10"
    nota.mkdir(parents=True)
    (nota / "NFSe_123.xml").write_text("<Nfse><IdentificacaoRps><Numero>10</Numero></IdentificacaoRps><PrestadorServico>"
                                       "<IdentificacaoPrestador><Cnpj>24875410000144</Cnpj></IdentificacaoPrestador>"
                                       "</PrestadorServico></Nfse>", encoding="utf-8")
    monkeypatch.setattr(migracao, "mesma_empresa", lambda p: True)          # como a versão antiga fazia
    monkeypatch.setattr(backup, "criar", lambda *a, **k: {})                # e sem backup antes
    monkeypatch.setitem(config.PADRAO["empresa"], "nome", "ESCRITORIO CONTABIL LTDA")
    monkeypatch.setitem(config.PADRAO["emissao"], "canal", "municipal")
    monkeypatch.setitem(config.PADRAO["emissao"], "municipio_emissor", "3301900")
    config.salvar({"emissao": {"canal": "municipal", "municipio_emissor": "3301900"}})
    migracao.importar(str(cliente))
    c = config.carregar()
    assert (c["empresa"]["nome"], c["emissao"]["canal"], c["empresa"]["pix_chave"]) == \
        ("CLINICA DE PSICOLOGIA LTDA", "nacional", "clinica@exemplo.com")      # o estrago
    monkeypatch.undo()
    monkeypatch.setattr(emissor, "RAIZ", emissor._Raiz(escritorio))
    monkeypatch.setattr(emissor, "BASE", escritorio)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: cliente.parents[2]))
    assert not list(backup.pasta_backups(escritorio).glob("backup_*.zip"))
    r = tratar("migracao/reparar", {})
    c = config.carregar()
    assert c["empresa"]["nome"] == "ESCRITORIO CONTABIL LTDA"                 # da instalação antiga do mesmo CNPJ
    assert c["empresa"]["assinatura"] == "Escritório Contábil"                # não tinha sido trocada
    assert (c["emissao"]["canal"], c["emissao"]["municipio_emissor"]) == ("municipal", "3301900")   # pelas notas
    assert c["empresa"]["pix_chave"] == ""                                     # da outra: apagado, nunca mantido
    assert any("pix_chave" in x for x in r["conferir"])
    assert not clientes.obter("52998224725") and clientes.obter("32396063000103")
    assert not (escritorio / "dados" / "certificados" / "certificado-cliente.pfx").exists()


def test_nome_diferente_do_certificado_deste_cnpj_e_avisado_e_corrigido(outra_empresa, monkeypatch):
    _, escritorio = outra_empresa
    assert migracao.identidade() is None                                       # sem certificado: nada a comparar
    monkeypatch.setattr(migracao, "_pelo_certificado", lambda cnpj, cfgs: "ESCRITORIO CONTABIL E ASSESSORIA LTDA")
    assert tratar("migracao/identidade", {}) is None                           # mesmo nome, escrita diferente
    config.salvar({"empresa": {"nome": "CLINICA DE PSICOLOGIA LTDA", "assinatura": "CLINICA DE PSICOLOGIA LTDA"}})
    i = tratar("migracao/identidade", {})
    assert i["oficial"] == "ESCRITORIO CONTABIL E ASSESSORIA LTDA" and i["fonte"] == "certificado digital"
    tratar("migracao/usar_nome_oficial", {})
    e = config.carregar()["empresa"]
    assert e["nome"] == e["assinatura"] == "ESCRITORIO CONTABIL E ASSESSORIA LTDA"
    assert tratar("migracao/identidade", {}) is None


def test_reparo_le_o_backup_protegido_por_senha(outra_empresa, monkeypatch):
    from nfse_itaborai import backup
    cliente, escritorio = outra_empresa
    config.salvar({"seguranca": {"backup_senha": "segredo123"}})
    assert backup.criar("automatico")["nome"].endswith(backup.EXT_PROTEGIDO)
    import time
    time.sleep(1.1)
    with monkeypatch.context() as antiga:                          # como a versão antiga fazia
        antiga.setattr(migracao, "mesma_empresa", lambda p: True)
        antiga.setattr(backup, "criar", lambda *a, **k: {})
        antiga.setitem(config.PADRAO["empresa"], "nome", "ESCRITORIO CONTABIL LTDA")
        migracao.importar(str(cliente))
    assert config.carregar()["empresa"]["nome"] == "CLINICA DE PSICOLOGIA LTDA"
    tratar("migracao/reparar", {})
    assert config.carregar()["empresa"]["nome"] == "ESCRITORIO CONTABIL LTDA"
