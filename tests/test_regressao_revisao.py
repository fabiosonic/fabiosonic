"""Regressões dos achados da revisão adversarial (cada teste reproduz o ataque/falha original)."""
import json
from pathlib import Path

import pytest
import yaml

from mo_autonomo.clientes.cadastro import CadastroInvalido, Carteira
from mo_autonomo.dominio.pastas import TIPOS_PADRAO, DestinoInvalido, caminho_destino
from mo_autonomo.fluxos.ciclo import rodar_ciclo
from mo_autonomo.grafo.motor import FIM, ErroGrafo, Grafo
from mo_autonomo.ia.cascata import Cascata
from tests.conftest import (CNPJ_A, CNPJ_B, CNPJ_X, carteira_teste, eml_bytes, nfe_xml, nfse_abrasf_xml, ofx_bytes,
                            pdf_com_texto)
from tests.test_ponta_a_ponta import ctx_de, projeto


def test_path_traversal_no_codigo_de_verificacao_abrasf(tmp_path):
    base = projeto(tmp_path, auto=True)
    xml = nfse_abrasf_xml(valor="10.00").replace(b"<CodigoVerificacao>ABC", b"<CodigoVerificacao>/../../../../../../PWNED")
    (base / "entrada" / "1.eml").write_bytes(eml_bytes({"x.xml": xml}))
    ctx = ctx_de(base)
    e = rodar_ciclo(ctx)
    assert not list(tmp_path.rglob("PWNED*")) or all("XML NOTAS" in str(p) for p in tmp_path.rglob("PWNED*"))
    for ex in e["execucoes"]:
        for r in ex["resultado"]:
            assert str(ctx.base_xml.resolve()) in str(Path(r["destino"]).resolve())


def test_caminho_destino_recusa_fuga():
    emp = carteira_teste().get(CNPJ_A)
    with pytest.raises(DestinoInvalido):
        caminho_destino(Path("base_teste").resolve(), TIPOS_PADRAO, emp, "NFE_SAIDA", "../..-10", "x.xml")
    base = Path("base_teste").resolve()
    d = caminho_destino(base, TIPOS_PADRAO, emp, "NFE_SAIDA", "2026-10", "../../x.xml")
    assert d.name == "x.xml" and d.resolve().is_relative_to(base)


def test_cadastro_recusa_apelido_com_caminho(tmp_path):
    f = tmp_path / "e.csv"
    for apelido in ("../../../Windows", "A/B", "A\\B", "C:", "NOME."):
        f.write_text(f"codigo_dominio;apelido;cnpj;regime\n1;{apelido};{CNPJ_A};SIMPLES\n", encoding="utf-8")
        with pytest.raises(CadastroInvalido, match="caractere inválido"):
            Carteira.carregar(f)


def test_nome_de_anexo_gigante_nao_trava_o_ciclo(tmp_path):
    base = projeto(tmp_path)
    (base / "entrada" / "1.eml").write_bytes(eml_bytes({"ok.xml": nfe_xml(numero=1), ("x" * 300) + ".xml": nfe_xml(numero=2)}))
    (base / "entrada" / "2.eml").write_bytes(eml_bytes({"outro.xml": nfe_xml(emit=CNPJ_B, crt="3", numero=7)}, assunto="b"))
    e = rodar_ciclo(ctx_de(base))
    assert e["emails_lidos"] == 2 and len(e["anexos"]) == 3
    assert len(list((base / "dados" / "_BRUTO_EMAIL" / "emails").glob("*.eml"))) == 2  # e-mail bruto guardado


def test_conta_de_cnpj_fora_da_carteira_e_ofx_infinito_nao_abortam(tmp_path):
    base = projeto(tmp_path)
    (base / "config" / "contas_bancarias.csv").write_text(
        f"cnpj;banco;agencia;conta;conta_contabil\n{CNPJ_X};341;0001;12345;1.1.1.02\n", encoding="utf-8")
    (base / "entrada" / "1.eml").write_bytes(eml_bytes({"e.ofx": ofx_bytes(), "n.xml": nfe_xml(numero=1),
                                                        "ruim.ofx": ofx_bytes(trans=(("20261005", "Infinity", "X", "1"),))}))
    e = rodar_ciclo(ctx_de(base))
    cods = {p["codigo"] for p in e["pendencias_gerais"]}
    assert "CONTA_DE_EMPRESA_FORA_DA_CARTEIRA" in cods and "DOCUMENTO_NAO_PROCESSADO" in cods
    assert any(l["area"] == "FISCAL" for l in e["lotes"])  # a NF-e seguiu normalmente


def test_excecao_dentro_do_no_de_excecao_nao_entra_em_laco():
    g = Grafo("t")
    g.no("a", lambda e, c: 1 / 0)
    g.no("falha", lambda e, c: {})
    g.no("registrar", lambda e, c: e["nao_existe"])
    g.ligar("a", FIM)
    g.ligar("falha", "registrar")
    g.ligar("registrar", FIM)
    g.excecao("falha")
    with pytest.raises(ErroGrafo, match="KeyError"):
        g.executar({})


def test_anexo_capturado_e_nao_processado_volta(tmp_path, monkeypatch):
    base = projeto(tmp_path)
    (base / "entrada" / "1.eml").write_bytes(eml_bytes({"n.xml": nfe_xml(numero=1)}))
    ctx = ctx_de(base)
    import mo_autonomo.fluxos.ciclo as C
    monkeypatch.setattr(C, "n_processar", lambda e, c: 1 / 0)
    with pytest.raises(ErroGrafo):
        rodar_ciclo(ctx)
    monkeypatch.undo()
    e = rodar_ciclo(ctx)  # novo run (Agendador), não retomar
    assert e["emails_lidos"] == 0 and len(e["anexos"]) == 1 and len(e["lotes"]) == 1


