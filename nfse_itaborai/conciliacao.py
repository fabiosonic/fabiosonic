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


def _mesmo_cliente(m: dict, t: dict) -> bool:
    """O histórico do extrato traz o CPF/CNPJ ou as duas primeiras palavras do nome do cliente do título."""
    memo = _norm(m["descricao"])
    palavras = [p for p in _norm(t["cliente_nome"]).split() if len(p) > 3][:2]
    return t["cpf_cnpj"] in re.sub(r"\D", "", m["descricao"]) or bool(palavras and all(p in memo for p in palavras))


def _ja_pagos(m: dict) -> list[dict]:
    """Títulos JÁ baixados (boleto/PIX reconhecido pelo banco, baixa manual) que ainda não têm o lançamento do extrato:
    mesmo valor recebido e pagamento até 5 dias antes ou depois. Os do mesmo cliente vêm primeiro (e sozinhos)."""
    dmov = date.fromisoformat(m["data"])
    ok = []
    for t in db.linhas("SELECT * FROM titulos t WHERE t.status='pago' AND COALESCE(t.data_pagamento,'')!='' "
                       "AND NOT EXISTS (SELECT 1 FROM movimentos x WHERE x.titulo_id=t.id)"):
        if m["valor_cent"] not in (t["valor_pago_cent"] or t["valor_cent"], t["valor_cent"]):
            continue
        try:
            if abs((date.fromisoformat(str(t["data_pagamento"])[:10]) - dmov).days) <= 5:
                ok.append(t)
        except ValueError:
            continue
    do_cliente = [t for t in ok if _mesmo_cliente(m, t)]
    return do_cliente or ok


def _candidatos(m: dict, abertos: list[dict]) -> list[dict]:
    memo = _norm(m["descricao"])
    dmov = date.fromisoformat(m["data"])
    ids = re.findall(r"\bT(\d+)\b", memo)
    por_id = [t for t in abertos if str(t["id"]) in ids]
    if por_id:
        return por_id
    def valor_ok(t):
        return m["valor_cent"] in (t["valor_cent"], financeiro.encargos(t, dmov)["total_cent"])
    por_nome = [t for t in abertos if valor_ok(t) and _mesmo_cliente(m, t)]
    if por_nome:
        return por_nome
    limite = (dmov + timedelta(days=10)).isoformat()
    return [t for t in abertos if valor_ok(t) and t["vencimento"] <= limite]


def regras() -> list:
    """Regras salvas pelo escritório primeiro; depois as palavras padrão que ainda não estão nelas."""
    salvas = config.carregar()["regras_despesa"]
    tem = {_norm(p).strip() for p, _ in salvas}
    return list(salvas) + [r for r in config.PADRAO["regras_despesa"] if _norm(r[0]).strip() not in tem]


def categoria(historico: str) -> str:
    texto = " " + _norm(historico) + " "
    for palavra, cat in regras():
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
            # recebimento de título que o banco já baixou (boleto/PIX do Inter) ou baixado à mão: só vincula
            pagos = [x for x in _ja_pagos(m) if _mesmo_cliente(m, x)]
            if len(pagos) == 1:
                with db.conexao() as con:
                    con.execute("UPDATE movimentos SET titulo_id=? WHERE id=?", (pagos[0]["id"], m["id"]))
                baixados += 1
                continue
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
            elif not desp and (_norm(_contraparte(m["descricao"])) in (config.carregar()["financeiro"].get("contrapartes_fora_dre") or {})):
                classificar(m["id"], config.carregar()["financeiro"]["contrapartes_fora_dre"][_contraparte(m["descricao"])], iguais=False)
                continue
            elif not desp and config.carregar()["automacao"].get("despesas_do_extrato") and not m.get("manual"):
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
        if m["valor_cent"] <= 0:
            m["sugestoes"] = []
            continue
        pagos = _ja_pagos(m)
        abertos_c = _candidatos(m, abertos)
        if any(_mesmo_cliente(m, x) for x in pagos):           # o do próprio cliente, já pago: só ele
            abertos_c = [x for x in abertos_c if _mesmo_cliente(m, x)]
        m["sugestoes"] = ([{"id": t["id"], "cliente": t["cliente_nome"], "valor_cent": t["valor_pago_cent"] or t["valor_cent"],
                            "vencimento": t["vencimento"], "pago": True} for t in pagos]
                          + [{"id": t["id"], "cliente": t["cliente_nome"], "valor_cent": t["valor_cent"],
                              "vencimento": t["vencimento"], "pago": False} for t in abertos_c])[:5]
    return lst


