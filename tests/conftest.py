import pytest

from mo_obrigacoes import db as dbmod
from mo_obrigacoes.catalogo import sincronizar_catalogo
from mo_obrigacoes.config import Config, set_config


@pytest.fixture()
def cfg(tmp_path):
    c = Config(database_url=f"sqlite:///{tmp_path}/t.db", local_drive_path=str(tmp_path / "drive"),
               admin_password="segredo", email_gestor="gestor@mo.com.br", cobranca_automatica_cliente=True)
    set_config(c)
    dbmod.init_engine(c.database_url)
    dbmod.criar_tabelas()
    return c


@pytest.fixture()
def s(cfg):
    sess = dbmod.nova_sessao()
    sincronizar_catalogo(sess)
    sess.commit()
    yield sess
    sess.close()
