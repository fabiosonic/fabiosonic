"""Grafo do ciclo completo (de hora em hora pelo Agendador):

capturar -> processar_documentos -> analisar_competencias -> contabil -> montar_lotes
        -> aprovar -> executar -> pareceres -> FIM

Cada passo é checkpoint na trilha: um ciclo interrompido é retomado com `retomar`.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from ..aprovacao import lote as L
from ..contabil.lancamentos import DePara, PlanoContas, _ler_csv, propor
from ..dominio.pastas import ConflitoArquivo, caminho_destino, gravar
from ..entrada.anexos import ZipSuspeito, anexos_do_email
from ..especialista import parecer
from ..especialista.motor import avaliar_competencia, cobertura
from ..grafo.motor import FIM, Grafo
from ..util.arquivos import escrever_atomico, sha256_bytes
from .documento import grafo_documento


def _bruto(ctx, sha: str, nome: str) -> Path:
    return ctx.dados / "_BRUTO_EMAIL" / sha[:2] / f"{sha}_{nome}"


def n_capturar(e, ctx):
    """Lê a caixa (somente leitura), extrai anexos, guarda o bruto e deduplica por sha256."""
    novos, pend, emails = [], [], 0
    for msg in ctx.fonte.mensagens():
        if ctx.trilha.email_lido(msg.uid):
            continue
        emails += 1
        cab = msg.cabecalhos
        try:
            anexos = anexos_do_email(msg.dados, msg.uid)
        except (ZipSuspeito, Exception) as exc:  # noqa: BLE001 — zip ruim não derruba o ciclo
            pend.append({"codigo": "ANEXO_ILEGIVEL", "cnpj": None, "referencia": msg.uid,
                         "mensagem": f"E-mail {cab['assunto']!r} de {cab['remetente']}: {exc}"})
            anexos = []
        for a in anexos:
            sha = sha256_bytes(a.dados)
            caminho = _bruto(ctx, sha, a.nome)
            if not caminho.exists():
                escrever_atomico(caminho, a.dados)
            if ctx.trilha.registrar_anexo(sha, a.nome, a.origem, str(caminho)):
                novos.append({"sha256": sha, "nome": a.nome, "origem": a.origem, "caminho": str(caminho)})
        ctx.trilha.registrar_email(msg.uid, cab["message_id"], cab["remetente"], cab["assunto"], cab["data"])
    ja = {a["sha256"] for a in novos}
    novos += [a for a in ctx.trilha.na_fila() if a["sha256"] not in ja]
    return {"anexos": novos, "emails_lidos": emails, "pendencias_gerais": e.get("pendencias_gerais", []) + pend}


def n_processar(e, ctx):
    """Roda o subgrafo de documento para cada anexo novo."""
    g = grafo_documento()
    resultados = []
    for a in e["anexos"]:
        dados = Path(a["caminho"]).read_bytes()
        r = g.executar({"sha256": a["sha256"], "nome": a["nome"], "dados": dados, "pendencias": []}, ctx)
        r.pop("dados", None)
        r.pop("_ultimo_traceback", None)
        resultados.append({**{k: v for k, v in r.items() if not k.startswith("_")}, "caminho": a["caminho"]})
    return {"documentos": resultados}


def _grupos(e):
    """(cnpj, competência) -> documentos roteados para a empresa."""
    g = defaultdict(list)
    for d in e["documentos"]:
        comp = (d.get("doc") or {}).get("competencia")
        cnpjs = [r["cnpj"] for r in d.get("rotas", [])] + [p["cnpj"] for p in d.get("pendencias", []) if p.get("cnpj")]
        for cnpj in dict.fromkeys(cnpjs):
            g[(cnpj, comp)].append(d)
    return g


def n_analisar_competencias(e, ctx):
    """Regras de escopo competência (duplicidade, sequência, cancelamento)."""
    extra = defaultdict(list)
    for (cnpj, comp), docs in _grupos(e).items():
        perfil = ctx.perfis.em(cnpj, ctx.hoje)
        if perfil is None or comp is None:
            continue
        normais = [d["doc"] for d in docs if d.get("doc")]
        for a in avaliar_competencia(normais, perfil, comp, ctx.catalogo, ctx.hoje, ctx.trilha):
            extra[f"{cnpj}|{comp}"].append(a.como_dict())
    return {"achados_competencia": dict(extra)}


def n_contabil(e, ctx):
    """Extratos OFX -> lançamentos propostos com de-para do razão do cliente."""
    propostas = []
    pasta = ctx.dados / "dominio"
    cfg = ctx.config.get("contabil") or {}
    for d in e["documentos"]:
        cnpj = d.get("extrato_empresa")
        if not cnpj:
            continue
        emp = ctx.carteira.get(cnpj)
        plano_csv, razao_csv = pasta / emp.codigo_dominio / "plano_contas.csv", pasta / emp.codigo_dominio / "razao.csv"
        if not plano_csv.exists() or not razao_csv.exists():
            propostas.append({"cnpj": cnpj, "competencia": None, "lancamentos": [], "pendencias": [{
                "codigo": "SEM_EXPORTACAO_DOMINIO", "cnpj": cnpj, "referencia": d["sha256"],
                "mensagem": f"Faltam plano_contas.csv/razao.csv em {pasta / emp.codigo_dominio}."}]})
            continue
        conta = d["extrato_conta_contabil"]
        r = propor(d["doc"], conta, DePara.do_razao(_ler_csv(razao_csv), conta), PlanoContas.carregar(plano_csv),
                   int(cfg.get("minimo_ocorrencias", 2)), float(cfg.get("dominancia", 0.8)))
        datas = [t["data"] for t in d["doc"]["transacoes"]]
        comp = f"{max(datas):%Y-%m}" if datas else None
        propostas.append({"cnpj": cnpj, "competencia": comp, "lancamentos": r["lancamentos"],
                          "pendencias": [{**p, "cnpj": cnpj, "referencia": p.get("fitid")} for p in r["pendencias"]]})
    return {"contabil": propostas}


def n_montar_lotes(e, ctx):
    """Um lote por empresa × competência × área, para um problema não travar os demais."""
    lotes = []
    run = e["_run_id"][:8]
    pasta = ctx.dados / "lotes"
    comp_achados = e.get("achados_competencia", {})
    for (cnpj, comp), docs in sorted(_grupos(e).items(), key=lambda x: (x[0][0], x[0][1] or "")):
        acoes, achados, pend = [], [], []
        for d in docs:
            achados += [a for a in d.get("achados", []) if a.get("cnpj") == cnpj]
            pend += [p for p in d.get("pendencias", []) if p.get("cnpj") in (cnpj, None)]
            for r in d.get("rotas", []):
                if r["cnpj"] == cnpj and comp:
                    nome = f"{(d.get('doc') or {}).get('chave') or d['sha256']}.xml"
                    acoes.append({"tipo": "copiar_xml_rotina", "sha256": d["sha256"], "origem": d["caminho"],
                                  "pasta_tipo": r["tipo"], "cnpj": cnpj, "competencia": comp, "nome": nome,
                                  "valor": "0"})
        if comp is None:
            pend.append({"codigo": "SEM_COMPETENCIA", "cnpj": cnpj, "mensagem": "documento sem data de competência"})
        achados += comp_achados.get(f"{cnpj}|{comp}", [])
        lote = L.montar_lote(f"FISCAL_{cnpj}_{comp or 'SEMCOMP'}_{run}", acoes, achados, _unicas(pend))
        lotes.append({"id": lote["id"], "cnpj": cnpj, "competencia": comp, "area": "FISCAL",
                      "arquivo": str(L.salvar(lote, pasta)), "hash": lote["hash"]})
    for p in e.get("contabil", []):
        acoes = [{"tipo": "lancamento_contabil", **l, "valor": str(l["valor"])} for l in p["lancamentos"]]
        lote = L.montar_lote(f"CONTABIL_{p['cnpj']}_{p['competencia'] or 'SEMCOMP'}_{run}", acoes, [], p["pendencias"])
        lotes.append({"id": lote["id"], "cnpj": p["cnpj"], "competencia": p["competencia"], "area": "CONTABIL",
                      "arquivo": str(L.salvar(lote, pasta)), "hash": lote["hash"]})
    gerais = list(e.get("pendencias_gerais", []))
    for d in e["documentos"]:
        if not d.get("rotas") and not any(p.get("cnpj") for p in d.get("pendencias", [])):
            gerais += [p for p in d.get("pendencias", [])]
    return {"lotes": lotes, "pendencias_gerais": _unicas(gerais)}


def _unicas(pends):
    vistos, out = set(), []
    for p in pends:
        k = (p.get("codigo"), p.get("mensagem"), p.get("referencia"), p.get("cnpj"))
        if k not in vistos:
            vistos.add(k)
            out.append(p)
    return out


def n_aprovar(e, ctx):
    """Aprovação por exceção (só se ativa e se o lote cumprir todas as condições)."""
    politica = ctx.config.get("aprovacao_por_excecao") or {}
    out = []
    for l in e["lotes"]:
        aprovado = L.aprovar_auto(Path(l["arquivo"]), politica, ctx.trilha)
        motivos = [] if aprovado else L.avaliar_auto(L.carregar(Path(l["arquivo"])), politica).motivos
        out.append({**l, "aprovado": str(aprovado) if aprovado else None, "aguardando": motivos})
    return {"lotes": out}


def executar_lote(caminho_aprovado: Path, ctx) -> list[dict]:
    """Executor: só roda com APROVADO_* íntegro. Nunca sobrescreve arquivo existente."""
    lote = L.exigir_aprovado(caminho_aprovado)
    tipos = ctx.config["dominio"]["tipos_pasta"]
    resultado = []
    for a in lote["acoes"]:
        if a["tipo"] == "copiar_xml_rotina":
            emp = ctx.carteira.get(a["cnpj"])
            destino = caminho_destino(ctx.base_xml, tipos, emp, a["pasta_tipo"], a["competencia"], a["nome"])
            try:
                st = gravar(destino, Path(a["origem"]).read_bytes())
            except ConflitoArquivo as exc:
                st = f"CONFLITO: {exc}"
            resultado.append({"acao": a["tipo"], "destino": str(destino), "status": st})
        elif a["tipo"] == "lancamento_contabil":
            resultado.append({"acao": a["tipo"], "status": "AGUARDANDO_LEIAUTE_DOMINIO",
                              "detalhe": "exportador só é escrito com o leiaute oficial de importação"})
        else:
            resultado.append({"acao": a["tipo"], "status": "SEM_EXECUTOR"})
    ctx.trilha.evento("LOTE_EXECUTADO", lote["id"], resultado)
    return resultado


def n_executar(e, ctx):
    """Executa os lotes aprovados (simulação grava em _STAGING)."""
    out = []
    for l in e["lotes"]:
        if l.get("aprovado"):
            out.append({"lote": l["id"], "resultado": executar_lote(Path(l["aprovado"]), ctx)})
    return {"execucoes": out}


def n_pareceres(e, ctx):
    """Parecer técnico por empresa/competência + resumo do ciclo."""
    pasta = ctx.dados / "pareceres"
    inativas = [c for c in cobertura(ctx.catalogo) if not c["ativa"]]
    gerados = []
    for l in e["lotes"]:
        if l["area"] != "FISCAL" or l["competencia"] is None:
            continue
        lote = L.carregar(Path(l["arquivo"]))
        emp = ctx.carteira.get(l["cnpj"])
        perfil = ctx.perfis.em(l["cnpj"], ctx.hoje)
        md = parecer.markdown(emp, l["competencia"], perfil, lote["achados"], lote["pendencias"],
                              len(lote["acoes"]), inativas)
        gerados.append(parecer.salvar(pasta / l["competencia"], f"{emp.pasta}_{l['id'][-8:]}", md, lote["achados"]))
    resumo = [f"# Resumo do ciclo {e['_run_id'][:8]} — {ctx.hoje:%d/%m/%Y} ({ctx.config['modo']})", "",
              f"- E-mails novos: {e.get('emails_lidos', 0)}", f"- Anexos novos: {len(e.get('anexos', []))}",
              f"- Lotes: {len(e['lotes'])} (auto-aprovados: {sum(1 for l in e['lotes'] if l.get('aprovado'))})", "",
              "## Lotes aguardando APROVADO", ""]
    for l in e["lotes"]:
        if not l.get("aprovado"):
            resumo.append(f"- `{l['id']}` hash `{l['hash'][:16]}…` — {'; '.join(l.get('aguardando') or [])}")
    resumo += ["", "## Vencimentos próximos (calendário conferido)", ""]
    resumo += _alertas_vencimento(ctx) or ["- Nenhum (ou nenhuma obrigação com norma conferida)."]
    resumo += ["", "## Pendências sem empresa identificada", ""]
    resumo += [f"- {p['codigo']}: {p['mensagem']}" for p in e.get("pendencias_gerais", [])] or ["- Nenhuma."]
    caminho = pasta / f"resumo_{e['_run_id'][:8]}.md"
    escrever_atomico(caminho, "\n".join(resumo).encode("utf-8"))
    return {"pareceres": gerados, "resumo": str(caminho)}


def _alertas_vencimento(ctx) -> list[str]:
    from datetime import date as _date

    from ..obrigacoes.calendario import alertas, gerar
    cal = ctx.config.get("calendario") or {}
    feriados = {_date.fromisoformat(str(f)) for f in cal.get("feriados") or []}
    dias = tuple(cal.get("dias_alerta", [3, 0]))
    linhas = []
    y, m = ctx.hoje.year, ctx.hoje.month
    comps = {f"{y:04d}-{m:02d}", f"{y - (m == 1):04d}-{(m - 2) % 12 + 1:02d}"}
    for comp in sorted(comps):
        d = _date.fromisoformat(comp + "-01")
        perfis = {e.cnpj: ctx.perfis.em(e.cnpj, d) for e in ctx.carteira if e.ativa}
        for a in alertas(gerar(comp, perfis, ctx.catalogo, feriados), ctx.hoje, dias):
            v = a["vencimento"]
            linhas.append(f"- **{a['quando']}** — {v.codigo} ({v.descricao}) {v.apelido}: "
                          f"{v.vencimento:%d/%m/%Y} [{v.norma}]")
    return linhas


def grafo_ciclo() -> Grafo:
    g = Grafo("ciclo")
    for nome, f in (("capturar", n_capturar), ("processar_documentos", n_processar),
                    ("analisar_competencias", n_analisar_competencias), ("contabil", n_contabil),
                    ("montar_lotes", n_montar_lotes), ("aprovar", n_aprovar), ("executar", n_executar),
                    ("pareceres", n_pareceres)):
        g.no(nome, f)
    ordem = ["capturar", "processar_documentos", "analisar_competencias", "contabil", "montar_lotes",
             "aprovar", "executar", "pareceres"]
    for a, b in zip(ordem, ordem[1:]):
        g.ligar(a, b)
    g.ligar("pareceres", FIM)
    return g


def rodar_ciclo(ctx, run_id: str | None = None) -> dict:
    return grafo_ciclo().executar({"pendencias_gerais": []}, ctx, ctx.trilha, run_id)
