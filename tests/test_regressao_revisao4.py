"""Regressões da 4ª revisão (convergência)."""
from pathlib import Path

from mo_autonomo.aprovacao import lote as L
from mo_autonomo.fluxos.ciclo import rodar_ciclo
from tests.conftest import eml_bytes, nfe_xml, ofx_bytes, zip_bytes
from tests.test_ponta_a_ponta import ctx_de, projeto


def test_lote_aprovado_por_pessoa_e_executado_no_proximo_ciclo(tmp_path):
    base = projeto(tmp_path)
    (base / "entrada" / "1.eml").write_bytes(eml_bytes({"n.xml": nfe_xml(numero=1)}))
    ctx = ctx_de(base)
    e = rodar_ciclo(ctx)
    lote = L.carregar(Path(e["lotes"][0]["arquivo"]))
    L.aprovar_humano(Path(e["lotes"][0]["arquivo"]), "APROVADO", lote["hash"], "Pessoa", ctx.trilha)
    e2 = rodar_ciclo(ctx)
    assert e2["execucoes"][0]["resultado"][0]["status"] == "GRAVADO"
    assert rodar_ciclo(ctx)["execucoes"] == []  # não repete


def test_zip_corrompido_nao_derruba_anexo_bom(tmp_path):
    base = projeto(tmp_path)
    ruim = zip_bytes({"x.xml": b"<a/>" * 100})[:40]
    (base / "entrada" / "1.eml").write_bytes(eml_bytes({"boa.xml": nfe_xml(numero=1), "ruim.zip": ruim}))
    ctx = ctx_de(base)
    e = rodar_ciclo(ctx)
    assert len(e["anexos"]) == 2 and len(L.carregar(Path(e["lotes"][0]["arquivo"]))["acoes"]) == 1
    situacoes = sorted(d["situacao"] for d in ctx.trilha.documentos())
    assert situacoes == ["OK", "PENDENTE"]  # o ZIP ruim fica pendente na trilha (durável)


def test_caixa_fora_do_ar_nao_para_o_ciclo(tmp_path):
    base = projeto(tmp_path, auto=True)
    (base / "entrada" / "1.eml").write_bytes(eml_bytes({"n.xml": nfe_xml(numero=1)}))
    ctx = ctx_de(base)

    class Fora:
        def mensagens(self, ja_lido=None):
            raise OSError("Email em Nuvem indisponível")
            yield  # noqa
    ctx.fonte = Fora()
    e = rodar_ciclo(ctx)
    assert any(p["codigo"] == "FONTE_EMAIL_INDISPONIVEL" for p in e["pendencias_gerais"])
    assert Path(e["resumo"]).exists() and Path(e["painel"]).exists()


def test_csv_ansi_do_windows(tmp_path):
    base = projeto(tmp_path)
    dom = base / "dados" / "dominio" / "101"
    (dom / "razao.csv").write_bytes(
        ("data;conta_debito;conta_credito;valor;historico\n"
         "01/09/2026;3.1.9.01;1.1.1.02;10;TARIFA BANCÁRIA PACOTE\n"
         "02/09/2026;3.1.9.01;1.1.1.02;10;TARIFA BANCÁRIA PACOTE\n").encode("cp1252"))
    emp = base / "config" / "empresas.csv"
    emp.write_bytes(emp.read_text(encoding="utf-8").replace("ALFA", "ALFA COMÉRCIO").encode("cp1252"))
    (base / "entrada" / "1.eml").write_bytes(eml_bytes({"e.ofx": ofx_bytes()}))
    e = rodar_ciclo(ctx_de(base))
    lote = L.carregar(Path(next(l for l in e["lotes"] if l["area"] == "CONTABIL")["arquivo"]))
    assert [a["debito"] for a in lote["acoes"]] == ["3.1.9.01"]
    assert not any(p["codigo"] == "ERRO_CONTABIL" for p in lote["informativas"])


def test_uma_caixa_fora_do_ar_vira_pendencia_e_as_outras_seguem(tmp_path):
    from mo_autonomo.entrada.fontes import FontePastaEml, FonteMultipla
    base = projeto(tmp_path)
    (base / "entrada" / "1.eml").write_bytes(eml_bytes({"n.xml": nfe_xml(numero=1)}))
    ctx = ctx_de(base)

    class Fora:
        usuario = "dp@exemplo.test"

        def mensagens(self, ja_lido=None):
            raise OSError("senha não está no cofre")
            yield  # noqa
    ctx.fonte = FonteMultipla([Fora(), FontePastaEml(base / "entrada")])
    e = rodar_ciclo(ctx)
    assert e["emails_lidos"] == 1 and len(e["lotes"]) == 1
    assert any("dp@exemplo.test" in p["mensagem"] for p in e["pendencias_gerais"] if p["codigo"] == "FONTE_EMAIL_INDISPONIVEL")
