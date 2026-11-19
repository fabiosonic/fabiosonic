"""Engine/sessões e aplicação de migrations."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

_engines: dict[str, Engine] = {}


def obter_engine(url: str) -> Engine:
    if url not in _engines:
        kw: dict = {"future": True, "pool_pre_ping": True}
        if url.startswith("sqlite"):
            kw["connect_args"] = {"check_same_thread": False, "timeout": 30}
        eng = create_engine(url, **kw)
        if url.startswith("sqlite"):
            @event.listens_for(eng, "connect")
            def _pragmas(dbapi_con, _):  # noqa: ANN001
                cur = dbapi_con.cursor()
                cur.execute("PRAGMA journal_mode=WAL")
                cur.execute("PRAGMA foreign_keys=ON")
                cur.execute("PRAGMA busy_timeout=30000")
                cur.close()
        _engines[url] = eng
    return _engines[url]


def fabrica(url: str) -> sessionmaker[Session]:
    return sessionmaker(bind=obter_engine(url), expire_on_commit=False, future=True)


@contextmanager
def sessao(url: str) -> Iterator[Session]:
    s = fabrica(url)()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def aplicar_migrations(url: str) -> None:
    """Executa ``alembic upgrade head`` programaticamente."""
    from alembic import command
    from alembic.config import Config

    pasta = Path(__file__).resolve().parent.parent / "migrations"
    cfg = Config()
    cfg.set_main_option("script_location", str(pasta))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(cfg, "head")
