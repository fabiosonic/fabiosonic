"""Integração / ponta a ponta do motor de captura no laboratório (sem rede real)."""

import os
import time
import zipfile
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from moxml import servicos
from moxml.db.modelos import (
    ChaveConhecida,
    Documento,
    Empresa,
    Evento,
    Execucao,
    Lacuna,
)
from moxml.motor.orquestrador import Opcoes, Orquestrador
from tests.laboratorio import gerador

from .conftest import CNPJ, RAZAO


def contar(app, modelo, filtro=None):
    with app.sessoes() as s:
        q = select(func.count()).select_from(modelo)
        if filtro is not None:
            q = q.where(filtro)
        return s.scalar(q)


def semente(app, empresa, nota):
    servicos.importar_semente_bytes(app, empresa.id, nota.xml_proc)


def test_nenhuma_nota_sem_serie(app, empresa):
    Orquestrador(app).executar(Opcoes(paralelismo=1))
    with app.sessoes() as s:
        ex = s.scalars(select(Execucao)).all()
    assert {e.status for e in ex} == {"PARCIAL"}
    assert all("SEM_SERIE_CADASTRADA" in e.detalhes["pendencias"] for e in ex)
    assert contar(app, Documento) == 0


def test_uma_nota_alem_da_semente(app, empresa, lab, base):
    notas = lab.popular(CNPJ, RAZAO, "55", 1, 10, 2, base)
    semente(app, empresa, notas[0])
    Orquestrador(app).executar(Opcoes(modelos=("55",), paralelismo=1))
    assert contar(app, Documento) == 2
    with app.sessoes() as s:
        d = s.scalar(select(Documento).where(Documento.numero == 11))
    assert d.origem == "svrs_portal_download" and d.tipo_xml == "NFE_AUTORIZADA" and d.modo == "TESTE"
    assert (app.cfg.pasta_xml / d.caminho_xml).exists()
    assert "/NFE_SAIDA/" in d.caminho_xml and d.caminho_xml.startswith("1-CLIENTES/CLIENTES ATIVOS/")


def test_nfe_e_nfce_independentes_e_cancelamento(app, empresa, lab, base):
    n65 = lab.popular(CNPJ, RAZAO, "65", 2, 1, 10, base, cancelar={4})
    n55 = lab.popular(CNPJ, RAZAO, "55", 1, 1, 3, base)
    semente(app, empresa, n65[0])
    semente(app, empresa, n55[0])
    Orquestrador(app).executar(Opcoes(paralelismo=1))
    assert contar(app, Documento, Documento.modelo == "65") == 10
    assert contar(app, Documento, Documento.modelo == "55") == 3
    assert contar(app, Documento, Documento.situacao == "CANCELADA") == 1
    assert contar(app, Evento, Evento.tipo_evento == "110111") == 1


def test_duplicidade_e_reexecucao_idempotente(app, empresa, lab, base):
    notas = lab.popular(CNPJ, RAZAO, "65", 1, 1, 5, base)
    semente(app, empresa, notas[0])
    orq = Orquestrador(app)
    orq.executar(Opcoes(modelos=("65",), paralelismo=1))
    arquivos_antes = sorted(p for p in app.cfg.pasta_xml.rglob("*.xml"))
    orq.executar(Opcoes(modelos=("65",), paralelismo=1))
    assert contar(app, Documento) == 5
    assert sorted(p for p in app.cfg.pasta_xml.rglob("*.xml")) == arquivos_antes
    # mesmo XML importado de novo é reconhecido como duplicado
    from moxml.motor.repositorio import Repositorio
    with app.sessoes() as s:
        r = Repositorio(s, app.armazenamento, app.modo).registrar_xml(notas[2].xml_proc, "teste", s.get(Empresa, empresa.id))
    assert r.resultado == "DUPLICADO"


