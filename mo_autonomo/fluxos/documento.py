"""Subgrafo por documento: classificar -> identificar empresa -> perfil + regras -> registrar."""
from __future__ import annotations

from ..documentos.classificador import classificar
from ..dominio.pastas import rotas
from ..especialista.motor import avaliar_documento
from ..grafo.motor import FIM, Grafo

FISCAIS = ("NFE", "NFCE", "CTE", "NFSE", "EVENTO_NFE", "EVENTO_NFCE", "EVENTO_CTE", "EVENTO_OUTRO")


def n_classificar(e, ctx):
    """Classifica pelo conteúdo."""
    r = classificar(e["dados"])
    doc = r["doc"]
    if doc is not None:
        doc["_sha256"] = e["sha256"]
    return {"classe": r["classe"], "doc": doc, "erro_leitura": r["erro"]}


def rota_classe(e):
    c = e["classe"]
    if c in FISCAIS:
        return "identificar_empresas"
    if c == "OFX":
        return "extrato"
    if c in ("PDF", "IMAGEM"):
        return "leitura_ia"
    return "pendente_humano"


def n_identificar(e, ctx):
    """Cruza participantes com a carteira por CNPJ e define a pasta do Domínio."""
    rs = rotas(e["doc"], ctx.carteira, ctx.catalogo)
    pend = [{"codigo": "ROTA_PENDENTE", "mensagem": r.pendencia, "cnpj": r.cnpj, "referencia": e["sha256"]}
            for r in rs if r.pendencia]
    return {"rotas": [{"cnpj": r.cnpj, "tipo": r.tipo} for r in rs if r.tipo],
            "pendencias": e.get("pendencias", []) + pend}


def n_analisar(e, ctx):
    """Perfil da empresa na data do documento + regras do especialista."""
    doc = e["doc"]
    achados, pend = [], list(e.get("pendencias", []))
    data = doc.get("emissao") or ctx.hoje
    cnpjs = list(dict.fromkeys([r["cnpj"] for r in e.get("rotas", [])] +
                               [p["cnpj"] for p in pend if p.get("cnpj")]))
    for cnpj in cnpjs:
        perfil = ctx.perfis.em(cnpj, data)
        if perfil is None:
            continue
        for p in perfil.pendencias:
            if p.bloqueia:
                pend.append({**p.como_dict(), "referencia": e["sha256"]})
        achados += [a.como_dict() for a in avaliar_documento(doc, perfil, ctx.catalogo, ctx.hoje)]
    return {"achados": achados, "pendencias": pend}


def n_extrato(e, ctx):
    """Identifica a empresa dona de cada conta do OFX (contas_bancarias) — um OFX pode ter várias."""
    from ..util.documentos_id import so_digitos
    contas = ctx.extras.get("contas_bancarias") or {}
    extratos, pend = [], list(e.get("pendencias", []))
    for ex in e["doc"]["extratos"]:
        conta = ex["conta"]
        k = (so_digitos(conta.get("banco") or "").lstrip("0"), so_digitos(conta.get("conta") or "").lstrip("0"))
        info = contas.get(k)
        if not info:
            pend.append({"codigo": "CONTA_BANCARIA_DESCONHECIDA", "cnpj": None, "referencia": e["sha256"],
                         "mensagem": f"Extrato do banco {conta.get('banco')} conta {conta.get('conta')} "
                                     "sem cadastro em contas_bancarias."})
        elif ctx.carteira.get(info["cnpj"]) is None:
            pend.append({"codigo": "CONTA_DE_EMPRESA_FORA_DA_CARTEIRA", "cnpj": None, "referencia": e["sha256"],
                         "mensagem": f"Conta {conta.get('conta')} cadastrada para CNPJ {info['cnpj']}, "
                                     "que não está no cadastro de empresas."})
        else:
            extratos.append({"cnpj": info["cnpj"], "conta_contabil": info["conta_contabil"],
                             "banco": conta.get("banco"), "conta": conta.get("conta"), "transacoes": ex["transacoes"]})
    return {"extratos_empresa": extratos, "pendencias": pend}


def n_leitura_ia(e, ctx):
    """PDF/imagem: texto extraído e lido pela cascata de IA (validado por código)."""
    if ctx.cascata is None:
        return {"leitura": {"status": "PENDENTE", "motivo": "IA desativada no config"}}
    from ..ia.leitor import extrair_texto_pdf, ler_nao_estruturado
    texto = ""
    if e["classe"] == "PDF":
        try:
            texto = extrair_texto_pdf(e["dados"])
        except Exception as exc:  # noqa: BLE001
            return {"leitura": {"status": "PENDENTE", "motivo": f"PDF ilegível: {exc}"}}
    nomes = [emp.apelido for emp in ctx.carteira] + list(ctx.extras.get("razoes_sociais") or [])
    minimo = float((ctx.config.get("ia") or {}).get("confianca_minima", 0.8))
    return {"leitura": ler_nao_estruturado(texto, ctx.cascata, minimo, nomes)}


