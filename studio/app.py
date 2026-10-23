"""Aplicativo web do Studio Contábil (FastAPI + páginas renderizadas no servidor)."""
from __future__ import annotations

import calendar
import hashlib
import hmac
import json
import os
import secrets
import shutil
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

from fastapi import BackgroundTasks, FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from avatar_contabil import config

from . import carrossel, fluxo, ia, pautas, publicacao, travas, video
from .db import Conteudo, Evento, Pauta, Perfil, Usuario, agora, registrar, select, sessao

AQUI = Path(__file__).parent
templates = Jinja2Templates(directory=AQUI / "templates")
templates.env.globals.update(ROTULOS=fluxo.ROTULOS, ESTILOS=ia.ESTILOS)

FORMATOS = {"post": "Post (imagem única)", "carrossel": "Carrossel", "video": "Vídeo com avatar"}
templates.env.globals["FORMATOS"] = FORMATOS
PUBLICAS = ("/login", "/primeiro-acesso", "/c/", "/static/")


# ---------- utilidades ----------

def cfg() -> dict:
    return config.carregar()


def pasta_studio(*partes: str) -> Path:
    p = config.DADOS.joinpath("studio", *partes)
    p.mkdir(parents=True, exist_ok=True)
    return p


def rel(caminho: Path) -> str:
    return caminho.resolve().relative_to(config.DADOS.resolve()).as_posix()


def hash_senha(senha: str, sal: str | None = None) -> str:
    sal = sal or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", senha.encode(), sal.encode(), 200_000).hex()
    return f"{sal}${dk}"


def confere_senha(senha: str, guardado: str) -> bool:
    sal, _, _ = guardado.partition("$")
    return hmac.compare_digest(hash_senha(senha, sal), guardado)


def segredo_sessao() -> str:
    if os.environ.get("STUDIO_SECRET"):
        return os.environ["STUDIO_SECRET"]
    arq = config.DADOS / ".studio_secret"
    arq.parent.mkdir(parents=True, exist_ok=True)
    if not arq.exists():
        arq.write_text(secrets.token_urlsafe(48))
    return arq.read_text().strip()


def ir(url: str, msg: str = "", request: Request | None = None) -> RedirectResponse:
    if msg and request is not None:
        request.session["msg"] = msg
    return RedirectResponse(url, status_code=303)


def pagina(request: Request, nome: str, **ctx) -> HTMLResponse:
    ctx.update(request=request, usuario=request.state.usuario, msg=request.session.pop("msg", ""), dry_run=config.dry_run())
    return templates.TemplateResponse(request, nome, ctx)


def slides_de_texto(texto: str) -> list[dict]:
    """Blocos separados por linha em branco; 1ª linha é o título."""
    saida = []
    for bloco in [b.strip() for b in texto.replace("\r\n", "\n").split("\n\n") if b.strip()]:
        titulo, _, corpo = bloco.partition("\n")
        saida.append({"titulo": titulo.strip(), "texto": " ".join(corpo.split())})
    return saida


def texto_de_slides(slides: list[dict]) -> str:
    return "\n\n".join(f"{s.get('titulo', '')}\n{s.get('texto', '')}" for s in slides)


def atualizar_previa(c: Conteudo, perfil: Perfil) -> None:
    """Redesenha as imagens do post/carrossel para revisão e aprovação."""
    if c.formato == "video":
        return
    dados = c.j("dados")
    destino = pasta_studio("conteudos", str(c.id), "previa")
    for antigo in destino.glob("*.png"):
        antigo.unlink()
    arquivos = carrossel.desenhar(perfil, dados.get("slides", []), destino, config.DADOS)
    c.guardar("arquivos", [rel(a) for a in arquivos])


def aplicar_travas(c: Conteudo, perfil: Perfil) -> None:
    c.guardar("alertas", travas.validar(cfg(), perfil, c.formato, c.j("dados")))


def avaliar(c: Conteudo, perfil: Perfil) -> None:
    c.guardar("nota", ia.avaliar(perfil, c.formato, c.j("dados")))


