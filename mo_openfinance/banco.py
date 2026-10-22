"""
Armazenamento local (SQLite) com as garantias que a conciliação precisa:

- idempotência por id de transação (reprocessar o mesmo período nunca duplica lançamento);
- exclusão na origem não apaga nada: a transação vira EXCLUIDA_ORIGEM e, se já tinha ido para a
  contabilidade, entra na fila de estorno (trilha de auditoria, ITG 2000);
- controle da janela de 6 h por conta+tipo para não estourar os créditos mensais do Open Finance;
- registro de webhooks por id para não processar o mesmo evento duas vezes.
"""
import json
import sqlite3
from datetime import datetime, timedelta
from decimal import Decimal

from .modelo import Transacao

ESQUEMA = """
CREATE TABLE IF NOT EXISTS conta (
  conta TEXT PRIMARY KEY, empresa TEXT NOT NULL, provedor TEXT NOT NULL, tipo TEXT NOT NULL DEFAULT 'BANK',
  cartao TEXT, item TEXT,                         -- item: openfinanceId (TecnoSpeed) / itemId (Pluggy)
  status TEXT NOT NULL DEFAULT 'PENDENTE', atualizada_em TEXT
);
CREATE TABLE IF NOT EXISTS protocolo (
  unique_id TEXT PRIMARY KEY, conta TEXT NOT NULL, tipo TEXT NOT NULL, inicio TEXT, fim TEXT,
  status TEXT NOT NULL, motivo TEXT, solicitado_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS transacao (
  id TEXT PRIMARY KEY, conta TEXT NOT NULL, tipo_extrato TEXT NOT NULL, data TEXT NOT NULL, valor TEXT NOT NULL,
  descricao TEXT, contraparte_doc TEXT, json TEXT NOT NULL,
  situacao TEXT NOT NULL DEFAULT 'ATIVA',        -- ATIVA | EXCLUIDA_ORIGEM
  exportada_em TEXT, estorno_exportado_em TEXT, recebida_em TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_transacao_conta_data ON transacao(conta, data);
CREATE TABLE IF NOT EXISTS evento (
  chave TEXT PRIMARY KEY, tipo TEXT NOT NULL, json TEXT NOT NULL, recebido_em TEXT NOT NULL
);
"""

CAMPOS_DECIMAIS = ("valor", "boleto_principal", "boleto_juros", "boleto_multa", "boleto_desconto")


def agora():
    return datetime.now().replace(microsecond=0)


