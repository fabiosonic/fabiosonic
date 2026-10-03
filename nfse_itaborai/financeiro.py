"""Contratos recorrentes, contas a receber (integradas à NFS-e) e contas a pagar."""

from __future__ import annotations

import calendar
import json
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


# Só está "em cobrança" (a receber, atraso, inadimplência, previsão de caixa) o título com cobrança de fato
# gerada: boleto registrado ou PIX. Nota emitida sem boleto/PIX é faturamento, não valor a receber cobrado.
SQL_COBRADO = "cobrar=1 AND (banco_id!='' OR pix_copia_cola!='' OR linha_digitavel!='')"


def tem_cobranca(t: dict) -> bool:
    return bool(t.get("cobrar", 1)) and bool(t.get("banco_id") or t.get("pix_copia_cola") or t.get("linha_digitavel"))


def situacao(titulo: dict, em: date | None = None) -> str:
    if titulo["status"] != "aberto":
        return titulo["status"]
    if not tem_cobranca(titulo):
        return "sem_cobranca"   # sem boleto/PIX: não é cobrado, não entra em a receber, atraso nem régua
    return "atrasado" if date.fromisoformat(titulo["vencimento"]) < (em or hoje()) else "aberto"


def enriquecer(t: dict, em: date | None = None) -> dict:
    return t | encargos(t, em) | {"situacao": situacao(t, em)}


# ---------------------------------------------------------------- contratos

CAMPOS_CONTRATO = ("cpf_cnpj", "descricao", "valor_cent", "dia_vencimento", "inicio", "fim", "ativo",
                   "emitir_nfse", "mes_reajuste", "reajuste_pct", "observacao", "cobrar", "nfse_quando")


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
        "cobrar": 0 if d.get("cobrar", True) in (False, 0, "0", "false") else 1,
        # '' = padrão da empresa | agora = emite ao gerar o título | pagamento = emite quando o cliente pagar
        "nfse_quando": _regra(d.get("nfse_quando")),
    }
    if "confirmado" in d:
        reg["confirmado"] = 0 if d["confirmado"] in (False, 0, "0", "false") else 1
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


def _mes_seguinte(comp: str) -> str:
    ano, mes = _mes(comp)
    return f"{ano + mes // 12}-{mes % 12 + 1:02d}"


def preencher_recorrencia() -> int:
    """Põe na recorrência todo cliente que ainda não tem, com o valor da última nota, como 'a confirmar'.
    Nada é cobrado até o usuário marcar 'Repetir todo mês' (confirmado)."""
    com_contrato = {c["cpf_cnpj"] for c in db.linhas("SELECT cpf_cnpj FROM contratos")}
    criados = 0
    for c in clientes.listar():
        if c["cpf_cnpj"] in com_contrato or cent(c.get("ultimo_valor") or 0) <= 0:
            continue
        base = (c.get("ultima_data") or hoje().isoformat())[:7]   # o mês da última nota já está faturado
        salvar_contrato({"cpf_cnpj": c["cpf_cnpj"], "valor": c["ultimo_valor"], "servico_id": c.get("servico_id") or "",
                         "inicio": _mes_seguinte(base),
                         "confirmado": False, "observacao": "Valor da última nota (a confirmar)"})
        criados += 1
    if criados:
        db.registrar("recorrencia", f"{criados} cliente(s) colocados na recorrência a confirmar")
    return criados


def lista_recorrencia() -> list[dict]:
    """Uma linha por recorrência e uma linha para cada cliente ainda sem recorrência."""
    geral = regra_geral()
    lst = listar_contratos()
    com = {k["cpf_cnpj"] for k in lst}
    linhas = [k | {"repetir": bool(k["ativo"] and k["confirmado"]), "regra": regra_do_contrato(k, geral)}
              for k in lst if k["ativo"]]
    for c in clientes.listar():
        if c["cpf_cnpj"] not in com:
            linhas.append({"id": None, "cpf_cnpj": c["cpf_cnpj"], "cliente_nome": c["razao_social"], "valor_cent": 0,
                           "dia_vencimento": int(config.carregar()["financeiro"]["dia_vencimento_padrao"]),
                           "servico_id": "", "nfse_quando": "", "cobrar": 1, "repetir": False, "regra": geral,
                           "ativo": 1, "confirmado": 0, "inicio": "", "fim": ""})
    return sorted(linhas, key=lambda x: (not x["repetir"], x["cliente_nome"].upper()))


