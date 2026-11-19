from datetime import datetime, timedelta

import httpx
import pytest

from moxml.conectores.apisimples import ApiSimplesConector
from moxml.conectores.base import ContextoCaptura, FonteSemDados
from moxml.conectores.sefaz_consulta import DescobertaImpossivel, SefazConsultaConector
from moxml.conectores.sefaz_sae import SefazSaeConector
from moxml.conectores.svrs_portal import CaptchaExigido, SvrsPortalConector
from moxml.fiscal import xmlfiscal as xf
from moxml.sefaz import catalogo
from moxml.sefaz.transporte import (
    ClienteSoap,
    ErroRede,
    LimitadorTaxa,
    LimiteExcedido,
    RespostaInvalida,
)

CNPJ = "99000001000101"


def ctx_para(lab, modelo="65", uf="RJ", cnpj=CNPJ):
    lim = LimitadorTaxa(padrao_por_minuto=1_000_000)
    return ContextoCaptura(
        empresa_id=1, cnpj=cnpj, uf=uf, modelo=modelo,
        cliente_soap=lambda: ClienteSoap(None, transport=lab.transport(), limitador=lim, dormir=lambda _s: None),
        cliente_http=lambda: httpx.Client(transport=lab.transport()))


def test_catalogo_rj_sem_sae_documentado():
    with pytest.raises(catalogo.ServicoIndisponivel, match="SAE"):
        catalogo.servico("NFCeListagemChaves", "RJ", "65", 1)
    assert "svrs" in catalogo.servico("NfeConsultaProtocolo", "RJ", "65", 1).url


def test_descoberta_562_devolve_chave(lab):
    lab.popular(CNPJ, "LOJA", "65", 1, 100, 5, datetime.now() - timedelta(days=1))
    r = list(SefazConsultaConector(max_falhas_consecutivas=3).descobrir_serie(ctx_para(lab), 1, 100))
    achadas = [x.chave for x in r if x.chave]
    assert len(achadas) == 5 and set(achadas) <= set(lab.notas)
    assert [x.cstat for x in r if not x.chave] == ["217", "217", "217"]


def test_descoberta_impossivel_sem_concatenacao(lab):
    lab.concatena_chave = False
    lab.popular(CNPJ, "LOJA", "55", 1, 1, 1, datetime.now())
    with pytest.raises(DescobertaImpossivel):
        SefazConsultaConector().sondar_numero(ctx_para(lab, "55"), 1, 1, datetime.now())


def test_descoberta_contingencia_tpemis_9(lab):
    lab.emissor(CNPJ, "LOJA")
    n = lab.emitir(CNPJ, "65", 1, 50, datetime.now(), tp_emis=9)
    lab.concatena_chave = True
    # cNF candidato '00000000' difere → 562 já devolve a chave, inclusive em contingência
    r = SefazConsultaConector().sondar_numero(ctx_para(lab), 1, 50, datetime.now())
    assert r.chave == n.chave


def test_situacao_cancelada_traz_evento(lab):
    notas = lab.popular(CNPJ, "LOJA", "55", 1, 1, 2, datetime.now(), cancelar={2})
    sit = SefazConsultaConector().consultar_situacao(ctx_para(lab, "55"), notas[1].chave)
    assert sit.situacao == "CANCELADA" and sit.eventos and sit.eventos[0].tp_evento == "110111"
    assert sit.prot_nfe and b"protNFe" in sit.prot_nfe


def test_consumo_indevido_bloqueia(lab):
    lab.popular(CNPJ, "LOJA", "55", 1, 1, 1, datetime.now())
    lab.consumo_indevido = True
    ctx = ctx_para(lab, "55")
    cli = ctx.cliente_soap()
    ctx.cliente_soap = lambda: cli
    con = SefazConsultaConector()
    with pytest.raises(LimiteExcedido):
        con.consultar_situacao(ctx, next(iter(lab.notas)))
    lab.consumo_indevido = False
    with pytest.raises(LimiteExcedido, match="suspensas"):
        con.consultar_situacao(ctx, next(iter(lab.notas)))


def test_portal_download_e_validacao(lab):
    n = lab.popular(CNPJ, "LOJA", "65", 1, 1, 1, datetime.now())[0]
    rec = SvrsPortalConector().recuperar_xml(ctx_para(lab), n.chave)
    d = xf.ler(rec.xml)
    assert d.e_xml_integral and d.chave == n.chave


def test_portal_com_captcha_interrompe(lab):
    n = lab.popular(CNPJ, "LOJA", "65", 1, 1, 1, datetime.now())[0]
    lab.captcha = True
    with pytest.raises(CaptchaExigido):
        SvrsPortalConector().recuperar_xml(ctx_para(lab), n.chave)
    assert not any(c.startswith("POST") for c in lab.chamadas), "não deve enviar formulário com CAPTCHA"


def test_sae_paginacao_milhares(lab):
    lab.limite_sae = 1000
    lab.emissor("99000002000148", "LOJA SP", uf="SP")
    lab.emissores["99000002000148"].uf = "SP"
    base = datetime.now() - timedelta(days=3)
    for i in range(3):
        lab.emitir("99000002000148", "65", 1, i + 1, base + timedelta(minutes=i))
    # milhares de notas (exige paginação por dhEmisUltNfce/cStat 101): chaves sintéticas evitam 2500 assinaturas
    from moxml.fiscal import chave as chv
    from tests.laboratorio.sefaz_fake import NotaLab
    modelo = next(iter(lab.notas.values()))
    for i in range(3, 2500):
        ch = chv.montar_chave("SP", base.year, base.month, "99000002000148", "65", 1, i + 1, 1, f"{i:08d}")
        lab.notas[ch] = NotaLab(ch, "99000002000148", "65", 1, i + 1, base + timedelta(minutes=i),
                                modelo.xml_proc, modelo.xml_nfe, modelo.prot)
    ctx = ctx_para(lab, "65", "SP", "99000002000148")
    ctx.inicio = base - timedelta(minutes=1)
    chaves = {d.chave for d in SefazSaeConector().listar_documentos(ctx)}
    assert len(chaves) == 2500


