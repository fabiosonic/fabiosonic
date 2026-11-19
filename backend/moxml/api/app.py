"""API REST local do painel (FastAPI). Servida em 127.0.0.1 por padrão."""

from __future__ import annotations

import asyncio
import hmac
import json
import threading
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select

from .. import __version__, servicos
from ..certificados.a1 import ErroCertificado, SenhaIncorreta
from ..db.modelos import (
    ArquivoDrive, ChaveConhecida, Certificado, ConectorConfig, Documento, Empresa, Evento, Execucao, Lacuna,
    LogExecucao, PastaMonitorada, RegistroFonte, Serie,
)
from ..integracoes import dominio
from ..motor.agendador import Agendador
from ..motor.aplicacao import Aplicacao
from ..motor.logs import HUB
from ..motor.orquestrador import Opcoes, Orquestrador, executar_com_trava
from ..motor.semente import SementeInvalida

WEB = Path(__file__).resolve().parent.parent / "web"


class EmpresaIn(BaseModel):
    razao_social: str = Field(min_length=2, max_length=160)
    cnpj: str
    uf: str = "RJ"
    regime: str | None = None
    nome_pasta: str | None = None
    captura_nfe: bool = True
    captura_nfce: bool = True


class EmpresaPatch(BaseModel):
    razao_social: str | None = None
    regime: str | None = None
    nome_pasta: str | None = None
    ativo: bool | None = None
    captura_nfe: bool | None = None
    captura_nfce: bool | None = None


class ChavesIn(BaseModel):
    chaves: list[str]


class PastaIn(BaseModel):
    caminho: str
    empresa_id: int | None = None


class ExecutarIn(BaseModel):
    empresas: list[int] | None = None
    modelos: list[str] = ["55", "65"]
    historico: dict[str, int] | None = None  # "empresa_id|modelo|serie" -> número inicial


class ExportarIn(BaseModel):
    ano: int
    mes: int = Field(ge=1, le=12)
    empresas: list[int] | None = None


class ConectorIn(BaseModel):
    ativo: bool


def _doc(d: Documento) -> dict:
    return {"id": d.id, "empresa_id": d.empresa_id, "chave": d.chave, "modelo": d.modelo, "serie": d.serie,
            "numero": d.numero, "data_emissao": d.data_emissao.isoformat() if d.data_emissao else None,
            "valor": float(d.valor) if d.valor is not None else None, "situacao": d.situacao, "tipo_xml": d.tipo_xml,
            "protocolo": d.protocolo, "origem": d.origem, "hash_sha256": d.hash_sha256,
            "assinatura_ok": d.assinatura_ok, "modo": d.modo, "data_captura": d.data_captura.isoformat()}


