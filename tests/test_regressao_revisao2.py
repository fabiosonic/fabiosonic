"""Regressões da 2ª revisão adversarial."""
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from mo_autonomo.aprovacao import lote as L
from mo_autonomo.fluxos.ciclo import rodar_ciclo
from mo_autonomo.fluxos.contexto import carregar_config, montar_contexto
from mo_autonomo.grafo.motor import ErroGrafo
from tests.conftest import CNPJ_A, CNPJ_X, HOJE, eml_bytes, nfe_xml, ofx_bytes, pdf_com_texto
from tests.test_ponta_a_ponta import ctx_de, projeto


def lote_de(e, area="FISCAL"):
    l = next(x for x in e["lotes"] if x["area"] == area)
    return l, L.carregar(Path(l["arquivo"]))


def test_pendencia_de_um_documento_nao_trava_os_outros(tmp_path):
    base = projeto(tmp_path)
    (base / "entrada" / "1.eml").write_bytes(eml_bytes({
        "ok.xml": nfe_xml(numero=1),
        "terceiro.xml": nfe_xml(emit=CNPJ_X, dest=CNPJ_A, tp_nf="0", numero=9)}))
    ctx = ctx_de(base)
    e = rodar_ciclo(ctx)
    l, lote = lote_de(e)
    assert len(lote["acoes"]) == 1 and lote["pendencias"] == []
    assert [p["codigo"] for p in lote["informativas"]] == ["ROTA_PENDENTE"]
    aprovado = L.aprovar_humano(Path(l["arquivo"]), "APROVADO", lote["hash"], "Pessoa", ctx.trilha)
    from mo_autonomo.fluxos.ciclo import executar_lote
    assert executar_lote(aprovado, ctx)[0]["status"] == "GRAVADO"


def test_queda_depois_de_processar_nao_perde_documento(tmp_path, monkeypatch):
    base = projeto(tmp_path)
    (base / "entrada" / "1.eml").write_bytes(eml_bytes({"n.xml": nfe_xml(numero=1)}))
    ctx = ctx_de(base)
    import mo_autonomo.fluxos.ciclo as C
    monkeypatch.setattr(C, "n_montar_lotes", lambda e, c: 1 / 0)
    with pytest.raises(ErroGrafo):
        rodar_ciclo(ctx)
    monkeypatch.undo()
    e = rodar_ciclo(ctx)
    assert len(e["anexos"]) == 1 and len(lote_de(e)[1]["acoes"]) == 1
    assert rodar_ciclo(ctx)["anexos"] == []  # depois de gravado o lote, não volta mais


def test_receitas_csv_do_excel_nao_derruba_o_ciclo(tmp_path):
    base = projeto(tmp_path)
    (base / "dados" / "apuracao").mkdir(parents=True)
    (base / "dados" / "apuracao" / "receitas.csv").write_bytes(
        f"cnpj;competencia;receita_declarada;fonte\n{CNPJ_A};2026-10;50,00;Declaração PGDAS\n{CNPJ_A};2026-09;;x\n"
        .encode("cp1252"))
    (base / "entrada" / "1.eml").write_bytes(eml_bytes({"n.xml": nfe_xml(numero=1)}))
    e = rodar_ciclo(ctx_de(base))
    assert any(p["codigo"] == "RECEITAS_CSV_INVALIDO" for p in e["pendencias_gerais"])
    assert "COMP_RECEITA_X_DECLARADA" in {a["regra"] for a in lote_de(e)[1]["achados"]}


def test_ofx_sem_exportacao_volta_quando_csv_chega(tmp_path):
    base = projeto(tmp_path)
    dom = base / "dados" / "dominio" / "101"
    plano, razao = (dom / "plano_contas.csv").read_text(encoding="utf-8"), (dom / "razao.csv").read_text(encoding="utf-8")
    (dom / "plano_contas.csv").unlink()
    (dom / "razao.csv").unlink()
    (base / "entrada" / "1.eml").write_bytes(eml_bytes({"e.ofx": ofx_bytes()}))
    e1 = rodar_ciclo(ctx_de(base))
    assert any(p["codigo"] == "SEM_EXPORTACAO_DOMINIO" for p in lote_de(e1, "CONTABIL")[1]["informativas"])
    (dom / "plano_contas.csv").write_text(plano, encoding="utf-8")
    (dom / "razao.csv").write_text(razao, encoding="utf-8")
    e2 = rodar_ciclo(ctx_de(base))  # novo processo do Agendador: versão da base mudou
    assert [a["fitid"] for a in lote_de(e2, "CONTABIL")[1]["acoes"]] == ["1"]


def test_valor_desconhecido_nao_e_zero_na_auto_aprovacao(tmp_path):
    base = projeto(tmp_path, auto=True)
    xml = nfe_xml(numero=1).replace(b"<vNF>100.00</vNF>", b"")
    (base / "entrada" / "1.eml").write_bytes(eml_bytes({"n.xml": xml}))
    e = rodar_ciclo(ctx_de(base))
    l, lote = lote_de(e)
    assert lote["acoes"][0]["valor"] is None and not l["aprovado"]
    assert any("valor desconhecido" in m for m in l["aguardando"])


def test_execucao_que_falhou_e_refeita(tmp_path, monkeypatch):
    base = projeto(tmp_path, auto=True)
    (base / "entrada" / "1.eml").write_bytes(eml_bytes({"n.xml": nfe_xml(numero=1)}))
    ctx = ctx_de(base)
    import mo_autonomo.fluxos.ciclo as C
    original = C.gravar
    monkeypatch.setattr(C, "gravar", lambda d, b: (_ for _ in ()).throw(OSError("D: indisponível")))
    e1 = rodar_ciclo(ctx)
    assert "ERRO" in e1["execucoes"][0]["resultado"][0]["status"]
    assert "Execuções com falha" in Path(e1["resumo"]).read_text(encoding="utf-8")
    assert "D: indisponível" in Path(e1["painel"]).read_text(encoding="utf-8")
    monkeypatch.setattr(C, "gravar", original)
    e2 = rodar_ciclo(ctx)
    assert e2["execucoes"][0]["refeita"] and e2["execucoes"][0]["resultado"][0]["status"] == "GRAVADO"
    assert ctx.trilha.acoes_com_falha() == []