def titulos_para_vincular(busca: str = "") -> list[dict]:
    """Para escolher à mão: títulos em aberto e títulos pagos ainda sem lançamento do extrato, filtrados pelo
    nome/CPF/CNPJ do cliente."""
    b = _norm(busca)
    out = []
    for t in db.linhas("SELECT * FROM titulos t WHERE t.status='aberto' OR (t.status='pago' AND NOT EXISTS "
                       "(SELECT 1 FROM movimentos x WHERE x.titulo_id=t.id)) ORDER BY t.vencimento DESC"):
        if b and b not in _norm(t["cliente_nome"]) and b not in t["cpf_cnpj"]:
            continue
        out.append({"id": t["id"], "cliente": t["cliente_nome"], "cpf_cnpj": t["cpf_cnpj"], "status": t["status"],
                    "valor_cent": t["valor_pago_cent"] if t["status"] == "pago" and t["valor_pago_cent"] else t["valor_cent"],
                    "vencimento": t["vencimento"], "data_pagamento": t["data_pagamento"] or "",
                    "competencia": t["competencia"], "nfse": t["nfse_numero"] or ""})
        if len(out) >= 60:
            break
    return out


def vincular(mov_id: int, titulo_id: int) -> dict:
    """Liga o lançamento do extrato ao título. Título em aberto: dá a baixa. Título já pago (o banco reconheceu o
    boleto/PIX antes do extrato chegar): só vincula, sem baixar de novo e sem nova nota."""
    m = db.linhas("SELECT * FROM movimentos WHERE id=?", (mov_id,))[0]
    t = financeiro.obter_titulo(titulo_id)
    if not t:
        raise ValueError("Título não encontrado.")
    if m["valor_cent"] <= 0:
        raise ValueError("Só lançamentos de entrada podem ser vinculados a um título.")
    if t["status"] == "aberto":
        financeiro.baixar(titulo_id, m["data"], financeiro.reais(m["valor_cent"]), "extrato")
    elif t["status"] != "pago":
        raise ValueError("Título cancelado não pode receber o lançamento.")
    with db.conexao() as con:
        con.execute("UPDATE movimentos SET titulo_id=? WHERE id=?", (titulo_id, mov_id))
    return {"ok": True, "baixado": t["status"] == "aberto"}


# ---------------------------------------------------------------- extrato completo e classificação

CLASSES = {"transferencia": "Transferência entre contas", "aporte": "Aporte / dinheiro do sócio",
           "outra_receita": "Outra receita (não é honorário)", "outra_saida": "Saída sem despesa (retirada, estorno…)",
           "distribuicao": "Distribuição de lucros / retirada do sócio"}
# saídas que NÃO são despesa (não entram na DRE): escolhidas na mesma lista das categorias
FORA_DRE = ("distribuicao", "transferencia", "outra_saida")


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
    if not tipo and m["despesa_id"]:
        d = db.linhas("SELECT fornecedor FROM despesas WHERE id=?", (m["despesa_id"],))
        if d and d[0]["fornecedor"] == "extrato":          # despesa criada pelo extrato: desfazer cancela e volta a pendente
            financeiro.excluir_despesa(m["despesa_id"])
            with db.conexao() as con:
                con.execute("UPDATE movimentos SET despesa_id=NULL, classificacao='', manual=1 WHERE id=?", (mov_id,))
            return {"ok": True, "aplicados": 1}
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


def recategorizar(mov_id: int, categoria_nova: str, iguais: bool = True, lembrar: bool = True) -> dict:
    """Muda a categoria da despesa que o extrato lançou sozinho. Com 'iguais', as outras despesas automáticas da mesma
    contraparte recebem a mesma categoria; com 'lembrar', a contraparte vira regra e os próximos já entram certos."""
    cat = (categoria_nova or "").strip()[:60]
    if not cat:
        raise ValueError("Informe a categoria.")
    m = db.linhas("SELECT m.*, d.fornecedor FROM movimentos m JOIN despesas d ON d.id=m.despesa_id WHERE m.id=?", (mov_id,))
    if not m:
        raise ValueError("Este lançamento não é uma despesa.")
    m = m[0]
    alvo = [m]
    cp = _contraparte(m["descricao"])
    if iguais and cp:
        alvo += [x for x in db.linhas("SELECT m.* FROM movimentos m JOIN despesas d ON d.id=m.despesa_id "
                                      "WHERE d.fornecedor='extrato' AND d.status!='cancelado' AND m.id!=?", (mov_id,))
                 if _contraparte(x["descricao"]) == cp]
    fora = cat[6:] if cat.startswith("__cls:") else ""
    if fora and fora not in FORA_DRE:
        raise ValueError("Classificação inválida.")
    if fora:          # não é despesa (ex.: distribuição de lucros ao sócio): cancela a despesa e classifica o lançamento
        for x in alvo:                  # uma gravação por vez (excluir_despesa abre a própria conexão)
            if m["fornecedor"] == "extrato" or x["id"] != m["id"]:
                financeiro.excluir_despesa(x["despesa_id"])
        with db.conexao() as con:
            for x in alvo:
                con.execute("UPDATE movimentos SET despesa_id=NULL, classificacao=? WHERE id=?", (fora, x["id"]))
        if lembrar and cp and len(cp) >= 5:
            fd = dict(config.carregar()["financeiro"].get("contrapartes_fora_dre") or {})
            fd[cp] = fora
            config.salvar({"financeiro": {"contrapartes_fora_dre": fd}})
        return {"ok": True, "aplicados": len(alvo), "regra": cp if lembrar else "", "fora_dre": fora}
    with db.conexao() as con:
        for x in alvo:
            con.execute("UPDATE despesas SET categoria=? WHERE id=?", (cat, x["despesa_id"]))
    if lembrar and cp and len(cp) >= 5 and m["fornecedor"] == "extrato":
        outras = [r for r in config.carregar()["regras_despesa"] if _norm(r[0]) != cp]
        config.salvar({"regras_despesa": [[cp, cat]] + outras})
        fd = dict(config.carregar()["financeiro"].get("contrapartes_fora_dre") or {})
        if fd.pop(cp, None):
            config.salvar({"financeiro": {"contrapartes_fora_dre": fd}})
    return {"ok": True, "aplicados": len(alvo), "regra": cp if lembrar else ""}


