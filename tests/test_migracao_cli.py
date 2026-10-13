"""Banco criado por versão anterior (sem colunas de vigência) continua funcionando pela linha de comando."""
from sqlalchemy import text

from mo_obrigacoes import db as dbmod
from mo_obrigacoes.cli import main
from mo_obrigacoes.models import Obrigacao


def test_cli_migra_banco_antigo(s, cfg):
    s.close()
    with dbmod.get_engine().begin() as con:
        con.execute(text("ALTER TABLE obrigacoes DROP COLUMN vigente_desde"))
        con.execute(text("ALTER TABLE obrigacoes DROP COLUMN vigente_ate"))
    main(["agenda", "--competencia", "2027-01"])  # antes da correção: OperationalError no such column
    s2 = dbmod.nova_sessao()
    pis = s2.query(Obrigacao).filter_by(codigo="PIS_COFINS").one()
    assert pis.vigente_ate == "2026-12"
    s2.close()
