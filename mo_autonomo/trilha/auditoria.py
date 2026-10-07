"""Trilha de auditoria em SQLite: anexos (sha256), execuções do grafo, eventos e aprovações.

Nada é apagado (regra 7): só INSERT; não há DELETE neste módulo.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from ..util.arquivos import dumps, loads

ESQUEMA = """
CREATE TABLE IF NOT EXISTS anexos (
    sha256 TEXT PRIMARY KEY,
    nome TEXT, origem TEXT, caminho_bruto TEXT, recebido_em TEXT
);
CREATE TABLE IF NOT EXISTS emails (
    uid TEXT PRIMARY KEY, message_id TEXT, remetente TEXT, assunto TEXT, data TEXT, lido_em TEXT
);
CREATE TABLE IF NOT EXISTS execucoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT, grafo TEXT, passo INTEGER, no TEXT, status TEXT,
    duracao_ms INTEGER, erro TEXT, proximo TEXT, estado TEXT, em TEXT
);
CREATE INDEX IF NOT EXISTS ix_exec_run ON execucoes(run_id, passo);
CREATE TABLE IF NOT EXISTS eventos (
    id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT, referencia TEXT, detalhe TEXT, em TEXT
);
CREATE TABLE IF NOT EXISTS documentos (
    sha256 TEXT PRIMARY KEY, tipo TEXT, chave TEXT, cnpjs TEXT, competencia TEXT,
    destinos TEXT, situacao TEXT, em TEXT
);
CREATE INDEX IF NOT EXISTS ix_doc_chave ON documentos(chave);
CREATE TABLE IF NOT EXISTS aprovacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT, lote TEXT, hash TEXT, modo TEXT, motivo TEXT,
    usuario TEXT, em TEXT
);
"""


def agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Trilha:
    def __init__(self, caminho: Path | str):
        self.caminho = str(caminho)
        if self.caminho != ":memory:":
            Path(self.caminho).parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(self.caminho)
        self.con.executescript(ESQUEMA)
        self.con.commit()

    def fechar(self):
        self.con.close()

    # --- anexos / e-mails ---------------------------------------------------
    def anexo_existe(self, sha: str) -> bool:
        return self.con.execute("SELECT 1 FROM anexos WHERE sha256=?", (sha,)).fetchone() is not None

    def registrar_anexo(self, sha: str, nome: str, origem: str, caminho_bruto: str) -> bool:
        cur = self.con.execute(
            "INSERT OR IGNORE INTO anexos VALUES (?,?,?,?,?)", (sha, nome, origem, caminho_bruto, agora())
        )
        self.con.commit()
        return cur.rowcount == 1

    def email_lido(self, uid: str) -> bool:
        return self.con.execute("SELECT 1 FROM emails WHERE uid=?", (uid,)).fetchone() is not None

    def registrar_email(self, uid, message_id, remetente, assunto, data):
        self.con.execute(
            "INSERT OR IGNORE INTO emails VALUES (?,?,?,?,?,?)",
            (uid, message_id, remetente, assunto, data, agora()),
        )
        self.con.commit()

    # --- documentos -------------------------------------------------------
    def documento_por_chave(self, chave: str):
        return self.con.execute(
            "SELECT sha256, situacao FROM documentos WHERE chave=?", (chave,)
        ).fetchall()

    def registrar_documento(self, sha, tipo, chave, cnpjs, competencia, destinos, situacao):
        self.con.execute(
            "INSERT OR REPLACE INTO documentos VALUES (?,?,?,?,?,?,?,?)",
            (sha, tipo, chave, dumps(cnpjs), competencia, dumps(destinos), situacao, agora()),
        )
        self.con.commit()

    def documentos(self, competencia: str | None = None):
        sql = "SELECT sha256, tipo, chave, cnpjs, competencia, destinos, situacao FROM documentos"
        args: tuple = ()
        if competencia:
            sql += " WHERE competencia=?"
            args = (competencia,)
        out = []
        for r in self.con.execute(sql, args):
            out.append(
                {"sha256": r[0], "tipo": r[1], "chave": r[2], "cnpjs": loads(r[3]),
                 "competencia": r[4], "destinos": loads(r[5]), "situacao": r[6]}
            )
        return out

    # --- grafo ------------------------------------------------------------
    def registrar_passo(self, run_id, grafo, passo, no, status, duracao_ms, erro, proximo, estado):
        self.con.execute(
            "INSERT INTO execucoes (run_id, grafo, passo, no, status, duracao_ms, erro, proximo, estado, em)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (run_id, grafo, passo, no, status, duracao_ms, erro, proximo, dumps(estado), agora()),
        )
        self.con.commit()

    def ultimo_passo(self, run_id: str):
        r = self.con.execute(
            "SELECT passo, no, status, proximo, estado FROM execucoes WHERE run_id=? ORDER BY passo DESC, id DESC LIMIT 1",
            (run_id,),
        ).fetchone()
        if not r:
            return None
        return {"passo": r[0], "no": r[1], "status": r[2], "proximo": r[3], "estado": loads(r[4])}

    def passos(self, run_id: str):
        return self.con.execute(
            "SELECT passo, no, status, erro FROM execucoes WHERE run_id=? ORDER BY passo, id", (run_id,)
        ).fetchall()

    # --- eventos / aprovações -----------------------------------------------
    def evento(self, tipo: str, referencia: str, detalhe) -> None:
        self.con.execute(
            "INSERT INTO eventos (tipo, referencia, detalhe, em) VALUES (?,?,?,?)",
            (tipo, referencia, dumps(detalhe), agora()),
        )
        self.con.commit()

    def eventos(self, tipo: str | None = None):
        sql, args = "SELECT tipo, referencia, detalhe FROM eventos", ()
        if tipo:
            sql, args = sql + " WHERE tipo=?", (tipo,)
        return [(t, r, loads(d)) for t, r, d in self.con.execute(sql + " ORDER BY id", args)]

    def registrar_aprovacao(self, lote, hash_lote, modo, motivo, usuario):
        self.con.execute(
            "INSERT INTO aprovacoes (lote, hash, modo, motivo, usuario, em) VALUES (?,?,?,?,?,?)",
            (lote, hash_lote, modo, motivo, usuario, agora()),
        )
        self.con.commit()

    def aprovacoes(self):
        return self.con.execute("SELECT lote, hash, modo, motivo, usuario FROM aprovacoes ORDER BY id").fetchall()