def test_sae_download_sem_protnfe(lab):
    lab.emissor("99000002000148", "LOJA SP", uf="SP")
    n = lab.emitir("99000002000148", "65", 1, 1, datetime.now())
    lab.cancelar(n.chave)
    rec = SefazSaeConector().recuperar_xml(ctx_para(lab, "65", "SP", "99000002000148"), n.chave)
    assert xf.ler(rec.xml).tipo == xf.TipoXML.NFE_SEM_PROTOCOLO and rec.protocolo and rec.eventos
    with pytest.raises(FonteSemDados):
        from moxml.fiscal import chave as chv
        inexistente = chv.montar_chave("SP", 2026, 1, "99000002000148", "65", 1, 999, 1, "11111111")
        SefazSaeConector().recuperar_xml(ctx_para(lab, "65", "SP", "99000002000148"), inexistente)


def test_falha_de_rede_com_retentativa(lab):
    n = lab.popular(CNPJ, "LOJA", "55", 1, 1, 1, datetime.now())[0]
    lab.falhas_rede = 2
    sit = SefazConsultaConector().consultar_situacao(ctx_para(lab, "55"), n.chave)
    assert sit.cstat == "100"


def test_timeout_esgota_retentativas(lab):
    n = lab.popular(CNPJ, "LOJA", "55", 1, 1, 1, datetime.now())[0]
    lab.timeouts = 5
    with pytest.raises(ErroRede, match="Timeout"):
        SefazConsultaConector().consultar_situacao(ctx_para(lab, "55"), n.chave)


def test_resposta_invalida(lab):
    n = lab.popular(CNPJ, "LOJA", "55", 1, 1, 1, datetime.now())[0]
    lab.respostas_invalidas = 1
    with pytest.raises(RespostaInvalida):
        SefazConsultaConector().consultar_situacao(ctx_para(lab, "55"), n.chave)


def test_limitador_local():
    t = [0.0]
    lim = LimitadorTaxa(padrao_por_minuto=6, relogio=lambda: t[0], dormir=lambda s: t.__setitem__(0, t[0] + s),
                        espera_maxima=100)
    for _ in range(5):
        lim.adquirir("h")
    assert t[0] > 0, "deve ter aguardado ao exceder a taxa"


def test_apisimples_desligado_por_padrao():
    c = ApiSimplesConector("https://x", lambda _c: None)
    assert c.suporta("RJ", "65").status.value == "NAO_CONFIGURADO"


def test_apisimples_paginacao_e_base64():
    import base64
    xml = b"<nfeProc xmlns='http://www.portalfiscal.inf.br/nfe'/>"

    def h(req: httpx.Request) -> httpx.Response:
        assert req.headers["authorization"] == "Bearer apse_teste"
        if req.url.path.endswith("/xml"):
            return httpx.Response(200, json={"xml": base64.b64encode(xml).decode()})
        pg = int(req.url.params["page"])
        return httpx.Response(200, json={"notas": [{"id": f"id{pg}", "chave": "3" * 44, "data_emissao": "2026-11-10 14:22:01"}],
                                         "tem_mais": pg < 3})
    c = ApiSimplesConector("https://api.exemplo/v1", lambda _c: "apse_teste", ativo=True, transport=httpx.MockTransport(h))
    ctx = ContextoCaptura(empresa_id=1, cnpj=CNPJ, uf="RJ", modelo="55")
    docs = list(c.listar_documentos(ctx))
    assert [d.ref_fonte for d in docs] == ["id1", "id2", "id3"]
    assert c.recuperar_xml(ctx, docs[0].chave, docs[0].ref_fonte).xml == xml


def test_distdfe_por_chave_retorna_xml_completo(lab):
    from moxml.conectores.dist_dfe import DistribuicaoDFeConector
    notas = lab.popular(CNPJ, "LOJA", "55", 1, 1, 2, datetime.now(), cancelar={2})
    rec = DistribuicaoDFeConector().recuperar_xml(ctx_para(lab, "55"), notas[1].chave)
    d = xf.ler(rec.xml)
    assert d.e_xml_integral and d.chave == notas[1].chave and d.assinatura_ok
    assert rec.eventos and b"procEventoNFe" in rec.eventos[0].xml  # cancelamento junto


def test_distdfe_indisponivel_para_nfce(lab):
    from moxml.conectores.dist_dfe import DistribuicaoDFeConector
    assert DistribuicaoDFeConector().suporta("RJ", "65").status.value == "INDISPONIVEL"
    assert DistribuicaoDFeConector().suporta("RJ", "55").status.value == "NAO_COMPROVADO"


def test_distdfe_sem_documento(lab):
    from moxml.conectores.dist_dfe import DistribuicaoDFeConector
    from moxml.conectores.base import FonteSemDados
    from moxml.fiscal import chave as chv
    lab.emissor(CNPJ, "LOJA")
    inexistente = chv.montar_chave("RJ", 2026, 1, CNPJ, "55", 9, 999, 1, "11111111")
    with pytest.raises(FonteSemDados):
        DistribuicaoDFeConector().recuperar_xml(ctx_para(lab, "55"), inexistente)
