"""Contratos recorrentes, contas a receber (integradas à NFS-e) e contas a pagar."""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from . import clientes, config, db, emissor, lote, servicos


# ---------------------------------------------------------------- utilidades

def cent(valor) -> int:
    """'1.234,56' | '1234.56' | 1234.56 | Decimal -> 123456."""
    if isinstance(valor, int) and not isinstance(valor, bool):
        return valor * 100
    s = str(valor or "0").strip().replace("R$", "").replace(" ", "")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    return int((Decimal(s) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def reais(c: int) -> str:
    return f"{Decimal(c) / 100:.2f}"


def hoje() -> date:
    return datetime.now(emissor.FUSO).date()


def competencia_de(d: date) -> str:
    return d.strftime("%Y-%m")


def dia_no_mes(ano: int, mes: int, dia: int) -> date:
    return date(ano, mes, min(max(int(dia), 1), calendar.monthrange(ano, mes)[1]))


def _mes(comp: str) -> tuple[int, int]:
    a, m = comp.split("-")
    return int(a), int(m)


def encargos(titulo: dict, em: date | None = None) -> dict:
    """Multa (uma vez) + juros simples pro rata dia sobre o valor, para títulos vencidos em aberto."""
    em = em or hoje()
    venc = date.fromisoformat(titulo["vencimento"])
    dias = (em - venc).days
    if titulo["status"] != "aberto" or dias <= 0:
        return {"dias_atraso": max(dias, 0) if titulo["status"] == "aberto" else 0, "multa_cent": 0,
                "juros_cent": 0, "total_cent": titulo["valor_cent"]}
    cob = config.carregar()["cobranca"]
    v = Decimal(titulo["valor_cent"])
    multa = (v * Decimal(str(cob["multa_pct"])) / 100).quantize(Decimal("1"), ROUND_HALF_UP)
    juros = (v * Decimal(str(cob["juros_mes_pct"])) / 100 / 30 * dias).quantize(Decimal("1"), ROUND_HALF_UP)
    return {"dias_atraso": dias, "multa_cent": int(multa), "juros_cent": int(juros),
            "total_cent": titulo["valor_cent"] + int(multa) + int(juros)}


def situacao(titulo: dict, em: date | None = None) -> str:
    if titulo["status"] != "aberto":
        return titulo["status"]
    return "atrasado" if date.fromisoformat(titulo["vencimento"]) < (em or hoje()) else "aberto"


def enriquecer(t: dict, em: date | None = None) -> dict:
    return t | encargos(t, em) | {"situacao": situacao(t, em)}


# ---------------------------------------------------------------- contratos

CAMPOS_CONTRATO = ("cpf_cnpj", "descricao", "valor_cent", "dia_vencimento", "inicio", "fim", "ativo",
                   "emitir_nfse", "mes_reajuste", "reajuste_pct", "observacao")


def listar_contratos() -> list[dict]:
    lst = db.linhas("SELECT * FROM contratos ORDER BY ativo DESC, id")
    nomes = {c["cpf_cnpj"]: c["razao_social"] for c in clientes.listar()}
    return [c | {"cliente_nome": nomes.get(c["cpf_cnpj"], c["cpf_cnpj"])} for c in lst]


def salvar_contrato(d: dict) -> dict:
    doc = clientes._digitos(d.get("cpf_cnpj"))
    if not clientes.obter(doc):
        raise ValueError("Cliente não cadastrado.")
    reg = {
        "cpf_cnpj": doc,
        "descricao": (d.get("descricao") or servicos.obter(d.get("servico_id") or clientes.obter(doc).get("servico_id"))
                      .get("descricao", "")).strip()[:190],
        "servico_id": servicos.obter(d.get("servico_id"))["id"] if d.get("servico_id") else "",
        "valor_cent": d["valor_cent"] if "valor_cent" in d else cent(d.get("valor")),
        "dia_vencimento": int(d.get("dia_vencimento") or config.carregar()["financeiro"]["dia_vencimento_padrao"]),
        "inicio": d.get("inicio") or competencia_de(hoje()),
        "fim": d.get("fim") or "",
        "ativo": 1 if d.get("ativo", True) not in (False, 0, "0", "false") else 0,
        "emitir_nfse": 1 if d.get("emitir_nfse", True) not in (False, 0, "0", "false") else 0,
        "mes_reajuste": int(d.get("mes_reajuste") or 0),
        "reajuste_pct": float(str(d.get("reajuste_pct") or 0).replace(",", ".")),
        "observacao": d.get("observacao", ""),
    }
    if reg["valor_cent"] <= 0:
        raise ValueError("Valor do contrato deve ser maior que zero.")
    if not 1 <= reg["dia_vencimento"] <= 31:
        raise ValueError("Dia de vencimento deve estar entre 1 e 31.")
    with db.conexao() as con:
        if d.get("id"):
            con.execute(f"UPDATE contratos SET {', '.join(f'{k}=?' for k in reg)} WHERE id=?",
                        (*reg.values(), int(d["id"])))
            reg["id"] = int(d["id"])
        else:
            cur = con.execute(f"INSERT INTO contratos ({', '.join(reg)}, criado_em) VALUES "
                              f"({', '.join('?' * len(reg))}, ?)", (*reg.values(), db.agora()))
            reg["id"] = cur.lastrowid
    return reg


def excluir_contrato(cid: int) -> None:
    with db.conexao() as con:
        con.execute("UPDATE contratos SET ativo=0 WHERE id=?", (cid,))


def contratos_do_historico(dia_vencimento: int | None = None) -> int:
    """Cria um contrato mensal para cada cliente com nota recente (últimos 120 dias), pelo valor da última nota."""
    existentes = {c["cpf_cnpj"] for c in db.linhas("SELECT cpf_cnpj FROM contratos WHERE ativo=1")}
    limite = (hoje() - timedelta(days=120)).isoformat()
    criados = 0
    for c in clientes.listar():
        if c["cpf_cnpj"] in existentes or not c.get("ultimo_valor") or c.get("ultima_data", "") < limite:
            continue
        salvar_contrato({"cpf_cnpj": c["cpf_cnpj"], "valor": c["ultimo_valor"],
                         "dia_vencimento": dia_vencimento, "observacao": "Criado a partir do histórico de notas"})
        criados += 1
    return criados


# ---------------------------------------------------------------- títulos (contas a receber)

def _nome(doc: str) -> str:
    return (clientes.obter(doc) or {}).get("razao_social", doc)


def gerar_titulos(competencia: str | None = None, em: date | None = None) -> list[int]:
    """Recorrência: cria o título do mês para cada contrato ativo (idempotente). Aplica reajuste anual."""
    em = em or hoje()
    comp = competencia or competencia_de(em)
    ano, mes = _mes(comp)
    novos = []
    with db.conexao() as con:
        for k in con.execute("SELECT * FROM contratos WHERE ativo=1 AND confirmado=1").fetchall():
            k = dict(k)
            if comp < k["inicio"] or (k["fim"] and comp > k["fim"]):
                continue
            if k["mes_reajuste"] == mes and k["reajuste_pct"] and k["ultimo_reajuste"] < ano \
                    and k["inicio"] < f"{ano}-{mes:02d}":
                novo = int((Decimal(k["valor_cent"]) * (1 + Decimal(str(k["reajuste_pct"])) / 100))
                           .quantize(Decimal("1"), ROUND_HALF_UP))
                con.execute("UPDATE contratos SET valor_cent=?, ultimo_reajuste=? WHERE id=?", (novo, ano, k["id"]))
                con.execute("INSERT INTO log (quando,tipo,mensagem) VALUES (?,?,?)",
                            (db.agora(), "reajuste", f"Contrato {k['id']}: {reais(k['valor_cent'])} -> {reais(novo)} "
                             f"({k['reajuste_pct']}%)"))
                k["valor_cent"] = novo
            cur = con.execute(
                "INSERT OR IGNORE INTO titulos (cpf_cnpj, cliente_nome, contrato_id, competencia, descricao, valor_cent,"
                " vencimento, nfse_status, criado_em, servico_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (k["cpf_cnpj"], _nome(k["cpf_cnpj"]), k["id"], comp, k["descricao"], k["valor_cent"],
                 dia_no_mes(ano, mes, k["dia_vencimento"]).isoformat(),
                 "pendente" if k["emitir_nfse"] else "nao_emitir", db.agora(), k.get("servico_id") or ""))
            if cur.rowcount:
                novos.append(cur.lastrowid)
    if novos:
        db.registrar("recorrencia", f"{len(novos)} título(s) gerado(s) para {comp}")
    return novos


def gerar_decimo_terceiro(em: date | None = None) -> list[int]:
    """13º honorário: em novembro e dezembro, cobra o honorário mensal de cada contrato em parcelas
    (padrão 50% em 30/11 e 50% em 20/12). Gera a parcela a partir do mês dela; idempotente."""
    em = em or hoje()
    d = config.carregar()["decimo_terceiro"]
    if not d.get("ativo"):
        return []
    novos = []
    with db.conexao() as con:
        for n, parc in enumerate(d["parcelas"], 1):
            mes, dia = (int(x) for x in str(parc["vencimento"]).split("/")[::-1])  # "30/11" -> 11, 30
            if em.month < mes or em.month > 12 or not float(parc["percentual"]):
                continue
            comp = f"{em.year}-{mes:02d}"
            venc = dia_no_mes(em.year, mes, dia)
            if em > venc:  # não cria parcela já vencida (evita multa/juros de surpresa se o sistema ficou parado)
                continue
            for k in con.execute("SELECT * FROM contratos WHERE ativo=1 AND confirmado=1").fetchall():
                if k["inicio"] > comp or (k["fim"] and k["fim"] < comp):
                    continue
                origem = f"13o:{k['id']}:{em.year}:{n}"
                if con.execute("SELECT 1 FROM titulos WHERE origem=?", (origem,)).fetchone():
                    continue
                valor = int((Decimal(k["valor_cent"]) * Decimal(str(parc["percentual"])) / 100)
                            .quantize(Decimal("1"), ROUND_HALF_UP))
                total = len(d["parcelas"])
                desc = f"{d.get('descricao') or '13º HONORÁRIO'} {em.year}" + (f" - PARCELA {n}/{total}" if total > 1 else "")
                emitir = k["emitir_nfse"] and d.get("emitir_nfse", True)
                cur = con.execute(
                    "INSERT INTO titulos (cpf_cnpj, cliente_nome, competencia, descricao, valor_cent, vencimento,"
                    " nfse_status, criado_em, origem, servico_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (k["cpf_cnpj"], _nome(k["cpf_cnpj"]), comp, desc[:190], valor, venc.isoformat(),
                     "pendente" if emitir else "nao_emitir", db.agora(), origem, k["servico_id"] or ""))
                novos.append(cur.lastrowid)
    if novos:
        db.registrar("13o", f"{len(novos)} parcela(s) do 13º honorário gerada(s)")
    return novos


