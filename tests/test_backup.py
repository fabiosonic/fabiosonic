"""Backup e restauração por empresa: estado volta, numeração não volta, produção não liga, empresas não se misturam."""

import base64
import json
import shutil
import zipfile

import pytest

from nfse_itaborai import backup, clientes, config, emissor, empresas, financeiro
from nfse_itaborai.tela import tratar
from test_empresas import multi  # noqa: F401  (fixture)

MORAES, PADARIA = "24875410000144", "11222333000181"


def _seq(raiz):
    return json.loads((raiz / "dados" / "sequencia.json").read_text(encoding="utf-8"))


def test_backup_e_restauracao_completos(multi):  # noqa: F811
    financeiro.criar_titulo("32396063000103", "250", vencimento="2026-10-10", emitir_nfse=False)
    (multi / "dados" / "sequencia.json").write_text('{"proximo_rps": 100, "proximo_dps": 5}', encoding="utf-8")
    (multi / "saida" / "2026-10").mkdir(parents=True)
    (multi / "saida" / "2026-10" / "nota.xml").write_text("<x/>", encoding="utf-8")
    b = tratar("backup/criar", {})
    assert b["cnpj"] == MORAES and b["valido"]
    with zipfile.ZipFile(backup.pasta_backups() / b["nome"]) as z:
        nomes = set(z.namelist())
    assert {"backup.json", ".env", "dados/sistema.db", "dados/clientes.json", "dados/config.json",
            "saida/2026-10/nota.xml"} <= nomes and not any(n.startswith("dados/backup/") for n in nomes)
    # depois do backup: cliente novo, título pago, numeração avançou, produção ligada pelo usuário
    clientes.salvar({"cpf_cnpj": "54399432000146", "razao_social": "CLIENTE NOVO"})
    financeiro.baixar(1, forma="manual")
    (multi / "dados" / "sequencia.json").write_text('{"proximo_rps": 130, "proximo_dps": 9}', encoding="utf-8")
    with open(multi / ".env", "a", encoding="utf-8") as f:
        f.write("ITABORAI_AMBIENTE=producao\nITABORAI_CIENTE_IRREVERSIVEL=SIM\n")
    r = tratar("backup/restaurar", {"nome": b["nome"]})
    assert r["restaurado"] == b["nome"] and r["backup_anterior"].endswith("antes_da_restauracao.zip")
    assert [c["razao_social"] for c in clientes.listar()] == ["CLIENTE DA MORAES"]
    assert financeiro.obter_titulo(1)["status"] == "aberto"
    assert _seq(multi)["proximo_rps"] == 130 and _seq(multi)["proximo_dps"] == 9      # numeração não volta
    assert emissor.ler_env(multi / ".env")["ITABORAI_PROXIMO_RPS"] == "130"
    assert emissor.em_producao()                                    # ambiente continua o atual
    nomes = [x["nome"] for x in tratar("backup/listar", {})["backups"]]
    assert b["nome"] in nomes and r["backup_anterior"] in nomes


def test_backup_de_outra_empresa_nunca_e_restaurado_aqui(multi):  # noqa: F811
    b = backup.criar("manual")
    empresas.criar({"nome": "PADARIA BOM PAO LTDA", "cnpj": PADARIA})
    clientes.salvar({"cpf_cnpj": "54399432000146", "razao_social": "CLIENTE DA PADARIA"})
    destino = backup.pasta_backups() / b["nome"]
    shutil.copy(multi / "dados" / "backup" / b["nome"], destino)
    with pytest.raises(ValueError, match="não pode ser restaurado"):
        backup.restaurar(destino)
    assert [c["razao_social"] for c in clientes.listar()] == ["CLIENTE DA PADARIA"]
    # pelo envio de arquivo, o backup vai para a empresa dona dele, não para a que está aberta
    b64 = base64.b64encode((multi / "dados" / "backup" / b["nome"]).read_bytes()).decode()
    r = tratar("backup/restaurar_arquivo", {"arquivo": "data:application/zip;base64," + b64})
    assert r["empresa_id"] == MORAES
    assert [c["razao_social"] for c in clientes.listar()] == ["CLIENTE DA PADARIA"]
    assert not list(backup.pasta_backups().glob("backup_enviado_*"))


def test_computador_novo_cadastra_a_empresa_do_backup(multi, tmp_path_factory):  # noqa: F811
    empresas.criar({"nome": "PADARIA BOM PAO LTDA", "cnpj": PADARIA})
    clientes.salvar({"cpf_cnpj": "54399432000146", "razao_social": "CLIENTE DA PADARIA"})
    zip_padaria = (emissor.raiz() / "dados" / "backup" / backup.criar("manual")["nome"]).read_bytes()
    # outra instalação, só com a empresa principal
    shutil.rmtree(multi / "empresas")
    (multi / "empresas.json").unlink()
    empresas.aplicar_ativa()
    r = tratar("backup/restaurar_arquivo", {"arquivo": base64.b64encode(zip_padaria).decode()})
    assert r["empresa_id"] == PADARIA and empresas.ativa()["cnpj"] == PADARIA
    assert [c["razao_social"] for c in clientes.listar()] == ["CLIENTE DA PADARIA"]
    assert not emissor.em_producao()


def test_zip_estranho_e_recusado(multi, tmp_path):  # noqa: F811
    ruim = tmp_path / "ruim.zip"
    with zipfile.ZipFile(ruim, "w") as z:
        z.writestr("backup.json", json.dumps({"sistema": "nfse_itaborai", "cnpj": MORAES}))
        z.writestr("../../fora.txt", "x")
    with pytest.raises(ValueError, match="fora do padrão"):
        backup.restaurar(ruim)
    r = tratar("backup/restaurar_arquivo", {"arquivo": base64.b64encode(b"nao e zip").decode()})
    assert "zip" in r["erro"]
    assert config.carregar()["empresa"]["nome"] == "MORAES & OLIVEIRA CONTABILIDADE"
