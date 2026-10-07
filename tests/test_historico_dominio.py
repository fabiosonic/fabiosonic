"""De-para aprendendo com os TXT já importados no Domínio (padrões reais do escritório, códigos fictícios)."""
from datetime import date
from decimal import Decimal

from mo_autonomo.contabil.lancamentos import DePara, PlanoContas, historico_empresa, ler_txt_dominio, propor

BANCO = "861"
TXT = ("20/06/2026;593;861;150,00;PGTO AUTOMATICO CGMP SEM PARAR;1;;;;;;\r\n"
       "18/06/2026;593;861;150,00;PGTO AUTOMATICO CGMP SEM PARAR;1;;;;;;\r\n"
       "20/05/2026;604;861;9,80;TARIFAS BANCARIAS CFE EXTRATO TAR;1;;;;;;\r\n"
       "19/05/2026;604;861;9,80;TARIFAS BANCARIAS CFE EXTRATO TAR;1;;;;;;\r\n"
       "17/06/2026;863;861;15400,00;VALOR TRANSFERENCIA ENTRE CONTAS - BRADESCO / BANCO X;1;;;;;;\r\n"
       "21/05/2026;9;861;30000,00;VALOR TRANSFERENCIA ENTRE CONTAS - BRADESCO / CAIXA;1;;;;;;\r\n"
       "02/04/2026;861;432;373,42;RENDIMENTO LIQUIDO RECEBIDO NO BANCO;1;;;;;;\r\n"
       "02/03/2026;861;432;12,00;RENDIMENTO LIQUIDO RECEBIDO NO BANCO;1;;;;;;\r\n"
       "linha estranha que nao e lancamento\r\n")
PLANO = PlanoContas({c: {"descricao": c, "analitica": True} for c in ("861", "593", "604", "863", "9", "432")})


def ofx(*trans):
    return {"transacoes": [{"fitid": str(i), "data": date(2026, 7, 1), "valor": Decimal(v), "memo": m}
                           for i, (v, m) in enumerate(trans)]}


def test_aprende_com_txt_do_dominio(tmp_path):
    (tmp_path / "historico").mkdir()
    (tmp_path / "historico" / "Dominio-LMG-Bradesco.txt").write_bytes(TXT.encode("cp1252"))
    linhas = historico_empresa(tmp_path)
    assert len(linhas) == 8 and linhas == ler_txt_dominio(tmp_path / "historico" / "Dominio-LMG-Bradesco.txt")
    r = propor(ofx(("-150.00", "PGTO AUTOMATICO CGMP SEM PARAR"), ("-9.80", "TARIFAS BANCARIAS CFE EXTRATO"),
                   ("50.00", "RENDIMENTO LIQUIDO RECEBIDO"), ("-1000.00", "VALOR TRANSFERENCIA ENTRE CONTAS")),
               BANCO, DePara.do_razao(linhas, BANCO), PLANO)
    got = {l["historico"][:10]: (l["debito"], l["credito"]) for l in r["lancamentos"]}
    assert got == {"PGTO AUTOM": ("593", "861"), "TARIFAS BA": ("604", "861"), "RENDIMENTO": ("861", "432")}
    # transferência: mesmo histórico, destinos diferentes no passado -> pendência, não chute
    assert [p["codigo"] for p in r["pendencias"]] == ["SEM_CONTRAPARTIDA"]
    assert "ambígua" in r["pendencias"][0]["mensagem"] or "mínimo" in r["pendencias"][0]["mensagem"]


def test_sem_historico_nem_razao_fica_vazio(tmp_path):
    assert historico_empresa(tmp_path) == []
