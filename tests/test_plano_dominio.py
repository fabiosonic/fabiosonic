from pathlib import Path

from mo_autonomo.clientes.cadastro import Carteira
from mo_autonomo.contabil.lancamentos import PlanoContas
from mo_autonomo.contabil.plano_dominio import importar_pasta, ler
from tests.conftest import carteira_teste

CAB = ("Impressão de campos da consulta;;;;;;;;;;;;;;;;;;;;;;;;;;;;Página: 1;;;;;\r\n\r\n"
       "+/-;Código;;;Classificação;;;;;;;;;;;Tipo;;;\r\nNome;;;\r\n")


def bloco(red, classif, tipo, nome, grupo="Ativo"):
    return (f";{red};;;{classif};;;;;;;;;;;{tipo};;;\r\n{nome};;;;;;;;\r\n"
            f";;;;;;;;;;;{grupo};;;;;;;;;Balanço Patrimonial;;;\r\n;;;;;;;;;\r\n;;;;;;;;;;;90113;;;\r\nComum;;;\r\n;;;;;\r\n")


def arquivo(p: Path):
    txt = CAB + bloco(1, "01", "T", "ATIVO") + bloco(6, "01.1.1.02", "T", "  BANCOS") + \
        bloco(702, "01.1.1.02.001", "C", "   Banco Ação S/A") + bloco(7, "01.1.1.02.001.001", "", "    Banco Ação S/A") + \
        bloco(5, "01.1.1.01.001", "", "    Caixa")
    p.write_bytes(txt.encode("cp1252"))
    return p


def test_le_plano_exportado_do_dominio(tmp_path):
    contas = ler(arquivo(tmp_path / "p.csv"))
    por = {c["codigo"]: c for c in contas}
    assert set(por) == {"1", "6", "702", "7", "5"}
    assert por["7"]["analitica"] and por["5"]["analitica"] and not por["702"]["analitica"] and not por["1"]["analitica"]
    assert por["7"]["descricao"] == "Banco Ação S/A" and por["7"]["classificacao"] == "01.1.1.02.001.001"


def test_importa_pasta_por_codigo_da_empresa(tmp_path):
    pasta = tmp_path / "planos"
    pasta.mkdir()
    arquivo(pasta / "101 - ALFA.csv")
    arquivo(pasta / "999 - FORA.csv")
    (pasta / "sem codigo.csv").write_text("x", encoding="utf-8")
    r = importar_pasta(pasta, carteira_teste(), tmp_path / "dominio")
    assert len(r["importados"]) == 1 and len(r["erros"]) == 2
    assert r["sem_plano"] == ["102-BETA SERVICOS", "103-GAMA MEI"]
    plano = PlanoContas.carregar(tmp_path / "dominio" / "101" / "plano_contas.csv")
    assert plano.valida("7") and not plano.valida("702")
