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


def conta_ofx(conteudo: str) -> str:
    """Identificação da conta do extrato (banco + agência + conta), para não misturar empresas."""
    tag = lambda n: (re.search(rf"<{n}>([^<\r\n]*)", conteudo, re.I) or [None, ""])[1].strip()  # noqa: E731
    return "-".join(x for x in (tag("BANKID"), tag("BRANCHID"), tag("ACCTID")) if x)


def _fonte(fitid: str) -> str:
    return "inter" if str(fitid).startswith("inter:") else "ofx"


def gravar_movimentos(movs: list[dict]) -> int:
    """Grava lançamentos sem duplicar. Na mesma fonte, o identificador (FITID / idTransacao) decide. Entre fontes
    diferentes (OFX e API do Inter) o identificador muda: para cada dia e valor, lançamentos já vindos da outra
    fonte contam como os mesmos — só entra o que o extrato novo tiver a mais."""
    novos = 0
    por_chave: dict = {}
    for m in movs:
        por_chave.setdefault((m["data"], m["valor_cent"], _fonte(m["fitid"])), []).append(m)
    with db.conexao() as con:
        for (data, valor, fonte), lote in por_chave.items():
            presentes = [m for m in lote if con.execute("SELECT 1 FROM movimentos WHERE fitid=?", (m["fitid"],)).fetchone()]
            outra = sum(1 for r in con.execute("SELECT fitid FROM movimentos WHERE data=? AND valor_cent=?", (data, valor))
                        if _fonte(r[0]) != fonte)
            vagas = len(lote) - len(presentes) - outra
            for m in lote:
                if vagas <= 0:
                    break
                if m in presentes:
                    continue
                con.execute("INSERT INTO movimentos (data, valor_cent, descricao, fitid, importado_em) VALUES (?,?,?,?,?)",
                            (data, valor, m["descricao"], m["fitid"], db.agora()))
                novos += 1
                vagas -= 1
    return novos