def salvar_recorrencia(linhas: list[dict]) -> dict:
    """Grava as linhas alteradas na aba Recorrência. 'repetir' = entra na cobrança mensal (confirmado)."""
    atuais = {k["id"]: k for k in db.linhas("SELECT * FROM contratos")}
    salvos = 0
    for l in linhas:
        valor = l.get("valor_cent") if "valor_cent" in l else cent(l.get("valor") or 0)
        dados = {"servico_id": l.get("servico_id") or "", "nfse_quando": l.get("nfse_quando") or "",
                 "cobrar": l.get("cobrar", True), "confirmado": bool(l.get("repetir")),
                 "dia_vencimento": l.get("dia_vencimento"), "valor_cent": valor}
        if l.get("id") and int(l["id"]) in atuais:
            k = atuais[int(l["id"])]
            if dados["confirmado"] and not k["confirmado"] and k["inicio"] < competencia_de(hoje()):
                dados["inicio"] = competencia_de(hoje())   # confirmou agora: cobra a partir deste mês
            salvar_contrato({**k, "descricao": k["descricao"] if k.get("servico_id") == dados["servico_id"] else "",
                             **dados, "id": k["id"]})
        elif valor > 0:
            salvar_contrato({"cpf_cnpj": l["cpf_cnpj"], **dados, "inicio": competencia_de(hoje())})
        else:
            continue
        salvos += 1
    return {"salvos": salvos}


# ---------------------------------------------------------------- títulos (contas a receber)

def _nome(doc: str) -> str:
    return (clientes.obter(doc) or {}).get("razao_social", doc)


REGRAS_NFSE = {"geracao": "Emitir NFS-e na geração do contas a receber",
               "baixa": "Emitir NFS-e ao efetuar a baixa do contas a receber",
               "lancar": "Apenas lançar o contas a receber, sem emitir NFS-e",
               "nada": "Não emitir NFS-e e não lançar (recorrência parada)"}
_LEGADO = {"agora": "geracao", "pagamento": "baixa"}


def _regra(valor) -> str:
    v = _LEGADO.get(str(valor or ""), str(valor or ""))
    return v if v in REGRAS_NFSE else ""


def regra_geral(cfg: dict | None = None) -> str:
    e = (cfg or config.carregar())["emissao"]
    return _regra(e.get("nfse_quando")) or ("baixa" if e.get("nfse_apos_pagamento") else "geracao")


def regra_do_contrato(k: dict, geral: str | None = None) -> str:
    """A regra da recorrência do cliente vale primeiro; sem regra própria, vale a geral."""
    if not k.get("emitir_nfse", 1):
        return "lancar"
    return _regra(k.get("nfse_quando")) or geral or regra_geral()


def regra_do_cliente(cpf_cnpj: str, geral: str | None = None) -> str:
    doc = clientes._digitos(cpf_cnpj)
    ks = db.linhas("SELECT * FROM contratos WHERE cpf_cnpj=? AND ativo=1 ORDER BY confirmado DESC, id", (doc,))
    return regra_do_contrato(ks[0], geral) if ks else (geral or regra_geral())


def regras_por_cliente() -> dict:
    geral = regra_geral()
    out = {}
    for k in db.linhas("SELECT * FROM contratos WHERE ativo=1 ORDER BY confirmado, id DESC"):
        out[k["cpf_cnpj"]] = regra_do_contrato(k, geral)
    return out


def _status_da_regra(regra: str) -> str:
    return {"baixa": "apos_pagamento", "lancar": "nao_emitir"}.get(regra, "pendente")


def status_nfse_inicial(emitir: bool, apos_pagamento: bool | None = None) -> str:
    """pendente = emite já; apos_pagamento = emite sozinha quando o pagamento for confirmado; nao_emitir."""
    if not emitir:
        return "nao_emitir"
    if apos_pagamento is None:
        r = regra_geral()
        return _status_da_regra(r if r != "nada" else "lancar")
    return "apos_pagamento" if apos_pagamento else "pendente"