def criar_titulo(cpf_cnpj: str, valor, descricao: str = "", vencimento: str = "", competencia: str = "",
                 emitir_nfse: bool = True, servico_id: str = "") -> int:
    doc = clientes._digitos(cpf_cnpj)
    if not clientes.obter(doc):
        raise ValueError("Cliente não cadastrado.")
    fin = config.carregar()["financeiro"]
    servico_id = servico_id or (clientes.obter(doc) or {}).get("servico_id") or ""
    venc = vencimento or (hoje() + timedelta(days=int(fin["prazo_avulso_dias"]))).isoformat()
    with db.conexao() as con:
        cur = con.execute(
            "INSERT INTO titulos (cpf_cnpj, cliente_nome, competencia, descricao, valor_cent, vencimento, nfse_status,"
            " criado_em, servico_id) VALUES (?,?,?,?,?,?,?,?,?)",
            (doc, _nome(doc), competencia or competencia_de(hoje()),
             (descricao or servicos.obter(servico_id)["descricao"])
             .strip()[:190], cent(valor), venc, "pendente" if emitir_nfse else "nao_emitir", db.agora(), servico_id or ""))
        return cur.lastrowid


def obter_titulo(tid: int) -> dict:
    r = db.linhas("SELECT * FROM titulos WHERE id=?", (tid,))
    if not r:
        raise ValueError(f"Título {tid} não encontrado.")
    return r[0]