def test_evento_posterior_capturado_na_reverificacao(app, empresa, lab, base):
    notas = lab.popular(CNPJ, RAZAO, "55", 1, 1, 3, base)
    semente(app, empresa, notas[0])
    orq = Orquestrador(app)
    orq.executar(Opcoes(modelos=("55",), paralelismo=1))
    lab.cancelar(notas[1].chave)  # cancelamento ocorre depois da captura
    lab.carta_correcao(notas[2].chave)
    with app.sessoes() as s:  # simula passagem do tempo de reverificação
        for d in s.scalars(select(Documento)):
            d.situacao_verificada_em = datetime.now(UTC) - timedelta(days=2)
        s.commit()
    orq.executar(Opcoes(modelos=("55",), paralelismo=1))
    with app.sessoes() as s:
        assert s.scalar(select(Documento.situacao).where(Documento.chave == notas[1].chave)) == "CANCELADA"
    assert contar(app, Evento, Evento.tipo_evento == "110110") == 1


def test_lacunas_classificadas_sem_presumir_omissao(app, empresa, lab, base):
    notas = lab.popular(CNPJ, RAZAO, "65", 1, 1001, 5, base, pular={1003})
    semente(app, empresa, notas[0])
    from moxml.motor.repositorio import Repositorio
    with app.sessoes() as s:  # inutilização homologada cobrindo 1010-1011 + nota 1012 existente
        Repositorio(s, app.armazenamento, app.modo).registrar_xml(
            gerador.gerar_inutilizacao(CNPJ, "RJ", "65", 1, 1010, 1011, base.year), "teste", s.get(Empresa, empresa.id))
        s.commit()
    lab.emitir(CNPJ, "65", 1, 1012, base + timedelta(hours=8))
    Orquestrador(app).executar(Opcoes(modelos=("65",), paralelismo=1))
    with app.sessoes() as s:
        lac = {lc.numero: lc.classificacao for lc in s.scalars(select(Lacuna))}
    assert lac[1003] == "NAO_CONSTA_NA_SEFAZ"
    assert lac[1010] == lac[1011] == "INUTILIZADA"
    assert all(v != "XML_PERDIDO" for v in lac.values())


def test_isolamento_de_falhas_entre_empresas(app, empresa, lab, base):
    outra = servicos.cadastrar_empresa(app, "OUTRA LTDA", "99000002000148")
    n1 = lab.popular(CNPJ, RAZAO, "55", 1, 1, 3, base)
    n2 = lab.popular("99000002000148", "OUTRA LTDA", "55", 1, 1, 3, base)
    semente(app, empresa, n1[0])
    semente(app, outra, n2[0])
    orq = Orquestrador(app)
    original = orq._processar

    def quebra(s, emp, modelo, ex, op):
        if emp.cnpj == CNPJ:
            raise RuntimeError("falha simulada nesta empresa")
        return original(s, emp, modelo, ex, op)
    orq._processar = quebra
    orq.executar(Opcoes(modelos=("55",), paralelismo=2))
    with app.sessoes() as s:
        st = {e.empresa_id: e.status for e in s.scalars(select(Execucao))}
    assert st[empresa.id] == "ERRO" and st[outra.id] == "SUCESSO"
    assert contar(app, Documento, Documento.empresa_id == outra.id) == 3


def test_reinicio_durante_captura_retoma_sem_perda(app, empresa, lab, base):
    notas = lab.popular(CNPJ, RAZAO, "65", 1, 1, 12, base)
    semente(app, empresa, notas[0])
    orig = lab._tratar
    cont = {"n": 0}

    def cai_no_meio(req):
        cont["n"] += 1
        if cont["n"] == 6:
            raise KeyboardInterrupt  # "queda" do processo no meio da descoberta
        return orig(req)
    lab._tratar = cai_no_meio
    orq = Orquestrador(app)
    try:
        orq.executar(Opcoes(modelos=("65",), paralelismo=1))
    except KeyboardInterrupt:
        pass
    with app.sessoes() as s:
        Orquestrador.marcar_interrompidas(s)
        parcial = s.scalar(select(func.count()).select_from(ChaveConhecida))
        assert s.scalar(select(Execucao.status)) == "INTERROMPIDA"
    assert 0 < parcial < 12
    lab._tratar = orig
    orq.executar(Opcoes(modelos=("65",), paralelismo=1))
    assert contar(app, Documento) == 12