def importar(conteudo: str, movs: list[dict] | None = None, origem: str = "OFX") -> dict:
    movs = ler_ofx(conteudo) if movs is None else movs
    novos = gravar_movimentos(movs)
    r = conciliar()
    r["entradas"] = sum(1 for m in movs if m["valor_cent"] > 0)
    r["saidas"] = sum(1 for m in movs if m["valor_cent"] < 0)
    db.registrar("conciliacao", f"{origem}: {len(movs)} lançamentos, {novos} novos, {r['titulos']} título(s) baixado(s), "
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


def _corrigir_transferencias() -> int:
    """Pix/TED entre contas da própria empresa que viraram despesa automática do extrato (versões antigas): a despesa
    é cancelada e o lançamento passa a ser transferência entre contas — não é despesa e não entra na DRE."""
    n = 0
    for m in db.linhas("SELECT m.*, d.fornecedor, d.status st FROM movimentos m JOIN despesas d ON d.id=m.despesa_id "
                       "WHERE m.valor_cent < 0 AND d.fornecedor='extrato' AND d.status!='cancelado'"):
        if _da_propria_empresa(m):
            financeiro.excluir_despesa(m["despesa_id"])
            with db.conexao() as con:
                con.execute("UPDATE movimentos SET despesa_id=NULL, classificacao='transferencia' WHERE id=?", (m["id"],))
            n += 1
    return n


def conciliar() -> dict:
    baixados = pagas = 0
    _corrigir_transferencias()
    pendentes = db.linhas("SELECT * FROM movimentos WHERE titulo_id IS NULL AND despesa_id IS NULL "
                          "AND COALESCE(classificacao,'')='' ORDER BY data")
    for m in pendentes:
        if _da_propria_empresa(m):                   # Pix/TED entre contas da própria empresa: não é receita nem despesa
            classificar(m["id"], "transferencia", iguais=False)
            continue
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
    lst = db.linhas("SELECT * FROM movimentos WHERE titulo_id IS NULL AND despesa_id IS NULL "
                    "AND COALESCE(classificacao,'')='' ORDER BY data DESC")
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


# ---------------------------------------------------------------- extrato completo e classificação

CLASSES = {"transferencia": "Transferência entre contas", "aporte": "Aporte / dinheiro do sócio",
           "outra_receita": "Outra receita (não é honorário)", "outra_saida": "Saída sem despesa (retirada, estorno…)"}


def _da_propria_empresa(m: dict) -> bool:
    nome = _norm(config.carregar()["empresa"].get("nome", ""))
    nome = re.sub(r"\b(LTDA|ME|EPP|EIRELI|SA|S A)\b", " ", nome).split()
    return len(nome) >= 2 and " ".join(nome[:3]) in " ".join(_norm(m["descricao"]).split())


def _contraparte(desc: str) -> str:
    """'Pix recebido Fulano de Tal' -> 'FULANO DE TAL' (para aplicar a mesma classificação aos iguais)."""
    d = " ".join(_norm(desc).split())
    return re.sub(r"^(PIX|TED|DOC|TRANSFERENCIA)\s+(RECEBIDO|ENVIADO|RECEBIDA|ENVIADA)\s+", "", d).strip()


def classificar(mov_id: int, tipo: str, iguais: bool = True, categoria_desp: str = "") -> dict:
    """Marca um lançamento que não é título nem despesa. tipo='despesa' lança e paga a despesa; '' desfaz.
    Com iguais=True, os pendentes da mesma contraparte e do mesmo sentido recebem a mesma classificação."""
    m = db.linhas("SELECT * FROM movimentos WHERE id=?", (mov_id,))
    if not m:
        raise ValueError("Lançamento não encontrado.")
    m = m[0]
    if tipo and tipo not in CLASSES and tipo != "despesa":
        raise ValueError("Classificação inválida.")
    if tipo == "despesa":
        if m["valor_cent"] >= 0:
            raise ValueError("Só saídas viram despesa.")
        did = financeiro.salvar_despesa({"descricao": (m["descricao"] or "Débito em conta")[:120], "fornecedor": "extrato",
                                         "categoria": categoria_desp or categoria(m["descricao"]),
                                         "valor": financeiro.reais(-m["valor_cent"]), "vencimento": m["data"]})
        financeiro.pagar_despesa(did, m["data"])
        with db.conexao() as con:
            con.execute("UPDATE movimentos SET despesa_id=?, classificacao='' WHERE id=?", (did, mov_id))
        return {"ok": True, "despesa": did, "aplicados": 1}
    alvo = [m]
    if iguais and tipo:
        cp = _contraparte(m["descricao"])
        alvo += [x for x in db.linhas("SELECT * FROM movimentos WHERE titulo_id IS NULL AND despesa_id IS NULL "
                                     "AND COALESCE(classificacao,'')='' AND id!=?", (mov_id,))
                 if cp and _contraparte(x["descricao"]) == cp and (x["valor_cent"] > 0) == (m["valor_cent"] > 0)]
    with db.conexao() as con:
        for x in alvo:
            con.execute("UPDATE movimentos SET classificacao=? WHERE id=?", (tipo, x["id"]))
    return {"ok": True, "aplicados": len(alvo)}


def extrato(inicio: str = "", fim: str = "") -> dict:
    """Todos os lançamentos do extrato no período (entradas e saídas), com o que cada um virou no sistema."""
    sql, p = "SELECT * FROM movimentos WHERE 1=1", []
    if inicio:
        sql += " AND data>=?"; p.append(inicio)
    if fim:
        sql += " AND data<=?"; p.append(fim)
    movs = db.linhas(sql + " ORDER BY data DESC, id DESC", p)
    tits = {t["id"]: t for t in db.linhas("SELECT id, cliente_nome, competencia FROM titulos")}
    desps = {d["id"]: d for d in db.linhas("SELECT id, descricao, categoria FROM despesas")}
    for m in movs:
        if m["titulo_id"] and m["titulo_id"] in tits:
            t = tits[m["titulo_id"]]
            m["situacao"], m["detalhe"] = "titulo", f"Recebimento de {t['cliente_nome']} (comp. {t['competencia'][5:]}/{t['competencia'][:4]})"
        elif m["despesa_id"] and m["despesa_id"] in desps:
            d = desps[m["despesa_id"]]
            m["situacao"], m["detalhe"] = "despesa", f"Despesa: {d['descricao']} ({d['categoria']})"
        elif m.get("classificacao"):
            m["situacao"], m["detalhe"] = "classificado", CLASSES.get(m["classificacao"], m["classificacao"])
        else:
            m["situacao"], m["detalhe"] = "pendente", "Não conciliado"
    ent = sum(m["valor_cent"] for m in movs if m["valor_cent"] > 0)
    sai = -sum(m["valor_cent"] for m in movs if m["valor_cent"] < 0)
    return {"movimentos": movs, "entradas": ent, "saidas": sai, "resultado": ent - sai,
            "pendentes": sum(1 for m in movs if m["situacao"] == "pendente"), "fontes": resumo_fontes()}


def resumo_fontes() -> dict:
    """O que já foi importado de cada origem (API do Inter / OFX), no total: quantidade de entradas e saídas e o
    período coberto. Mostra ao escritório que as saídas também vieram, mesmo quando já foram conciliadas sozinhas."""
    out = {}
    for r in db.linhas("SELECT CASE WHEN fitid LIKE 'inter:%' THEN 'inter' ELSE 'ofx' END fonte, COUNT(*) n, "
                       "SUM(valor_cent>0) entradas, SUM(valor_cent<0) saidas, MIN(data) de, MAX(data) ate, "
                       "SUM(titulo_id IS NULL AND despesa_id IS NULL AND COALESCE(classificacao,'')='') pendentes "
                       "FROM movimentos GROUP BY 1"):
        out[r["fonte"]] = {k: r[k] for k in ("n", "entradas", "saidas", "de", "ate", "pendentes")}
    return out
