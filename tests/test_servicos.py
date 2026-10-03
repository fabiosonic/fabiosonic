"""Catálogo de serviços por empresa: cadastro manual, importação das notas e escolha do serviço na emissão."""

import re
from datetime import date

import pytest

from nfse_itaborai import clientes, financeiro, importador, lote, servicos
from nfse_itaborai.tela import tratar
from test_emissor import Simulador, ambiente  # noqa: F401  (fixture)
from test_empresas import multi  # noqa: F401  (fixture)
from test_financeiro import CLI_A, CLI_B, base  # noqa: F401  (fixture)
from test_importador import MORAES, nacional

CONSULTORIA = {"nome": "Consultoria", "descricao": "CONSULTORIA EMPRESARIAL", "item_lista_servico": "17.01",
               "codigo_desdobro": "170101", "codigo_nbs": "113011000", "cnae": "7020400", "aliquota_iss": "2.00",
               "tipo_tributacao": "4", "iss_retido": "2", "indicador_operacao": "100301",
               "classificacao_tributaria": "200052"}


def _tag(xml: str, tag: str) -> str:
    return re.search(rf"<{tag}>([^<]*)</{tag}>", xml).group(1)


def test_catalogo_nasce_do_servico_padrao_antigo(base):  # noqa: F811
    lst = tratar("servicos", {})
    assert len(lst) == 1 and lst[0]["padrao"] and lst[0]["nome"] == "Contabilidade"
    assert lst[0]["codigo_desdobro"] == "171901" and lote.servico_padrao()["descricao"] == "HONORARIOS CONTABEIS MENSAIS"


def test_cadastro_manual_padrao_e_exclusao(base):  # noqa: F811
    s = tratar("servico/salvar", CONSULTORIA)
    assert s["id"] and not s.get("padrao")
    assert "6 dígitos" in tratar("servico/salvar", {**CONSULTORIA, "nome": "X", "codigo_desdobro": "17"})["erro"]
    assert "Já existe" in tratar("servico/salvar", {**CONSULTORIA})["erro"]
    tratar("servico/salvar", {**s, "padrao": True})
    assert servicos.padrao()["nome"] == "Consultoria" and len([x for x in servicos.listar() if x["padrao"]]) == 1
    tratar("servico/excluir", {"id": s["id"]})
    assert servicos.padrao()["nome"] == "Contabilidade"
    assert "pelo menos um" in tratar("servico/excluir", {"id": servicos.padrao()["id"]})["erro"]


def test_emissao_com_o_servico_escolhido(base):  # noqa: F811
    s = servicos.salvar(CONSULTORIA)
    r = tratar("emitir", {"cpf_cnpj": CLI_A["cpf_cnpj"], "valor": "800", "servico_id": s["id"]})
    assert r["sucesso"], r
    xml = Simulador.recebidos[-1][1]
    assert _tag(xml, "ItemListaServico") == "17.01" and _tag(xml, "CodigoLsnDesdobro") == "17.01.01"
    assert _tag(xml, "CodigoNbs") == "113011000" and "CONSULTORIA EMPRESARIAL" in xml
    assert financeiro.obter_titulo(r["titulo_id"])["servico_id"] == s["id"]
    # sem escolha: serviço padrão
    tratar("emitir", {"cpf_cnpj": CLI_A["cpf_cnpj"], "valor": "100"})
    assert _tag(Simulador.recebidos[-1][1], "ItemListaServico") == "17.19"


def test_servico_habitual_do_cliente_e_do_contrato(base):  # noqa: F811
    s = servicos.salvar(CONSULTORIA)
    clientes.salvar({**clientes.obter(CLI_B["cpf_cnpj"]), "servico_id": s["id"]})
    assert lote.montar_rps(CLI_B["cpf_cnpj"], "10")["item_lista_servico"] == "17.01"   # padrão do cliente
    k = financeiro.salvar_contrato({"cpf_cnpj": CLI_A["cpf_cnpj"], "valor": "500", "inicio": "2026-01", "servico_id": s["id"]})
    assert k["descricao"] == "CONSULTORIA EMPRESARIAL"
    tid = financeiro.gerar_titulos("2026-10", date(2026, 10, 1))[0]
    assert financeiro.obter_titulo(tid)["servico_id"] == s["id"]
    decimo = financeiro.gerar_decimo_terceiro(date(2026, 11, 2))
    assert financeiro.obter_titulo(decimo[0])["servico_id"] == s["id"]
    financeiro.emitir_nfse_titulo(tid)
    assert _tag(Simulador.recebidos[-1][1], "ItemListaServico") == "17.01"


def test_importacao_separa_atividades_e_liga_clientes(multi):  # noqa: F811
    c = importador.caixa()
    (c / "a.xml").write_text(nacional(MORAES, "33000167000101", "CLIENTE CONTAB", 1), encoding="utf-8")
    (c / "b.xml").write_text(nacional(MORAES, "11444777000161", "CLIENTE CONSULT", 2, "CONSULTORIA EMPRESARIAL",
                                      "170101"), encoding="utf-8")
    (c / "c.xml").write_text(nacional(MORAES, "22333444000105", "CLIENTE TREIN", 3, "TREINAMENTO DE EQUIPE",
                                      "080201"), encoding="utf-8")
    g = tratar("importador/analisar", {})["grupos"][0]
    nomes = {s["nome"] for s in g["servicos"]}
    assert nomes == {"Contabilidade", "Consultoria", "Treinamento"}
    contab = next(s for s in g["servicos"] if s["nome"] == "Contabilidade")
    assert contab["existente_id"] == "padrao"                          # já está no catálogo (mesmos códigos)
    r = tratar("importador/importar", {"empresa_id": MORAES, "cnpj": MORAES,
                                       "servicos": [s for s in g["servicos"] if not s["existente_id"]]})
    assert r["servicos"] == 2 and r["clientes_com_servico"] == 3
    cat = {s["nome"]: s for s in servicos.listar()}
    assert set(cat) == {"Contabilidade", "Consultoria", "Treinamento"}
    assert cat["Treinamento"]["item_lista_servico"] == "08.02" and cat["Treinamento"]["codigo_desdobro"] == "080201"
    habitual = {c["razao_social"]: c.get("servico_id") for c in clientes.listar()}
    assert habitual["CLIENTE CONSULT"] == cat["Consultoria"]["id"] and habitual["CLIENTE TREIN"] == cat["Treinamento"]["id"]
    assert lote.montar_rps("22333444000105", "50")["itens"][0]["descricao"] == "TREINAMENTO DE EQUIPE"
