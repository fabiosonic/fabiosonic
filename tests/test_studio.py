import re
import shutil
import zipfile
from io import BytesIO

import pytest
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
    assert _status(cid) == fluxo.APROVADO
    assert "Link indisponível" in anonimo.get(f"/c/{token}").text  # link de uso único

    cliente.post(f"/conteudos/{cid}/acao/produzir")  # TestClient roda a tarefa de fundo
    assert _status(cid) == fluxo.PRODUZIDO
    z = zipfile.ZipFile(BytesIO(cliente.get(f"/conteudos/{cid}/pacote.zip").content))
    assert "legenda.txt" in z.namelist() and any(n.endswith(".png") for n in z.namelist())
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
    assert _status(cid) == fluxo.APROVADO


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
def test_video_exige_consentimento_e_produz(cliente):
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
