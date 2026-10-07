"""Regressões da 3ª revisão (máquina de estados de documentos, lotes e ações)."""
import json
from pathlib import Path

import pytest

from mo_autonomo.aprovacao import lote as L
from mo_autonomo.fluxos.ciclo import rodar_ciclo
from mo_autonomo.grafo.motor import ErroGrafo
from tests.conftest import CNPJ_A, CNPJ_X, eml_bytes, nfe_xml, ofx_bytes
from tests.test_ponta_a_ponta import ctx_de, projeto


def estado_acoes(ctx):
    return [r[0] for r in ctx.trilha.con.execute("SELECT estado FROM acoes ORDER BY em")]


def test_falha_na_analise_do_mes_nao_prende_acoes(tmp_path, monkeypatch):
    base = projeto(tmp_path, auto=True)
    (base / "entrada" / "1.eml").write_bytes(eml_bytes({"n.xml": nfe_xml(numero=1)}))
    ctx = ctx_de(base)
    import mo_autonomo.fluxos.ciclo as C
    original = C.avaliar_competencia
    monkeypatch.setattr(C, "avaliar_competencia", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("database is locked")))
    e1 = rodar_ciclo(ctx)
    lote = L.carregar(Path(e1["lotes"][0]["arquivo"]))
    assert lote["acoes"] == [] and lote["pendencias"][0]["codigo"] == "ERRO_ANALISE_MES"
    monkeypatch.setattr(C, "avaliar_competencia", original)
    e2 = rodar_ciclo(ctx)
    assert len(e2["anexos"]) == 1 and e2["execucoes"][0]["resultado"][0]["status"] == "GRAVADO"


def test_fitid_ausente_vira_pendencia_e_reuso_nao_some(tmp_path):
    base = projeto(tmp_path)
    sem = ofx_bytes(trans=(("20261005", "100.00", "PIX RECEBIDO CLIENTE A", ""),))
    sem = sem.replace(b"<FITID><MEMO>", b"<MEMO>")
    (base / "entrada" / "1.eml").write_bytes(eml_bytes({"s.ofx": sem}))
    e = rodar_ciclo(ctx_de(base))
    lote = L.carregar(Path(next(l for l in e["lotes"] if l["area"] == "CONTABIL")["arquivo"]))
    assert lote["acoes"] == [] and [p["codigo"] for p in lote["informativas"]] == ["SEM_FITID"]

    base2 = projeto(tmp_path / "b")
    ctx2 = ctx_de(base2)
    (base2 / "entrada" / "1.eml").write_bytes(eml_bytes({"set.ofx": ofx_bytes(trans=(("20260905", "10.00", "PIX RECEBIDO CLIENTE A", "1"),))}))
    rodar_ciclo(ctx2)
    (base2 / "entrada" / "2.eml").write_bytes(eml_bytes({"out.ofx": ofx_bytes(trans=(("20261005", "20.00", "PIX RECEBIDO CLIENTE B", "1"),))}, assunto="b"))
    e2 = rodar_ciclo(ctx2)
    novos = [l for l in e2["lotes"] if l["area"] == "CONTABIL" and not l.get("reapresentado")]
    assert [a["valor"] for a in L.carregar(Path(novos[0]["arquivo"]))["acoes"]] == ["20.00"]


def test_lote_nao_gravado_documento_volta(tmp_path, monkeypatch):
    base = projeto(tmp_path)
    (base / "entrada" / "1.eml").write_bytes(eml_bytes({"n.xml": nfe_xml(numero=1)}))
    ctx = ctx_de(base)
    original = L.salvar
    monkeypatch.setattr(L, "salvar", lambda *a, **k: (_ for _ in ()).throw(OSError("disco cheio")))
    e1 = rodar_ciclo(ctx)
    assert e1["lotes"] == [] and any(p["codigo"] == "ERRO_LOTE" for p in e1["pendencias_gerais"])
    monkeypatch.setattr(L, "salvar", original)
    e2 = rodar_ciclo(ctx)
    assert len(e2["anexos"]) == 1 and len(L.carregar(Path(e2["lotes"][0]["arquivo"]))["acoes"]) == 1


def test_lote_orfao_e_reapresentado_e_auto_aprovado(tmp_path, monkeypatch):
    base = projeto(tmp_path, auto=True)
    (base / "entrada" / "1.eml").write_bytes(eml_bytes({"n.xml": nfe_xml(numero=1)}))
    ctx = ctx_de(base)
    import mo_autonomo.fluxos.ciclo as C
    monkeypatch.setattr(C, "n_aprovar", lambda e, c: 1 / 0)
    with pytest.raises(ErroGrafo):
        rodar_ciclo(ctx)
    monkeypatch.undo()
    e2 = rodar_ciclo(ctx)
    assert any(l.get("reapresentado") and l.get("aprovado") for l in e2["lotes"])
    assert estado_acoes(ctx) == ["EXECUTADA"]


