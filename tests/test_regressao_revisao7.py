"""Revisão 7: cadastro pela planilha (código repetido, razão vazia, status, CNPJ numérico) e
exportação para o Domínio (sem TXT em dobro, sem aprender com a própria saída)."""
from pathlib import Path

import openpyxl
import pytest

from mo_autonomo.aprovacao import lote as L
from mo_autonomo.clientes.cadastro import CadastroInvalido, Carteira, Empresa
from mo_autonomo.clientes.importar_planilha import converter, ler_planilha
from mo_autonomo.fluxos.ciclo import executar_lote, rodar_ciclo
from tests.conftest import CNPJ_A, CNPJ_B, CNPJ_C, eml_bytes, ofx_bytes
from tests.test_ponta_a_ponta import ctx_de
from tests.test_exportador_dominio import _projeto_reduzido

CNPJ_ZERO = "01234567000195"  # fictício válido com zero à esquerda


def _planilha(tmp_path, linhas) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Cadastro de Clientes"
    ws.append(["CÓD.", "RAZÃO SOCIAL", "CNPJ / CPF", "REGIME TRIBUTÁRIO", "STATUS"])
    for l in linhas:
        ws.append(l)
    p = tmp_path / "c.xlsx"
    wb.save(p)
    return p


def test_codigo_repetido_vira_pendencia(tmp_path):
    emp, pend = converter(ler_planilha(_planilha(tmp_path, [
        [11, "Beta", CNPJ_A, "SIMPLES NACIONAL", "ATIVO"], [11, "Gama", CNPJ_B, "SIMPLES NACIONAL", "ATIVO"]])))
    assert emp == [] and sum("CÓD. 11 repetido" in p for p in pend) == 2


def test_carteira_recusa_codigo_dividido():
    with pytest.raises(CadastroInvalido):
        Carteira([Empresa(codigo_dominio="11", apelido="A", cnpj=CNPJ_A, regime_dominio="SIMPLES"),
                  Empresa(codigo_dominio="11", apelido="B", cnpj=CNPJ_B, regime_dominio="SIMPLES")])


def test_razao_vazia_e_status_desconhecido_viram_pendencia(tmp_path):
    emp, pend = converter(ler_planilha(_planilha(tmp_path, [
        [1, None, CNPJ_A, "SIMPLES NACIONAL", "ATIVO"],
        [2, "Ativa", CNPJ_B, "SIMPLES NACIONAL", "ATIVA"],
        [3, "Sem status", CNPJ_C, "SIMPLES NACIONAL", None]])))
    assert [(e["apelido"], e["ativa"]) for e in emp] == [("ATIVA", "S")]
    assert any("razão social vazia" in p for p in pend) and any("STATUS" in p for p in pend)


def test_cnpj_numerico_recupera_zero_a_esquerda(tmp_path):
    emp, pend = converter(ler_planilha(_planilha(tmp_path, [[5, "Zero", int(CNPJ_ZERO), "MEI", "INATIVO"]])))
    assert not pend and emp[0]["cnpj"] == CNPJ_ZERO and emp[0]["ativa"] == "N"


def _aprovado_executado(tmp_path):
    base = _projeto_reduzido(tmp_path)
    (base / "entrada" / "1.eml").write_bytes(eml_bytes({"e.ofx": ofx_bytes()}))
    ctx = ctx_de(base)
    l = next(x for x in rodar_ciclo(ctx)["lotes"] if x["area"] == "CONTABIL")
    lote = L.carregar(Path(l["arquivo"]))
    aprovado = L.aprovar_humano(Path(l["arquivo"]), "APROVADO", lote["hash"], "Pessoa", ctx.trilha)
    r = executar_lote(aprovado, ctx)
    assert r[0]["status"] == "GRAVADO"
    return ctx, aprovado, Path(r[0]["destino"])


def test_reexecutar_lote_nao_gera_txt_em_dobro(tmp_path):
    ctx, aprovado, txt = _aprovado_executado(tmp_path)
    txt.unlink()  # escritório importou e tirou o arquivo da pasta
    r = [x for x in executar_lote(aprovado, ctx) if x["acao"] == "lancamento_contabil"]
    assert [x["status"] for x in r] == ["IGNORADO: lançamento já EXECUTADA (não exporta em dobro)"]
    assert not list(txt.parent.glob("*.txt"))


def test_txt_exportado_nao_alimenta_o_de_para(tmp_path):
    ctx, _, txt = _aprovado_executado(tmp_path)
    hist = ctx.dados / "dominio"
    assert not list(hist.rglob("historico/" + txt.name))