def gerar_titulos(competencia: str | None = None, em: date | None = None) -> list[int]:
    """Recorrência: cria o título do mês para cada contrato ativo (idempotente). Aplica reajuste anual."""
    em = em or hoje()
    comp = competencia or competencia_de(em)
    ano, mes = _mes(comp)
    novos = []
    geral = regra_geral()
    with db.conexao() as con:
        for k in con.execute("SELECT * FROM contratos WHERE ativo=1 AND confirmado=1").fetchall():
            k = dict(k)
            if comp < k["inicio"] or (k["fim"] and comp > k["fim"]):
                continue
            regra = regra_do_contrato(k, geral)
            if regra == "nada":
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
                " vencimento, nfse_status, criado_em, servico_id, cobrar) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (k["cpf_cnpj"], _nome(k["cpf_cnpj"]), k["id"], comp, k["descricao"], k["valor_cent"],
                 dia_no_mes(ano, mes, k["dia_vencimento"]).isoformat(),
                 _status_da_regra(regra), db.agora(), k.get("servico_id") or "", k.get("cobrar", 1)))
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
                k = dict(k)
                if k["inicio"] > comp or (k["fim"] and k["fim"] < comp):
                    continue
                origem = f"13o:{k['id']}:{em.year}:{n}"
                if con.execute("SELECT 1 FROM titulos WHERE origem=?", (origem,)).fetchone():
                    continue
                valor = int((Decimal(k["valor_cent"]) * Decimal(str(parc["percentual"])) / 100)
                            .quantize(Decimal("1"), ROUND_HALF_UP))
                total = len(d["parcelas"])
                desc = f"{d.get('descricao') or '13º HONORÁRIO'} {em.year}" + (f" - PARCELA {n}/{total}" if total > 1 else "")
                regra = regra_do_contrato(k)
                if regra == "nada":
                    continue
                emitir = d.get("emitir_nfse", True) and regra != "lancar"
                cur = con.execute(
                    "INSERT INTO titulos (cpf_cnpj, cliente_nome, competencia, descricao, valor_cent, vencimento,"
                    " nfse_status, criado_em, origem, servico_id, cobrar) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (k["cpf_cnpj"], _nome(k["cpf_cnpj"]), comp, desc[:190], valor, venc.isoformat(),
                     _status_da_regra(regra) if emitir else "nao_emitir", db.agora(), origem, k["servico_id"] or "",
                     k.get("cobrar", 1)))
                novos.append(cur.lastrowid)
    if novos:
        db.registrar("13o", f"{len(novos)} parcela(s) do 13º honorário gerada(s)")
    return novos


def criar_titulo(cpf_cnpj: str, valor, descricao: str = "", vencimento: str = "", competencia: str = "",
                 emitir_nfse: bool = True, servico_id: str = "", cobrar: bool = True,
                 apos_pagamento: bool | None = False, extras: dict | None = None) -> int:
    doc = clientes._digitos(cpf_cnpj)
    if not clientes.obter(doc):
        raise ValueError("Cliente não cadastrado.")
    fin = config.carregar()["financeiro"]
    servico_id = servico_id or (clientes.obter(doc) or {}).get("servico_id") or ""
    from . import fiscal
    extras_json = json.dumps(fiscal.normalizar_nota(extras), ensure_ascii=False) if extras else ""
    venc = vencimento or (hoje() + timedelta(days=int(fin["prazo_avulso_dias"]))).isoformat()
    with db.conexao() as con:
        cur = con.execute(
            "INSERT INTO titulos (cpf_cnpj, cliente_nome, competencia, descricao, valor_cent, vencimento, nfse_status,"
            " criado_em, servico_id, cobrar, extras) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (doc, _nome(doc), competencia or competencia_de(hoje()),
             (descricao or servicos.obter(servico_id)["descricao"])
             .strip()[:190], cent(valor), venc, status_nfse_inicial(emitir_nfse, apos_pagamento), db.agora(), servico_id or "",
             int(bool(cobrar)), extras_json))
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
        lst = [t for t in lst if t["situacao"] in ("aberto", "atrasado")]
    elif filtro == "sem_cobranca":
        lst = [t for t in lst if t["situacao"] == "sem_cobranca"]
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
    if t["nfse_status"] == "apos_pagamento":
        # nota só depois do pagamento: liberou agora; em produção emite já (o robô repete se a prefeitura falhar)
        atualizar_titulo(tid, nfse_status="pendente")
        if emissor.em_producao():
            try:
                emitir_nfse_titulo(tid)
            except Exception as ex:  # noqa: BLE001 — a baixa vale mesmo se a emissão falhar; o robô tenta de novo
                db.registrar("nfse", f"Título {tid}: emissão após o pagamento ficou pendente ({ex})")
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
                           servico_id=t.get("servico_id") or "", extras=json.loads(t.get("extras") or "{}"))
    except Exception:
        atualizar_titulo(tid, nfse_status=t["nfse_status"])
        raise
    if r["sucesso"]:
        atualizar_titulo(tid, nfse_status="emitida" if producao else "teste", nfse_numero=r.get("nfse", ""),
                         nfse_data=hoje().isoformat(),
                         nfse_rps=r.get("rps", ""), nfse_link=r.get("link", ""), nfse_erro="",
                         nfse_canal=r.get("canal", "municipal"), nfse_chave=r.get("chave", ""))
        subst = json.loads(t.get("extras") or "{}").get("subst_chave")
        if subst and producao:      # a nota substituída deixa de valer (fica cancelada por substituição)
            for velho in db.linhas("SELECT id, status FROM titulos WHERE nfse_chave=? AND id!=?", (subst, tid)):
                atualizar_titulo(velho["id"], nfse_status="cancelada",
                                 observacao=f"Substituída pela NFS-e {r.get('nfse', '')}")
                if velho["status"] == "aberto":
                    cancelar_titulo(velho["id"], "NFS-e substituída")
    else:
        msg = "; ".join(r.get("erros", []))[:500]
        transitoria = any(x in msg.lower() for x in ("falha de comunicação", "timed out", "tempo esgotado",
                                                     "connection", "temporarily"))
        # rede/servidor fora do ar: fica pendente e o robô tenta de novo; recusa da prefeitura vai para revisão
        atualizar_titulo(tid, nfse_status="pendente" if transitoria else "erro", nfse_erro=msg)
    db.registrar("nfse", f"Título {tid} ({t['cliente_nome']}): {'NFS-e ' + r.get('nfse', '') if r['sucesso'] else 'erro'}")
    return r | {"titulo": obter_titulo(tid)}