class Banco:
    def __init__(self, caminho=":memory:"):
        self.db = sqlite3.connect(caminho)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(ESQUEMA)

    # ------------------------------------------------------------------ contas
    def registrar_conta(self, conta, empresa, provedor, tipo="BANK", cartao=None, item=None, status="PENDENTE"):
        self.db.execute("INSERT INTO conta(conta, empresa, provedor, tipo, cartao, item, status, atualizada_em) "
                        "VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(conta) DO UPDATE SET empresa=excluded.empresa, "
                        "provedor=excluded.provedor, tipo=excluded.tipo, cartao=excluded.cartao, "
                        "item=COALESCE(excluded.item, conta.item)",
                        (conta, empresa, provedor, tipo, cartao, item, status, agora().isoformat()))
        self.db.commit()

    def mudar_status_conta(self, conta_ou_item, status):
        """Aceita o accountHash/accountId ou o item (webhooks da Pluggy só trazem itemId). Devolve quantas mudaram."""
        cur = self.db.execute("UPDATE conta SET status=?, atualizada_em=? WHERE conta=? OR item=?",
                              (status, agora().isoformat(), conta_ou_item, conta_ou_item))
        self.db.commit()
        return cur.rowcount

    def contas(self, status=None):
        sql, args = "SELECT * FROM conta", ()
        if status:
            sql, args = sql + " WHERE status=?", (status,)
        return [dict(r) for r in self.db.execute(sql, args)]

    # ------------------------------------------------------------------ protocolos e janela de 6 h
    def registrar_protocolo(self, unique_id, conta, tipo, inicio, fim, quando=None):
        self.db.execute("INSERT OR REPLACE INTO protocolo VALUES (?,?,?,?,?,?,?,?)",
                        (unique_id, conta, tipo, inicio, fim, "PROCESSING", None, (quando or agora()).isoformat()))
        self.db.commit()

    def atualizar_protocolo(self, unique_id, status, motivo=None):
        self.db.execute("UPDATE protocolo SET status=?, motivo=? WHERE unique_id=?", (status, motivo, unique_id))
        self.db.commit()

    def protocolos_pendentes(self):
        return [dict(r) for r in self.db.execute("SELECT * FROM protocolo WHERE status='PROCESSING'")]

    def pode_solicitar(self, conta, tipo, intervalo_horas, quando=None):
        """Respeita o limite da TecnoSpeed: 1 protocolo bem-sucedido a cada N h por conta+tipo, zerando às 00h."""
        if not intervalo_horas:
            return True
        quando = quando or agora()
        r = self.db.execute("SELECT MAX(solicitado_em) FROM protocolo WHERE conta=? AND tipo=? AND status<>'FAILED'",
                            (conta, tipo)).fetchone()[0]
        if not r:
            return True
        ultimo = datetime.fromisoformat(r)
        if ultimo.date() < quando.date():
            return True
        return quando >= ultimo + timedelta(hours=intervalo_horas)

    # ------------------------------------------------------------------ transações
    def gravar(self, transacoes):
        """Insere só o que é novo. Devolve a quantidade inserida."""
        novas = 0
        for t in transacoes:
            cur = self.db.execute(
                "INSERT OR IGNORE INTO transacao(id, conta, tipo_extrato, data, valor, descricao, contraparte_doc, json, "
                "recebida_em) VALUES (?,?,?,?,?,?,?,?,?)",
                (t.id, t.conta, t.tipo_extrato, t.data, str(t.valor), t.descricao, t.contraparte_doc,
                 json.dumps(t.para_dict(), ensure_ascii=False, default=str), agora().isoformat()))
            novas += cur.rowcount
        self.db.commit()
        return novas

    def marcar_excluidas(self, ids):
        """Exclusão na origem (transaction_deleted / transactions/deleted). Devolve as que já tinham sido exportadas."""
        ja_exportadas = []
        for i in ids:
            r = self.db.execute("SELECT exportada_em FROM transacao WHERE id=?", (str(i),)).fetchone()
            if r is None:
                continue
            self.db.execute("UPDATE transacao SET situacao='EXCLUIDA_ORIGEM' WHERE id=?", (str(i),))
            if r["exportada_em"]:
                ja_exportadas.append(str(i))
        self.db.commit()
        return ja_exportadas

    @staticmethod
    def _carregar(row):
        d = json.loads(row["json"])
        for k in CAMPOS_DECIMAIS:
            if d.get(k) is not None:
                d[k] = Decimal(d[k])
        d.pop("bruto", None)
        return Transacao(**d)

    def a_exportar(self, conta=None, ate=None):
        sql = "SELECT * FROM transacao WHERE situacao='ATIVA' AND exportada_em IS NULL"
        args = []
        if conta:
            sql += " AND conta=?"
            args.append(conta)
        if ate:
            sql += " AND data<=?"
            args.append(ate)
        return [self._carregar(r) for r in self.db.execute(sql + " ORDER BY data, id", args)]

    def a_estornar(self, conta=None):
        sql = "SELECT * FROM transacao WHERE situacao='EXCLUIDA_ORIGEM' AND exportada_em IS NOT NULL " \
              "AND estorno_exportado_em IS NULL"
        args = []
        if conta:
            sql += " AND conta=?"
            args.append(conta)
        return [self._carregar(r) for r in self.db.execute(sql + " ORDER BY data, id", args)]

    def marcar_exportadas(self, ids, estorno=False):
        coluna = "estorno_exportado_em" if estorno else "exportada_em"
        self.db.executemany(f"UPDATE transacao SET {coluna}=? WHERE id=?", [(agora().isoformat(), str(i)) for i in ids])
        self.db.commit()

    # ------------------------------------------------------------------ webhooks
    def evento_novo(self, chave, tipo, payload):
        cur = self.db.execute("INSERT OR IGNORE INTO evento VALUES (?,?,?,?)",
                              (chave, tipo, json.dumps(payload, ensure_ascii=False), agora().isoformat()))
        self.db.commit()
        return cur.rowcount == 1