def test_sem_fonte_de_xml_integral_mantem_pendente(app, empresa, lab, base):
    notas = lab.popular(CNPJ, RAZAO, "65", 1, 1, 3, base)
    semente(app, empresa, notas[0])
    lab.captcha = True  # portal passa a exigir CAPTCHA
    Orquestrador(app).executar(Opcoes(modelos=("65",), paralelismo=1))
    with app.sessoes() as s:
        pend = s.scalars(select(ChaveConhecida).where(ChaveConhecida.status != "RECUPERADA")).all()
        ex = s.scalar(select(Execucao))
    assert len(pend) == 2 and all(p.status == "SEM_FONTE" for p in pend)
    assert any("CAPTCHA" in p for p in ex.detalhes["pendencias"])
    assert contar(app, Documento) == 1  # só a semente; nada é inventado


def test_modo_real_recusa_transporte_de_teste(app, empresa, lab, base):
    notas = lab.popular(CNPJ, RAZAO, "55", 1, 1, 2, base)
    semente(app, empresa, notas[0])
    app.modo = "REAL"  # produção: o laboratório injetado não pode ser usado
    import pytest
    with pytest.raises(RuntimeError, match="somente com fontes reais"):
        app.cliente_soap(CNPJ, None)
    assert lab.chamadas == []


def test_modo_real_sem_certificado_nao_consulta(app, empresa, lab, base):
    app.modo = "REAL"
    app.transporte_soap = lambda _c: None
    Orquestrador(app).executar(Opcoes(paralelismo=1))
    with app.sessoes() as s:
        assert all("CERTIFICADO_AUSENTE" in e.detalhes["pendencias"] for e in s.scalars(select(Execucao)))
    assert lab.chamadas == []


def test_pasta_emissor_incremental_incompleto_zip(app, empresa, lab, base, tmp_path):
    notas = lab.popular(CNPJ, RAZAO, "65", 1, 1, 4, base)
    pasta = tmp_path / "pdv"
    pasta.mkdir()
    antigo = time.time() - 3600
    for n in notas[:2]:
        p = pasta / f"{n.chave}.xml"
        p.write_bytes(n.xml_proc)
        os.utime(p, (antigo, antigo))
    with zipfile.ZipFile(pasta / "lote.zip", "w") as z:
        z.writestr(f"{notas[2].chave}.xml", notas[2].xml_proc)
    os.utime(pasta / "lote.zip", (antigo, antigo))
    (pasta / "gravando.xml").write_bytes(notas[3].xml_proc[:200])  # recém-modificado e truncado
    (pasta / "lixo.xml").write_bytes(b"<x/>")
    os.utime(pasta / "lixo.xml", (antigo, antigo))
    orq = Orquestrador(app)
    r1 = orq.importar_pastas(caminho_unico=str(pasta), empresa_id=empresa.id)
    assert r1["novos"] == 3 and r1["incompletos"] == 1 and r1["rejeitados"] == 1
    r2 = orq.importar_pastas(caminho_unico=str(pasta), empresa_id=empresa.id)
    assert r2["novos"] == 0  # incremental
    assert contar(app, Documento) == 3


def test_xml_de_outro_cnpj_rejeitado(app, empresa, lab, base):
    lab.popular("99000002000148", "OUTRA", "55", 1, 1, 1, base)
    from moxml.motor.repositorio import Repositorio
    with app.sessoes() as s:
        r = Repositorio(s, app.armazenamento, app.modo).registrar_xml(
            next(iter(lab.notas.values())).xml_proc, "teste", s.get(Empresa, empresa.id))
    assert r.resultado == "REJEITADO" and "incompatível" in r.mensagem


def test_chaves_manuais_validadas(app, empresa, lab, base):
    n = lab.popular(CNPJ, RAZAO, "55", 1, 1, 1, base)[0]
    r = servicos.adicionar_chaves(app, empresa.id, [n.chave, "123", n.chave[:-1] + str((int(n.chave[-1]) + 1) % 10)])
    assert r["aceitas"] == 1 and len(r["rejeitadas"]) == 2
    Orquestrador(app).executar(Opcoes(modelos=("55",), paralelismo=1))
    assert contar(app, ChaveConhecida, ChaveConhecida.status == "RECUPERADA") == 1