def listar_titulos(filtro: str = "todos", cpf_cnpj: str = "", competencia: str = "", em: date | None = None) -> list[dict]:
    sql, p = "SELECT * FROM titulos WHERE 1=1", []
    if cpf_cnpj:
        sql += " AND cpf_cnpj=?"
        p.append(clientes._digitos(cpf_cnpj))
    if competencia:
        sql += " AND competencia=?"
        p.append(competencia)
    lst = [enriquecer(t, em) for t in db.linhas(sql + " ORDER BY vencimento, id", p)]
    if filtro in ("aberto", "atrasado", "pago", "cancelado"):
        lst = [t for t in lst if t["situacao"] == filtro]
    elif filtro == "a_receber":
        lst = [t for t in lst if t["status"] == "aberto"]
    elif filtro == "sem_nfse":
        lst = [t for t in lst if t["nfse_status"] in ("pendente", "erro", "teste", "emitindo")
               and t["status"] != "cancelado"]
    return lst


def atualizar_titulo(tid: int, **campos) -> None:
    if not campos:
        return
    with db.conexao() as con:
        con.execute(f"UPDATE titulos SET {', '.join(f'{k}=?' for k in campos)} WHERE id=?", (*campos.values(), tid))


def baixar(tid: int, data: str = "", valor=None, forma: str = "manual") -> dict:
    t = obter_titulo(tid)
    if t["status"] == "cancelado":
        raise ValueError("Título cancelado não pode ser baixado.")
    pago = cent(valor) if valor not in (None, "") else encargos(t)["total_cent"]
    atualizar_titulo(tid, status="pago", data_pagamento=data or hoje().isoformat(), valor_pago_cent=pago,
                     forma_pagamento=forma)
    db.registrar("baixa", f"Título {tid} ({t['cliente_nome']}) pago R$ {reais(pago)} via {forma}")
    return obter_titulo(tid)