def rota_leitura(e):
    return "arquivar" if e["leitura"]["status"] == "OK" else "pendente_humano"


def n_arquivar(e, ctx):
    """Leitura OK: arquiva na pasta da empresa (organização) — ou pendência se não der para afirmar a empresa."""
    l = e["leitura"]
    emp = ctx.carteira.get(l.get("cnpj")) if l.get("cnpj") else None
    if emp is None or not l.get("competencia"):
        motivo = "empresa não identificada pelo CNPJ" if emp is None else "competência não identificada"
        return {"pendencias": e.get("pendencias", []) + [{
            "codigo": "DOCUMENTO_A_ARQUIVAR", "cnpj": emp.cnpj if emp else None, "referencia": e["sha256"],
            "mensagem": f"{e['nome']}: lido como {l.get('tipo')} ({l.get('resumo')}); {motivo}."}]}
    doc = {"tipo": l["tipo"], "competencia": l["competencia"], "chave": None, "emissao": None,
           "totais": {"valor": l.get("valor")}, "participantes": [emp.cnpj]}
    return {"doc": doc, "rotas": [{"cnpj": emp.cnpj, "tipo": "ARQUIVO"}]}


def n_pendente(e, ctx):
    """Documento que precisa de olho humano (não reconhecido, ilegível, baixa confiança)."""
    motivo = e.get("erro_leitura") or (e.get("leitura") or {}).get("motivo") or f"classe {e['classe']}"
    status = (e.get("leitura") or {}).get("status")
    codigo = "FILA_IA" if status == "FILA" else "DOCUMENTO_NAO_PROCESSADO"
    return {"pendencias": e.get("pendencias", []) + [{"codigo": codigo, "mensagem": f"{e['nome']}: {motivo}",
                                                      "cnpj": None, "referencia": e["sha256"]}]}


def n_falha(e, ctx):
    """Nó de exceção: erro inesperado vira pendência com o motivo (nunca some)."""
    ultimo = (e.get("_erros") or [{}])[-1]
    return {"pendencias": e.get("pendencias", []) + [{
        "codigo": "ERRO_PROCESSAMENTO", "cnpj": None, "referencia": e["sha256"],
        "mensagem": f"{e.get('nome')}: falha em {ultimo.get('no')}: {ultimo.get('erro')}"}]}


def n_registrar(e, ctx):
    """Grava o documento na trilha."""
    doc = e.get("doc") or {}
    pend = e.get("pendencias") or []
    situacao = "FILA" if any(p["codigo"] == "FILA_IA" for p in pend) else ("PENDENTE" if pend else "OK")
    resumo = resumo_documento(doc)
    resumo["_versao_base"] = getattr(ctx, "versao_base", None)
    ctx.trilha.registrar_documento(
        e["sha256"], e.get("classe", "ERRO"), doc.get("chave"), [r["cnpj"] for r in e.get("rotas", [])],
        doc.get("competencia"), e.get("rotas", []), situacao, resumo)
    return {}


def resumo_documento(doc: dict) -> dict:
    """O mínimo para cruzamentos do mês sem reler o XML (faturamento, cancelamentos)."""
    if not doc:
        return {}
    return {"tipo": doc.get("tipo"), "emitente": doc.get("emitente_cnpj"), "prestador": doc.get("prestador_cnpj"),
            "tp_nf": doc.get("tp_nf"), "valor": valor_documento(doc), "chave_ref": doc.get("chave_ref"),
            "tp_evento": doc.get("tp_evento"), "cstat": doc.get("autorizacao_cstat"), "emissao": doc.get("emissao"),
            "modelo": doc.get("modelo"), "serie": doc.get("serie"), "numero": doc.get("numero"),
            "cancelada": doc.get("cancelada", False)}


def valor_documento(doc: dict):
    t = (doc or {}).get("totais") or {}
    return next((t[k] for k in ("vNF", "vServ", "vTPrest", "valor") if t.get(k) is not None), None)


def grafo_documento() -> Grafo:
    g = Grafo("documento")
    g.no("classificar", n_classificar)
    g.no("identificar_empresas", n_identificar)
    g.no("analisar", n_analisar)
    g.no("extrato", n_extrato)
    g.no("leitura_ia", n_leitura_ia)
    g.no("arquivar", n_arquivar)
    g.no("pendente_humano", n_pendente)
    g.no("falha", n_falha)
    g.no("registrar", n_registrar)
    g.rotear("classificar", rota_classe, ("identificar_empresas", "extrato", "leitura_ia", "pendente_humano"))
    g.ligar("identificar_empresas", "analisar")
    g.ligar("analisar", "registrar")
    g.ligar("extrato", "registrar")
    g.rotear("leitura_ia", rota_leitura, ("arquivar", "pendente_humano"))
    g.ligar("arquivar", "registrar")
    g.ligar("pendente_humano", "registrar")
    g.ligar("falha", "registrar")
    g.ligar("registrar", FIM)
    g.excecao("falha")
    return g
