import re
import shutil
import zipfile
from io import BytesIO

import pytest
import yaml
from fastapi.testclient import TestClient

from avatar_contabil import config
from studio import db, fluxo, ia, pautas, video


@pytest.fixture(autouse=True)
def dados_temporarios(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DADOS", tmp_path / "data")
    monkeypatch.setenv("DRY_RUN", "1")
    db.reiniciar_engine()
    yield
    db.reiniciar_engine()


@pytest.fixture
def ajustar_config(tmp_path, monkeypatch):
    """Grava uma cópia do config.yaml com as alterações e aponta o Studio para ela."""
    def ajustar(**studio):
        cfg = config.carregar()
        cfg["studio"].update(studio)
        arq = tmp_path / "config_teste.yaml"
        arq.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
        monkeypatch.setenv("AVATAR_CONFIG", str(arq))
    return ajustar


@pytest.fixture
def cliente():
    from studio.app import criar_app

    c = TestClient(criar_app())
    r = c.post("/primeiro-acesso", data={"nome": "Ana Contadora", "email": "ana@ex.com", "crc": "CRC-SP 1/O-1", "senha": "segredo123"})
    assert r.status_code == 200
    return c


def _id(url: str) -> int:
    return int(re.search(r"/(\d+)$", url).group(1))


def _perfil(cliente, tipo="cliente", nome="Padaria Pão Bom") -> int:
    r = cliente.post("/perfis", data={"nome": nome, "tipo": tipo}, follow_redirects=False)
    return _id(r.headers["location"])


def _conteudo(cliente, perfil_id: int, formato: str) -> int:
    cliente.post("/pautas/ideia", data={"titulo": "Prazo do DAS", "resumo": "O DAS vence no dia 20."})
    with db.sessao() as s:
        pauta_id = s.exec(db.select(db.Pauta)).first().id
    r = cliente.post(f"/pautas/{pauta_id}/criar", data={"perfil_id": perfil_id, "formato": formato, "estilo": "checklist"}, follow_redirects=False)
    return _id(r.headers["location"])


def _status(cid: int) -> str:
    with db.sessao() as s:
        return s.get(db.Conteudo, cid).status


def test_exige_login():
    from studio.app import criar_app

    r = TestClient(criar_app()).get("/conteudos", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login"


def test_todas_as_paginas_abrem(cliente):
    pid = _perfil(cliente)
    cid = _conteudo(cliente, pid, "carrossel")
    for url in ["/", "/pautas", "/conteudos", "/calendario", "/calendario?mes=2026-11", "/perfis", f"/perfis/{pid}", f"/conteudos/{cid}", "/usuarios"]:
        assert cliente.get(url).status_code == 200, url


def test_fluxo_carrossel_com_aprovacao_do_cliente(cliente):
    pid = _perfil(cliente)
    cid = _conteudo(cliente, pid, "carrossel")
    with db.sessao() as s:
        c = s.get(db.Conteudo, cid)
        assert c.j("nota")["total"] == 75
        assert len(c.j("arquivos")) == len(c.j("dados")["slides"]) >= 2  # prévias desenhadas

    cliente.post(f"/conteudos/{cid}/acao/enviar_revisao")
    assert _status(cid) == fluxo.REVISAO
    cliente.post(f"/conteudos/{cid}/acao/aprovar_tecnico")
    assert _status(cid) == fluxo.CLIENTE

    pagina = cliente.get(f"/conteudos/{cid}").text
    link = re.search(r'value="(http[^"]+/c/[^"]+)"', pagina).group(1)
    token = link.rsplit("/", 1)[1]
    assert "wa.me" in pagina

    anonimo = TestClient(cliente.app)
    assert "Aprovação de conteúdo" in anonimo.get(f"/c/{token}").text
    assert anonimo.get(f"/c/{token}/img/0").status_code == 200
    assert anonimo.post(f"/c/{token}/responder", data={"decisao": "ajuste", "nome": "Seu Zé", "comentario": ""}).status_code == 200
    assert _status(cid) == fluxo.CLIENTE  # ajuste sem comentário é recusado
    anonimo.post(f"/c/{token}/responder", data={"decisao": "aprovar", "nome": "Seu Zé"})
    assert _status(cid) == fluxo.PRODUZIDO  # aprovado pelo cliente: imagens finais geradas na hora
    assert "Link indisponível" in anonimo.get(f"/c/{token}").text  # link de uso único

    z = zipfile.ZipFile(BytesIO(cliente.get(f"/conteudos/{cid}/pacote.zip").content))
    assert "legenda.txt" in z.namelist() and any(n.endswith(".jpg") for n in z.namelist())
    cliente.post(f"/conteudos/{cid}/acao/publicado")
    assert _status(cid) == fluxo.PUBLICADO


def test_cliente_pede_ajuste_e_volta_para_edicao(cliente):
    pid = _perfil(cliente)
    cid = _conteudo(cliente, pid, "post")
    cliente.post(f"/conteudos/{cid}/acao/enviar_revisao")
    cliente.post(f"/conteudos/{cid}/acao/aprovar_tecnico")
    with db.sessao() as s:
        token = s.get(db.Conteudo, cid).token_cliente
    TestClient(cliente.app).post(f"/c/{token}/responder", data={"decisao": "ajuste", "nome": "Zé", "comentario": "Trocar a cor"})
    assert _status(cid) == fluxo.AJUSTE
    assert "Trocar a cor" in cliente.get(f"/conteudos/{cid}").text
    cliente.post(f"/conteudos/{cid}/acao/produzir")
    assert _status(cid) == fluxo.AJUSTE  # não pula a aprovação


def test_perfil_do_escritorio_pula_cliente(cliente):
    pid = _perfil(cliente, tipo="escritorio", nome="Contabilidade Exemplo")
    cid = _conteudo(cliente, pid, "post")
    cliente.post(f"/conteudos/{cid}/acao/enviar_revisao")
    cliente.post(f"/conteudos/{cid}/acao/aprovar_tecnico")
    assert _status(cid) == fluxo.PRODUZIDO


def test_trava_bloqueia_envio(cliente):
    pid = _perfil(cliente)
    cid = _conteudo(cliente, pid, "post")
    cliente.post(f"/conteudos/{cid}/editar", data={"titulo": "T", "gancho": "Economia garantido para você", "legenda": "x",
                                                    "cta": "", "hashtags": "", "slides": "Capa\nTexto"})
    cliente.post(f"/conteudos/{cid}/acao/enviar_revisao")
    assert _status(cid) == fluxo.RASCUNHO


def test_revisao_exige_crc(cliente):
    cliente.post("/usuarios", data={"nome": "Beto", "email": "beto@ex.com", "crc": "", "papel": "redator", "senha": "segredo123"})
    pid = _perfil(cliente)
    cid = _conteudo(cliente, pid, "post")
    cliente.post(f"/conteudos/{cid}/acao/enviar_revisao")
    beto = TestClient(cliente.app)
    beto.post("/login", data={"email": "beto@ex.com", "senha": "segredo123"})
    beto.post(f"/conteudos/{cid}/acao/aprovar_tecnico")
    assert _status(cid) == fluxo.REVISAO


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg não instalado")
def test_video_exige_consentimento_e_produz(cliente, ajustar_config):
    ajustar_config(formatos=["post", "carrossel", "video"])
    pid = _perfil(cliente, tipo="escritorio", nome="Contabilidade Exemplo")
    cid = _conteudo(cliente, pid, "video")
    assert "Custo estimado" not in cliente.get(f"/conteudos/{cid}").text
    cliente.post(f"/conteudos/{cid}/acao/enviar_revisao")
    cliente.post(f"/conteudos/{cid}/acao/aprovar_tecnico")
    assert "Custo estimado" in cliente.get(f"/conteudos/{cid}").text
    cliente.post(f"/conteudos/{cid}/acao/produzir")
    assert _status(cid) == fluxo.APROVADO  # sem termo, não produz
    cliente.post(f"/perfis/{pid}/consentimento", files={"termo": ("termo.pdf", b"%PDF-1.4 teste", "application/pdf")})
    cliente.post(f"/conteudos/{cid}/acao/produzir")
    assert _status(cid) == fluxo.PRODUZIDO
    with db.sessao() as s:
        arquivos = s.get(db.Conteudo, cid).j("arquivos")
    assert [a.rsplit("/", 1)[1] for a in arquivos] == ["instagram.mp4", "youtube.mp4"]


def test_replicar_para_outros_perfis(cliente):
    a = _perfil(cliente, nome="Cliente A")
    b = _perfil(cliente, nome="Cliente B")
    cid = _conteudo(cliente, a, "carrossel")
    cliente.post(f"/conteudos/{cid}/replicar", data={"perfis": [str(b)]})
    with db.sessao() as s:
        assert {c.perfil_id for c in s.exec(db.select(db.Conteudo)).all()} == {a, b}


def test_calendario_fiscal_e_pautas(cliente):
    obrig = pautas.obrigacoes_do_mes(2026, 2)
    assert all(o.data.month == 2 for o in obrig)
    nomes = {o.nome for o in pautas.obrigacoes_do_mes(2026, 5)}
    assert "DASN-SIMEI (declaração anual do MEI)" in nomes
    cliente.post("/pautas/fiscais", data={"mes": "2026-11"})
    cliente.post("/pautas/fiscais", data={"mes": "2026-11"})  # não duplica
    with db.sessao() as s:
        fiscais = s.exec(db.select(db.Pauta).where(db.Pauta.origem == "fiscal")).all()
    assert len(fiscais) == len(pautas.obrigacoes_do_mes(2026, 11))
    assert "13º salário" in cliente.get("/calendario?mes=2026-11").text


def test_pronuncia_e_custo():
    dic = {"DAS": "dás", "MEI": "mêi", "DASN-SIMEI": "dásse ene simêi"}
    assert video.para_fala("O DAS do MEI e a DASN-SIMEI", dic) == "O dás do mêi e a dásse ene simêi"
    assert video.para_fala("DASHBOARD", dic) == "DASHBOARD"
    est = video.estimar(config.carregar(), "palavra " * 100)
    assert est["segundos"] == 40 and est["usd"] > 0 and est["brl"] > est["usd"]


def test_cores_do_site():
    html = '<meta name="theme-color" content="#123abc"><style>a{color:#FFFFFF}b{color:#ff6600}c{color:#ff6600}</style>'
    assert ia.cores_do_html(html) == ["#123ABC", "#FF6600"]


def test_salvar_perfil_e_legenda_com_crc_e_whatsapp(cliente):
    pid = _perfil(cliente)
    cliente.post(f"/perfis/{pid}", data={"nome": "Padaria Pão Bom", "tipo": "cliente", "whatsapp": "+55 (11) 99999-8888",
                                         "crc_responsavel": "CRC-SP 2SP000000/O-1", "cor_primaria": "#112233",
                                         "postiz_canais": '{"instagram": "abc"}'},
                 files={"logo": ("logo.png", b"", "image/png")})
    with db.sessao() as s:
        p = s.get(db.Perfil, pid)
    assert p.crc_responsavel == "CRC-SP 2SP000000/O-1" and p.cor_primaria == "#112233" and p.canais() == {"instagram": "abc"}
    cid = _conteudo(cliente, pid, "post")
    pagina = cliente.get(f"/conteudos/{cid}").text
    assert "https://wa.me/5511999998888" in pagina and "CRC-SP 2SP000000/O-1" in pagina


def test_formulario_do_perfil_vem_preenchido(cliente):
    pid = _perfil(cliente, nome="Padaria Pão Bom")
    html = cliente.get(f"/perfis/{pid}").text
    assert f'action="/perfis/{pid}"' in html and 'value="Padaria Pão Bom"' in html


def test_rodape_do_slide_preserva_o_crc(tmp_path):
    from PIL import Image, ImageDraw

    from studio import carrossel

    perfil = db.Perfil(nome="Nome muito comprido de uma empresa cliente " * 3, crc_responsavel="CRC-SP 2SP000000/O-1")
    img = Image.new("RGB", (carrossel.LARG, carrossel.ALT))
    textos = []
    draw = ImageDraw.Draw(img)
    original = draw.text
    draw.text = lambda xy, t, **kw: (textos.append(t), original(xy, t, **kw))
    carrossel._rodape(draw, perfil, "#FFFFFF", "1/5")
    assert textos[0].endswith("CRC-SP 2SP000000/O-1") and "…" in textos[0]


# ---------- sem vídeo, piloto automático e Instagram ----------

def _aprovar(cliente, cid):
    cliente.post(f"/conteudos/{cid}/acao/enviar_revisao")
    cliente.post(f"/conteudos/{cid}/acao/aprovar_tecnico")


def test_video_desligado_por_padrao(cliente):
    pid = _perfil(cliente)
    cliente.post("/pautas/ideia", data={"titulo": "Pauta", "resumo": "Fato."})
    html = cliente.get("/pautas").text
    assert "Vídeo com avatar" not in html and "Carrossel" in html
    with db.sessao() as s:
        pauta_id = s.exec(db.select(db.Pauta)).first().id
    cliente.post(f"/pautas/{pauta_id}/criar", data={"perfil_id": pid, "formato": "video", "estilo": "noticia"})
    with db.sessao() as s:
        assert s.exec(db.select(db.Conteudo)).first() is None
    assert "Consentimento do avatar" not in cliente.get(f"/perfis/{pid}").text


def _perfil_automatico(cliente, **extra) -> int:
    pid = _perfil(cliente, tipo="escritorio", nome="Contabilidade Exemplo")
    dados = {"nome": "Contabilidade Exemplo", "tipo": "escritorio", "auto_ativo": "1", "auto_horario": "09:00",
             "auto_antecedencia": "7", "auto_dias": [str(d) for d in range(7)], "auto_formatos": ["carrossel", "post"],
             "ig_user_id": "1784", "ig_token": "tok"}
    dados.update(extra)
    cliente.post(f"/perfis/{pid}", data=dados)
    return pid


def test_piloto_automatico_cria_posts_da_semana_sem_duplicar(cliente):
    from studio import automacao

    pid = _perfil_automatico(cliente)
    with db.sessao() as s:
        p = s.get(db.Perfil, pid)
        assert p.auto_ativo and p.dias_auto() == list(range(7)) and p.instagram_conectado
        for i in range(10):
            s.add(db.Pauta(origem="ideia", titulo=f"Ideia {i}", resumo="Fato da fonte.", chave=f"i{i}"))
        s.commit()
    criados = automacao.gerar_automatico()
    assert criados["Contabilidade Exemplo"] >= 7
    with db.sessao() as s:
        conts = s.exec(db.select(db.Conteudo)).all()
    assert all(c.automatico and c.status == fluxo.REVISAO and c.agendado_para.hour == 9 for c in conts)
    assert len({c.agendado_para.date() for c in conts}) == len(conts)  # um por dia
    assert {c.formato for c in conts} == {"carrossel", "post"}  # alterna formatos
    assert len({c.pauta_id for c in conts}) == len(conts)  # não repete pauta
    assert automacao.gerar_automatico()["Contabilidade Exemplo"] == 0  # rodar de novo não duplica


def test_prioriza_vencimento_fiscal_da_semana():
    from datetime import datetime

    from studio import automacao

    quando = datetime(2026, 11, 16, 9)
    ideia = db.Pauta(id=1, origem="ideia", titulo="Ideia")
    longe = db.Pauta(id=2, origem="fiscal", titulo="13º", data_ref="2026-11-30")
    perto = db.Pauta(id=3, origem="fiscal", titulo="DAS", data_ref="2026-11-20")
    noticia_fraca = db.Pauta(id=4, origem="noticia", titulo="Fofoca")
    escolhida = automacao.escolher_pauta(db.Perfil(nome="x"), quando, [ideia, longe, perto, noticia_fraca], {4: 3}, 7)
    assert escolhida is perto
    assert automacao.escolher_pauta(db.Perfil(nome="x"), quando, [ideia, noticia_fraca], {4: 3}, 7) is ideia


def test_aprovado_vira_agendado_e_publica_no_horario(cliente, ajustar_config, monkeypatch):
    from datetime import timedelta

    from studio import automacao

    ajustar_config(url_publica="https://studio.exemplo.com.br")
    monkeypatch.setenv("DRY_RUN", "0")
    publicados = []

    class InstagramFalso:
        def __init__(self, user_id, token, base):
            assert (user_id, token) == ("1784", "tok")

        def publicar(self, urls, legenda):
            publicados.append((urls, legenda))
            return "midia-123"

    monkeypatch.setattr(automacao, "Instagram", InstagramFalso)
    pid = _perfil_automatico(cliente)
    monkeypatch.setenv("DRY_RUN", "1")  # a IA continua de exemplo
    cid = _conteudo(cliente, pid, "carrossel")
    amanha = (db.agora() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
    cliente.post(f"/conteudos/{cid}/data", data={"quando": amanha})
    _aprovar(cliente, cid)
    assert _status(cid) == fluxo.AGENDADO

    with db.sessao() as s:
        c = s.get(db.Conteudo, cid)
        token, n = c.midia_token, len(c.j("arquivos"))
        assert all(a.endswith(".jpg") for a in c.j("arquivos"))
    r = TestClient(cliente.app).get(f"/m/{token}/0.jpg")  # público: o Instagram baixa sem login
    assert r.status_code == 200 and r.content[:2] == b"\xff\xd8"
    assert TestClient(cliente.app).get(f"/m/{'x' * 32}/0.jpg").status_code == 404

    monkeypatch.setenv("DRY_RUN", "0")
    assert automacao.publicar_vencidos() == 0  # ainda não chegou a hora
    with db.sessao() as s:
        c = s.get(db.Conteudo, cid)
        c.agendado_para = db.agora() - timedelta(minutes=1)
        s.add(c)
        s.commit()
    assert automacao.publicar_vencidos() == 1
    assert _status(cid) == fluxo.PUBLICADO
    urls, legenda = publicados[0]
    assert urls == [f"https://studio.exemplo.com.br/m/{token}/{i}.jpg" for i in range(n)]
    assert "Conteúdo informativo" in legenda


def test_falha_de_publicacao_tenta_tres_vezes(cliente, ajustar_config, monkeypatch):
    from datetime import timedelta

    from studio import automacao

    ajustar_config(url_publica="https://studio.exemplo.com.br")

    class InstagramFora:
        def __init__(self, *a):
            pass

        def publicar(self, urls, legenda):
            raise RuntimeError("token expirado")

    monkeypatch.setattr(automacao, "Instagram", InstagramFora)
    pid = _perfil_automatico(cliente)
    cid = _conteudo(cliente, pid, "post")
    cliente.post(f"/conteudos/{cid}/data", data={"quando": (db.agora() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")})
    _aprovar(cliente, cid)
    with db.sessao() as s:
        c = s.get(db.Conteudo, cid)
        c.agendado_para = db.agora() - timedelta(minutes=1)
        s.add(c)
        s.commit()
    monkeypatch.setenv("DRY_RUN", "0")
    for _ in range(3):
        automacao.publicar_vencidos()
    assert _status(cid) == fluxo.ERRO
    assert "token expirado" in cliente.get(f"/conteudos/{cid}").text


def test_publicar_agora_em_modo_de_teste_e_cancelar_agendamento(cliente):
    from datetime import timedelta

    pid = _perfil_automatico(cliente)
    cid = _conteudo(cliente, pid, "post")
    cliente.post(f"/conteudos/{cid}/data", data={"quando": (db.agora() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M")})
    _aprovar(cliente, cid)
    assert _status(cid) == fluxo.AGENDADO
    cliente.post(f"/conteudos/{cid}/acao/cancelar_agendamento")
    assert _status(cid) == fluxo.PRODUZIDO
    cliente.post(f"/conteudos/{cid}/publicar-instagram")
    assert _status(cid) == fluxo.PUBLICADO


def test_instagram_api_carrossel(monkeypatch):
    from studio import instagram

    chamadas = []

    class Resp:
        def __init__(self, dados):
            self.dados, self.status_code, self.text = dados, 200, ""

        def json(self):
            return self.dados

    def post(url, data, timeout):
        chamadas.append((url.rsplit("/", 1)[-1], data))
        return Resp({"id": f"id{len(chamadas)}"})

    monkeypatch.setattr(instagram.requests, "post", post)
    monkeypatch.setattr(instagram.requests, "get", lambda url, params, timeout: Resp({"status_code": "FINISHED"}))
    ig = instagram.Instagram("1784", "tok", espera=0)
    assert ig.publicar(["https://x/0.jpg", "https://x/1.jpg"], "Legenda #a") == "id4"
    assert [c[0] for c in chamadas] == ["media", "media", "media", "media_publish"]
    assert chamadas[0][1]["is_carousel_item"] == "true"
    assert chamadas[2][1]["media_type"] == "CAROUSEL" and chamadas[2][1]["children"] == "id1,id2"
    assert chamadas[3][1]["creation_id"] == "id3"
    legenda = instagram.ajustar_legenda(" ".join(f"#t{i}" for i in range(40)))
    assert legenda.count("#") == 30


def test_migracao_acrescenta_colunas(tmp_path):
    import sqlite3

    config.DADOS.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(config.DADOS / "studio.db")
    con.execute("create table perfil (id integer primary key, nome varchar not null)")
    con.execute("insert into perfil(nome) values ('Antigo')")
    con.commit()
    con.close()
    db.reiniciar_engine()
    with db.sessao() as s:
        p = s.get(db.Perfil, 1)
    assert p.nome == "Antigo" and p.auto_dias == "0,2,4" and p.auto_antecedencia == 7 and not p.auto_ativo