def estornar(tid: int) -> None:
    atualizar_titulo(tid, status="aberto", data_pagamento="", valor_pago_cent=0, forma_pagamento="")
    with db.conexao() as con:
        con.execute("UPDATE movimentos SET titulo_id=NULL WHERE titulo_id=?", (tid,))


def cancelar_titulo(tid: int, motivo: str = "") -> None:
    t = obter_titulo(tid)
    if t["status"] == "pago":
        raise ValueError("Título pago: faça o estorno antes de cancelar.")
    atualizar_titulo(tid, status="cancelado", observacao=(t["observacao"] + " " + motivo).strip())
    db.registrar("cancelamento", f"Título {tid} cancelado. {motivo}")


def emitir_nfse_titulo(tid: int, url: str | None = None) -> dict:
    """Emite a NFS-e do título (homologação ou produção, conforme o ambiente) e grava o resultado."""
    t = obter_titulo(tid)
    if t["nfse_status"] in ("emitida", "nao_emitir"):
        return {"sucesso": t["nfse_status"] == "emitida", "erros": [] if t["nfse_status"] == "emitida"
                else ["Título marcado para não emitir NFS-e."], "titulo": t}
    # Reserva atômica: só um processo (tela, robô da tela ou robô agendado) emite cada título.
    with db.conexao() as con:
        reservado = con.execute("UPDATE titulos SET nfse_status='emitindo' WHERE id=? AND nfse_status IN "
                                "('pendente','teste','erro')", (tid,)).rowcount
    if not reservado:
        return {"sucesso": False, "erros": ["NFS-e deste título já está sendo emitida."], "titulo": obter_titulo(tid)}
    producao = emissor.em_producao()
    try:
        r = lote.emitir_um(t["cpf_cnpj"], reais(t["valor_cent"]), t["descricao"], producao=producao, url=url,
                           servico_id=t.get("servico_id") or "")
    except Exception:
        atualizar_titulo(tid, nfse_status=t["nfse_status"])
        raise
    if r["sucesso"]:
        atualizar_titulo(tid, nfse_status="emitida" if producao else "teste", nfse_numero=r.get("nfse", ""),
                         nfse_rps=r.get("rps", ""), nfse_link=r.get("link", ""), nfse_erro="",
                         nfse_canal=r.get("canal", "municipal"), nfse_chave=r.get("chave", ""))
    else:
        msg = "; ".join(r.get("erros", []))[:500]
        transitoria = any(x in msg.lower() for x in ("falha de comunicação", "timed out", "tempo esgotado",
                                                     "connection", "temporarily"))
        # rede/servidor fora do ar: fica pendente e o robô tenta de novo; recusa da prefeitura vai para revisão
        atualizar_titulo(tid, nfse_status="pendente" if transitoria else "erro", nfse_erro=msg)
    db.registrar("nfse", f"Título {tid} ({t['cliente_nome']}): {'NFS-e ' + r.get('nfse', '') if r['sucesso'] else 'erro'}")
    return r | {"titulo": obter_titulo(tid)}