def criar_api(app: Aplicacao, iniciar_agendador: bool = True) -> FastAPI:
    orq = Orquestrador(app)
    agendador = Agendador(app, orq)

    @asynccontextmanager
    async def ciclo(_api: FastAPI):
        with app.sessoes() as s:
            n = Orquestrador.marcar_interrompidas(s)
            if n:
                HUB.publicar("AVISO", f"{n} execução(ões) interrompida(s) no último encerramento; checkpoints preservados")
        if iniciar_agendador and app.cfg.agendamento_ativo:
            agendador.iniciar()
        yield
        agendador.parar()

    api = FastAPI(title="M&O XML Captador", version=__version__, lifespan=ciclo)

    def autenticar(request: Request) -> None:
        tok = app.cfg.api_token
        if not tok:
            return
        rec = request.headers.get("x-api-token") or request.cookies.get("moxml_token") or ""
        if not hmac.compare_digest(rec, tok):
            raise HTTPException(401, "token inválido")

    dep = [Depends(autenticar)]

    @api.exception_handler(servicos.ErroNegocio)
    async def _erro_neg(_r: Request, e: servicos.ErroNegocio):
        return JSONResponse({"detail": str(e)}, status_code=422)

    # ------------------------------------------------------------------ sistema
    @api.get("/api/saude")
    def saude():
        return {"ok": True, "versao": __version__, "modo": app.modo, "hora": datetime.now(UTC).isoformat()}

    @api.get("/api/resumo", dependencies=dep)
    def resumo():
        r = servicos.resumo(app)
        r["proximas_execucoes"] = agendador.proximas() if agendador.sched.running else []
        r["captura_em_andamento"] = orq._executando
        return r

    # ------------------------------------------------------------------ empresas
    @api.get("/api/empresas", dependencies=dep)
    def empresas(busca: str | None = None):
        with app.sessoes() as s:
            q = select(Empresa).order_by(Empresa.razao_social)
            if busca:
                q = q.where(or_(Empresa.razao_social.ilike(f"%{busca}%"), Empresa.cnpj.like(f"%{servicos.so_digitos(busca)}%")))
            out = []
            for e in s.scalars(q):
                cert = app.certificado_ativo(s, e.id)
                ndocs = s.scalar(select(func.count()).select_from(Documento).where(Documento.empresa_id == e.id))
                pend = s.scalar(select(func.count()).select_from(ChaveConhecida).where(
                    ChaveConhecida.empresa_id == e.id, ChaveConhecida.status != "RECUPERADA"))
                ult = s.scalar(select(Execucao).where(Execucao.empresa_id == e.id).order_by(Execucao.inicio.desc()).limit(1))
                out.append({"id": e.id, "razao_social": e.razao_social, "cnpj": e.cnpj, "uf": e.uf, "regime": e.regime,
                            "ativo": e.ativo, "captura_nfe": e.captura_nfe, "captura_nfce": e.captura_nfce,
                            "nome_pasta": e.nome_pasta,
                            "certificado": {"status": cert.status, "validade": cert.validade.isoformat()} if cert else None,
                            "documentos": ndocs, "pendentes": pend,
                            "ultima_execucao": {"status": ult.status, "inicio": ult.inicio.isoformat()} if ult else None})
            return out

    @api.post("/api/empresas", dependencies=dep, status_code=201)
    def criar_empresa(e: EmpresaIn):
        emp = servicos.cadastrar_empresa(app, e.razao_social, e.cnpj, e.uf, e.regime, e.nome_pasta, e.captura_nfe, e.captura_nfce)
        return {"id": emp.id}

    @api.patch("/api/empresas/{eid}", dependencies=dep)
    def editar_empresa(eid: int, p: EmpresaPatch):
        with app.sessoes() as s:
            e = s.get(Empresa, eid)
            if e is None:
                raise HTTPException(404, "empresa não encontrada")
            for k, v in p.model_dump(exclude_none=True).items():
                setattr(e, k, v)
            s.commit()
        return {"ok": True}

    @api.get("/api/empresas/{eid}/series", dependencies=dep)
    def series(eid: int):
        with app.sessoes() as s:
            return [{"id": x.id, "modelo": x.modelo, "serie": x.serie, "ambiente": x.ambiente,
                     "ultimo_numero_identificado": x.ultimo_numero_identificado,
                     "ultimo_numero_recuperado": x.ultimo_numero_recuperado, "chave_semente": x.chave_semente,
                     "data_semente": x.data_semente.isoformat() if x.data_semente else None, "ativo": x.ativo}
                    for x in s.scalars(select(Serie).where(Serie.empresa_id == eid).order_by(Serie.modelo, Serie.serie))]

    @api.post("/api/empresas/{eid}/semente", dependencies=dep)
    async def semente(eid: int, arquivo: UploadFile = File(...)):
        dados = await arquivo.read()
        try:
            info = servicos.importar_semente_bytes(app, eid, dados)
        except SementeInvalida as e:
            raise HTTPException(422, str(e)) from None
        return info.__dict__ | {"data_emissao": info.data_emissao.isoformat() if info.data_emissao else None}

    @api.post("/api/empresas/{eid}/chaves", dependencies=dep)
    def chaves(eid: int, c: ChavesIn):
        return servicos.adicionar_chaves(app, eid, c.chaves)

    # ------------------------------------------------------------------ certificados
    @api.get("/api/certificados", dependencies=dep)
    def certificados():
        with app.sessoes() as s:
            rows = s.execute(select(Certificado, Empresa.razao_social).join(Empresa, isouter=True)
                             .order_by(Certificado.validade)).all()
            return [{"id": c.id, "empresa_id": c.empresa_id, "empresa": nome, "titular": c.titular, "cnpj": c.cnpj,
                     "validade": c.validade.isoformat(), "valido_de": c.valido_de.isoformat(), "status": c.status,
                     "ativo": c.ativo, "emissor": c.emissor, "autorizado_por": c.autorizado_por,
                     "autorizado_em": c.autorizado_em.isoformat(), "impressao_digital": c.impressao_digital[:16]}
                    for c, nome in rows]

    @api.post("/api/empresas/{eid}/certificado", dependencies=dep, status_code=201)
    async def enviar_certificado(eid: int, arquivo: UploadFile = File(...), senha: str = Form(...),
                                 autorizado_por: str = Form(...), termo: str = Form(...),
                                 confirmo_autorizacao: bool = Form(...)):
        if not confirmo_autorizacao:
            raise HTTPException(422, "é necessário confirmar a autorização do titular para uso do certificado")
        pfx = await arquivo.read()
        try:
            c = servicos.cadastrar_certificado(app, eid, pfx, senha, autorizado_por, termo)
        except SenhaIncorreta:
            raise HTTPException(422, "senha do certificado incorreta") from None
        except ErroCertificado as e:
            raise HTTPException(422, str(e)) from None
        return {"id": c.id, "titular": c.titular, "validade": c.validade.isoformat(), "status": c.status}

    # ------------------------------------------------------------------ documentos
    @api.get("/api/documentos", dependencies=dep)
    def documentos(empresa_id: int | None = None, modelo: str | None = None, situacao: str | None = None,
                   chave: str | None = None, inicio: str | None = None, fim: str | None = None,
                   pagina: int = Query(1, ge=1), limite: int = Query(50, ge=1, le=500)):
        with app.sessoes() as s:
            q = select(Documento)
            if empresa_id:
                q = q.where(Documento.empresa_id == empresa_id)
            if modelo:
                q = q.where(Documento.modelo == modelo)
            if situacao:
                q = q.where(Documento.situacao == situacao)
            if chave:
                q = q.where(Documento.chave.like(f"%{servicos.so_digitos(chave)}%"))
            if inicio:
                q = q.where(Documento.data_emissao >= datetime.fromisoformat(inicio))
            if fim:
                q = q.where(Documento.data_emissao <= datetime.fromisoformat(fim))
            total = s.scalar(select(func.count()).select_from(q.subquery()))
            itens = s.scalars(q.order_by(Documento.data_emissao.desc()).offset((pagina - 1) * limite).limit(limite)).all()
            return {"total": total, "pagina": pagina, "limite": limite, "itens": [_doc(d) for d in itens]}

    @api.get("/api/documentos/{did}/xml", dependencies=dep)
    def documento_xml(did: int):
        with app.sessoes() as s:
            d = s.get(Documento, did)
            if d is None or not d.caminho_xml:
                raise HTTPException(404, "documento não encontrado")
            caminho = (Path(app.cfg.pasta_xml) / d.caminho_xml).resolve()
            if Path(app.cfg.pasta_xml).resolve() not in caminho.parents:
                raise HTTPException(400, "caminho inválido")
            return FileResponse(caminho, media_type="application/xml", filename=caminho.name)

    @api.get("/api/pendentes", dependencies=dep)
    def pendentes(empresa_id: int | None = None, limite: int = 200):
        with app.sessoes() as s:
            q = select(ChaveConhecida).where(ChaveConhecida.status != "RECUPERADA")
            if empresa_id:
                q = q.where(ChaveConhecida.empresa_id == empresa_id)
            return [{"chave": c.chave, "empresa_id": c.empresa_id, "modelo": c.modelo, "serie": c.serie,
                     "numero": c.numero, "status": c.status, "situacao_sefaz": c.situacao_sefaz, "origem": c.origem,
                     "tentativas": c.tentativas, "mensagem": c.mensagem}
                    for c in s.scalars(q.order_by(ChaveConhecida.numero).limit(limite))]

    @api.get("/api/eventos", dependencies=dep)
    def eventos(empresa_id: int | None = None, tipo: str | None = None, limite: int = 200):
        with app.sessoes() as s:
            q = select(Evento)
            if empresa_id:
                q = q.where(Evento.empresa_id == empresa_id)
            if tipo:
                q = q.where(Evento.tipo_evento == tipo)
            return [{"id": e.id, "empresa_id": e.empresa_id, "chave": e.chave, "tipo_evento": e.tipo_evento,
                     "descricao": e.descricao, "sequencia": e.sequencia, "protocolo": e.protocolo,
                     "data_evento": e.data_evento.isoformat() if e.data_evento else None, "origem": e.origem}
                    for e in s.scalars(q.order_by(Evento.data_evento.desc()).limit(limite))]

    @api.get("/api/lacunas", dependencies=dep)
    def lacunas(empresa_id: int | None = None, classificacao: str | None = None, limite: int = 500):
        with app.sessoes() as s:
            q = select(Lacuna, Empresa.razao_social).join(Empresa)
            if empresa_id:
                q = q.where(Lacuna.empresa_id == empresa_id)
            if classificacao:
                q = q.where(Lacuna.classificacao == classificacao)
            return [{"id": lac.id, "empresa_id": lac.empresa_id, "empresa": nome, "modelo": lac.modelo, "serie": lac.serie,
                     "numero": lac.numero, "periodo": lac.periodo, "classificacao": lac.classificacao,
                     "observacao": lac.observacao, "ultima_verificacao": lac.ultima_verificacao.isoformat()}
                    for lac, nome in s.execute(q.order_by(Lacuna.empresa_id, Lacuna.modelo, Lacuna.serie, Lacuna.numero)
                                               .limit(limite))]

    # ------------------------------------------------------------------ capturas
    @api.post("/api/capturas/executar", dependencies=dep, status_code=202)
    def executar(p: ExecutarIn):
        if orq._executando:
            raise HTTPException(409, "já existe captura em andamento")
        a_partir = None
        if p.historico:
            a_partir = {}
            for k, v in p.historico.items():
                e, m, sr = k.split("|")
                a_partir[(int(e), m, int(sr))] = int(v)
        op = Opcoes(gatilho="HISTORICA" if a_partir else "MANUAL", empresas=p.empresas, modelos=tuple(p.modelos),
                    a_partir_de=a_partir)
        threading.Thread(target=executar_com_trava, args=(orq, op), daemon=True, name="captura-manual").start()
        return {"iniciada": True}

    @api.get("/api/execucoes", dependencies=dep)
    def execucoes(limite: int = 100, empresa_id: int | None = None):
        with app.sessoes() as s:
            q = select(Execucao, Empresa.razao_social).join(Empresa, isouter=True)
            if empresa_id:
                q = q.where(Execucao.empresa_id == empresa_id)
            return [{"id": x.id, "lote": x.lote, "empresa": nome, "empresa_id": x.empresa_id, "modelo": x.modelo,
                     "gatilho": x.gatilho, "inicio": x.inicio.isoformat(), "fim": x.fim.isoformat() if x.fim else None,
                     "status": x.status, "quantidade": x.quantidade, "erros": x.erros, "detalhes": x.detalhes, "modo": x.modo}
                    for x, nome in s.execute(q.order_by(Execucao.inicio.desc()).limit(limite))]

    @api.get("/api/execucoes/{xid}/logs", dependencies=dep)
    def logs_execucao(xid: int):
        with app.sessoes() as s:
            return [{"momento": lg.momento.isoformat(), "nivel": lg.nivel, "mensagem": lg.mensagem}
                    for lg in s.scalars(select(LogExecucao).where(LogExecucao.execucao_id == xid).order_by(LogExecucao.id))]

    @api.get("/api/logs/stream", dependencies=dep)
    async def stream(request: Request, desde: int = 0):
        async def gerar():
            seq = desde
            while not await request.is_disconnected():
                for item in HUB.desde(seq):
                    seq = item["seq"]
                    yield f"id: {seq}\ndata: {json.dumps(item, ensure_ascii=False)}\n\n"
                await asyncio.sleep(1)
        return StreamingResponse(gerar(), media_type="text/event-stream")

    @api.get("/api/logs/recentes", dependencies=dep)
    def logs_recentes(desde: int = 0):
        return HUB.desde(desde)[-300:]

    # ------------------------------------------------------------------ integrações
    @api.get("/api/integracoes", dependencies=dep)
    def integracoes():
        with app.sessoes() as s:
            cfgs = {c.nome: c.ativo for c in s.scalars(select(ConectorConfig))}
            fontes = s.execute(select(RegistroFonte.servico, RegistroFonte.cstat, func.count()).group_by(
                RegistroFonte.servico, RegistroFonte.cstat)).all()
            drive = dict(s.execute(select(ArquivoDrive.status, func.count()).group_by(ArquivoDrive.status)).all())
        conectores = []
        for c in app.registro.conectores.values():
            d = c.descrever()
            d["ativo"] = cfgs.get(c.nome, not c.comercial)
            conectores.append(d)
        return {"conectores": conectores, "matriz": app.registro.matriz(["RJ", "SP"]),
                "estatisticas_fontes": [{"servico": a, "cstat": b, "quantidade": n} for a, b, n in fontes],
                "google_drive": {"ativo": app.cfg.gdrive_ativo, "status": drive},
                "dominio": {"modo": "pacote de importação por XML (integração direta não validada)"}}

    @api.put("/api/conectores/{nome}", dependencies=dep)
    def conector(nome: str, p: ConectorIn):
        if nome not in app.registro.conectores:
            raise HTTPException(404, "conector desconhecido")
        with app.sessoes() as s:
            c = s.scalar(select(ConectorConfig).where(ConectorConfig.nome == nome))
            if c is None:
                s.add(ConectorConfig(nome=nome, ativo=p.ativo))
            else:
                c.ativo = p.ativo
            s.commit()
        return {"ok": True}

    @api.post("/api/drive/sincronizar", dependencies=dep)
    def drive():
        from ..integracoes.gdrive import sincronizar_drive
        try:
            return sincronizar_drive(app)
        except RuntimeError as e:
            raise HTTPException(422, str(e)) from None

    @api.post("/api/dominio/exportar", dependencies=dep)
    def exportar_dominio(p: ExportarIn):
        destino = Path(app.cfg.home) / "exportacoes" / "dominio"
        return dominio.exportar_lote(app, p.ano, p.mes, destino, p.empresas)

    @api.get("/api/pastas", dependencies=dep)
    def pastas():
        with app.sessoes() as s:
            return [{"id": p.id, "caminho": p.caminho, "empresa_id": p.empresa_id, "ativo": p.ativo,
                     "ultima_varredura": p.ultima_varredura.isoformat() if p.ultima_varredura else None}
                    for p in s.scalars(select(PastaMonitorada))]

    @api.post("/api/pastas", dependencies=dep, status_code=201)
    def nova_pasta(p: PastaIn):
        if not Path(p.caminho).exists():
            raise HTTPException(422, "pasta não encontrada neste computador")
        return {"id": servicos.adicionar_pasta(app, p.caminho, p.empresa_id).id}

    @api.get("/api/configuracoes", dependencies=dep)
    def configuracoes():
        c = app.cfg
        return {"modo": c.modo.value, "home": str(c.home), "banco": c.url_banco.split("@")[-1],
                "horarios_execucao": c.horarios_execucao, "agendamento_ativo": c.agendamento_ativo,
                "pasta_xml": str(c.pasta_xml), "ca_bundle": str(c.ca_bundle) if c.ca_bundle else None,
                "cofre": app.cofre.mecanismo, "timeout_segundos": c.timeout_segundos, "retentativas": c.retentativas,
                "gdrive_ativo": c.gdrive_ativo, "apisimples_ativo": c.apisimples_ativo,
                "token_api_exigido": bool(c.api_token)}

    # ------------------------------------------------------------------ frontend
    if (WEB / "index.html").exists():
        api.mount("/assets", StaticFiles(directory=WEB / "assets"), name="assets")

        @api.get("/{caminho:path}", include_in_schema=False)
        def spa(caminho: str):
            if caminho.startswith("api/"):
                return Response(status_code=404)
            return FileResponse(WEB / "index.html")

    return api