def test_pendencia_reprocessa_quando_norma_passa_a_conferida(tmp_path):
    base = projeto(tmp_path, conferidas=[])
    (base / "entrada" / "1.eml").write_bytes(eml_bytes({"n.xml": nfe_xml(numero=1)}))
    e1 = rodar_ciclo(ctx_de(base))
    assert e1["lotes"][0]["aguardando"] and not json.loads(Path(e1["lotes"][0]["arquivo"]).read_text())["acoes"]
    assert rodar_ciclo(ctx_de(base))["anexos"] == []  # mesma base: não reprocessa à toa
    projeto_conferido = projeto(tmp_path / "ref")
    (base / "config" / "normas" / "teste.yaml").write_text(
        (projeto_conferido / "config" / "normas" / "teste.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    e3 = rodar_ciclo(ctx_de(base))
    assert len(e3["anexos"]) == 1
    lote = json.loads(Path(e3["lotes"][0]["arquivo"]).read_text())
    assert [a["pasta_tipo"] for a in lote["acoes"]] == ["NFE_SAIDA"]


def test_sequencia_considera_ciclos_anteriores(tmp_path):
    base = projeto(tmp_path)
    (base / "entrada" / "1.eml").write_bytes(eml_bytes({f"{n}.xml": nfe_xml(numero=n) for n in (2, 3, 4)}))
    ctx = ctx_de(base)
    rodar_ciclo(ctx)
    (base / "entrada" / "2.eml").write_bytes(eml_bytes({"1.xml": nfe_xml(numero=1), "5.xml": nfe_xml(numero=5)}, assunto="b"))
    e = rodar_ciclo(ctx)
    lote = json.loads(Path(e["lotes"][0]["arquivo"]).read_text())
    assert "COMP_SEQUENCIA" not in {a["regra"] for a in lote["achados"]}


def test_ofx_sobreposto_e_virada_de_mes(tmp_path):
    base = projeto(tmp_path)
    trans = (("20260929", "100.00", "PIX RECEBIDO CLIENTE Z", "F1"), ("20261002", "200.00", "PIX RECEBIDO CLIENTE W", "F2"))
    (base / "entrada" / "1.eml").write_bytes(eml_bytes({"a.ofx": ofx_bytes(trans=trans)}))
    ctx = ctx_de(base)
    e = rodar_ciclo(ctx)
    comps = sorted(l["competencia"] for l in e["lotes"] if l["area"] == "CONTABIL")
    assert comps == ["2026-09", "2026-10"]
    trans2 = trans[1:] + (("20261003", "300.00", "PIX RECEBIDO CLIENTE V", "F3"),)
    (base / "entrada" / "2.eml").write_bytes(eml_bytes({"b.ofx": ofx_bytes(trans=trans2)}, assunto="b"))
    e2 = rodar_ciclo(ctx)
    lotes = [json.loads(Path(l["arquivo"]).read_text()) for l in e2["lotes"] if l["area"] == "CONTABIL"]
    fitids = [a["fitid"] for l in lotes for a in l["acoes"]]
    assert fitids == ["F3"]  # F2 já tinha sido proposto


def test_pdf_lido_pela_ia_e_arquivado_ou_pendente(tmp_path):
    class Prov:
        nome, local = "local", True

        def __init__(self, cnpj):
            self.cnpj = cnpj

        def completar(self, s, u):
            return json.dumps({"tipo": "GUIA_TRIBUTO", "cnpj": self.cnpj, "competencia": "2026-09",
                               "valor": "150,00", "confianca": 0.95, "resumo": "guia"})

    from mo_autonomo.fluxos.contexto import carregar_config, montar_contexto
    from tests.conftest import HOJE
    base = projeto(tmp_path, auto=True)
    pdf = pdf_com_texto(f"GUIA CNPJ {CNPJ_A} VALOR 150,00")
    (base / "entrada" / "1.eml").write_bytes(eml_bytes({"guia.pdf": pdf}))
    ctx = montar_contexto(carregar_config(base / "config" / "config.yaml"), hoje=HOJE, cascata=Cascata([Prov(CNPJ_A)]))
    e = rodar_ciclo(ctx)
    lote = json.loads(Path(e["lotes"][0]["arquivo"]).read_text())
    assert lote["acoes"][0]["tipo"] == "arquivar_documento" and lote["acoes"][0]["valor"] == "150.00"
    # auto-aprovação não cobre arquivar_documento (não está em acoes_auto_permitidas): aguarda
    assert not e["lotes"][0]["aprovado"]
    # CNPJ que não está no texto: vira pendência, não some
    base2 = projeto(tmp_path / "b")
    (base2 / "entrada" / "1.eml").write_bytes(eml_bytes({"guia.pdf": pdf_com_texto("GUIA VALOR 150,00")}))
    ctx2 = montar_contexto(carregar_config(base2 / "config" / "config.yaml"), hoje=HOJE, cascata=Cascata([Prov(None)]))
    e2 = rodar_ciclo(ctx2)
    assert any(p["codigo"] == "DOCUMENTO_A_ARQUIVAR" for p in e2["pendencias_gerais"])
