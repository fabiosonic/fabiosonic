"""Revisão 8: lançamento bloqueado recuperável só pelo próprio lote, plano do Domínio sem escolher
lado nem sobrescrever, vigência da norma nas regras de competência."""
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from mo_autonomo.aprovacao import lote as L
from mo_autonomo.contabil.plano_dominio import importar_pasta, ler
from mo_autonomo.especialista.motor import avaliar_competencia, cobertura
from mo_autonomo.fluxos.ciclo import _destino_importacao, executar_lote, rodar_ciclo
from mo_autonomo.normas.catalogo import Catalogo
from tests.conftest import carteira_teste, eml_bytes, ofx_bytes
from tests.test_exportador_dominio import _projeto_reduzido
from tests.test_plano_dominio import CAB, arquivo, bloco
from tests.test_ponta_a_ponta import ctx_de


def _lote_com_conflito(tmp_path):
    base = _projeto_reduzido(tmp_path)
    (base / "entrada" / "1.eml").write_bytes(eml_bytes({"e.ofx": ofx_bytes()}))
    ctx = ctx_de(base)
    l = next(x for x in rodar_ciclo(ctx)["lotes"] if x["area"] == "CONTABIL")
    lote = L.carregar(Path(l["arquivo"]))
    ap = L.aprovar_humano(Path(l["arquivo"]), "APROVADO", lote["hash"], "Pessoa", ctx.trilha)
    dest = _destino_importacao(ctx, lote["acoes"][0], lote["id"][-8:])
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"outro conteudo")
    assert executar_lote(ap, ctx)[0]["status"].startswith("CONFLITO")
    return base, ctx, ap, dest


def test_bloqueada_volta_a_exportar_quando_a_pessoa_reexecuta_o_lote(tmp_path):
    _, ctx, ap, dest = _lote_com_conflito(tmp_path)
    dest.unlink()  # pessoa resolveu o conflito
    r = executar_lote(ap, ctx)
    assert r[0]["status"] == "GRAVADO" and r[0]["lancamentos"] == 2


def test_aprovacao_antiga_nao_exporta_lancamento_de_outro_lote(tmp_path):
    base, ctx, ap, dest = _lote_com_conflito(tmp_path)
    dest.unlink()
    trans = (("20261005", "1500.00", "PIX RECEBIDO CLIENTE ALFA", "1"), ("20261006", "-320.50", "TARIFA BANCARIA PACOTE", "2"),
             ("20261007", "-320.50", "TARIFA BANCARIA PACOTE", "3"))
    (base / "entrada" / "2.eml").write_bytes(eml_bytes({"f.ofx": ofx_bytes(trans=trans)}, assunto="extrato completo"))
    rodar_ciclo(ctx)  # os lançamentos bloqueados passam para o lote novo (ainda sem aprovação)
    r = executar_lote(ap, ctx)
    assert all(x["status"].startswith("IGNORADO") for x in r if x["acao"] == "lancamento_contabil")
    assert not dest.exists()


def test_dois_arquivos_para_o_mesmo_codigo_nenhum_importa(tmp_path):
    pasta = tmp_path / "planos"
    pasta.mkdir()
    arquivo(pasta / "0101 - OUTRA.csv")
    arquivo(pasta / "101 - ALFA.csv")
    r = importar_pasta(pasta, carteira_teste(), tmp_path / "dominio")
    assert not r["importados"] and sum("nenhum foi importado" in e for e in r["erros"]) == 2


def test_plano_existente_so_troca_com_sobrescrever_e_guarda_bak(tmp_path):
    pasta = tmp_path / "planos"
    pasta.mkdir()
    arquivo(pasta / "101 - ALFA.csv")
    destino = tmp_path / "dominio" / "101" / "plano_contas.csv"
    destino.parent.mkdir(parents=True)
    destino.write_text("codigo;descricao;analitica\n862;Banco;S\n", encoding="utf-8")
    r = importar_pasta(pasta, carteira_teste(), tmp_path / "dominio")
    assert not r["importados"] and "862;Banco" in destino.read_text(encoding="utf-8")
    r = importar_pasta(pasta, carteira_teste(), tmp_path / "dominio", sobrescrever=True)
    assert r["importados"] and list(destino.parent.glob("plano_contas.*.bak"))


def test_conta_tipo_t_sem_filha_nao_aceita_lancamento(tmp_path):
    p = tmp_path / "p.csv"
    p.write_bytes((CAB + bloco(1, "01", "T", "ATIVO") + bloco(9, "01.2", "T", "GRUPO VAZIO")).encode("cp1252"))
    por = {c["codigo"]: c for c in ler(p)}
    assert not por["9"]["analitica"] and por["9"]["divergente"]


def _catalogo_vencido():
    return Catalogo.de_lista([{
        "id": "MOC_NFE", "titulo": "MOC", "status": "CONFERIDO", "fonte_url": "https://www.nfe.fazenda.gov.br/x",
        "conferido_por": "Fulano", "conferido_em": "2026-01-01", "vigencia": {"inicio": "2010-01-01", "fim": "2020-12-31"},
        "parametros": {"tp_evento_cancelamento": ["X"], "cstat_evento_homologado": ["Y"], "cstat_autorizado": ["Z"]}}])


def test_regra_de_competencia_respeita_vigencia_da_norma():
    p = SimpleNamespace(cnpj="11222333000181", regime="SIMPLES")
    docs = [{"tipo": "EVENTO_CANC", "chave_ref": "K1", "tp_evento": "X", "autorizacao_cstat": "Y", "_sha256": "s"}]
    assert avaliar_competencia(docs, p, "2026-10", _catalogo_vencido(), date(2026, 10, 7)) == []
    c = {x["regra"]: x for x in cobertura(_catalogo_vencido(), em=date(2026, 10, 7))}
    assert not c["COMP_CANCELAMENTO"]["ativa"]
