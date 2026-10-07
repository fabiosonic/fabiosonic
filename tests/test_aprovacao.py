import json

import pytest

from mo_autonomo.aprovacao import lote as L
from mo_autonomo.trilha.auditoria import Trilha

POL = {"ativa": True, "valor_limite": "1000", "acoes_auto_permitidas": ["copiar_xml_rotina"]}
ACAO = {"tipo": "copiar_xml_rotina", "valor": "0"}
CTRL = {"natureza": "CONTROLE", "bloqueia": False}


def salvar(tmp_path, acoes=(ACAO,), achados=(), pend=()):
    lote = L.montar_lote("T1", list(acoes), list(achados), list(pend))
    return L.salvar(lote, tmp_path), lote


def test_aprovacao_humana(tmp_path):
    p, lote = salvar(tmp_path)
    t = Trilha(":memory:")
    with pytest.raises(L.AprovacaoRecusada, match="exatamente"):
        L.aprovar_humano(p, "aprovado", lote["hash"], "Fulano")
    with pytest.raises(L.AprovacaoRecusada, match="exatamente"):
        L.aprovar_humano(p, "APROVADO ", lote["hash"], "Fulano")
    with pytest.raises(L.AprovacaoRecusada, match="hash"):
        L.aprovar_humano(p, "APROVADO", "x", "Fulano")
    destino = L.aprovar_humano(p, "APROVADO", lote["hash"], "Fulano", t)
    assert destino.name == "APROVADO_T1.json" and t.aprovacoes()[0][2] == "HUMANO"
    assert L.exigir_aprovado(destino)["id"] == "T1"


def test_pendencia_impede_aprovacao_humana(tmp_path):
    p, lote = salvar(tmp_path, pend=[{"codigo": "X"}])
    with pytest.raises(L.AprovacaoRecusada, match="pendência"):
        L.aprovar_humano(p, "APROVADO", lote["hash"], "Fulano")


def test_lote_adulterado(tmp_path):
    p, lote = salvar(tmp_path)
    dados = json.loads(p.read_text())
    dados["acoes"][0]["tipo"] = "pagar_guia"
    p.write_text(json.dumps(dados))
    with pytest.raises(L.AprovacaoRecusada, match="adulterado"):
        L.carregar(p)


def test_auto_aprovacao_condicoes(tmp_path):
    t = Trilha(":memory:")
    p, _ = salvar(tmp_path, achados=[CTRL])
    assert L.aprovar_auto(p, POL, t) is not None
    assert t.aprovacoes()[0][2] == "AUTO_APROVADO"
    casos = [
        ({**POL, "ativa": False}, {}, "desligada"),
        (POL, {"pend": [{"codigo": "X"}]}, "pendência"),
        (POL, {"achados": [{"natureza": "CONTROLE", "bloqueia": True}]}, "bloqueante"),
        (POL, {"achados": [{"natureza": "INDÍCIO", "bloqueia": False}]}, "INDÍCIO/APONTAMENTO"),
        (POL, {"acoes": [{"tipo": "lancamento_contabil", "valor": "1"}]}, "fora de acoes_auto"),
        (POL, {"acoes": [{"tipo": "copiar_xml_rotina", "valor": "5000"}]}, "acima do limite"),
        ({**POL, "valor_limite": None}, {}, "valor_limite"),
        ({**POL, "acoes_auto_permitidas": ["pagar_guia"]}, {"acoes": [{"tipo": "pagar_guia", "valor": "1"}]},
         "sempre exige"),
    ]
    for pol, kw, motivo in casos:
        p, lote = salvar(tmp_path, **kw)
        av = L.avaliar_auto(lote, pol)
        assert not av.pode_auto and any(motivo in m for m in av.motivos), (motivo, av.motivos)
        assert L.aprovar_auto(p, pol) is None


def test_executor_exige_aprovado(tmp_path):
    p, _ = salvar(tmp_path)
    with pytest.raises(L.AprovacaoRecusada, match="APROVADO_"):
        L.exigir_aprovado(p)
    falso = tmp_path / "APROVADO_falso.json"
    falso.write_text(p.read_text())
    with pytest.raises(L.AprovacaoRecusada, match="inválido"):
        L.exigir_aprovado(falso)


def test_sempre_humano_nao_passa_em_auto_mesmo_forjado(tmp_path):
    lote = L.montar_lote("T9", [{"tipo": "transmitir_declaracao", "valor": "0"}], [], [])
    destino = L._gravar_aprovado(lote, tmp_path, "AUTO_APROVADO", "forjado")
    with pytest.raises(L.AprovacaoRecusada, match="humana"):
        L.exigir_aprovado(destino)
