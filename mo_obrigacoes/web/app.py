"""Painel web (FastAPI + Jinja2)."""
from __future__ import annotations

import secrets
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from .. import agenda as agenda_mod
from ..alertas import executar_alertas
from ..calendario import competencia_anterior, formatar_competencia, parse_competencia, somar_meses
from ..catalogo import sincronizar_catalogo
from ..classificador import so_digitos, cnpj_valido, cpf_valido
from ..config import get_config
from ..db import criar_tabelas, nova_sessao
from ..drive import extrair_id_pasta
from ..models import (
    DEPARTAMENTOS,
    REGIMES,
    STATUS_DISPENSADA,
    STATUS_LABELS,
    STATUS_PENDENTE,
    Documento,
    Empresa,
    EstadoSync,
    Evento,
    Obrigacao,
    Responsavel,
    Tarefa,
)
from ..monitor import Monitor, classificar_manual, dar_baixa
from ..relatorios import exportar_csv, indicadores, resumo_competencia

AQUI = Path(__file__).parent
templates = Jinja2Templates(directory=str(AQUI / "templates"))
templates.env.globals.update(
    STATUS_LABELS=STATUS_LABELS, DEPARTAMENTOS=DEPARTAMENTOS, REGIMES=REGIMES,
    formatar_competencia=formatar_competencia,
)
seguranca = HTTPBasic(auto_error=False)

FLAGS_EMPRESA = [
    ("comercio", "Comércio (contribuinte de ICMS)"),
    ("industria", "Indústria (contribuinte de IPI)"),
    ("servicos", "Prestação de serviços (ISS)"),
    ("possui_funcionarios", "Possui empregados"),
    ("possui_prolabore", "Retira pró-labore"),
    ("retem_tributos", "Efetua retenções (EFD-Reinf)"),
    ("area_saude", "Serviços de saúde (DMED)"),
    ("atividade_imobiliaria", "Atividade imobiliária (DIMOB)"),
]


def usuario_atual(cred: HTTPBasicCredentials | None = Depends(seguranca)) -> str:
    cfg = get_config()
    if not cfg.admin_password:
        return "admin"  # modo desenvolvimento: defina MO_ADMIN_PASSWORD em produção
    if cred is None or not (
        secrets.compare_digest(cred.username.encode(), cfg.admin_user.encode())
        and secrets.compare_digest(cred.password.encode(), cfg.admin_password.encode())
    ):
        raise HTTPException(401, "Credenciais inválidas", headers={"WWW-Authenticate": "Basic"})
    return cred.username


def get_db():
    s = nova_sessao()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def _competencia(valor: str | None) -> str:
    if valor and len(valor) == 7 and valor[4] == "-":
        return valor
    return competencia_anterior()


def _vizinhas(comp: str) -> tuple[str, str]:
    a, m = parse_competencia(comp)
    ant = "%04d-%02d" % somar_meses(a, m, -1)
    prox = "%04d-%02d" % somar_meses(a, m, 1)
    return ant, prox


def _render(request: Request, nome: str, **ctx):
    cfg = get_config()
    ctx.setdefault("hoje", date.today())
    ctx["escritorio"] = cfg.nome_escritorio
    ctx["sem_senha"] = not cfg.admin_password
    ctx["msg"] = request.query_params.get("msg", "")
    return templates.TemplateResponse(request, nome, ctx)


def _voltar(url: str, msg: str) -> RedirectResponse:
    sep = "&" if "?" in url else "?"
    from urllib.parse import quote

    return RedirectResponse(f"{url}{sep}msg={quote(msg)}", status_code=303)