def emitir_avulsa(cpf_cnpj: str, valor, descricao: str = "", vencimento: str = "", url: str | None = None,
                  servico_id: str = "", cobrar: bool = True, apos_pagamento: bool | None = None,
                  recorrente: bool = False, recorrente_ate: str = "", regra: str = "", extras: dict | None = None) -> dict:
    """Aba 'Emitir nota'. A regra da NFS-e vem da recorrência do cliente (se tiver regra própria) ou da regra
    geral das Configurações; 'regra'/'apos_pagamento' só forçam uma regra quando informados."""
    regra = _regra(regra) or ({True: "baixa", False: "geracao"}.get(apos_pagamento) if apos_pagamento is not None
                              else regra_do_cliente(cpf_cnpj))
    if regra == "nada":
        regra = "lancar"
    apos_pagamento = regra == "baixa"
    r = _faturar_avulsa(cpf_cnpj, valor, descricao, vencimento, url, servico_id, cobrar, regra, extras)
    if recorrente:
        t = obter_titulo(r["titulo_id"])
        if t["status"] == "cancelado":
            r.setdefault("alertas", []).append("Repetição mensal não criada: a nota não foi emitida ou foi só um "
                                               "teste em homologação.")
        else:
            ano, mes = _mes(t["competencia"])
            inicio = f"{ano + mes // 12}-{mes % 12 + 1:02d}"    # o mês atual já está faturado
            k = salvar_contrato({"cpf_cnpj": t["cpf_cnpj"], "valor_cent": t["valor_cent"], "descricao": t["descricao"],
                                 "servico_id": t.get("servico_id") or "", "dia_vencimento": int(t["vencimento"][8:10]),
                                 "inicio": inicio, "fim": recorrente_ate or "", "cobrar": cobrar,
                                 "nfse_quando": "pagamento" if apos_pagamento else "agora"})
            r["contrato_id"] = k["id"]
            db.registrar("contrato", f"Contrato {k['id']} criado pela emissão (todo mês a partir de {inicio})")
    return r


def _faturar_avulsa(cpf_cnpj, valor, descricao, vencimento, url, servico_id, cobrar, regra, extras=None) -> dict:
    """Cria a conta a receber e, conforme a regra, emite a NFS-e agora, só na baixa, ou não emite.

    cobrar=False: só a conta a receber (sem boleto/PIX e fora da régua)."""
    if regra in ("baixa", "lancar"):
        tid = criar_titulo(cpf_cnpj, valor, descricao, vencimento, servico_id=servico_id, cobrar=cobrar,
                           emitir_nfse=regra == "baixa", apos_pagamento=regra == "baixa", extras=extras)
        r = {"sucesso": True, "aguardando_pagamento": regra == "baixa", "sem_nota": regra == "lancar",
             "erros": [], "alertas": [], "titulo_id": tid}
        if cobrar and config.carregar()["cobranca"]["provedor"] != "nenhum":
            from . import cobranca
            try:
                t = cobranca.preparar_pagamento(tid)
                r["boleto"] = bool(t.get("banco_id"))
                r["link"] = t.get("cobranca_link", "")
            except Exception as ex:  # noqa: BLE001 — o robô cria a cobrança na próxima rodada
                r["alertas"].append(f"Cobrança não criada agora ({ex}); o robô tenta de novo.")
        db.registrar("faturamento", f"Título {tid}: " + ("NFS-e após o pagamento" if regra == "baixa"
                                                          else "lançado sem NFS-e"))
        return r | {"titulo": obter_titulo(tid)}
    tid = criar_titulo(cpf_cnpj, valor, descricao, vencimento, servico_id=servico_id, cobrar=cobrar, extras=extras)
    r = emitir_nfse_titulo(tid, url=url)
    if not r["sucesso"]:
        cancelar_titulo(tid, "NFS-e não emitida")
    elif not emissor.em_producao():
        cancelar_titulo(tid, "teste em homologação (não entra no financeiro)")
    return r | {"titulo_id": tid}