def categorias_despesa() -> list[dict]:
    """Categorias organizadas pelas linhas da DRE (cada uma cai no grupo certo) + o que fica fora da DRE."""
    from .contabil import FINANCEIRAS, GRUPOS
    usadas = {r["categoria"] for r in db.linhas("SELECT DISTINCT categoria FROM despesas WHERE categoria!='' AND status!='cancelado'")}
    usadas |= {c for c in (config.carregar()["financeiro"].get("categorias_despesa") or []) if c}
    grupos = [{"grupo": g, "categorias": list(cats)} for g, cats in GRUPOS.items()]
    grupos.append({"grupo": "Despesas financeiras", "categorias": list(FINANCEIRAS)})
    conhecidas = {c for g in grupos for c in g["categorias"]}
    extras = sorted(usadas - conhecidas, key=str.lower)
    if extras:   # categoria criada pelo escritório: na DRE entra em despesas administrativas
        grupos[2]["categorias"] += extras
    grupos.append({"grupo": "Fora da DRE (não é despesa)", "categorias": [], "fora": [{"valor": "__cls:" + k, "nome": CLASSES[k]} for k in FORA_DRE]})
    return grupos


def extrato(inicio: str = "", fim: str = "") -> dict:
    """Todos os lançamentos do extrato no período (entradas e saídas), com o que cada um virou no sistema."""
    sql, p = "SELECT * FROM movimentos WHERE 1=1", []
    if inicio:
        sql += " AND data>=?"; p.append(inicio)
    if fim:
        sql += " AND data<=?"; p.append(fim)
    movs = db.linhas(sql + " ORDER BY data DESC, id DESC", p)
    tits = {t["id"]: t for t in db.linhas("SELECT id, cliente_nome, competencia FROM titulos")}
    desps = {d["id"]: d for d in db.linhas("SELECT id, descricao, categoria, fornecedor FROM despesas")}
    for m in movs:
        if m["titulo_id"] and m["titulo_id"] in tits:
            t = tits[m["titulo_id"]]
            m["situacao"], m["detalhe"] = "titulo", f"Recebimento de {t['cliente_nome']} (comp. {t['competencia'][5:]}/{t['competencia'][:4]})"
        elif m["despesa_id"] and m["despesa_id"] in desps:
            d = desps[m["despesa_id"]]
            m["situacao"], m["detalhe"] = "despesa", f"Despesa: {d['descricao']} ({d['categoria']})"
            m["categoria"], m["despesa_auto"] = d["categoria"], d["fornecedor"] == "extrato"
        elif m.get("classificacao"):
            m["situacao"], m["detalhe"] = "classificado", CLASSES.get(m["classificacao"], m["classificacao"])
        else:
            m["situacao"], m["detalhe"] = "pendente", "Não conciliado"
    ent = sum(m["valor_cent"] for m in movs if m["valor_cent"] > 0)
    sai = -sum(m["valor_cent"] for m in movs if m["valor_cent"] < 0)
    return {"movimentos": movs, "entradas": ent, "saidas": sai, "resultado": ent - sai,
            "pendentes": sum(1 for m in movs if m["situacao"] == "pendente"), "fontes": resumo_fontes(),
            "a_revisar": sum(1 for m in movs if m.get("despesa_auto") and m.get("categoria") == "Outras"),
            "categorias": categorias_despesa()}


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