def emitir_avulsa(cpf_cnpj: str, valor, descricao: str = "", vencimento: str = "", url: str | None = None,
                  servico_id: str = "") -> dict:
    """Fluxo da aba 'Emitir nota': cria a conta a receber e emite a NFS-e dela com o serviço escolhido."""
    tid = criar_titulo(cpf_cnpj, valor, descricao, vencimento, servico_id=servico_id)
    r = emitir_nfse_titulo(tid, url=url)
    if not r["sucesso"]:
        cancelar_titulo(tid, "NFS-e não emitida")
    elif not emissor.em_producao():
        cancelar_titulo(tid, "teste em homologação (não entra no financeiro)")
    return r | {"titulo_id": tid}


# ---------------------------------------------------------------- contas a pagar

def salvar_despesa(d: dict) -> int:
    reg = {"descricao": d["descricao"].strip(), "fornecedor": d.get("fornecedor", "").strip(),
           "categoria": d.get("categoria") or "Outras", "valor_cent": cent(d.get("valor")),
           "vencimento": d.get("vencimento") or hoje().isoformat(),
           "recorrente": 1 if d.get("recorrente") else 0, "competencia": (d.get("vencimento") or hoje().isoformat())[:7]}
    if reg["valor_cent"] <= 0 or not reg["descricao"]:
        raise ValueError("Informe descrição e valor.")
    with db.conexao() as con:
        if d.get("id"):
            con.execute(f"UPDATE despesas SET {', '.join(f'{k}=?' for k in reg)} WHERE id=?", (*reg.values(), int(d["id"])))
            return int(d["id"])
        return con.execute(f"INSERT INTO despesas ({', '.join(reg)}, criado_em) VALUES ({', '.join('?' * len(reg))}, ?)",
                           (*reg.values(), db.agora())).lastrowid


def listar_despesas(filtro: str = "todos", em: date | None = None) -> list[dict]:
    em = em or hoje()
    lst = db.linhas("SELECT * FROM despesas ORDER BY vencimento, id")
    for d in lst:
        d["situacao"] = d["status"] if d["status"] != "aberto" else (
            "atrasado" if date.fromisoformat(d["vencimento"]) < em else "aberto")
    return lst if filtro == "todos" else [d for d in lst if d["situacao"] == filtro or
                                          (filtro == "a_pagar" and d["status"] == "aberto")]


def pagar_despesa(did: int, data: str = "") -> None:
    with db.conexao() as con:
        con.execute("UPDATE despesas SET status='pago', data_pagamento=? WHERE id=?", (data or hoje().isoformat(), did))


def excluir_despesa(did: int) -> None:
    with db.conexao() as con:
        con.execute("UPDATE despesas SET status='cancelado' WHERE id=?", (did,))


def gerar_despesas_recorrentes(em: date | None = None) -> int:
    """Repete no mês corrente as despesas marcadas como recorrentes (mesmo dia de vencimento)."""
    em = em or hoje()
    comp = competencia_de(em)
    n = 0
    with db.conexao() as con:
        for d in con.execute("SELECT * FROM despesas WHERE recorrente=1 AND origem_id IS NULL AND status!='cancelado'"):
            if d["competencia"] >= comp:
                continue
            venc = dia_no_mes(em.year, em.month, int(d["vencimento"][8:10]))
            cur = con.execute(
                "INSERT OR IGNORE INTO despesas (descricao, fornecedor, categoria, valor_cent, vencimento, recorrente,"
                " origem_id, competencia, criado_em) VALUES (?,?,?,?,?,0,?,?,?)",
                (d["descricao"], d["fornecedor"], d["categoria"], d["valor_cent"], venc.isoformat(), d["id"], comp,
                 db.agora()))
            n += cur.rowcount
    return n