def criar_conteudo(s, perfil: Perfil, pauta: Pauta, formato: str, estilo: str, instrucao: str, usuario: str, base: dict | None = None) -> Conteudo:
    gerado = ia.gerar(perfil, pauta, formato, estilo, instrucao, base=base)
    c = Conteudo(perfil_id=perfil.id, pauta_id=pauta.id, formato=formato, estilo=estilo)
    c.guardar("dados", gerado.model_dump())
    s.add(c)
    s.flush()
    aplicar_travas(c, perfil)
    avaliar(c, perfil)
    atualizar_previa(c, perfil)
    registrar(s, c.id, usuario, "criado", f"{FORMATOS[formato]} · {ia.ESTILOS.get(estilo, '')[:40]}" + (" (réplica)" if base else ""))
    return c


def dentro_de_dados(caminho: str) -> Path | None:
    alvo = (config.DADOS / caminho).resolve()
    base = (config.DADOS / "studio").resolve()
    return alvo if alvo.is_file() and base in alvo.parents else None


# ---------- aplicativo ----------

def criar_app() -> FastAPI:
    app = FastAPI(title="Studio Contábil", docs_url=None, redoc_url=None)

    @app.middleware("http")
    async def exigir_login(request: Request, chamar):
        request.state.usuario = None
        uid = request.session.get("uid")
        if uid:
            with sessao() as s:
                request.state.usuario = s.get(Usuario, uid)
        if request.state.usuario is None and not request.url.path.startswith(PUBLICAS):
            return RedirectResponse("/login", status_code=303)
        return await chamar(request)

    app.add_middleware(SessionMiddleware, secret_key=segredo_sessao(), same_site="lax", max_age=60 * 60 * 12)
    app.mount("/static", StaticFiles(directory=AQUI / "static"), name="static")

    # ----- login -----
    @app.get("/login", response_class=HTMLResponse)
    def login_form(request: Request):
        with sessao() as s:
            vazio = s.exec(select(Usuario)).first() is None
        return pagina(request, "login.html", primeiro_acesso=vazio)

    @app.post("/login")
    def login(request: Request, email: str = Form(...), senha: str = Form(...)):
        with sessao() as s:
            u = s.exec(select(Usuario).where(Usuario.email == email.strip().lower())).first()
            if not u or not confere_senha(senha, u.senha_hash):
                return ir("/login", "E-mail ou senha inválidos.", request)
            request.session["uid"] = u.id
        return ir("/")

    @app.post("/primeiro-acesso")
    def primeiro_acesso(request: Request, nome: str = Form(...), email: str = Form(...), crc: str = Form(""), senha: str = Form(...)):
        with sessao() as s:
            if s.exec(select(Usuario)).first():
                return ir("/login", "O administrador já foi criado.", request)
            if len(senha) < 8:
                return ir("/login", "A senha precisa ter pelo menos 8 caracteres.", request)
            u = Usuario(nome=nome.strip(), email=email.strip().lower(), crc=crc.strip(), papel="admin", senha_hash=hash_senha(senha))
            s.add(u)
            s.commit()
            request.session["uid"] = u.id
        return ir("/", "Bem-vindo! Comece cadastrando o perfil do seu escritório.", request)

    @app.get("/sair")
    def sair(request: Request):
        request.session.clear()
        return ir("/login")

    # ----- painel -----
    @app.get("/", response_class=HTMLResponse)
    def painel(request: Request):
        hoje = date.today()
        with sessao() as s:
            conteudos = s.exec(select(Conteudo)).all()
            perfis = {p.id: p for p in s.exec(select(Perfil)).all()}
        contagem = {st: sum(1 for c in conteudos if c.status == st) for st in fluxo.ORDEM}
        proximo = (hoje.replace(day=1) + timedelta(days=32)).replace(day=1)
        obrig = [o for o in pautas.obrigacoes_do_mes(hoje.year, hoje.month) + pautas.obrigacoes_do_mes(proximo.year, proximo.month)
                 if hoje <= o.data <= hoje + timedelta(days=30)]
        pendentes = [c for c in conteudos if c.status in (fluxo.REVISAO, fluxo.AJUSTE, fluxo.ERRO)]
        return pagina(request, "painel.html", contagem=contagem, obrigacoes=obrig, pendentes=pendentes, perfis=perfis, sem_perfil=not perfis)

    # ----- perfis -----
    @app.get("/perfis", response_class=HTMLResponse)
    def perfis_lista(request: Request):
        with sessao() as s:
            lista = s.exec(select(Perfil).order_by(Perfil.tipo.desc(), Perfil.nome)).all()
        return pagina(request, "perfis.html", perfis=lista)

    @app.post("/perfis")
    def perfil_criar(request: Request, nome: str = Form(...), tipo: str = Form("cliente"), site: str = Form("")):
        with sessao() as s:
            p = Perfil(nome=nome.strip(), tipo="escritorio" if tipo == "escritorio" else "cliente", site=site.strip())
            s.add(p)
            s.commit()
            pid = p.id
        if site.strip():
            return importar_site(request, pid)
        return ir(f"/perfis/{pid}", "Perfil criado. Complete o kit de marca.", request)

    @app.get("/perfis/{pid}", response_class=HTMLResponse)
    def perfil_ver(request: Request, pid: int):
        with sessao() as s:
            p = s.get(Perfil, pid)
        if not p:
            return ir("/perfis", "Perfil não encontrado.", request)
        return pagina(request, "perfil.html", p=p, canais=json.dumps(p.canais(), ensure_ascii=False, indent=1))

    @app.post("/perfis/{pid}")
    async def perfil_salvar(request: Request, pid: int):
        form = await request.form()
        with sessao() as s:
            p = s.get(Perfil, pid)
            for campo in ("nome", "site", "instagram", "whatsapp", "crc_responsavel", "cor_primaria", "cor_secundaria",
                          "cor_destaque", "tom", "publico", "servicos", "nunca_dizer", "heygen_avatar_id", "elevenlabs_voice_id"):
                if campo in form:
                    setattr(p, campo, str(form[campo]).strip())
            p.tipo = "escritorio" if form.get("tipo") == "escritorio" else "cliente"
            try:
                canais = json.loads(str(form.get("postiz_canais") or "{}"))
                assert isinstance(canais, dict)
                p.postiz_canais = json.dumps(canais)
            except (ValueError, AssertionError):
                return ir(f"/perfis/{pid}", "Canais do Postiz: use o formato {\"instagram\": \"id\"}.", request)
            logo: UploadFile | None = form.get("logo")
            conteudo_logo = await logo.read() if logo is not None and getattr(logo, "filename", "") else b""
            if conteudo_logo:
                try:
                    from PIL import Image

                    Image.open(BytesIO(conteudo_logo)).verify()
                except Exception:
                    return ir(f"/perfis/{pid}", "O logo precisa ser uma imagem PNG ou JPG válida.", request)
                destino = pasta_studio("perfis", str(pid)) / f"logo{Path(logo.filename).suffix.lower() or '.png'}"
                destino.write_bytes(conteudo_logo)
                p.logo = rel(destino)
            s.add(p)
            s.commit()
        return ir(f"/perfis/{pid}", "Perfil salvo.", request)

    @app.post("/perfis/{pid}/importar-site")
    def importar_site(request: Request, pid: int):
        with sessao() as s:
            p = s.get(Perfil, pid)
            if not p.site:
                return ir(f"/perfis/{pid}", "Informe o site do perfil primeiro.", request)
            try:
                marca, cores = ia.marca_do_site(p.site)
            except Exception as e:
                return ir(f"/perfis/{pid}", f"Não consegui ler o site: {e}", request)
            p.tom, p.publico = marca.tom, marca.publico
            p.servicos = ", ".join(marca.servicos) or p.servicos
            if marca.nunca_dizer:
                p.nunca_dizer = "\n".join(dict.fromkeys(p.termos_proibidos() + marca.nunca_dizer))
            for campo, cor in zip(("cor_primaria", "cor_destaque", "cor_secundaria"), cores):
                setattr(p, campo, cor)
            s.add(p)
            s.commit()
        return ir(f"/perfis/{pid}", "Marca preenchida a partir do site. Revise os campos.", request)

    @app.post("/perfis/{pid}/consentimento")
    async def consentimento(request: Request, pid: int, termo: UploadFile = File(...)):
        if not termo.filename:
            return ir(f"/perfis/{pid}", "Anexe o termo assinado.", request)
        destino = pasta_studio("perfis", str(pid)) / f"termo_consentimento{Path(termo.filename).suffix.lower()}"
        destino.write_bytes(await termo.read())
        with sessao() as s:
            p = s.get(Perfil, pid)
            p.consentimento_arquivo, p.consentimento_em = rel(destino), agora()
            s.add(p)
            registrar(s, None, request.state.usuario.nome, "consentimento", f"perfil {p.nome}")
            s.commit()
        return ir(f"/perfis/{pid}", "Termo registrado. Vídeos com avatar liberados para este perfil.", request)

    # ----- pautas -----
    @app.get("/pautas", response_class=HTMLResponse)
    def pautas_lista(request: Request, origem: str = ""):
        with sessao() as s:
            q = select(Pauta).where(Pauta.arquivada == False).order_by(Pauta.criada_em.desc())  # noqa: E712
            if origem:
                q = q.where(Pauta.origem == origem)
            lista = s.exec(q).all()
            perfis = s.exec(select(Perfil).order_by(Perfil.tipo.desc(), Perfil.nome)).all()
        hoje = date.today()
        return pagina(request, "pautas.html", pautas=lista, perfis=perfis, origem=origem, mes=f"{hoje:%Y-%m}")

    @app.post("/pautas/noticias")
    def pautas_noticias(request: Request):
        with sessao() as s:
            n = pautas.importar_noticias(s, cfg())
            s.commit()
        return ir("/pautas", f"{n} notícias novas.", request)

    @app.post("/pautas/fiscais")
    def pautas_fiscais(request: Request, mes: str = Form(...)):
        ano, m = (int(x) for x in mes.split("-"))
        with sessao() as s:
            n = pautas.importar_fiscais(s, ano, m)
            s.commit()
        return ir("/pautas?origem=fiscal", f"{n} pautas do calendário fiscal de {m:02d}/{ano}.", request)

    @app.post("/pautas/ideia")
    def pautas_ideia(request: Request, titulo: str = Form(...), resumo: str = Form("")):
        with sessao() as s:
            pautas.nova_ideia(s, titulo, resumo)
            s.commit()
        return ir("/pautas?origem=ideia", "Ideia adicionada.", request)

    @app.post("/pautas/{paid}/arquivar")
    def pauta_arquivar(request: Request, paid: int):
        with sessao() as s:
            p = s.get(Pauta, paid)
            p.arquivada = True
            s.add(p)
            s.commit()
        return ir("/pautas", "Pauta arquivada.", request)

    @app.post("/pautas/{paid}/criar")
    def pauta_criar(request: Request, paid: int, perfil_id: int = Form(...), formato: str = Form(...),
                    estilo: str = Form("noticia"), instrucao: str = Form("")):
        if formato not in FORMATOS:
            return ir("/pautas", "Formato inválido.", request)
        with sessao() as s:
            perfil, pauta = s.get(Perfil, perfil_id), s.get(Pauta, paid)
            try:
                c = criar_conteudo(s, perfil, pauta, formato, estilo, instrucao, request.state.usuario.nome)
            except Exception as e:
                return ir("/pautas", f"Falha ao gerar: {e}", request)
            s.commit()
            cid = c.id
        return ir(f"/conteudos/{cid}", "Conteúdo gerado. Revise, ajuste e envie para revisão técnica.", request)

    # ----- conteúdos -----
    @app.get("/conteudos", response_class=HTMLResponse)
    def conteudos_lista(request: Request, status: str = "", perfil: int = 0):
        with sessao() as s:
            q = select(Conteudo).order_by(Conteudo.atualizado_em.desc())
            if status:
                q = q.where(Conteudo.status == status)
            if perfil:
                q = q.where(Conteudo.perfil_id == perfil)
            lista = s.exec(q).all()
            perfis = {p.id: p for p in s.exec(select(Perfil)).all()}
        return pagina(request, "conteudos.html", conteudos=lista, perfis=perfis, status=status, perfil_sel=perfil)

    def _carregar(s, cid: int):
        c = s.get(Conteudo, cid)
        return c, (s.get(Perfil, c.perfil_id) if c else None)

    @app.get("/conteudos/{cid}", response_class=HTMLResponse)
    def conteudo_ver(request: Request, cid: int):
        with sessao() as s:
            c, perfil = _carregar(s, cid)
            if not c:
                return ir("/conteudos", "Conteúdo não encontrado.", request)
            pauta = s.get(Pauta, c.pauta_id) if c.pauta_id else None
            eventos = s.exec(select(Evento).where(Evento.conteudo_id == cid).order_by(Evento.quando.desc())).all()
            outros = s.exec(select(Perfil).where(Perfil.id != c.perfil_id)).all()
        dados = c.j("dados")
        link_cliente = whatsapp = ""
        if fluxo.token_valido(c):
            link_cliente = f"{str(request.base_url).rstrip('/')}/c/{c.token_cliente}"
            numero = "".join(ch for ch in perfil.whatsapp if ch.isdigit())
            texto = quote(f"Olá! Segue o conteúdo \"{dados.get('titulo', '')}\" para sua aprovação: {link_cliente}")
            whatsapp = f"https://wa.me/{numero}?text={texto}" if numero else f"https://wa.me/?text={texto}"
        return pagina(
            request, "conteudo.html", c=c, perfil=perfil, pauta=pauta, dados=dados, nota=c.j("nota"), alertas=c.j("alertas"),
            arquivos=c.j("arquivos"), publicacao_info=c.j("publicacao"), eventos=eventos, outros_perfis=outros,
            slides_txt=texto_de_slides(dados.get("slides", [])), editavel=c.status in fluxo.EDITAVEIS,
            legenda=travas.legenda_final(cfg(), perfil, dados), custo=video.estimar(cfg(), dados.get("texto_narrado", "")) if c.formato == "video" else None,
            link_cliente=link_cliente, whatsapp=whatsapp, postiz_ativo=cfg()["studio"]["postiz"]["ativo"],
        )

    @app.post("/conteudos/{cid}/editar")
    def conteudo_editar(request: Request, cid: int, titulo: str = Form(""), gancho: str = Form(""), legenda: str = Form(""),
                        cta: str = Form(""), hashtags: str = Form(""), texto_narrado: str = Form(""), slides: str = Form("")):
        with sessao() as s:
            c, perfil = _carregar(s, cid)
            if c.status not in fluxo.EDITAVEIS:
                return ir(f"/conteudos/{cid}", "Este conteúdo não pode mais ser editado.", request)
            dados = c.j("dados")
            dados.update(titulo=titulo.strip(), gancho=gancho.strip(), legenda=legenda.strip(), cta=cta.strip(),
                         hashtags=[h.strip().lstrip("#") for h in hashtags.replace(",", " ").split() if h.strip()],
                         texto_narrado=" ".join(texto_narrado.split()))
            if c.formato != "video":
                dados["slides"] = slides_de_texto(slides)
            c.guardar("dados", dados)
            c.status = fluxo.RASCUNHO
            c.atualizado_em = agora()
            aplicar_travas(c, perfil)
            atualizar_previa(c, perfil)
            registrar(s, cid, request.state.usuario.nome, "editado")
            s.add(c)
            s.commit()
        return ir(f"/conteudos/{cid}", "Alterações salvas.", request)

    @app.post("/conteudos/{cid}/regenerar")
    def conteudo_regenerar(request: Request, cid: int, instrucao: str = Form("")):
        with sessao() as s:
            c, perfil = _carregar(s, cid)
            if c.status not in fluxo.EDITAVEIS:
                return ir(f"/conteudos/{cid}", "Este conteúdo não pode mais ser editado.", request)
            pauta = s.get(Pauta, c.pauta_id)
            extra = instrucao or ("Ajuste pedido pelo cliente: " + c.comentario_cliente if c.comentario_cliente else "")
            try:
                gerado = ia.gerar(perfil, pauta, c.formato, c.estilo, extra)
            except Exception as e:
                return ir(f"/conteudos/{cid}", f"Falha ao gerar: {e}", request)
            c.guardar("dados", gerado.model_dump())
            c.status, c.atualizado_em = fluxo.RASCUNHO, agora()
            aplicar_travas(c, perfil)
            avaliar(c, perfil)
            atualizar_previa(c, perfil)
            registrar(s, cid, request.state.usuario.nome, "regenerado", instrucao[:200])
            s.add(c)
            s.commit()
        return ir(f"/conteudos/{cid}", "Nova versão gerada.", request)

    @app.post("/conteudos/{cid}/reavaliar")
    def conteudo_reavaliar(request: Request, cid: int):
        with sessao() as s:
            c, perfil = _carregar(s, cid)
            try:
                avaliar(c, perfil)
            except Exception as e:
                return ir(f"/conteudos/{cid}", f"Falha ao avaliar: {e}", request)
            s.add(c)
            s.commit()
        return ir(f"/conteudos/{cid}", "Nota atualizada.", request)

    @app.post("/conteudos/{cid}/data")
    def conteudo_data(request: Request, cid: int, quando: str = Form("")):
        with sessao() as s:
            c, _ = _carregar(s, cid)
            c.agendado_para = datetime.fromisoformat(quando) if quando else None
            s.add(c)
            registrar(s, cid, request.state.usuario.nome, "data planejada", quando)
            s.commit()
        return ir(f"/conteudos/{cid}", "Data planejada salva.", request)

    @app.post("/conteudos/{cid}/acao/{acao}")
    def conteudo_acao(request: Request, cid: int, acao: str, background: BackgroundTasks):
        u = request.state.usuario
        with sessao() as s:
            c, perfil = _carregar(s, cid)
            try:
                if acao == "enviar_revisao":
                    fluxo.enviar_revisao(c)
                elif acao == "aprovar_tecnico":
                    fluxo.aprovar_tecnico(c, perfil, u.nome, u.crc, cfg()["studio"]["link_cliente_dias"])
                elif acao == "voltar_rascunho":
                    fluxo.voltar_rascunho(c)
                elif acao == "produzir":
                    fluxo.iniciar_producao(c, perfil)
                    background.add_task(produzir, cid, u.nome)
                elif acao == "publicado":
                    fluxo.marcar_publicado(c)
                else:
                    return ir(f"/conteudos/{cid}", "Ação desconhecida.", request)
            except fluxo.FluxoInvalido as e:
                return ir(f"/conteudos/{cid}", str(e), request)
            c.atualizado_em = agora()
            registrar(s, cid, u.nome, acao.replace("_", " "))
            s.add(c)
            s.commit()
        return ir(f"/conteudos/{cid}", f"Status: {fluxo.ROTULOS[c.status]}.", request)

    @app.post("/conteudos/{cid}/agendar")
    def conteudo_agendar(request: Request, cid: int):
        with sessao() as s:
            c, perfil = _carregar(s, cid)
            if not cfg()["studio"]["postiz"]["ativo"]:
                return ir(f"/conteudos/{cid}", "Postiz desativado. Baixe o pacote e publique manualmente.", request)
            if not c.agendado_para or c.agendado_para < datetime.now():
                return ir(f"/conteudos/{cid}", "Defina uma data planejada futura antes de agendar.", request)
            try:
                fluxo.agendar(c)
                resp = publicacao.Postiz(cfg()).agendar(cfg(), perfil, c, c.agendado_para)
            except Exception as e:
                return ir(f"/conteudos/{cid}", f"Falha ao agendar: {e}", request)
            c.guardar("publicacao", {"postiz": resp, "quando": c.agendado_para.isoformat()})
            registrar(s, cid, request.state.usuario.nome, "agendado no Postiz", c.agendado_para.isoformat())
            s.add(c)
            s.commit()
        return ir(f"/conteudos/{cid}", "Agendado no Postiz.", request)

    @app.post("/conteudos/{cid}/replicar")
    async def conteudo_replicar(request: Request, cid: int):
        form = await request.form()
        ids = [int(v) for v in form.getlist("perfis")]
        criados = 0
        with sessao() as s:
            c, _ = _carregar(s, cid)
            pauta = s.get(Pauta, c.pauta_id)
            for pid in ids:
                try:
                    criar_conteudo(s, s.get(Perfil, pid), pauta, c.formato, c.estilo, "", request.state.usuario.nome, base=c.j("dados"))
                    criados += 1
                except Exception as e:
                    request.session["msg"] = f"Falha ao replicar: {e}"
            s.commit()
        return ir("/conteudos?status=rascunho", f"{criados} versões criadas para outros perfis.", request)

    @app.get("/conteudos/{cid}/pacote.zip")
    def conteudo_pacote(request: Request, cid: int):
        with sessao() as s:
            c, perfil = _carregar(s, cid)
        if c.status not in (fluxo.PRODUZIDO, fluxo.AGENDADO, fluxo.PUBLICADO):
            return ir(f"/conteudos/{cid}", "O pacote fica disponível depois da produção.", request)
        destino = pasta_studio("conteudos", str(cid)) / f"pacote_{cid}.zip"
        publicacao.pacote(cfg(), perfil, c, destino)
        return FileResponse(destino, filename=destino.name)

    @app.get("/arquivo/{caminho:path}")
    def arquivo(caminho: str):
        alvo = dentro_de_dados(caminho)
        return FileResponse(alvo) if alvo else HTMLResponse("Arquivo não encontrado", 404)

    # ----- aprovação do cliente (sem login) -----
    def _por_token(s, token: str):
        c = s.exec(select(Conteudo).where(Conteudo.token_cliente == token)).first() if token else None
        return (c, s.get(Perfil, c.perfil_id)) if c and fluxo.token_valido(c) else (None, None)

    @app.get("/c/{token}", response_class=HTMLResponse)
    def cliente_ver(request: Request, token: str):
        with sessao() as s:
            c, perfil = _por_token(s, token)
        if not c:
            return pagina(request, "cliente.html", c=None)
        dados = c.j("dados")
        return pagina(request, "cliente.html", c=c, perfil=perfil, dados=dados, arquivos=c.j("arquivos"),
                      legenda=travas.legenda_final(cfg(), perfil, dados), token=token)

    @app.get("/c/{token}/img/{n}")
    def cliente_img(token: str, n: int):
        with sessao() as s:
            c, _ = _por_token(s, token)
        arquivos = c.j("arquivos") if c else []
        alvo = dentro_de_dados(arquivos[n]) if 0 <= n < len(arquivos) else None
        return FileResponse(alvo) if alvo else HTMLResponse("Não encontrado", 404)

    @app.post("/c/{token}/responder")
    def cliente_responder(request: Request, token: str, decisao: str = Form(...), nome: str = Form(...), comentario: str = Form("")):
        with sessao() as s:
            c, _ = _por_token(s, token)
            if not c:
                return pagina(request, "cliente.html", c=None)
            try:
                if decisao == "aprovar":
                    fluxo.cliente_aprova(c)
                else:
                    fluxo.cliente_pede_ajuste(c, comentario)
            except fluxo.FluxoInvalido as e:
                request.session["msg"] = str(e)
                return ir(f"/c/{token}")
            c.atualizado_em = agora()
            registrar(s, c.id, f"cliente: {nome.strip()}", "aprovado pelo cliente" if decisao == "aprovar" else "ajuste solicitado", comentario[:500])
            s.add(c)
            s.commit()
        return pagina(request, "cliente.html", c=None, obrigado=True)

    # ----- calendário -----
    @app.get("/calendario", response_class=HTMLResponse)
    def calendario_mes(request: Request, mes: str = ""):
        hoje = date.today()
        ano, m = (int(x) for x in mes.split("-")) if mes else (hoje.year, hoje.month)
        inicio = date(ano, m, 1)
        fim = date(ano, m, calendar.monthrange(ano, m)[1])
        with sessao() as s:
            conts = [c for c in s.exec(select(Conteudo)).all() if c.agendado_para and inicio <= c.agendado_para.date() <= fim]
            perfis = {p.id: p for p in s.exec(select(Perfil)).all()}
        por_dia: dict[int, dict] = {d: {"conteudos": [], "obrigacoes": []} for d in range(1, fim.day + 1)}
        for c in conts:
            por_dia[c.agendado_para.day]["conteudos"].append(c)
        for o in pautas.obrigacoes_do_mes(ano, m):
            por_dia[o.data.day]["obrigacoes"].append(o)
        semanas = calendar.Calendar(firstweekday=6).monthdayscalendar(ano, m)
        anterior = (inicio - timedelta(days=1)).strftime("%Y-%m")
        seguinte = (fim + timedelta(days=1)).strftime("%Y-%m")
        nomes = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
        return pagina(request, "calendario.html", semanas=semanas, por_dia=por_dia, perfis=perfis, titulo=f"{nomes[m - 1]} de {ano}",
                      anterior=anterior, seguinte=seguinte, hoje=hoje if (hoje.year, hoje.month) == (ano, m) else None)

    # ----- usuários -----
    @app.get("/usuarios", response_class=HTMLResponse)
    def usuarios(request: Request):
        with sessao() as s:
            lista = s.exec(select(Usuario).order_by(Usuario.nome)).all()
        return pagina(request, "usuarios.html", usuarios=lista)

    @app.post("/usuarios")
    def usuario_criar(request: Request, nome: str = Form(...), email: str = Form(...), crc: str = Form(""),
                      papel: str = Form("redator"), senha: str = Form(...)):
        if request.state.usuario.papel != "admin":
            return ir("/usuarios", "Só o administrador cria usuários.", request)
        if len(senha) < 8:
            return ir("/usuarios", "A senha precisa ter pelo menos 8 caracteres.", request)
        with sessao() as s:
            if s.exec(select(Usuario).where(Usuario.email == email.strip().lower())).first():
                return ir("/usuarios", "Já existe usuário com esse e-mail.", request)
            s.add(Usuario(nome=nome.strip(), email=email.strip().lower(), crc=crc.strip(),
                          papel=papel if papel in ("admin", "revisor", "redator") else "redator", senha_hash=hash_senha(senha)))
            s.commit()
        return ir("/usuarios", "Usuário criado.", request)

    return app


def produzir(cid: int, usuario: str) -> None:
    """Roda em segundo plano: imagens (post/carrossel) ou voz + avatar + montagem (vídeo)."""
    with sessao() as s:
        c = s.get(Conteudo, cid)
        perfil = s.get(Perfil, c.perfil_id)
        try:
            if c.formato == "video":
                pasta = pasta_studio("conteudos", str(cid), "video")
                arquivos = video.produzir(cfg(), perfil, c.j("dados"), pasta)
            else:
                destino = pasta_studio("conteudos", str(cid), "final")
                arquivos = []
                for a in c.j("arquivos"):
                    origem = config.DADOS / a
                    shutil.copy2(origem, destino / origem.name)
                    arquivos.append(destino / origem.name)
            c.guardar("arquivos", [rel(a) for a in arquivos])
            c.status = fluxo.PRODUZIDO
            registrar(s, cid, usuario, "produzido")
        except Exception as e:
            c.status, c.erro = fluxo.ERRO, str(e)[:2000]
            registrar(s, cid, usuario, "erro na produção", str(e)[:500])
        c.atualizado_em = agora()
        s.add(c)
        s.commit()


app = criar_app()
