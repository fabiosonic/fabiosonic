"""Conciliação bancária por extrato OFX (todos os bancos exportam): baixa automática dos títulos pagos.

Regras de casamento, da mais forte para a mais fraca (só baixa quando há UM candidato):
  1. identificador do PIX do título (T123) no histórico do lançamento;
  2. CPF/CNPJ ou nome do cliente no histórico + valor original ou atualizado;
  3. valor exato único entre os títulos em aberto (vencidos até 10 dias depois do crédito).
Débitos casam com contas a pagar em aberto pelo valor (único).
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta

from . import config, db, financeiro


def _norm(s: str) -> str:
    return re.sub(r"[^A-Z0-9 ]", " ", unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore")
                  .decode().upper())


def ler_ofx(conteudo: str) -> list[dict]:
    movs = []
    for bloco in re.findall(r"<STMTTRN>(.*?)(?:</STMTTRN>|(?=<STMTTRN>)|(?=</BANKTRANLIST>))", conteudo, re.S | re.I):
        def tag(nome):
            m = re.search(rf"<{nome}>([^<\r\n]*)", bloco, re.I)
            return m.group(1).strip() if m else ""
        dt, valor = tag("DTPOSTED")[:8], tag("TRNAMT").replace(",", ".")
        if len(dt) != 8 or not valor:
            continue
        memo = " ".join(x for x in (tag("NAME"), tag("MEMO")) if x)
        movs.append({"data": f"{dt[:4]}-{dt[4:6]}-{dt[6:8]}", "valor_cent": financeiro.cent(valor),
                     "descricao": memo, "fitid": tag("FITID") or f"{dt}-{valor}-{memo}"[:120]})
    return movs


def importar(conteudo: str) -> dict:
    movs = ler_ofx(conteudo)
    novos = 0
    with db.conexao() as con:
        for m in movs:
            cur = con.execute("INSERT OR IGNORE INTO movimentos (data, valor_cent, descricao, fitid, importado_em)"
                              " VALUES (?,?,?,?,?)", (m["data"], m["valor_cent"], m["descricao"], m["fitid"], db.agora()))
            novos += cur.rowcount
    r = conciliar()
    db.registrar("conciliacao", f"OFX: {len(movs)} lançamentos, {novos} novos, {r['titulos']} título(s) baixado(s), "
                                f"{r['despesas']} despesa(s) paga(s)")
    return {"lancamentos": len(movs), "novos": novos} | r


def _candidatos(m: dict, abertos: list[dict]) -> list[dict]:
    memo = _norm(m["descricao"])
    dmov = date.fromisoformat(m["data"])
    ids = re.findall(r"\bT(\d+)\b", memo)
    por_id = [t for t in abertos if str(t["id"]) in ids]
    if por_id:
        return por_id
    def valor_ok(t):
        return m["valor_cent"] in (t["valor_cent"], financeiro.encargos(t, dmov)["total_cent"])
    def nome_ok(t):
        doc = t["cpf_cnpj"]
        palavras = [p for p in _norm(t["cliente_nome"]).split() if len(p) > 3][:2]
        return doc in re.sub(r"\D", "", m["descricao"]) or (palavras and all(p in memo for p in palavras))
    por_nome = [t for t in abertos if valor_ok(t) and nome_ok(t)]
    if por_nome:
        return por_nome
    limite = (dmov + timedelta(days=10)).isoformat()
    return [t for t in abertos if valor_ok(t) and t["vencimento"] <= limite]


def categoria(historico: str) -> str:
    texto = " " + _norm(historico) + " "
    for palavra, cat in config.carregar()["regras_despesa"]:
        if _norm(palavra) in texto:
            return cat
    return "Outras"


def conciliar() -> dict:
    baixados = pagas = 0
    pendentes = db.linhas("SELECT * FROM movimentos WHERE titulo_id IS NULL AND despesa_id IS NULL ORDER BY data")
    for m in pendentes:
        if m["valor_cent"] > 0:
            abertos = db.linhas("SELECT * FROM titulos WHERE status='aberto'")
            c = _candidatos(m, abertos)
            if len(c) > 1 and len({t["cpf_cnpj"] for t in c}) == 1 and len({t["valor_cent"] for t in c}) == 1:
                c = sorted(c, key=lambda t: (t["vencimento"], t["id"]))[:1]   # mesmo cliente e valor: quita o mais antigo
            if len(c) == 1:
                financeiro.baixar(c[0]["id"], m["data"], financeiro.reais(m["valor_cent"]), "extrato")
                with db.conexao() as con:
                    con.execute("UPDATE movimentos SET titulo_id=? WHERE id=?", (c[0]["id"], m["id"]))
                baixados += 1
        else:
            desp = [d for d in db.linhas("SELECT * FROM despesas WHERE status='aberto'")
                    if d["valor_cent"] == -m["valor_cent"]]
            if len(desp) == 1:
                financeiro.pagar_despesa(desp[0]["id"], m["data"])
                did = desp[0]["id"]
            elif not desp and config.carregar()["automacao"].get("despesas_do_extrato"):
                did = financeiro.salvar_despesa({"descricao": (m["descricao"] or "Débito em conta")[:120],
                                                 "fornecedor": "extrato", "categoria": categoria(m["descricao"]),
                                                 "valor": financeiro.reais(-m["valor_cent"]), "vencimento": m["data"]})
                financeiro.pagar_despesa(did, m["data"])
            else:
                continue
            with db.conexao() as con:
                con.execute("UPDATE movimentos SET despesa_id=? WHERE id=?", (did, m["id"]))
            pagas += 1
    return {"titulos": baixados, "despesas": pagas}


def nao_conciliados() -> list[dict]:
    lst = db.linhas("SELECT * FROM movimentos WHERE titulo_id IS NULL AND despesa_id IS NULL ORDER BY data DESC")
    abertos = db.linhas("SELECT * FROM titulos WHERE status='aberto'")
    for m in lst:
        m["sugestoes"] = [{"id": t["id"], "cliente": t["cliente_nome"], "valor_cent": t["valor_cent"],
                           "vencimento": t["vencimento"]} for t in _candidatos(m, abertos)][:5] if m["valor_cent"] > 0 else []
    return lst


def vincular(mov_id: int, titulo_id: int) -> None:
    m = db.linhas("SELECT * FROM movimentos WHERE id=?", (mov_id,))[0]
    financeiro.baixar(titulo_id, m["data"], financeiro.reais(m["valor_cent"]), "extrato")
    with db.conexao() as con:
        con.execute("UPDATE movimentos SET titulo_id=? WHERE id=?", (titulo_id, mov_id))