def criar_app() -> FastAPI:
    @asynccontextmanager
    async def ciclo_de_vida(_app):
        criar_tabelas()
        with nova_sessao() as sess:
            sincronizar_catalogo(sess)  # mantém o catálogo do banco igual ao do código
            sess.commit()
        yield

    app = FastAPI(title="Moraes e Oliveira - Monitor de Obrigações", docs_url="/api/docs", lifespan=ciclo_de_vida)
    app.mount("/static", StaticFiles(directory=str(AQUI / "static")), name="static")

    @app.get("/saude")
    def saude():
        return {"ok": True, "momento": datetime.utcnow().isoformat()}

    # ------------------------------------------------------------- Painel
    @app.get("/", response_class=HTMLResponse)
    def painel(request: Request, competencia: str | None = None, db: Session = Depends(get_db),
               usuario: str = Depends(usuario_atual)):
        comp = _competencia(competencia)
        hoje = date.today()
        cfg = get_config()
        resumo = resumo_competencia(db, comp, hoje)
        criticas = list(db.scalars(
            select(Tarefa).options(joinedload(Tarefa.empresa), joinedload(Tarefa.obrigacao))
            .where(Tarefa.status == STATUS_PENDENTE, Tarefa.vencimento <= hoje + timedelta(days=cfg.dias_alerta_vencimento))
            .order_by(Tarefa.vencimento).limit(40)).unique())
        ultimos = list(db.scalars(select(Documento).options(joinedload(Documento.empresa))
                                  .order_by(Documento.processado_em.desc()).limit(12)).unique())
        revisar = db.scalar(select(func.count(Documento.id)).where(
            Documento.situacao.in_(["nao_identificado", "divergente", "sem_tarefa"])))
        ultima_sync = db.scalar(select(func.max(EstadoSync.ultima_varredura)))
        ant, prox = _vizinhas(comp)
        return _render(request, "painel.html", comp=comp, ant=ant, prox=prox, r=resumo, criticas=criticas,
                       ultimos=ultimos, revisar=revisar, ultima_sync=ultima_sync, dias_alerta=cfg.dias_alerta_vencimento)

    # ------------------------------------------------------------- Empresas
    @app.get("/empresas", response_class=HTMLResponse)
    def empresas(request: Request, q: str = "", db: Session = Depends(get_db), usuario: str = Depends(usuario_atual)):
        stmt = select(Empresa).order_by(Empresa.codigo)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(Empresa.razao_social.ilike(like) | Empresa.codigo.ilike(like)
                              | Empresa.cnpj.ilike(f"%{so_digitos(q) or q}%") | Empresa.nome_fantasia.ilike(like))
        lista = list(db.scalars(stmt))
        hoje = date.today()
        pend = dict(db.execute(select(Tarefa.empresa_id, func.count(Tarefa.id)).where(
            Tarefa.status == STATUS_PENDENTE, Tarefa.vencimento < hoje).group_by(Tarefa.empresa_id)).all())
        return _render(request, "empresas.html", empresas=lista, atrasos=pend, q=q)

    def _form_empresa(request: Request, db: Session, emp: Empresa | None):
        resp = list(db.scalars(select(Responsavel).where(Responsavel.ativo.is_(True)).order_by(Responsavel.nome)))
        obrigs = list(db.scalars(select(Obrigacao).order_by(Obrigacao.departamento, Obrigacao.nome)))
        aplic = {o.codigo: agenda_mod.obrigacao_aplicavel(emp, o) for o in obrigs} if emp else {}
        return _render(request, "empresa_form.html", emp=emp, responsaveis=resp, flags=FLAGS_EMPRESA,
                       obrigacoes=obrigs, aplicaveis=aplic)

    @app.get("/empresas/nova", response_class=HTMLResponse)
    def empresa_nova(request: Request, db: Session = Depends(get_db), usuario: str = Depends(usuario_atual)):
        return _form_empresa(request, db, None)

    @app.get("/empresas/{empresa_id}/editar", response_class=HTMLResponse)
    def empresa_editar(empresa_id: int, request: Request, db: Session = Depends(get_db),
                       usuario: str = Depends(usuario_atual)):
        emp = db.get(Empresa, empresa_id) or _404()
        return _form_empresa(request, db, emp)

    @app.post("/empresas/salvar")
    async def empresa_salvar(request: Request, db: Session = Depends(get_db), usuario: str = Depends(usuario_atual)):
        f = await request.form()
        emp_id = f.get("id")
        emp = db.get(Empresa, int(emp_id)) if emp_id else Empresa()
        cnpj = so_digitos(f.get("cnpj", ""))
        if not (cnpj_valido(cnpj) or cpf_valido(cnpj)):
            return _voltar(f"/empresas/{emp_id}/editar" if emp_id else "/empresas/nova", "CNPJ/CPF inválido")
        codigo = f.get("codigo", "").strip()
        duplicada = db.scalar(select(Empresa).where((Empresa.cnpj == cnpj) | (Empresa.codigo == codigo)))
        if duplicada is not None and duplicada.id != emp.id:
            return _voltar(f"/empresas/{emp_id}/editar" if emp_id else "/empresas/nova",
                           f"Já existe a empresa {duplicada.codigo} com este código ou CNPJ")
        emp.codigo = codigo
        emp.razao_social = f.get("razao_social", "").strip().upper()
        emp.nome_fantasia = f.get("nome_fantasia", "").strip()
        emp.cnpj = cnpj
        emp.regime = f.get("regime", "SIMPLES")
        emp.uf = f.get("uf", "").strip().upper()[:2]
        emp.municipio = f.get("municipio", "").strip()
        emp.email_cliente = f.get("email_cliente", "").strip()
        emp.whatsapp_cliente = f.get("whatsapp_cliente", "").strip()
        emp.drive_folder_id = extrair_id_pasta(f.get("drive_folder_id", ""))
        emp.ativa = f.get("ativa") == "on"
        for flag, _ in FLAGS_EMPRESA:
            setattr(emp, flag, f.get(flag) == "on")
        for campo in ("resp_fiscal_id", "resp_contabil_id", "resp_pessoal_id"):
            v = f.get(campo)
            setattr(emp, campo, int(v) if v else None)
        pers = {}
        for o in db.scalars(select(Obrigacao)):
            regra = {}
            modo = f.get(f"pers_{o.codigo}", "")
            if modo == "ignorar":
                regra["ignorar"] = True
            elif modo == "incluir":
                regra["incluir"] = True
            dia = f.get(f"dia_{o.codigo}", "").strip()
            if dia.isdigit() and 1 <= int(dia) <= 31:
                regra["dia"] = int(dia)
            if regra:
                pers[o.codigo] = regra
        emp.personalizacoes = pers
        if not emp_id:
            db.add(emp)
        db.flush()
        n = agenda_mod.recalcular_vencimentos(db, emp) if emp_id else 0
        db.add(Evento(tipo="empresa_salva", usuario=usuario, empresa_id=emp.id,
                      mensagem=f"{emp.codigo} salva ({n} vencimento(s) recalculado(s))"))
        return _voltar(f"/empresas/{emp.id}", "Empresa salva")

    @app.get("/empresas/{empresa_id}", response_class=HTMLResponse)
    def empresa_detalhe(empresa_id: int, request: Request, db: Session = Depends(get_db),
                        usuario: str = Depends(usuario_atual)):
        emp = db.get(Empresa, empresa_id) or _404()
        tarefas = list(db.scalars(select(Tarefa).options(joinedload(Tarefa.obrigacao))
                                  .where(Tarefa.empresa_id == emp.id)
                                  .order_by(Tarefa.competencia.desc(), Tarefa.vencimento)).unique())
        comps = sorted({t.competencia for t in tarefas}, reverse=True)[:12]
        obrig = sorted({t.obrigacao for t in tarefas if t.competencia in comps}, key=lambda o: (o.departamento, o.nome))
        grade = {(t.obrigacao_id, t.competencia): t for t in tarefas}
        docs = list(db.scalars(select(Documento).where(Documento.empresa_id == emp.id)
                               .order_by(Documento.processado_em.desc()).limit(50)))
        est = db.scalar(select(EstadoSync).where(EstadoSync.empresa_id == emp.id))
        return _render(request, "empresa.html", emp=emp, comps=list(reversed(comps)), obrigacoes=obrig, grade=grade,
                       docs=docs, estado=est, kpi=indicadores(tarefas))

    @app.post("/empresas/{empresa_id}/criar-pastas")
    def empresa_criar_pastas(empresa_id: int, ano: int = Form(...), db: Session = Depends(get_db),
                             usuario: str = Depends(usuario_atual)):
        from ..drive import criar_cliente
        from ..pastas import criar_estrutura_ano, criar_pasta_empresa

        emp = db.get(Empresa, empresa_id) or _404()
        cfg = get_config()
        drive = criar_cliente()
        if not emp.drive_folder_id:
            if not cfg.drive_root_folder_id and cfg.drive_backend == "google":
                return _voltar(f"/empresas/{emp.id}", "Configure MO_DRIVE_ROOT_FOLDER_ID")
            criar_pasta_empresa(drive, emp, cfg.drive_root_folder_id or "")
        n = criar_estrutura_ano(drive, emp, ano)
        db.add(Evento(tipo="pastas_criadas", usuario=usuario, empresa_id=emp.id, mensagem=f"{n} pastas para {ano}"))
        return _voltar(f"/empresas/{emp.id}", f"Estrutura de pastas {ano} garantida ({n} pastas)")

    @app.post("/empresas/{empresa_id}/sincronizar")
    def empresa_sync(empresa_id: int, db: Session = Depends(get_db), usuario: str = Depends(usuario_atual)):
        from ..drive import criar_cliente

        emp = db.get(Empresa, empresa_id) or _404()
        if not emp.drive_folder_id:
            return _voltar(f"/empresas/{emp.id}", "Empresa sem pasta do Drive vinculada")
        r = Monitor(db, criar_cliente()).sincronizar([emp], completo=True)
        return _voltar(f"/empresas/{emp.id}", f"{r.arquivos_lidos} arquivo(s) lido(s), {r.baixas} baixa(s)"
                       + (f" — erro: {r.erros[0]}" if r.erros else ""))

    # ------------------------------------------------------------- Tarefas
    @app.get("/tarefas", response_class=HTMLResponse)
    def tarefas(request: Request, competencia: str = "", status: str = "", departamento: str = "",
                situacao: str = "", empresa_id: str = "", obrigacao: str = "",
                db: Session = Depends(get_db), usuario: str = Depends(usuario_atual)):
        hoje = date.today()
        stmt = select(Tarefa).options(joinedload(Tarefa.empresa), joinedload(Tarefa.obrigacao),
                                      joinedload(Tarefa.documentos)).join(Obrigacao).join(Empresa)
        if competencia:
            stmt = stmt.where(Tarefa.competencia == competencia)
        if status:
            stmt = stmt.where(Tarefa.status == status)
        if departamento:
            stmt = stmt.where(Obrigacao.departamento == departamento)
        if empresa_id.isdigit():
            stmt = stmt.where(Tarefa.empresa_id == int(empresa_id))
        if obrigacao:
            stmt = stmt.where(Obrigacao.codigo == obrigacao)
        if situacao == "atrasada":
            stmt = stmt.where(Tarefa.status == STATUS_PENDENTE, Tarefa.vencimento < hoje)
        elif situacao == "a_vencer":
            stmt = stmt.where(Tarefa.status == STATUS_PENDENTE, Tarefa.vencimento >= hoje,
                              Tarefa.vencimento <= hoje + timedelta(days=get_config().dias_alerta_vencimento))
        lista = list(db.scalars(stmt.order_by(Tarefa.vencimento, Empresa.codigo).limit(1000)).unique())
        comps = [c for (c,) in db.execute(select(Tarefa.competencia).distinct().order_by(Tarefa.competencia.desc()))]
        obrigs = list(db.scalars(select(Obrigacao).order_by(Obrigacao.nome)))
        return _render(request, "tarefas.html", tarefas=lista, comps=comps, obrigs=obrigs,
                       filtro=dict(competencia=competencia, status=status, departamento=departamento,
                                   situacao=situacao, empresa_id=empresa_id, obrigacao=obrigacao))

    @app.post("/tarefas/{tarefa_id}/acao")
    def tarefa_acao(tarefa_id: int, request: Request, acao: str = Form(...), observacao: str = Form(""),
                    voltar: str = Form("/tarefas"), db: Session = Depends(get_db),
                    usuario: str = Depends(usuario_atual)):
        t = db.get(Tarefa, tarefa_id) or _404()
        if acao == "baixa":
            dar_baixa(db, t, datetime.now(), "manual", usuario, observacao)
            msg = "Baixa manual registrada"
        elif acao == "dispensar":
            if not observacao.strip():
                return _voltar(voltar, "Informe a justificativa para dispensar (ex.: sem movimento)")
            t.status, t.observacao, t.origem_baixa, t.data_entrega = STATUS_DISPENSADA, observacao, "manual", datetime.now()
            db.add(Evento(tipo="dispensa", usuario=usuario, empresa_id=t.empresa_id, tarefa_id=t.id, mensagem=observacao))
            msg = "Tarefa dispensada"
        elif acao == "reabrir":
            t.status, t.data_entrega, t.origem_baixa = STATUS_PENDENTE, None, ""
            db.add(Evento(tipo="reabertura", usuario=usuario, empresa_id=t.empresa_id, tarefa_id=t.id,
                          mensagem=observacao or "reaberta"))
            msg = "Tarefa reaberta"
        else:
            raise HTTPException(400, "ação inválida")
        if not voltar.startswith("/"):
            voltar = "/tarefas"
        return _voltar(voltar, msg)

    # ------------------------------------------------------------- Documentos
    @app.get("/documentos", response_class=HTMLResponse)
    def documentos(request: Request, situacao: str = "revisar", db: Session = Depends(get_db),
                   usuario: str = Depends(usuario_atual)):
        stmt = select(Documento).options(joinedload(Documento.empresa), joinedload(Documento.tarefa))
        if situacao == "revisar":
            stmt = stmt.where(Documento.situacao.in_(["nao_identificado", "divergente", "sem_tarefa"]))
        elif situacao:
            stmt = stmt.where(Documento.situacao == situacao)
        lista = list(db.scalars(stmt.order_by(Documento.processado_em.desc()).limit(500)).unique())
        obrigs = list(db.scalars(select(Obrigacao).order_by(Obrigacao.nome)))
        return _render(request, "documentos.html", docs=lista, situacao=situacao, obrigs=obrigs,
                       comp_padrao=competencia_anterior())

    @app.post("/documentos/{doc_id}/classificar")
    def documento_classificar(doc_id: int, codigo: str = Form(...), competencia: str = Form(...),
                              db: Session = Depends(get_db), usuario: str = Depends(usuario_atual)):
        doc = db.get(Documento, doc_id) or _404()
        try:
            parse_competencia(competencia)
            classificar_manual(db, doc, codigo, competencia, usuario)
        except (ValueError, IndexError) as exc:
            return _voltar("/documentos", f"Erro: {exc}")
        return _voltar("/documentos", f"'{doc.nome}' classificado e tarefa baixada")

    # ------------------------------------------------------------- Cadastros auxiliares
    @app.get("/obrigacoes", response_class=HTMLResponse)
    def obrigacoes(request: Request, db: Session = Depends(get_db), usuario: str = Depends(usuario_atual)):
        lista = list(db.scalars(select(Obrigacao).order_by(Obrigacao.departamento, Obrigacao.nome)))
        return _render(request, "obrigacoes.html", obrigacoes=lista)

    @app.get("/responsaveis", response_class=HTMLResponse)
    def responsaveis(request: Request, db: Session = Depends(get_db), usuario: str = Depends(usuario_atual)):
        return _render(request, "responsaveis.html",
                       responsaveis=list(db.scalars(select(Responsavel).order_by(Responsavel.nome))))

    @app.post("/responsaveis")
    def responsavel_salvar(nome: str = Form(...), email: str = Form(""), departamento: str = Form("FISCAL"),
                           db: Session = Depends(get_db), usuario: str = Depends(usuario_atual)):
        db.add(Responsavel(nome=nome.strip(), email=email.strip(), departamento=departamento))
        return _voltar("/responsaveis", "Responsável cadastrado")

    @app.post("/responsaveis/{resp_id}/alternar")
    def responsavel_alternar(resp_id: int, db: Session = Depends(get_db), usuario: str = Depends(usuario_atual)):
        r = db.get(Responsavel, resp_id) or _404()
        r.ativo = not r.ativo
        return _voltar("/responsaveis", "Situação alterada")

    # ------------------------------------------------------------- Relatórios
    @app.get("/relatorios", response_class=HTMLResponse)
    def relatorios(request: Request, competencia: str | None = None, db: Session = Depends(get_db),
                   usuario: str = Depends(usuario_atual)):
        comp = _competencia(competencia)
        ant, prox = _vizinhas(comp)
        return _render(request, "relatorios.html", comp=comp, ant=ant, prox=prox, r=resumo_competencia(db, comp))

    @app.get("/relatorios/csv")
    def relatorio_csv(competencia: str = "", db: Session = Depends(get_db), usuario: str = Depends(usuario_atual)):
        stmt = select(Tarefa).options(joinedload(Tarefa.empresa), joinedload(Tarefa.obrigacao),
                                      joinedload(Tarefa.documentos))
        if competencia:
            stmt = stmt.where(Tarefa.competencia == competencia)
        conteudo = exportar_csv(list(db.scalars(stmt).unique()))
        nome = f"obrigacoes_{competencia or 'todas'}.csv"
        return Response(conteudo, media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{nome}"'})

    @app.get("/eventos", response_class=HTMLResponse)
    def eventos(request: Request, db: Session = Depends(get_db), usuario: str = Depends(usuario_atual)):
        lista = list(db.scalars(select(Evento).order_by(Evento.momento.desc()).limit(300)))
        return _render(request, "eventos.html", eventos=lista)

    # ------------------------------------------------------------- Ações
    @app.post("/acoes/agenda")
    def acao_agenda(competencia: str = Form(...), db: Session = Depends(get_db), usuario: str = Depends(usuario_atual)):
        r = agenda_mod.gerar_agenda(db, _competencia(competencia), usuario=usuario)
        return _voltar(f"/?competencia={r['competencia']}", f"Agenda {r['competencia']}: {r['tarefas_criadas']} tarefa(s) criada(s)")

    @app.post("/acoes/sincronizar")
    def acao_sync(db: Session = Depends(get_db), usuario: str = Depends(usuario_atual)):
        from ..drive import criar_cliente

        r = Monitor(db, criar_cliente()).sincronizar()
        return _voltar("/", f"Drive verificado: {r.arquivos_lidos} arquivo(s), {r.baixas} baixa(s), "
                            f"{r.nao_identificados} não identificado(s)" + (f", {len(r.erros)} erro(s)" if r.erros else ""))

    @app.post("/acoes/alertas")
    def acao_alertas(db: Session = Depends(get_db), usuario: str = Depends(usuario_atual)):
        r = executar_alertas(db)
        return _voltar("/", f"Alertas: {r['emails']} e-mail(s), {r['cobrancas_cliente']} cobrança(s)")

    # ------------------------------------------------------------- API JSON
    @app.get("/api/resumo")
    def api_resumo(competencia: str | None = None, db: Session = Depends(get_db), usuario: str = Depends(usuario_atual)):
        comp = _competencia(competencia)
        r = resumo_competencia(db, comp)
        return JSONResponse({"competencia": comp, **r})

    @app.get("/api/tarefas")
    def api_tarefas(competencia: str = "", empresa_id: int | None = None, db: Session = Depends(get_db),
                    usuario: str = Depends(usuario_atual)):
        stmt = select(Tarefa).options(joinedload(Tarefa.empresa), joinedload(Tarefa.obrigacao))
        if competencia:
            stmt = stmt.where(Tarefa.competencia == competencia)
        if empresa_id:
            stmt = stmt.where(Tarefa.empresa_id == empresa_id)
        return [{
            "id": t.id, "empresa": t.empresa.codigo, "cnpj": t.empresa.cnpj, "obrigacao": t.obrigacao.codigo,
            "competencia": t.competencia, "vencimento": t.vencimento.isoformat(), "status": t.status,
            "situacao": t.situacao(), "data_entrega": t.data_entrega.isoformat() if t.data_entrega else None,
        } for t in db.scalars(stmt.limit(5000)).unique()]

    return app


def _404():
    raise HTTPException(404, "Não encontrado")


app = criar_app()