def test_pdf_pendente_por_ia_desligada_volta_quando_liga(tmp_path):
    base = projeto(tmp_path)
    (base / "entrada" / "1.eml").write_bytes(eml_bytes({"g.pdf": pdf_com_texto(f"GUIA CNPJ {CNPJ_A} VALOR 150,00")}))
    cfg_path = base / "config" / "config.yaml"
    e1 = rodar_ciclo(montar_contexto(carregar_config(cfg_path), hoje=HOJE))
    assert any(p["codigo"] == "DOCUMENTO_NAO_PROCESSADO" for p in e1["pendencias_gerais"])

    class Prov:
        nome, local = "local", True

        def completar(self, s, u):
            return json.dumps({"tipo": "GUIA_TRIBUTO", "cnpj": CNPJ_A, "competencia": "2026-09", "valor": "150,00",
                               "confianca": 0.9, "resumo": "guia"})
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    cfg["ia"] = {"ativa": True, "provedores": []}
    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    from mo_autonomo.ia.cascata import Cascata
    e2 = rodar_ciclo(montar_contexto(carregar_config(cfg_path), hoje=HOJE, cascata=Cascata([Prov()])))
    assert len(e2["anexos"]) == 1 and lote_de(e2)[1]["acoes"][0]["tipo"] == "arquivar_documento"


def test_competencia_do_relatorio_dominio():
    from mo_autonomo.__main__ import _mesma_competencia
    assert _mesma_competencia("10/2026", "2026-10") and _mesma_competencia("15/10/2026", "2026-10")
    assert _mesma_competencia("2026-10", "2026-10") and not _mesma_competencia("09/2026", "2026-10")


def test_calendario_obrigacao_dois_meses_e_janela():
    from mo_autonomo.clientes.perfil import Perfis
    from mo_autonomo.normas.catalogo import Catalogo
    from mo_autonomo.obrigacoes.calendario import alertas, competencias_para_alerta, gerar
    from tests.conftest import CONFERIDA, carteira_teste
    cat = Catalogo.de_lista([{"id": "O", "titulo": "t", "area": "f", **CONFERIDA, "parametros": {"obrigacoes": [
        {"codigo": "M1", "dia": 9, "meses_apos_competencia": 1}, {"codigo": "M2", "dia": 9, "meses_apos_competencia": 2}]}}])
    hoje = date(2026, 10, 7)
    comps = competencias_para_alerta(hoje, cat)
    assert comps == ["2026-08", "2026-09", "2026-10"]
    p = Perfis(carteira_teste(), {}, cat)
    venc = [v for c in comps for v in gerar(c, {CNPJ_A: p.em(CNPJ_A, hoje)}, cat, set())]
    assert sorted(a["vencimento"].codigo for a in alertas(venc, hoje)) == ["M1", "M2"]
    assert alertas(venc, date(2026, 10, 8))  # 1 dia antes: ainda alerta (não depende do dia exato)


def test_irrf_sem_base_do_redutor_fica_inativo():
    from mo_autonomo.dp.folha import conferir
    from tests.conftest import CONFERIDA, PARAMS_TESTE
    from mo_autonomo.normas.catalogo import Catalogo
    p = json.loads(json.dumps(PARAMS_TESTE["TABELA_IRRF_MENSAL"]))
    del p["redutor"]["base"]
    cat = Catalogo.de_lista([{"id": "TABELA_IRRF_MENSAL", "titulo": "t", "area": "dp", **CONFERIDA, "parametros": p}])
    folha = [{"cpf": "x", "nome": "n", "competencia": "2026-09", "salario_contribuicao": Decimal("1"),
              "inss_descontado": Decimal("0"), "base_irrf": Decimal("2800.00"), "dependentes": 0,
              "irrf_descontado": Decimal("999.00")}]
    r = conferir(folha, CNPJ_A, cat)
    assert r["achados"] == [] and any("redutor.base" in i for i in r["inativas"])


def test_rascunho_nao_sobrescreve(tmp_path):
    from mo_autonomo.especialista.solicitacoes import salvar
    from tests.conftest import carteira_teste
    emp = carteira_teste().get(CNPJ_A)
    a = salvar(tmp_path, emp, "2026-10", "v1", "aaaa")
    a.write_text("editado pela pessoa", encoding="utf-8")
    assert salvar(tmp_path, emp, "2026-10", "v2", "aaaa").read_text(encoding="utf-8") == "editado pela pessoa"
    assert salvar(tmp_path, emp, "2026-10", "v2", "bbbb").read_text(encoding="utf-8") == "v2"


def test_ofx_reenviado_nao_duplica_lancamento(tmp_path):
    base = projeto(tmp_path)
    (base / "entrada" / "1.eml").write_bytes(eml_bytes({"e.ofx": ofx_bytes()}))
    (base / "entrada" / "2.eml").write_bytes(eml_bytes({"e2.ofx": ofx_bytes() + b"\n"}, assunto="reenvio"))
    e = rodar_ciclo(ctx_de(base))
    fitids = [a["fitid"] for l in e["lotes"] if l["area"] == "CONTABIL"
              for a in L.carregar(Path(l["arquivo"]))["acoes"]]
    assert fitids == ["1"]