def test_sem_competencia_fica_pendente(tmp_path):
    base = projeto(tmp_path)
    xml = nfe_xml(numero=1).replace(b"<dhEmi>2026-10-01T10:00:00-03:00</dhEmi>", b"")
    (base / "entrada" / "1.eml").write_bytes(eml_bytes({"n.xml": xml}))
    ctx = ctx_de(base)
    rodar_ciclo(ctx)
    assert [d["situacao"] for d in ctx.trilha.documentos()] == ["PENDENTE"]


def test_achado_de_documento_retido_nao_trava_auto_aprovacao(tmp_path):
    base = projeto(tmp_path, auto=True)
    (base / "entrada" / "1.eml").write_bytes(eml_bytes({
        "ok.xml": nfe_xml(numero=1),
        "retido.xml": nfe_xml(emit=CNPJ_X, dest=CNPJ_A, tp_nf="0", numero=9, itens=(("1", "5102", "10.00"),))}))
    e = rodar_ciclo(ctx_de(base))
    assert e["lotes"][0]["aprovado"]
    lote = L.carregar(Path(e["lotes"][0]["arquivo"]))
    assert lote["achados_informativos"] and lote["informativas"]


def test_conflito_bloqueia_sem_repetir_toda_hora(tmp_path):
    base = projeto(tmp_path)
    (base / "entrada" / "1.eml").write_bytes(eml_bytes({"n.xml": nfe_xml(numero=1)}))
    ctx = ctx_de(base)
    e = rodar_ciclo(ctx)
    from mo_autonomo.dominio.pastas import TIPOS_PADRAO, caminho_destino
    lote = L.carregar(Path(e["lotes"][0]["arquivo"]))
    a = lote["acoes"][0]
    destino = caminho_destino(ctx.base_xml, TIPOS_PADRAO, ctx.carteira.get(CNPJ_A), a["pasta_tipo"], a["competencia"], a["nome"])
    destino.parent.mkdir(parents=True)
    destino.write_bytes(b"outro conteudo")
    aprovado = L.aprovar_humano(Path(e["lotes"][0]["arquivo"]), "APROVADO", lote["hash"], "P", ctx.trilha)
    from mo_autonomo.fluxos.ciclo import executar_lote
    assert executar_lote(aprovado, ctx)[0]["status"].startswith("CONFLITO")
    assert estado_acoes(ctx) == ["BLOQUEADA"]
    e2 = rodar_ciclo(ctx)
    assert e2["execucoes"] == [] and "Ações bloqueadas" in Path(e2["resumo"]).read_text(encoding="utf-8")


def test_falha_comum_tem_teto_de_tentativas(tmp_path, monkeypatch):
    base = projeto(tmp_path, auto=True)
    (base / "entrada" / "1.eml").write_bytes(eml_bytes({"n.xml": nfe_xml(numero=1)}))
    ctx = ctx_de(base)
    ctx.config["execucao"] = {"max_tentativas": 2}
    import mo_autonomo.fluxos.ciclo as C
    monkeypatch.setattr(C, "gravar", lambda d, b: (_ for _ in ()).throw(OSError("rede")))
    rodar_ciclo(ctx)
    assert estado_acoes(ctx) == ["FALHOU"]
    rodar_ciclo(ctx)
    assert estado_acoes(ctx) == ["BLOQUEADA"]
    assert rodar_ciclo(ctx)["execucoes"] == []


def test_reprocesso_sem_novidade_nao_gera_lote(tmp_path):
    import os
    import time
    base = projeto(tmp_path)
    (base / "entrada" / "1.eml").write_bytes(eml_bytes({"t.xml": nfe_xml(emit=CNPJ_X, dest=CNPJ_A, tp_nf="0", numero=9)}))
    assert len(rodar_ciclo(ctx_de(base))["lotes"]) == 1
    razao = base / "dados" / "dominio" / "101" / "razao.csv"
    for k in range(2):
        t = time.time() + 10 * (k + 1)
        os.utime(razao, (t, t))
        e = rodar_ciclo(ctx_de(base))
        assert len(e["anexos"]) == 1 and [l for l in e["lotes"] if not l.get("reapresentado")] == []
