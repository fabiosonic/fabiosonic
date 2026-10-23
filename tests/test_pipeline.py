import json
import shutil
from pathlib import Path

import pytest

from avatar_contabil import cli, config, fila, legenda, montagem, travas
from avatar_contabil.modelos import Roteiro


@pytest.fixture(autouse=True)
def dados_temporarios(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DADOS", tmp_path / "data")
    monkeypatch.setenv("DRY_RUN", "1")
    return tmp_path


@pytest.fixture
def cfg():
    return config.carregar()


def _roteiro(**extra) -> Roteiro:
    base = dict(
        titulo="Teste", gancho="Gancho.", corpo="Corpo.", pergunta_final="Pergunta?",
        cta="Chame no WhatsApp.", texto_narrado="Gancho. Corpo. Pergunta?",
        base_legal=[], pontos_a_verificar=[], legenda_post="Legenda", hashtags=["contabilidade"],
    )
    return Roteiro(**{**base, **extra})


def test_travas_bloqueiam_promessa(cfg):
    r = _roteiro(texto_narrado="Com a gente o resultado é garantido e você pode sonegar.")
    alertas = travas.validar_roteiro(cfg, r)
    assert any("garantido" in a for a in alertas)
    assert any("sonegar" in a for a in alertas)


def test_travas_aceitam_texto_sobrio(cfg):
    assert travas.validar_roteiro(cfg, _roteiro()) == []


def test_travas_limitam_tamanho(cfg):
    assert travas.validar_roteiro(cfg, _roteiro(texto_narrado="palavra " * 500))


def test_legenda_final_tem_avisos_e_cta_so_no_instagram(cfg):
    r = _roteiro()
    insta = travas.legenda_final(cfg, r, com_cta=True)
    yt = travas.legenda_final(cfg, r, com_cta=False)
    assert cfg["travas"]["aviso_ia"] in insta and cfg["travas"]["aviso_ia"] in yt
    assert r.cta in insta and r.cta not in yt


def test_limite_diario(cfg):
    cfg["publicacao"]["limite_diario"] = 1
    assert travas.pode_publicar(cfg)
    travas.registrar("a", "youtube", True, "url")
    travas.registrar("a", "instagram", True, "url")  # mesmo vídeo conta uma vez
    assert travas.publicados_hoje() == 1
    assert not travas.pode_publicar(cfg)


def test_eventos_de_legenda_cobrem_a_duracao():
    ev = legenda.eventos_fala("Uma frase curta. Outra frase um pouco maior que a primeira!", 10.0)
    assert ev[0][0] == 0.0
    assert ev[-1][1] == pytest.approx(10.0)
    assert all(len(t.split()) <= 5 for _, _, t in ev)


def test_ass_com_e_sem_cta(tmp_path):
    com = legenda.gerar_ass("Texto narrado.", 8.0, tmp_path / "a.ass", cta="Fale conosco")
    sem = legenda.gerar_ass("Texto narrado.", 8.0, tmp_path / "b.ass")
    assert ",CTA,," in com.read_text()
    assert ",CTA,," not in sem.read_text()


def test_comando_ffmpeg_inclui_musica_e_logo():
    cmd = montagem.comando(avatar="a.mp4", saida="s.mp4", legenda_ass="l.ass", duracao=5, logo="logo.png", musica="m.mp3")
    filtro = cmd[cmd.index("-filter_complex") + 1]
    assert "chromakey" in filtro and "ass=l.ass" in filtro and "amix" in filtro and "[lg]" in filtro


def test_aprovacao_exige_revisor_e_sem_alertas(cfg):
    from avatar_contabil import pauta

    p = pauta.exemplo()[0]
    item = fila.adicionar(p, _roteiro(), 8, "ok", ["termo proibido: 'garantido'"])
    with pytest.raises(ValueError):
        fila.aprovar(item["id"], "Fulano CRC")
    item["alertas_travas"] = []
    fila.salvar(item)
    assert fila.aprovar(item["id"], "Fulano CRC")["status"] == fila.APROVADO
    with pytest.raises(ValueError):
        fila.aprovar(item["id"], "Fulano CRC")


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg não instalado")
def test_pipeline_completo_em_modo_de_teste(capsys):
    cli.main(["pautas"])
    itens = fila.listar(fila.PENDENTE)
    assert len(itens) == 2
    cli.main(["aprovar", itens[0]["id"], "--revisor", "Teste CRC"])
    cli.main(["produzir"])
    item = fila.carregar(itens[0]["id"])
    assert item["status"] == fila.PRODUZIDO
    for arq in item["arquivos"].values():
        assert Path(arq).stat().st_size > 10_000
    cli.main(["publicar"])  # DRY_RUN: não publica
    assert fila.carregar(itens[0]["id"])["status"] == fila.PRODUZIDO
    # a segunda pauta continua aguardando revisão
    assert fila.carregar(itens[1]["id"])["status"] == fila.PENDENTE
