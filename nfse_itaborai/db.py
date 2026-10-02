"""Banco local (SQLite, dados/sistema.db): contratos, contas a receber/pagar, cobrança e conciliação.

Valores monetários são guardados em centavos (inteiros) para não haver erro de arredondamento.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from . import emissor

ESQUEMA = """
CREATE TABLE IF NOT EXISTS contratos (
    id INTEGER PRIMARY KEY,
    cpf_cnpj TEXT NOT NULL,
    descricao TEXT NOT NULL,
    valor_cent INTEGER NOT NULL,
    dia_vencimento INTEGER NOT NULL DEFAULT 10,
    inicio TEXT NOT NULL,                -- AAAA-MM
    fim TEXT DEFAULT '',                 -- AAAA-MM ('' = sem fim)
    ativo INTEGER NOT NULL DEFAULT 1,
    emitir_nfse INTEGER NOT NULL DEFAULT 1,
    mes_reajuste INTEGER DEFAULT 0,      -- 1..12 (0 = sem reajuste automático)
    reajuste_pct REAL DEFAULT 0,
    ultimo_reajuste INTEGER DEFAULT 0,   -- ano
    observacao TEXT DEFAULT '',
    criado_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS titulos (
    id INTEGER PRIMARY KEY,
    cpf_cnpj TEXT NOT NULL,
    cliente_nome TEXT NOT NULL,
    contrato_id INTEGER,
    competencia TEXT NOT NULL,           -- AAAA-MM
    descricao TEXT NOT NULL,
    valor_cent INTEGER NOT NULL,
    vencimento TEXT NOT NULL,            -- AAAA-MM-DD
    status TEXT NOT NULL DEFAULT 'aberto',   -- aberto | pago | cancelado
    data_pagamento TEXT DEFAULT '',
    valor_pago_cent INTEGER DEFAULT 0,
    forma_pagamento TEXT DEFAULT '',
    nfse_status TEXT NOT NULL DEFAULT 'pendente',  -- pendente | emitida | teste | erro | nao_emitir
    nfse_numero TEXT DEFAULT '',
    nfse_rps TEXT DEFAULT '',
    nfse_link TEXT DEFAULT '',
    nfse_erro TEXT DEFAULT '',
    asaas_id TEXT DEFAULT '',
    cobranca_link TEXT DEFAULT '',
    pix_copia_cola TEXT DEFAULT '',
    linha_digitavel TEXT DEFAULT '',
    observacao TEXT DEFAULT '',
    criado_em TEXT NOT NULL,
    UNIQUE (contrato_id, competencia)
);
CREATE INDEX IF NOT EXISTS ix_titulos_venc ON titulos(vencimento);
CREATE INDEX IF NOT EXISTS ix_titulos_cli ON titulos(cpf_cnpj);
CREATE TABLE IF NOT EXISTS eventos_cobranca (
    id INTEGER PRIMARY KEY,
    titulo_id INTEGER NOT NULL,
    etapa INTEGER NOT NULL,              -- dias em relação ao vencimento (-3, 0, 5...)
    canal TEXT NOT NULL,                 -- email | whatsapp
    data TEXT NOT NULL,
    status TEXT NOT NULL,                -- enviado | pendente | sem_contato | erro | feito
    detalhe TEXT DEFAULT '',
    UNIQUE (titulo_id, etapa, canal)
);
CREATE TABLE IF NOT EXISTS despesas (
    id INTEGER PRIMARY KEY,
    descricao TEXT NOT NULL,
    fornecedor TEXT DEFAULT '',
    categoria TEXT NOT NULL DEFAULT 'Outras',
    valor_cent INTEGER NOT NULL,
    vencimento TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'aberto',   -- aberto | pago | cancelado
    data_pagamento TEXT DEFAULT '',
    recorrente INTEGER NOT NULL DEFAULT 0,
    origem_id INTEGER,                       -- despesa recorrente que gerou esta
    competencia TEXT DEFAULT '',
    criado_em TEXT NOT NULL,
    UNIQUE (origem_id, competencia)
);
CREATE TABLE IF NOT EXISTS movimentos (
    id INTEGER PRIMARY KEY,
    data TEXT NOT NULL,
    valor_cent INTEGER NOT NULL,             -- + crédito / - débito
    descricao TEXT DEFAULT '',
    fitid TEXT UNIQUE,
    titulo_id INTEGER,
    despesa_id INTEGER,
    importado_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS arquivos_processados (
    caminho TEXT PRIMARY KEY,
    mtime REAL NOT NULL,
    quando TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS log (
    id INTEGER PRIMARY KEY,
    quando TEXT NOT NULL,
    tipo TEXT NOT NULL,
    mensagem TEXT NOT NULL
);
"""


def caminho() -> Path:
    return emissor.RAIZ / "dados" / "sistema.db"


@contextmanager
def conexao():
    arq = caminho()
    arq.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(arq, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(ESQUEMA)
    _migrar(con)
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


# Colunas acrescentadas depois da primeira versão (bancos antigos recebem o ALTER TABLE).
MIGRACOES = {
    "contratos": {"confirmado": "INTEGER NOT NULL DEFAULT 1", "origem": "TEXT DEFAULT 'manual'"},
    "titulos": {"origem": "TEXT DEFAULT 'sistema'"},
}


def _migrar(con: sqlite3.Connection) -> None:
    for tabela, colunas in MIGRACOES.items():
        existentes = {r[1] for r in con.execute(f"PRAGMA table_info({tabela})")}
        for nome, tipo in colunas.items():
            if nome not in existentes:
                con.execute(f"ALTER TABLE {tabela} ADD COLUMN {nome} {tipo}")


def agora() -> str:
    return datetime.now(emissor.FUSO).strftime("%Y-%m-%d %H:%M:%S")


def registrar(tipo: str, mensagem: str) -> None:
    with conexao() as con:
        con.execute("INSERT INTO log (quando, tipo, mensagem) VALUES (?,?,?)", (agora(), tipo, mensagem))


def linhas(sql: str, params=()) -> list[dict]:
    with conexao() as con:
        return [dict(r) for r in con.execute(sql, params).fetchall()]


def backup() -> Path:
    """Cópia diária do banco em dados/backup (mantém os 30 mais recentes)."""
    pasta = caminho().parent / "backup"
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f"sistema_{datetime.now(emissor.FUSO):%Y-%m-%d}.db"
    if not destino.exists():
        with conexao() as con, sqlite3.connect(destino) as dst:
            con.backup(dst)
    for velho in sorted(pasta.glob("sistema_*.db"))[:-30]:
        velho.unlink()
    return destino
