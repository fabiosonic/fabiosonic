"""Trilha de auditoria em SQLite: anexos (sha256), execuções do grafo, eventos e aprovações.

Nada é apagado (regra 7): só INSERT; não há DELETE neste módulo.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from ..util.arquivos import dumps, loads, sha256_bytes

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
    destinos TEXT, situacao TEXT, em TEXT, resumo TEXT
);
CREATE INDEX IF NOT EXISTS ix_doc_chave ON documentos(chave);
CREATE TABLE IF NOT EXISTS ofx_transacoes (
    banco TEXT, conta TEXT, fitid TEXT, sha256 TEXT, em TEXT, PRIMARY KEY (banco, conta, fitid)
);
CREATE TABLE IF NOT EXISTS acoes (
    id TEXT PRIMARY KEY, lote TEXT, sha256 TEXT, cnpj TEXT, competencia TEXT, tipo TEXT,
    estado TEXT, dados TEXT, detalhe TEXT, em TEXT
);
CREATE INDEX IF NOT EXISTS ix_acoes_estado ON acoes(estado);
CREATE TABLE IF NOT EXISTS lotes_conteudo (chave TEXT PRIMARY KEY, hash TEXT, em TEXT);
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
        colunas = {r[1] for r in self.con.execute("PRAGMA table_info(documentos)")}
        if "resumo" not in colunas:  # migração de trilhas criadas antes desta versão
            self.con.execute("ALTER TABLE documentos ADD COLUMN resumo TEXT")
        if "tentativas" not in {r[1] for r in self.con.execute("PRAGMA table_info(acoes)")}:
            self.con.execute("ALTER TABLE acoes ADD COLUMN tentativas INTEGER DEFAULT 0")
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

    def registrar_documento(self, sha, tipo, chave, cnpjs, competencia, destinos, situacao, resumo=None):
        self.con.execute(
            "INSERT OR REPLACE INTO documentos (sha256, tipo, chave, cnpjs, competencia, destinos, situacao, em, resumo)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (sha, tipo, chave, dumps(cnpjs), competencia, dumps(destinos), situacao, agora(), dumps(resumo or {})),
        )
        self.con.commit()

    def na_fila(self) -> list[dict]:
        """Documentos que aguardam IA (cota esgotada) — voltam no próximo ciclo."""
        rows = self.con.execute(
            "SELECT d.sha256, a.nome, a.origem, a.caminho_bruto FROM documentos d JOIN anexos a USING (sha256)"
            " WHERE d.situacao='FILA' ORDER BY d.em").fetchall()
        return [{"sha256": r[0], "nome": r[1], "origem": r[2], "caminho": r[3], "reprocesso": True} for r in rows]

    def anexos_sem_documento(self) -> list[dict]:
        """Anexos capturados que nunca chegaram a ser processados (ex.: queda no meio do ciclo)."""
        rows = self.con.execute(
            "SELECT a.sha256, a.nome, a.origem, a.caminho_bruto FROM anexos a"
            " LEFT JOIN documentos d USING (sha256) WHERE d.sha256 IS NULL ORDER BY a.recebido_em").fetchall()
        return [{"sha256": r[0], "nome": r[1], "origem": r[2], "caminho": r[3], "reprocesso": True} for r in rows]

    def pendentes_para_reprocessar(self, versao_base: str | None) -> list[dict]:
        """Documentos PENDENTE/ERRO analisados com outra versão da base (normas/cadastro mudaram)."""
        out = []
        rows = self.con.execute(
            "SELECT d.sha256, a.nome, a.origem, a.caminho_bruto, d.resumo FROM documentos d JOIN anexos a USING (sha256)"
            " WHERE d.situacao IN ('PENDENTE','ERRO')").fetchall()
        for sha, nome, origem, caminho, resumo in rows:
            versao = (loads(resumo) if resumo else {}).get("_versao_base")
            if versao != versao_base:
                out.append({"sha256": sha, "nome": nome, "origem": origem, "caminho": caminho, "reprocesso": True})
        return out

    # --- ações (estado durável: PROPOSTA -> EXECUTADA | FALHOU) -------------------
    @staticmethod
    def id_acao(a: dict) -> str:
        if a["tipo"] == "lancamento_contabil":
            # FITID pode ser reaproveitado pelo banco em outro mês: data e valor entram na identidade
            return (f"lancamento_contabil|{a.get('banco')}|{a.get('conta')}|{a.get('fitid')}|{a.get('data')}|"
                    f"{a.get('valor')}|{a['cnpj']}")
        return f"{a['tipo']}|{a.get('sha256')}|{a['cnpj']}|{a.get('pasta_tipo') or ''}"

    def acoes_ja_propostas(self, acoes: list[dict]) -> set[str]:
        ids = [self.id_acao(a) for a in acoes]
        if not ids:
            return set()
        marcas = ",".join("?" * len(ids))
        return {r[0] for r in self.con.execute(
            f"SELECT id FROM acoes WHERE id IN ({marcas}) AND estado IN ('PROPOSTA','EXECUTADA','FALHOU')", ids)}

    def registrar_acoes(self, lote: str, acoes: list[dict]) -> None:
        for a in acoes:
            # ação BLOQUEADA proposta de novo (ex.: pessoa resolveu o conflito): volta a PROPOSTA no lote novo
            self.con.execute("UPDATE acoes SET lote=?, estado='PROPOSTA', tentativas=0, dados=?, detalhe=NULL, em=?"
                             " WHERE id=? AND estado='BLOQUEADA'", (lote, dumps(a), agora(), self.id_acao(a)))
            self.con.execute(
                "INSERT OR IGNORE INTO acoes (id, lote, sha256, cnpj, competencia, tipo, estado, dados, detalhe, em)"
                " VALUES (?,?,?,?,?,?,'PROPOSTA',?,NULL,?)",
                (self.id_acao(a), lote, a.get("sha256"), a["cnpj"], a.get("competencia"), a["tipo"], dumps(a), agora()))
        self.con.commit()

    def estado_acao(self, a: dict) -> tuple[str | None, str | None]:
        """(estado, lote dono da ação) — (None, None) se a ação nunca foi registrada."""
        r = self.con.execute("SELECT estado, lote FROM acoes WHERE id=?", (self.id_acao(a),)).fetchone()
        return (r[0], r[1]) if r else (None, None)

    def marcar_acao(self, a: dict, estado: str, detalhe: str | None = None) -> None:
        self.con.execute("UPDATE acoes SET estado=?, detalhe=?, em=? WHERE id=?",
                         (estado, detalhe, agora(), self.id_acao(a)))
        self.con.commit()

    def marcar_falha(self, a: dict, detalhe: str, teto: int) -> None:
        """FALHOU (refeita no próximo ciclo) até o teto de tentativas; depois BLOQUEADA (precisa de pessoa)."""
        self.con.execute("UPDATE acoes SET tentativas=COALESCE(tentativas,0)+1, detalhe=?, em=? WHERE id=?",
                         (detalhe, agora(), self.id_acao(a)))
        n = self.con.execute("SELECT tentativas FROM acoes WHERE id=?", (self.id_acao(a),)).fetchone()
        estado = "BLOQUEADA" if n and n[0] >= teto else "FALHOU"
        self.con.execute("UPDATE acoes SET estado=? WHERE id=?", (estado, self.id_acao(a)))
        self.con.commit()

    def acoes_bloqueadas(self) -> list[dict]:
        return [{"lote": l, "acao": loads(d), "detalhe": det} for l, d, det in self.con.execute(
            "SELECT lote, dados, detalhe FROM acoes WHERE estado='BLOQUEADA' ORDER BY em")]

    def lotes_aprovados_pendentes(self, tipos=("copiar_xml_rotina", "arquivar_documento", "lancamento_contabil")) -> list[str]:
        """Lotes com aprovação registrada e ação executável ainda PROPOSTA (aprovados fora do ciclo)."""
        marcas = ",".join("?" * len(tipos))
        return [r[0] for r in self.con.execute(
            f"SELECT DISTINCT a.lote FROM acoes a JOIN aprovacoes p ON p.lote = a.lote"
            f" WHERE a.estado='PROPOSTA' AND a.tipo IN ({marcas}) ORDER BY a.lote", tuple(tipos))]

    def lotes_aguardando(self) -> list[str]:
        """Lotes com ação PROPOSTA e nenhuma aprovação registrada."""
        return [r[0] for r in self.con.execute(
            "SELECT DISTINCT a.lote FROM acoes a LEFT JOIN aprovacoes p ON p.lote = a.lote"
            " WHERE a.estado='PROPOSTA' AND p.lote IS NULL ORDER BY a.lote")]

    def conteudo_novo(self, chave: str, conteudo, registrar: bool = False) -> bool:
        h = sha256_bytes(dumps(conteudo).encode())
        r = self.con.execute("SELECT hash FROM lotes_conteudo WHERE chave=?", (chave,)).fetchone()
        if registrar:
            self.con.execute("INSERT OR REPLACE INTO lotes_conteudo VALUES (?,?,?)", (chave, h, agora()))
            self.con.commit()
        return r is None or r[0] != h

    def acoes_com_falha(self) -> list[dict]:
        return [{"lote": l, "acao": loads(d), "detalhe": det} for l, d, det in self.con.execute(
            "SELECT lote, dados, detalhe FROM acoes WHERE estado='FALHOU' ORDER BY em")]

    def atualizar_situacao(self, sha: str, situacao: str) -> None:
        self.con.execute("UPDATE documentos SET situacao=? WHERE sha256=?", (situacao, sha))
        self.con.commit()

    def analisados_sem_lote(self) -> list[dict]:
        """Documentos analisados cujo lote não chegou a ser gravado (queda no meio do ciclo)."""
        rows = self.con.execute(
            "SELECT d.sha256, a.nome, a.origem, a.caminho_bruto FROM documentos d JOIN anexos a USING (sha256)"
            " WHERE d.situacao='ANALISADO'").fetchall()
        return [{"sha256": r[0], "nome": r[1], "origem": r[2], "caminho": r[3], "reprocesso": True} for r in rows]

    def aprovacao_registrada(self, lote: str, hash_lote: str, modo: str) -> bool:
        return self.con.execute("SELECT 1 FROM aprovacoes WHERE lote=? AND hash=? AND modo=?",
                                (lote, hash_lote, modo)).fetchone() is not None

    def documentos(self, competencia: str | None = None):
        sql = "SELECT sha256, tipo, chave, cnpjs, competencia, destinos, situacao, resumo FROM documentos"
        args: tuple = ()
        if competencia:
            sql += " WHERE competencia=?"
            args = (competencia,)
        out = []
        for r in self.con.execute(sql, args):
            out.append(
                {"sha256": r[0], "tipo": r[1], "chave": r[2], "cnpjs": loads(r[3]),
                 "competencia": r[4], "destinos": loads(r[5]), "situacao": r[6],
                 "resumo": loads(r[7]) if r[7] else {}}
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
