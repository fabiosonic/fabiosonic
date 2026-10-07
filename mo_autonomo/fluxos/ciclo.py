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
    for extra in (ctx.trilha.anexos_sem_documento(), ctx.trilha.analisados_sem_lote(), ctx.trilha.na_fila(),
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
    extra, fat_out, falhas, erros_csv = defaultdict(list), {}, [], []
    try:
        declaradas = ler_receitas_declaradas(ctx.dados / "apuracao" / "receitas.csv", erros_csv)
    except Exception as exc:  # noqa: BLE001
        declaradas, erros_csv = {}, [f"receitas.csv ilegível: {type(exc).__name__}: {exc}"]
    falhas += [_falha("RECEITAS_CSV_INVALIDO", m) for m in erros_csv]
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
    """Extratos OFX -> lançamentos propostos (por empresa e mês) com de-para do razão do cliente.

    Transação só é "consumida" quando vira ação registrada num lote (tabela acoes); sem as
    exportações do Domínio ou com transações sem contrapartida, o OFX fica PENDENTE e volta
    quando a base mudar (ex.: razão atualizado).
    """
    propostas = []
    pasta = ctx.dados / "dominio"
    cfg = ctx.config.get("contabil") or {}
    for d in e["documentos"]:
        for ex in d.get("extratos_empresa") or []:
            cnpj = ex["cnpj"]
            try:
                emp = ctx.carteira.get(cnpj)
                plano_csv, razao_csv = pasta / emp.codigo_dominio / "plano_contas.csv", pasta / emp.codigo_dominio / "razao.csv"
                por_mes = defaultdict(list)
                for t in ex["transacoes"]:
                    por_mes[f"{t['data']:%Y-%m}"].append(t)
                for comp, trans in sorted(por_mes.items()):
                    if not plano_csv.exists() or not razao_csv.exists():
                        propostas.append({"cnpj": cnpj, "competencia": comp, "sha256": d["sha256"], "lancamentos": [],
                                          "pendencias": [_falha("SEM_EXPORTACAO_DOMINIO",
                                                                f"Faltam plano_contas.csv/razao.csv em {pasta / emp.codigo_dominio} "
                                                                f"({len(trans)} transação(ões) aguardando).", cnpj, d["sha256"])]})
                        continue
                    conta = ex["conta_contabil"]
                    r = propor({"transacoes": trans}, conta, DePara.do_razao(_ler_csv(razao_csv), conta),
                               PlanoContas.carregar(plano_csv), int(cfg.get("minimo_ocorrencias", 2)),
                               float(cfg.get("dominancia", 0.8)))
                    lanc = [{**l, "banco": ex["banco"], "conta": ex["conta"], "cnpj": cnpj, "competencia": comp,
                             "sha256": d["sha256"]} for l in r["lancamentos"]]
                    propostas.append({"cnpj": cnpj, "competencia": comp, "sha256": d["sha256"], "lancamentos": lanc,
                                      "pendencias": [{**p, "cnpj": cnpj, "referencia": p.get("fitid")} for p in r["pendencias"]]})
            except Exception as exc:  # noqa: BLE001
                propostas.append({"cnpj": cnpj, "competencia": None, "sha256": d["sha256"], "lancamentos": [],
                                  "pendencias": [_falha("ERRO_CONTABIL", f"{type(exc).__name__}: {exc}", cnpj, d["sha256"])]})
    return {"contabil": propostas}


def _acao_documento(d: dict, rota: dict, cnpj: str, comp: str) -> dict:
    doc = d.get("doc") or {}
    valor = valor_documento(doc)
    base = {"sha256": d["sha256"], "origem": d["caminho"], "cnpj": cnpj, "competencia": comp,
            "valor": str(valor) if valor is not None else None}  # desconhecido != zero (barra auto-aprovação)
    if rota["tipo"] == "ARQUIVO":
        return {"tipo": "arquivar_documento", **base, "tipo_documento": doc.get("tipo"),
                "nome": f"{d['sha256'][:12]}_{nome_seguro(d.get('nome') or 'documento')}"}
    return {"tipo": "copiar_xml_rotina", **base, "pasta_tipo": rota["tipo"],
            "nome": f"{nome_seguro(doc.get('chave') or d['sha256'])}.xml"}


def _bloqueia_doc(d: dict, cnpj: str) -> list[dict]:
    """Pendências do documento que impedem propor as ações dele para esta empresa."""
    return [p for p in d.get("pendencias", []) if p.get("cnpj") in (cnpj, None)]


def _salvar_lote(ctx, lote_id, acoes, achados, pend, info, cnpj, comp, area, achados_info=None) -> dict | None:
    ja = ctx.trilha.acoes_ja_propostas(acoes)
    acoes = [a for a in acoes if ctx.trilha.id_acao(a) not in ja]
    achados_info = achados_info or []
    if not (acoes or achados or pend or info or achados_info):
        return None
    pend, info = _unicas(pend), _unicas(info)
    if not acoes and not ctx.trilha.conteudo_novo(f"{area}|{cnpj}|{comp}", [achados, pend, info, achados_info]):
        return None  # reprocesso sem nada novo: não gera lote/parecer repetido
    lote = L.montar_lote(lote_id, acoes, achados, pend, info, achados_info)
    arquivo = L.salvar(lote, ctx.dados / "lotes")
    ctx.trilha.registrar_acoes(lote["id"], acoes)
    ctx.trilha.conteudo_novo(f"{area}|{cnpj}|{comp}", [achados, pend, info, achados_info], registrar=True)
    return {"id": lote["id"], "cnpj": cnpj, "competencia": comp, "area": area, "arquivo": str(arquivo),
            "hash": lote["hash"]}


def n_montar_lotes(e, ctx):
    """Um lote por empresa × competência × área. Pendência de um documento NÃO trava os outros:

    - ações só de documentos sem pendência para a empresa;
    - pendências e achados de documentos retidos vão como `informativas`/`achados_informativos`
      (aparecem no parecer, não bloqueiam a aprovação nem a auto-aprovação das notas limpas);
    - `pendencias` do lote = falha do grupo inteiro (ex.: análise do mês falhou). Nesse caso o lote
      NÃO leva ações e os documentos ficam ANALISADO, voltando no próximo ciclo;
    - documento só vira OK se o lote do grupo dele foi gravado.
    """
    lotes = []
    run = e["_run_id"][:8]
    comp_achados = e.get("achados_competencia", {})
    falhas_comp = defaultdict(list)
    gerais = list(e.get("pendencias_gerais", []))
    nao_ok: set = set()
    for f in e.get("falhas_competencia", []):
        if f.get("cnpj"):
            falhas_comp[(f["cnpj"], f["referencia"])].append(f)
        else:
            gerais.append(f)
    for (cnpj, comp), docs in sorted(_grupos(e).items(), key=lambda x: (x[0][0], x[0][1] or "")):
        try:
            acoes, achados, info, achados_info = [], [], [], []
            pend = list(falhas_comp.get((cnpj, comp), []))
            for d in docs:
                proprios = [a for a in d.get("achados", []) if a.get("cnpj") == cnpj]
                bloqueios = _bloqueia_doc(d, cnpj)
                if bloqueios:
                    info += bloqueios
                    achados_info += proprios
                    continue
                achados += proprios
                for r in d.get("rotas", []):
                    if r["cnpj"] == cnpj and comp:
                        acoes.append(_acao_documento(d, r, cnpj, comp))
            if pend:  # grupo com falha: nada de ação; documentos voltam no próximo ciclo
                nao_ok |= {d["sha256"] for d in docs}
                acoes = []
            achados += comp_achados.get(f"{cnpj}|{comp}", [])
            l = _salvar_lote(ctx, f"FISCAL_{cnpj}_{comp or 'SEMCOMP'}_{run}", acoes, achados, pend, info, cnpj, comp,
                             "FISCAL", achados_info)
            if l:
                lotes.append(l)
        except Exception as exc:  # noqa: BLE001
            gerais.append(_falha("ERRO_LOTE", f"{cnpj} {comp}: {type(exc).__name__}: {exc}", None, cnpj))
            nao_ok |= {d["sha256"] for d in docs}
    pend_ofx = set()
    por_chave = defaultdict(lambda: {"lancamentos": [], "pendencias": [], "shas": set()})
    for p in e.get("contabil", []):  # vários extratos da mesma empresa/mês = um lote só
        g = por_chave[(p["cnpj"], p["competencia"])]
        g["lancamentos"] += p["lancamentos"]
        g["pendencias"] += p["pendencias"]
        g["shas"].add(p.get("sha256"))
        if p["pendencias"]:
            pend_ofx.add(p.get("sha256"))
    for (cnpj, comp), g in sorted(por_chave.items(), key=lambda x: (x[0][0], x[0][1] or "")):
        try:
            vistos, acoes, pend_g = set(), [], list(g["pendencias"])
            for l in g["lancamentos"]:
                a = {"tipo": "lancamento_contabil", **l, "valor": str(l["valor"])}
                if not l.get("fitid"):
                    pend_g.append(_falha("SEM_FITID", f"transação de {l['data']} valor {l['valor']} sem FITID no "
                                         "extrato: sem identificador não há como evitar duplicidade", cnpj, l.get("sha256")))
                    pend_ofx.add(l.get("sha256"))
                    continue
                if ctx.trilha.id_acao(a) not in vistos:
                    vistos.add(ctx.trilha.id_acao(a))
                    acoes.append(a)
            l = _salvar_lote(ctx, f"CONTABIL_{cnpj}_{comp or 'SEMCOMP'}_{run}", acoes, [], [], pend_g,
                             cnpj, comp, "CONTABIL")
            if l:
                lotes.append(l)
        except Exception as exc:  # noqa: BLE001
            gerais.append(_falha("ERRO_LOTE", f"contábil {cnpj}: {type(exc).__name__}: {exc}"))
            nao_ok |= g["shas"]
    for d in e["documentos"]:
        if not d.get("rotas") and not d.get("extratos_empresa") and not any(p.get("cnpj") for p in d.get("pendencias", [])):
            gerais += [p for p in d.get("pendencias", [])]
    # lotes gravados: documentos analisados viram OK (OFX com transação sem destino -> PENDENTE;
    # grupo que não gravou lote -> continua ANALISADO e volta no próximo ciclo)
    for d in e["documentos"]:
        if d.get("sha256") in nao_ok:
            continue
        if d.get("sha256") in pend_ofx:
            ctx.trilha.atualizar_situacao(d["sha256"], "PENDENTE")
        elif not d.get("pendencias") and d.get("classe") != "ERRO":
            ctx.trilha.atualizar_situacao(d["sha256"], "OK")
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
    """Aprovação por exceção (só se ativa e se o lote cumprir todas as condições).

    Também reapresenta lotes de ciclos anteriores que ainda têm ações PROPOSTA sem aprovação
    (ex.: ciclo caiu depois de gravar o lote): ficam visíveis no resumo/painel e podem ser
    auto-aprovados.
    """
    politica = ctx.config.get("aprovacao_por_excecao") or {}
    out = []
    atuais = {l["id"] for l in e["lotes"]}
    lotes = list(e["lotes"])
    for lid in ctx.trilha.lotes_aguardando():
        arq = ctx.dados / "lotes" / f"lote_{lid}.json"
        if lid in atuais or not arq.exists():
            continue
        try:
            lote = L.carregar(arq)
        except Exception:  # noqa: BLE001
            continue
        partes = lid.split("_")
        lotes.append({"id": lid, "cnpj": partes[1], "competencia": partes[2] if partes[2] != "SEMCOMP" else None,
                      "area": partes[0], "arquivo": str(arq), "hash": lote["hash"], "reapresentado": True})
    for l in lotes:
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


def executar_acao(a: dict, ctx) -> dict:
    """Executa UMA ação já aprovada. Nunca sobrescreve; resultado vai para a tabela de ações."""
    tipos = ctx.config["dominio"]["tipos_pasta"]
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
            return {"acao": a["tipo"], "status": "AGUARDANDO_LEIAUTE_DOMINIO",
                    "detalhe": "exportador só é escrito com o leiaute oficial de importação"}
        else:
            r = {"acao": a["tipo"], "status": "SEM_EXECUTOR"}
            ctx.trilha.marcar_acao(a, "BLOQUEADA", r["status"])
            return r
        try:
            st = gravar(destino, Path(a["origem"]).read_bytes())
        except ConflitoArquivo as exc:
            st = f"CONFLITO: {exc}"
        r = {"acao": a["tipo"], "destino": str(destino), "status": st}
    except Exception as exc:  # noqa: BLE001 — uma ação ruim não impede as outras
        r = {"acao": a["tipo"], "status": f"ERRO: {type(exc).__name__}: {exc}"}
    ok = r["status"] in ("GRAVADO", "JA_EXISTIA")
    if ok:
        ctx.trilha.marcar_acao(a, "EXECUTADA")
    elif r["status"].startswith("CONFLITO"):
        ctx.trilha.marcar_acao(a, "BLOQUEADA", r["status"])  # repetir não resolve: precisa de pessoa
    else:
        teto = int((ctx.config.get("execucao") or {}).get("max_tentativas", 24))
        ctx.trilha.marcar_falha(a, r["status"], teto)
    return r


def executar_lote(caminho_aprovado: Path, ctx) -> list[dict]:
    """Executor: só roda com APROVADO_* íntegro e registrado na trilha."""
    lote = L.exigir_aprovado(caminho_aprovado, ctx.trilha)
    resultado = [executar_acao(a, ctx) for a in lote["acoes"]]
    ctx.trilha.evento("LOTE_EXECUTADO", lote["id"], resultado)
    return resultado


def n_executar(e, ctx):
    """Executa os lotes aprovados e refaz ações que falharam antes (ex.: D: indisponível)."""
    out, feitos = [], set()
    for l in e["lotes"]:
        if l.get("aprovado"):
            feitos.add(l["id"])
            try:
                out.append({"lote": l["id"], "resultado": executar_lote(Path(l["aprovado"]), ctx)})
            except Exception as exc:  # noqa: BLE001
                out.append({"lote": l["id"], "resultado": [{"status": f"ERRO: {type(exc).__name__}: {exc}"}]})
    for f in ctx.trilha.acoes_com_falha():
        if f["lote"] in feitos:
            continue
        aprovado = ctx.dados / "lotes" / f"APROVADO_{f['lote']}.json"
        try:
            lote = L.exigir_aprovado(aprovado, ctx.trilha)
            if ctx.trilha.id_acao(f["acao"]) not in {ctx.trilha.id_acao(a) for a in lote["acoes"]}:
                raise L.AprovacaoRecusada("ação não pertence ao lote aprovado")
            out.append({"lote": f["lote"], "resultado": [executar_acao(f["acao"], ctx)], "refeita": True})
        except Exception as exc:  # noqa: BLE001
            out.append({"lote": f["lote"], "resultado": [{"status": f"ERRO: {type(exc).__name__}: {exc}"}], "refeita": True})
    return {"execucoes": out}


def n_pareceres(e, ctx):
    """Parecer técnico por empresa/competência + resumo do ciclo + painel."""
    pasta = ctx.dados / "pareceres"
    inativas = [c for c in cobertura(ctx.catalogo) if not c["ativa"]]
    gerados, falhas = [], []
    for l in e["lotes"]:
        if l["area"] != "FISCAL" or l["competencia"] is None or l.get("reapresentado"):
            continue
        try:
            lote = L.carregar(Path(l["arquivo"]))
            emp = ctx.carteira.get(l["cnpj"])
            perfil = ctx.perfis.em(l["cnpj"], ctx.hoje)
            md = parecer.markdown(emp, l["competencia"], perfil, lote["achados"] + lote.get("achados_informativos", []),
                                  lote["pendencias"] + lote.get("informativas", []),
                                  len(lote["acoes"]), inativas,
                                  (e.get("faturamento") or {}).get(f"{l['cnpj']}|{l['competencia']}"))
            gerados.append(parecer.salvar(pasta / l["competencia"], f"{emp.pasta}_{l['id'][-8:]}", md, lote["achados"]))
            texto = solicitacoes.rascunho(emp, l["competencia"], lote["achados"],
                                          lote["pendencias"] + lote.get("informativas", []))
            if texto:
                solicitacoes.salvar(ctx.dados / "solicitacoes", emp, l["competencia"], texto, l["id"][-8:])
        except Exception as exc:  # noqa: BLE001
            falhas.append(f"{l['id']}: {type(exc).__name__}: {exc}")
    resumo = [f"# Resumo do ciclo {e['_run_id'][:8]} — {ctx.hoje:%d/%m/%Y} ({ctx.config['modo']})", "",
              f"- E-mails novos: {e.get('emails_lidos', 0)}", f"- Anexos processados: {len(e.get('anexos', []))}",
              f"- Lotes: {len(e['lotes'])} (auto-aprovados: {sum(1 for l in e['lotes'] if l.get('aprovado'))})", "",
              "## Lotes aguardando APROVADO", ""]
    for l in e["lotes"]:
        if not l.get("aprovado"):
            origem = " (de ciclo anterior)" if l.get("reapresentado") else ""
            resumo.append(f"- `{l['id']}`{origem} hash `{l['hash'][:16]}…` — {'; '.join(l.get('aguardando') or [])}")
    try:
        alertas = _alertas_vencimento(ctx)
    except Exception as exc:  # noqa: BLE001
        alertas = [f"- ERRO no calendário: {exc}"]
    resumo += ["", "## Vencimentos próximos (calendário conferido)", ""]
    resumo += alertas or ["- Nenhum (ou nenhuma obrigação com norma conferida)."]
    resumo += ["", "## Pendências sem empresa identificada", ""]
    resumo += [f"- {p['codigo']}: {p['mensagem']}" for p in e.get("pendencias_gerais", [])] or ["- Nenhuma."]
    falhas_exec = [(x["lote"], r) for x in e.get("execucoes", []) for r in x["resultado"]
                   if r.get("status") not in ("GRAVADO", "JA_EXISTIA", "AGUARDANDO_LEIAUTE_DOMINIO")]
    if falhas_exec:
        resumo += ["", "## Execuções com falha (serão refeitas no próximo ciclo)", ""]
        resumo += [f"- `{lid}` {r.get('acao', '')}: {r['status']}" for lid, r in falhas_exec]
    bloqueadas = ctx.trilha.acoes_bloqueadas()
    if bloqueadas:
        resumo += ["", "## Ações bloqueadas (precisam de uma pessoa: conflito ou tentativas esgotadas)", ""]
        resumo += [f"- `{b['lote']}` {b['acao']['tipo']} {b['acao'].get('nome', b['acao'].get('fitid', ''))}: {b['detalhe']}"
                   for b in bloqueadas]
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

    from ..obrigacoes.calendario import alertas, competencias_para_alerta, gerar
    cal = ctx.config.get("calendario") or {}
    feriados = {_date.fromisoformat(str(f)) for f in cal.get("feriados") or []}
    dias = tuple(cal.get("dias_alerta", [3, 0]))
    linhas = []
    for comp in competencias_para_alerta(ctx.hoje, ctx.catalogo):
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
