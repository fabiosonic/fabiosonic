"""Grafo do ciclo completo (de hora em hora pelo Agendador):

capturar -> processar_documentos -> analisar_competencias -> contabil -> montar_lotes
        -> aprovar -> executar -> pareceres -> FIM

Cada passo é checkpoint na trilha: um ciclo interrompido é retomado com `retomar`.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import traceback

from ..aprovacao import lote as L
from ..contabil.lancamentos import DePara, PlanoContas, _ler_csv, propor
from ..dominio.pastas import ConflitoArquivo, DestinoInvalido, caminho_destino, gravar
from ..entrada.anexos import anexos_do_email
from ..especialista import parecer, solicitacoes
from ..especialista.motor import avaliar_competencia, cobertura
from ..grafo.motor import FIM, Grafo
from ..util.arquivos import escrever_atomico, extensao_segura, nome_seguro, sha256_bytes
from .documento import grafo_documento, valor_documento


def _bruto(ctx, sha: str, nome: str) -> Path:
    """Arquivo bruto nomeado pelo hash (o nome original fica só na trilha): nome hostil não quebra o disco."""
    return ctx.dados / "_BRUTO_EMAIL" / sha[:2] / f"{sha}{extensao_segura(nome)}"


def _falha(codigo: str, msg: str, cnpj=None, referencia=None) -> dict:
    return {"codigo": codigo, "cnpj": cnpj, "referencia": referencia, "mensagem": msg}


def n_capturar(e, ctx):
    """Lê a caixa (somente leitura), guarda o e-mail bruto, extrai anexos e deduplica por sha256.

    Também recoloca no fluxo: anexos capturados e não processados, documentos na fila da IA e
    pendências analisadas com outra versão da base (norma conferida/cadastro corrigido).
    """
    novos, pend, emails = [], [], 0
    for msg in ctx.fonte.mensagens():
        if ctx.trilha.email_lido(msg.uid):
            continue
        emails += 1
        sha_email = sha256_bytes(msg.dados)
        bruto_email = ctx.dados / "_BRUTO_EMAIL" / "emails" / f"{sha_email}.eml"
        if not bruto_email.exists():
            escrever_atomico(bruto_email, msg.dados)
        try:
            cab = msg.cabecalhos
        except Exception:  # noqa: BLE001 — cabeçalho corrompido
            cab = {"message_id": "", "remetente": "?", "assunto": "?", "data": ""}
        try:
            anexos = anexos_do_email(msg.dados, msg.uid)
        except Exception as exc:  # noqa: BLE001 — zip ruim/MIME quebrado não derruba o ciclo
            pend.append(_falha("ANEXO_ILEGIVEL", f"E-mail {cab['assunto']!r} de {cab['remetente']}: {exc} "
                                                 f"(bruto em {bruto_email})", referencia=msg.uid))
            anexos = []
        for a in anexos:
            try:
                sha = sha256_bytes(a.dados)
                caminho = _bruto(ctx, sha, a.nome)
                if not caminho.exists():
                    escrever_atomico(caminho, a.dados)
                if ctx.trilha.registrar_anexo(sha, a.nome, a.origem, str(caminho)):
                    novos.append({"sha256": sha, "nome": a.nome, "origem": a.origem, "caminho": str(caminho)})
            except Exception as exc:  # noqa: BLE001
                pend.append(_falha("ANEXO_NAO_GRAVADO", f"{a.nome!r}: {exc} (bruto do e-mail em {bruto_email})",
                                   referencia=msg.uid))
        ctx.trilha.registrar_email(msg.uid, cab["message_id"], cab["remetente"], cab["assunto"], cab["data"])
    ja = {a["sha256"] for a in novos}
    for extra in (ctx.trilha.anexos_sem_documento(), ctx.trilha.na_fila(),
                  ctx.trilha.pendentes_para_reprocessar(ctx.versao_base)):
        for a in extra:
            if a["sha256"] not in ja:
                ja.add(a["sha256"])
                novos.append(a)
    return {"anexos": novos, "emails_lidos": emails, "pendencias_gerais": e.get("pendencias_gerais", []) + pend}


def n_processar(e, ctx):
    """Roda o subgrafo de documento para cada anexo; falha de um documento não para os outros."""
    g = grafo_documento()
    resultados = []
    for a in e["anexos"]:
        try:
            dados = Path(a["caminho"]).read_bytes()
            r = g.executar({"sha256": a["sha256"], "nome": a["nome"], "dados": dados, "pendencias": []}, ctx)
            r.pop("dados", None)
            r.pop("_ultimo_traceback", None)
            resultados.append({**{k: v for k, v in r.items() if not k.startswith("_")}, "caminho": a["caminho"]})
        except Exception as exc:  # noqa: BLE001
            p = _falha("ERRO_PROCESSAMENTO", f"{a['nome']}: {type(exc).__name__}: {exc}", referencia=a["sha256"])
            ctx.trilha.registrar_documento(a["sha256"], "ERRO", None, [], None, [], "ERRO",
                                           {"_versao_base": ctx.versao_base})
            ctx.trilha.evento("ERRO_DOCUMENTO", a["sha256"], traceback.format_exc(limit=5))
            resultados.append({"sha256": a["sha256"], "nome": a["nome"], "classe": "ERRO", "doc": None,
                               "pendencias": [p], "rotas": [], "achados": [], "caminho": a["caminho"]})
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


def _historico(registros: list[dict]) -> list[dict]:
    """Documentos do mês na trilha (todos os ciclos), no formato que as regras do mês leem."""
    out = []
    for r in registros:
        res = r.get("resumo") or {}
        if not res.get("tipo"):
            continue
        out.append({"tipo": res["tipo"], "chave": r.get("chave"), "_sha256": r["sha256"],
                    "emitente_cnpj": res.get("emitente"), "modelo": res.get("modelo"), "serie": res.get("serie"),
                    "numero": res.get("numero"), "chave_ref": res.get("chave_ref"), "tp_evento": res.get("tp_evento"),
                    "autorizacao_cstat": res.get("cstat")})
    return out


def n_analisar_competencias(e, ctx):
    """Regras do mês (duplicidade, sequência, cancelamento) e faturamento × receita declarada.

    As regras do mês leem a TRILHA (todos os ciclos da competência), não só o ciclo atual.
    """
    from decimal import Decimal

    from ..especialista.faturamento import cruzar, faturamento, ler_receitas_declaradas
    extra, fat_out, falhas = defaultdict(list), {}, []
    declaradas = ler_receitas_declaradas(ctx.dados / "apuracao" / "receitas.csv")
    tol = Decimal(str((ctx.config.get("cruzamentos") or {}).get("tolerancia_receita", "1.00")))
    for (cnpj, comp), _docs in _grupos(e).items():
        try:
            perfil = ctx.perfis.em(cnpj, ctx.hoje)
            if perfil is None or comp is None:
                continue
            registros = [r for r in ctx.trilha.documentos(comp) if cnpj in (r["cnpjs"] or [])
                         or (r["resumo"] or {}).get("emitente") == cnpj]
            for a in avaliar_competencia(_historico(registros), perfil, comp, ctx.catalogo, ctx.hoje):
                extra[f"{cnpj}|{comp}"].append(a.como_dict())
            fat = faturamento(registros, cnpj, ctx.catalogo)
            fat_out[f"{cnpj}|{comp}"] = fat
            for a in cruzar(fat, declaradas.get((cnpj, comp)), cnpj, comp, tol):
                extra[f"{cnpj}|{comp}"].append(a.como_dict())
        except Exception as exc:  # noqa: BLE001
            falhas.append(_falha("ERRO_ANALISE_MES", f"{type(exc).__name__}: {exc}", cnpj, comp))
    return {"achados_competencia": dict(extra), "faturamento": fat_out, "falhas_competencia": falhas}


def n_contabil(e, ctx):
    """Extratos OFX -> lançamentos propostos (por empresa e mês) com de-para do razão do cliente."""
    propostas = []
    pasta = ctx.dados / "dominio"
    cfg = ctx.config.get("contabil") or {}
    for d in e["documentos"]:
        for ex in d.get("extratos_empresa") or []:
            cnpj = ex["cnpj"]
            try:
                emp = ctx.carteira.get(cnpj)
                novas = [t for t in ex["transacoes"]
                         if not t.get("fitid") or ctx.trilha.registrar_fitid(ex["banco"], ex["conta"], t["fitid"], d["sha256"])]
                repetidas = len(ex["transacoes"]) - len(novas)
                plano_csv, razao_csv = pasta / emp.codigo_dominio / "plano_contas.csv", pasta / emp.codigo_dominio / "razao.csv"
                por_mes = defaultdict(list)
                for t in novas:
                    por_mes[f"{t['data']:%Y-%m}"].append(t)
                for comp, trans in sorted(por_mes.items()):
                    if not plano_csv.exists() or not razao_csv.exists():
                        propostas.append({"cnpj": cnpj, "competencia": comp, "lancamentos": [], "pendencias": [_falha(
                            "SEM_EXPORTACAO_DOMINIO", f"Faltam plano_contas.csv/razao.csv em {pasta / emp.codigo_dominio} "
                            f"({len(trans)} transação(ões) aguardando).", cnpj, d["sha256"])]})
                        continue
                    conta = ex["conta_contabil"]
                    r = propor({"transacoes": trans}, conta, DePara.do_razao(_ler_csv(razao_csv), conta),
                               PlanoContas.carregar(plano_csv), int(cfg.get("minimo_ocorrencias", 2)),
                               float(cfg.get("dominancia", 0.8)))
                    propostas.append({"cnpj": cnpj, "competencia": comp, "lancamentos": r["lancamentos"],
                                      "repetidas": repetidas,
                                      "pendencias": [{**p, "cnpj": cnpj, "referencia": p.get("fitid")} for p in r["pendencias"]]})
            except Exception as exc:  # noqa: BLE001
                propostas.append({"cnpj": cnpj, "competencia": None, "lancamentos": [], "pendencias": [_falha(
                    "ERRO_CONTABIL", f"{type(exc).__name__}: {exc}", cnpj, d["sha256"])]})
    return {"contabil": propostas}


def _acao_documento(d: dict, rota: dict, cnpj: str, comp: str) -> dict:
    doc = d.get("doc") or {}
    valor = valor_documento(doc)
    base = {"sha256": d["sha256"], "origem": d["caminho"], "cnpj": cnpj, "competencia": comp,
            "valor": str(valor) if valor is not None else "0"}
    if rota["tipo"] == "ARQUIVO":
        return {"tipo": "arquivar_documento", **base, "tipo_documento": doc.get("tipo"),
                "nome": f"{d['sha256'][:12]}_{nome_seguro(d.get('nome') or 'documento')}"}
    return {"tipo": "copiar_xml_rotina", **base, "pasta_tipo": rota["tipo"],
            "nome": f"{nome_seguro(doc.get('chave') or d['sha256'])}.xml"}


def n_montar_lotes(e, ctx):
    """Um lote por empresa × competência × área, para um problema não travar os demais."""
    lotes = []
    run = e["_run_id"][:8]
    pasta = ctx.dados / "lotes"
    comp_achados = e.get("achados_competencia", {})
    falhas_comp = defaultdict(list)
    for f in e.get("falhas_competencia", []):
        falhas_comp[(f["cnpj"], f["referencia"])].append(f)
    gerais = list(e.get("pendencias_gerais", []))
    for (cnpj, comp), docs in sorted(_grupos(e).items(), key=lambda x: (x[0][0], x[0][1] or "")):
        try:
            acoes, achados, pend = [], [], list(falhas_comp.get((cnpj, comp), []))
            for d in docs:
                achados += [a for a in d.get("achados", []) if a.get("cnpj") == cnpj]
                pend += [p for p in d.get("pendencias", []) if p.get("cnpj") in (cnpj, None)]
                for r in d.get("rotas", []):
                    if r["cnpj"] == cnpj and comp:
                        acoes.append(_acao_documento(d, r, cnpj, comp))
            if comp is None:
                pend.append(_falha("SEM_COMPETENCIA", "documento sem data de competência", cnpj))
            achados += comp_achados.get(f"{cnpj}|{comp}", [])
            lote = L.montar_lote(f"FISCAL_{cnpj}_{comp or 'SEMCOMP'}_{run}", acoes, achados, _unicas(pend))
            lotes.append({"id": lote["id"], "cnpj": cnpj, "competencia": comp, "area": "FISCAL",
                          "arquivo": str(L.salvar(lote, pasta)), "hash": lote["hash"]})
        except Exception as exc:  # noqa: BLE001
            gerais.append(_falha("ERRO_LOTE", f"{cnpj} {comp}: {type(exc).__name__}: {exc}", None, cnpj))
    for p in e.get("contabil", []):
        try:
            acoes = [{"tipo": "lancamento_contabil", **l, "valor": str(l["valor"])} for l in p["lancamentos"]]
            lote = L.montar_lote(f"CONTABIL_{p['cnpj']}_{p['competencia'] or 'SEMCOMP'}_{run}", acoes, [], p["pendencias"])
            lotes.append({"id": lote["id"], "cnpj": p["cnpj"], "competencia": p["competencia"], "area": "CONTABIL",
                          "arquivo": str(L.salvar(lote, pasta)), "hash": lote["hash"]})
        except Exception as exc:  # noqa: BLE001
            gerais.append(_falha("ERRO_LOTE", f"contábil {p.get('cnpj')}: {type(exc).__name__}: {exc}"))
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
        try:
            aprovado = L.aprovar_auto(Path(l["arquivo"]), politica, ctx.trilha)
            motivos = [] if aprovado else L.avaliar_auto(L.carregar(Path(l["arquivo"])), politica).motivos
        except Exception as exc:  # noqa: BLE001
            aprovado, motivos = None, [f"erro na avaliação: {type(exc).__name__}: {exc}"]
        out.append({**l, "aprovado": str(aprovado) if aprovado else None, "aguardando": motivos})
    return {"lotes": out}


def _base_documentos(ctx) -> Path:
    if ctx.config["modo"] == "producao":
        p = (ctx.config.get("pastas") or {}).get("documentos_organizados")
        if not p:
            raise DestinoInvalido("modo produção sem pastas.documentos_organizados")
        return Path(p)
    return ctx.dados / "_STAGING" / "DOCUMENTOS"


def executar_lote(caminho_aprovado: Path, ctx) -> list[dict]:
    """Executor: só roda com APROVADO_* íntegro e registrado na trilha. Nunca sobrescreve arquivo."""
    lote = L.exigir_aprovado(caminho_aprovado, ctx.trilha)
    tipos = ctx.config["dominio"]["tipos_pasta"]
    resultado = []
    for a in lote["acoes"]:
        try:
            if a["tipo"] == "copiar_xml_rotina":
                emp = ctx.carteira.get(a["cnpj"])
                destino = caminho_destino(ctx.base_xml, tipos, emp, a["pasta_tipo"], a["competencia"], a["nome"])
            elif a["tipo"] == "arquivar_documento":
                emp = ctx.carteira.get(a["cnpj"])
                ano, mes = a["competencia"].split("-")
                base = _base_documentos(ctx)
                destino = base / emp.pasta / f"{mes}{ano}" / nome_seguro(a.get("tipo_documento") or "OUTRO") / nome_seguro(a["nome"])
                if not destino.resolve().is_relative_to(base.resolve()):
                    raise DestinoInvalido(f"destino fora da pasta base: {destino}")
            elif a["tipo"] == "lancamento_contabil":
                resultado.append({"acao": a["tipo"], "status": "AGUARDANDO_LEIAUTE_DOMINIO",
                                  "detalhe": "exportador só é escrito com o leiaute oficial de importação"})
                continue
            else:
                resultado.append({"acao": a["tipo"], "status": "SEM_EXECUTOR"})
                continue
            try:
                st = gravar(destino, Path(a["origem"]).read_bytes())
            except ConflitoArquivo as exc:
                st = f"CONFLITO: {exc}"
            resultado.append({"acao": a["tipo"], "destino": str(destino), "status": st})
        except Exception as exc:  # noqa: BLE001 — uma ação ruim não impede as outras
            resultado.append({"acao": a["tipo"], "status": f"ERRO: {type(exc).__name__}: {exc}"})
    ctx.trilha.evento("LOTE_EXECUTADO", lote["id"], resultado)
    return resultado


def n_executar(e, ctx):
    """Executa os lotes aprovados (simulação grava em _STAGING)."""
    out = []
    for l in e["lotes"]:
        if l.get("aprovado"):
            try:
                out.append({"lote": l["id"], "resultado": executar_lote(Path(l["aprovado"]), ctx)})
            except Exception as exc:  # noqa: BLE001
                out.append({"lote": l["id"], "resultado": [{"status": f"ERRO: {type(exc).__name__}: {exc}"}]})
    return {"execucoes": out}


def n_pareceres(e, ctx):
    """Parecer técnico por empresa/competência + resumo do ciclo + painel."""
    pasta = ctx.dados / "pareceres"
    inativas = [c for c in cobertura(ctx.catalogo) if not c["ativa"]]
    gerados, falhas = [], []
    for l in e["lotes"]:
        if l["area"] != "FISCAL" or l["competencia"] is None:
            continue
        try:
            lote = L.carregar(Path(l["arquivo"]))
            emp = ctx.carteira.get(l["cnpj"])
            perfil = ctx.perfis.em(l["cnpj"], ctx.hoje)
            md = parecer.markdown(emp, l["competencia"], perfil, lote["achados"], lote["pendencias"],
                                  len(lote["acoes"]), inativas,
                                  (e.get("faturamento") or {}).get(f"{l['cnpj']}|{l['competencia']}"))
            gerados.append(parecer.salvar(pasta / l["competencia"], f"{emp.pasta}_{l['id'][-8:]}", md, lote["achados"]))
            texto = solicitacoes.rascunho(emp, l["competencia"], lote["achados"], lote["pendencias"])
            if texto:
                solicitacoes.salvar(ctx.dados / "solicitacoes", emp, l["competencia"], texto)
        except Exception as exc:  # noqa: BLE001
            falhas.append(f"{l['id']}: {type(exc).__name__}: {exc}")
    resumo = [f"# Resumo do ciclo {e['_run_id'][:8]} — {ctx.hoje:%d/%m/%Y} ({ctx.config['modo']})", "",
              f"- E-mails novos: {e.get('emails_lidos', 0)}", f"- Anexos processados: {len(e.get('anexos', []))}",
              f"- Lotes: {len(e['lotes'])} (auto-aprovados: {sum(1 for l in e['lotes'] if l.get('aprovado'))})", "",
              "## Lotes aguardando APROVADO", ""]
    for l in e["lotes"]:
        if not l.get("aprovado"):
            resumo.append(f"- `{l['id']}` hash `{l['hash'][:16]}…` — {'; '.join(l.get('aguardando') or [])}")
    try:
        alertas = _alertas_vencimento(ctx)
    except Exception as exc:  # noqa: BLE001
        alertas = [f"- ERRO no calendário: {exc}"]
    resumo += ["", "## Vencimentos próximos (calendário conferido)", ""]
    resumo += alertas or ["- Nenhum (ou nenhuma obrigação com norma conferida)."]
    resumo += ["", "## Pendências sem empresa identificada", ""]
    resumo += [f"- {p['codigo']}: {p['mensagem']}" for p in e.get("pendencias_gerais", [])] or ["- Nenhuma."]
    if falhas:
        resumo += ["", "## Falhas ao gerar pareceres", ""] + [f"- {f}" for f in falhas]
    caminho = pasta / f"resumo_{e['_run_id'][:8]}.md"
    escrever_atomico(caminho, "\n".join(resumo).encode("utf-8"))
    from ..especialista.painel import gerar as gerar_painel
    painel = ctx.dados / "painel.html"
    escrever_atomico(painel, gerar_painel(e, ctx, cobertura(ctx.catalogo)).encode("utf-8"))
    return {"pareceres": gerados, "resumo": str(caminho), "painel": str(painel)}


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
