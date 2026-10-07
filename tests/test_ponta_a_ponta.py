from pathlib import Path

import yaml

from mo_autonomo.aprovacao import lote as L
from mo_autonomo.fluxos.ciclo import executar_lote, grafo_ciclo, rodar_ciclo
from mo_autonomo.fluxos.contexto import carregar_config, montar_contexto
from tests.conftest import (CNPJ_A, CNPJ_B, CNPJ_X, CONFERIDA, HOJE, PARAMS_TESTE, TODAS, eml_bytes, evento_xml,
                            chave_nfe, nfe_xml, nfse_abrasf_xml, ofx_bytes, zip_bytes)


def projeto(tmp_path, conferidas=TODAS, auto=False):
    (tmp_path / "config" / "normas").mkdir(parents=True)
    normas = []
    for nid in TODAS:
        n = {"id": nid, "titulo": nid, "area": "teste"}
        if nid in conferidas:
            n.update(CONFERIDA, parametros=PARAMS_TESTE.get(nid, {}))
        normas.append(n)
    (tmp_path / "config" / "normas" / "teste.yaml").write_text(yaml.safe_dump(normas, allow_unicode=True), encoding="utf-8")
    (tmp_path / "config" / "empresas.csv").write_text(
        "codigo_dominio;apelido;cnpj;regime;codigo_apuracao;uf;municipio_ibge;ie;ativa\n"
        f"101;ALFA;{CNPJ_A};SIMPLES;;RJ;3304557;;S\n102;BETA;{CNPJ_B};PRESUMIDO;;RJ;3304557;;S\n", encoding="utf-8")
    (tmp_path / "config" / "contas_bancarias.csv").write_text(
        f"cnpj;banco;agencia;conta;conta_contabil\n{CNPJ_A};341;0001;12345;1.1.1.02\n", encoding="utf-8")
    cfg = {"modo": "simulacao", "pastas": {"dados": "dados", "normas": "config/normas"},
           "cadastro": {"empresas": "config/empresas.csv", "contas_bancarias": "config/contas_bancarias.csv"},
           "email": {"tipo": "pasta", "pasta_eml": "entrada"},
           "aprovacao_por_excecao": {"ativa": auto, "valor_limite": "0", "acoes_auto_permitidas": ["copiar_xml_rotina"]}}
    (tmp_path / "config" / "config.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    dom = tmp_path / "dados" / "dominio" / "101"
    dom.mkdir(parents=True)
    (dom / "plano_contas.csv").write_text("codigo;descricao;analitica\n1.1.1.02;Banco;S\n1.1.2.01;Clientes;S\n3.1.9.01;Tarifas;S\n",
                                          encoding="utf-8")
    (dom / "razao.csv").write_text(
        "data;conta_debito;conta_credito;valor;historico\n"
        "01/09/2026;1.1.1.02;1.1.2.01;10;PIX RECEBIDO CLIENTE X\n02/09/2026;1.1.1.02;1.1.2.01;10;PIX RECEBIDO CLIENTE Y\n",
        encoding="utf-8")
    (tmp_path / "entrada").mkdir()
    return tmp_path


def emails(base: Path):
    ok = zip_bytes({"n1.xml": nfe_xml(numero=1), "sub/n2.zip": zip_bytes({"n2.xml": nfe_xml(numero=2)})})
    (base / "entrada" / "1.eml").write_bytes(eml_bytes({"notas.zip": ok}, assunto="notas alfa"))
    (base / "entrada" / "2.eml").write_bytes(eml_bytes({
        "erro.xml": nfe_xml(emit=CNPJ_B, crt="1", numero=9),        # Presumido emitindo com CRT 1
        "servico.xml": nfse_abrasf_xml(),                           # ALFA presta para BETA
        "extrato.ofx": ofx_bytes(),
        "boleto.pdf": b"%PDF-1.4 sem texto",
        "lixo.txt": b"ola",
        "terceiro.xml": nfe_xml(emit=CNPJ_X, dest=None, numero=3),
        "cancel.xml": evento_xml(chave_nfe(CNPJ_A, 2)),
    }, assunto="diversos"))


def ctx_de(base):
    return montar_contexto(carregar_config(base / "config" / "config.yaml"), hoje=HOJE)


def test_ciclo_completo_simulacao(tmp_path):
    base = projeto(tmp_path)
    emails(base)
    ctx = ctx_de(base)
    e = rodar_ciclo(ctx)
    assert e["emails_lidos"] == 2 and len(e["anexos"]) == 9
    lotes = {l["id"].rsplit("_", 1)[0]: l for l in e["lotes"]}
    assert set(lotes) == {f"FISCAL_{CNPJ_A}_2026-10", f"FISCAL_{CNPJ_B}_2026-10", f"CONTABIL_{CNPJ_A}_2026-10"}

    alfa = L.carregar(Path(lotes[f"FISCAL_{CNPJ_A}_2026-10"]["arquivo"]))
    tipos = sorted(a["pasta_tipo"] for a in alfa["acoes"])
    assert tipos == ["NFE_EVENTOS", "NFE_SAIDA", "NFE_SAIDA", "NFSE_EMITIDA"]
    assert {a["regra"] for a in alfa["achados"]} == {"COMP_CANCELAMENTO"}

    beta = L.carregar(Path(lotes[f"FISCAL_{CNPJ_B}_2026-10"]["arquivo"]))
    regras_beta = {a["regra"] for a in beta["achados"]}
    assert {"NFE_CRT_REGIME", "NFSE_RETENCOES_FEDERAIS"} <= regras_beta

    contabil = L.carregar(Path(lotes[f"CONTABIL_{CNPJ_A}_2026-10"]["arquivo"]))
    assert len(contabil["acoes"]) == 1 and contabil["acoes"][0]["credito"] == "1.1.2.01"
    assert [p["codigo"] for p in contabil["pendencias"]] == ["SEM_CONTRAPARTIDA"]  # tarifa sem histórico

    gerais = {p["codigo"] for p in e["pendencias_gerais"]}
    assert {"DOCUMENTO_NAO_PROCESSADO", "ROTA_PENDENTE"} <= gerais  # pdf/lixo e nota de terceiro

    # simulação, auto-aprovação desligada: nada foi copiado para as pastas
    assert not (ctx.dados / "_STAGING").exists()
    assert all(not l.get("aprovado") for l in e["lotes"])
    assert Path(e["resumo"]).exists() and len(e["pareceres"]) == 2
    md = Path(e["pareceres"][0]["md"]).read_text(encoding="utf-8")
    assert "Parecer técnico" in md

    # aprovação humana do lote da ALFA e execução: grava no _STAGING
    p = Path(lotes[f"FISCAL_{CNPJ_A}_2026-10"]["arquivo"])
    aprovado = L.aprovar_humano(p, "APROVADO", alfa["hash"], "Pessoa de Teste", ctx.trilha)
    res = executar_lote(aprovado, ctx)
    assert all(r["status"] == "GRAVADO" for r in res)
    saida = ctx.base_xml / "NFE SAIDA" / "101-ALFA" / "102026"
    assert len(list(saida.glob("*.xml"))) == 2
    assert executar_lote(aprovado, ctx)[0]["status"] == "JA_EXISTIA"  # idempotente

    # segundo ciclo: nada novo (e-mails já lidos, anexos deduplicados)
    e2 = rodar_ciclo(ctx)
    assert e2["emails_lidos"] == 0 and e2["anexos"] == [] and e2["lotes"] == []

    # e-mail repetido com os mesmos anexos: dedupe por sha256
    (base / "entrada" / "3.eml").write_bytes(eml_bytes({"x.xml": nfe_xml(numero=1)}, assunto="reenvio"))
    e3 = rodar_ciclo(ctx)
    assert e3["emails_lidos"] == 1 and e3["anexos"] == []


def test_auto_aprovacao_por_excecao(tmp_path):
    base = projeto(tmp_path, auto=True)
    (base / "entrada" / "1.eml").write_bytes(eml_bytes({"n1.xml": nfe_xml(numero=1)}))
    ctx = ctx_de(base)
    e = rodar_ciclo(ctx)
    assert len(e["lotes"]) == 1 and e["lotes"][0]["aprovado"]
    assert e["execucoes"][0]["resultado"][0]["status"] == "GRAVADO"
    assert ctx.trilha.aprovacoes()[0][2] == "AUTO_APROVADO"


def test_auto_aprovacao_negada_com_achado(tmp_path):
    base = projeto(tmp_path, auto=True)
    (base / "entrada" / "1.eml").write_bytes(eml_bytes({"n1.xml": nfe_xml(numero=1, crt="3")}))
    e = rodar_ciclo(ctx_de(base))
    assert not e["lotes"][0]["aprovado"] and any("bloqueante" in m for m in e["lotes"][0]["aguardando"])


def test_sem_normas_conferidas_tudo_vira_pendencia(tmp_path):
    base = projeto(tmp_path, conferidas=[], auto=True)
    (base / "entrada" / "1.eml").write_bytes(eml_bytes({"n1.xml": nfe_xml(numero=1, crt="3")}))
    e = rodar_ciclo(ctx_de(base))
    lote = L.carregar(Path(e["lotes"][0]["arquivo"]))
    assert lote["acoes"] == [] and lote["pendencias"][0]["codigo"] == "ROTA_PENDENTE"
    assert not e["lotes"][0]["aprovado"]


def test_retomar_ciclo_interrompido(tmp_path, monkeypatch):
    base = projeto(tmp_path)
    (base / "entrada" / "1.eml").write_bytes(eml_bytes({"n1.xml": nfe_xml(numero=1)}))
    ctx = ctx_de(base)
    import mo_autonomo.fluxos.ciclo as C
    original = C.n_pareceres
    monkeypatch.setattr(C, "n_pareceres", lambda e, c: 1 / 0)
    try:
        rodar_ciclo(ctx, run_id="runX")
    except Exception:
        pass
    monkeypatch.setattr(C, "n_pareceres", original)
    e = grafo_ciclo().retomar("runX", ctx.trilha, ctx)
    assert Path(e["resumo"]).exists() and e["_historico"][-1] == "pareceres"