# ---------------------------------------------------------------- notas fiscais emitidas

SITUACAO_NOTA = {"emitida": "Emitida", "cancelada": "Cancelada", "teste": "Homologação (teste)"}


def listar_notas(competencia: str = "", situacao: str = "validas", busca: str = "", servico_id: str = "") -> dict:
    """Todas as NFS-e (emitidas pelo sistema ou importadas dos XML), com filtros e totais."""
    sql, p = "SELECT * FROM titulos WHERE nfse_numero!='' AND nfse_status IN ('emitida','cancelada','teste')", []
    if competencia:
        sql += " AND competencia=?"
        p.append(competencia)
    if situacao == "validas":
        sql += " AND nfse_status IN ('emitida','cancelada')"
    elif situacao in SITUACAO_NOTA:
        sql += " AND nfse_status=?"
        p.append(situacao)
    if servico_id:
        sql += " AND servico_id=?"
        p.append(servico_id)
    b = clientes._digitos(busca) if busca else ""
    notas = []
    for t in db.linhas(sql + " ORDER BY competencia DESC, CAST(nfse_numero AS INTEGER) DESC, id DESC", p):
        if busca and not (busca.strip().lower() in t["cliente_nome"].lower() or (b and b in t["cpf_cnpj"])
                          or (b and b == t["nfse_numero"][-len(b):])):
            continue
        notas.append({k: t[k] for k in ("id", "cpf_cnpj", "cliente_nome", "competencia", "descricao", "valor_cent",
                                        "nfse_numero", "nfse_status", "nfse_link", "nfse_canal", "nfse_chave",
                                        "nfse_rps", "status", "origem", "servico_id", "observacao")}
                     | {"data": t.get("nfse_data") or t["criado_em"][:10],
                        "pode_cancelar": t["nfse_status"] == "emitida" and t["origem"] != "importado"})
    emitidas = [n for n in notas if n["nfse_status"] == "emitida"]
    return {"notas": notas, "qtd": len(emitidas), "total_cent": sum(n["valor_cent"] for n in emitidas),
            "canceladas": sum(1 for n in notas if n["nfse_status"] == "cancelada")}


# campos que são de UMA nota só e nunca se repetem na cópia (substituição, documentos, reembolso, pedido)
NAO_COPIAR = ("subst_chave", "subst_motivo", "subst_xmotivo", "ref_nfse", "ded_docs", "pedido")


def dados_da_nota(tid: int) -> dict:
    """Dados para emitir de novo com base numa nota: valor, descrição, serviço e os campos extras da nota."""
    t = obter_titulo(tid)
    extras = {k: v for k, v in json.loads(t.get("extras") or "{}").items()
              if k not in NAO_COPIAR and not k.startswith("ree_")}
    return {"id": t["id"], "cpf_cnpj": t["cpf_cnpj"], "cliente_nome": t["cliente_nome"], "valor_cent": t["valor_cent"],
            "descricao": t["descricao"], "servico_id": t.get("servico_id") or "", "extras": extras,
            "nfse_numero": t.get("nfse_numero") or "", "competencia": t["competencia"],
            "data": t.get("nfse_data") or t["criado_em"][:10], "cobrar": bool(t.get("cobrar"))}


def ultima_nota(cpf_cnpj: str) -> dict | None:
    """Última NFS-e válida emitida para o tomador (do sistema ou importada dos XML)."""
    doc = clientes._digitos(cpf_cnpj)
    linhas = db.linhas("SELECT id FROM titulos WHERE cpf_cnpj=? AND nfse_numero!='' AND nfse_status='emitida' "
                       "ORDER BY COALESCE(NULLIF(nfse_data,''), substr(criado_em,1,10)) DESC, id DESC LIMIT 1", (doc,))
    return dados_da_nota(linhas[0]["id"]) if linhas else None


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
