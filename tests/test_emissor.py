import base64
import hashlib
import json
import re
import threading
import xml.etree.ElementTree as ET
from datetime import date, datetime
from decimal import Decimal
from email.parser import BytesParser
from email.policy import default as politica
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from nfse_itaborai import cliente, emissor
from nfse_itaborai.modelos import Prestador, Retencoes
from nfse_itaborai.validacao import ErroValidacao, validar
from nfse_itaborai.xml_rps import (chave_seguranca_cancelamento, chave_seguranca_envio,
                                   formatar_item_lista, gerar_cancelamento, gerar_envio)

EXEMPLO = Path(__file__).resolve().parent.parent / "exemplos" / "rps_exemplo.json"
CHAVE = "chave-de-teste-123"
PRESTADOR = Prestador(cnpj="24875410000144", inscricao_municipal="1034265", chave_webservice=CHAVE)
AGORA = datetime(2026, 10, 1, 9, 30, 15)


def rps_exemplo(**alteracoes):
    d = json.loads(EXEMPLO.read_text(encoding="utf-8"))
    d.update(alteracoes)
    r = emissor.rps_de_dict(d)
    r.numero = r.numero or "3400"
    r.data_emissao = AGORA
    return r


def filhos(no):
    return [c.tag for c in no]


# ------------------------------------------------------------------ XML

def test_estrutura_e_ordem_identicas_ao_provedor_cta():
    raiz = ET.fromstring(gerar_envio(PRESTADOR, [rps_exemplo()], lote="7", producao=False, agora=AGORA))
    assert raiz.tag == "RpsNfse" and raiz.get("versao") == "2.00" and raiz.get("Id") == "7"
    assert filhos(raiz) == ["ChaveSeguranca", "Producao", "Prestador", "ListaRps"]
    assert filhos(raiz.find("Prestador")) == ["DataEmissao", "Cnpj", "InscricaoEstadual", "InscricaoMunicipal",
                                              "OptanteSimplesNacional", "IncentivoFiscalImunidade"]
    rps = raiz.find("ListaRps/Rps")
    assert filhos(rps) == ["IdentificacaoRps", "Servico1", "Servico2", "Servico3", "Servico4", "Servico5",
                           "Valores", "Informacoes", "InformacoesIBSCBS", "ValoresRetencoes", "Observacoes",
                           "Tomador", "Endereco"]
    assert filhos(rps.find("InformacoesIBSCBS")) == ["IndicadorOperacao", "ClassificacaoTributaria"]
    assert filhos(rps.find("IdentificacaoRps")) == ["Numero", "DataDeEmissao", "Competencia", "LocalDaPrestacao",
                                                    "LocalDoRecolhimento", "CodigoDaObra", "TipoDeTributacao"]
    # Correção ACBR-9690 (29/09/2026): NBS e desdobro antes do CNAE
    assert filhos(rps.find("Informacoes")) == ["IssRetido", "ResponsavelRecolhimento", "ItemListaServico",
                                               "CodigoNbs", "CodigoLsnDesdobro", "ClassificacaoCNAE",
                                               "CodigoTributacaoMunicipio"]
    assert filhos(rps.find("Valores")) == ["ValorTotalDosServicos", "ValorDeducoes", "DescontoIncondicionado",
                                           "DescontoCondicionado", "BaseDeCalculoDoISS", "Aliquota", "ValorIss",
                                           "ValorLiquidoNota", "CargaTributariaTotal", "ValorCargaTributariaTotal"]
    assert filhos(rps.find("ValoresRetencoes")) == ["AliquotaPIS", "ValorPIS", "AliquotaCOFINS", "ValorCOFINS",
                                                    "AliquotaCSLL", "ValorCSLL", "BaseCalculoINSS", "AliquotaINSS",
                                                    "ValorINSS", "AliquotaIR", "ValorIR"]
    assert filhos(rps.find("Tomador")) == ["Tipo", "CpfCnpj", "InscricaoMunicipal", "InscricaoEstadual", "RazaoSocial"]
    assert len(rps.find("Endereco")) == 11


def test_conteudo_dos_campos():
    raiz = ET.fromstring(gerar_envio(PRESTADOR, [rps_exemplo()], lote="1", producao=False, agora=AGORA))
    assert raiz.findtext("Producao") == "1"
    assert raiz.findtext("Prestador/DataEmissao") == "2026-10-01T09:30:15"
    assert raiz.findtext("Prestador/OptanteSimplesNacional") == "1"
    r = raiz.find("ListaRps/Rps")
    assert r.findtext("IdentificacaoRps/Numero") == "3400"
    assert r.findtext("IdentificacaoRps/Competencia") == "10-2026"
    assert r.findtext("IdentificacaoRps/LocalDoRecolhimento") == "3301900"
    assert r.findtext("IdentificacaoRps/TipoDeTributacao") == "4"
    assert r.findtext("Servico1/ValorTotalDoItem") == "1000.00"
    assert r.findtext("Servico2/QuantidadeDoItem") == "0"
    assert r.findtext("Valores/Aliquota") == "0.00"   # Simples sem retenção: ISS vai no DAS
    assert r.findtext("Valores/ValorIss") == "0.00"
    assert r.findtext("Valores/ValorLiquidoNota") == "1000.00"
    assert r.findtext("Valores/CargaTributariaTotal") == "18.20"
    assert r.findtext("Informacoes/ItemListaServico") == "17.19"
    assert r.findtext("Informacoes/CodigoNbs") == "113022100"
    assert r.findtext("Informacoes/CodigoLsnDesdobro") == "17.19.01"   # como na NFS-e 3385 aceita
    assert r.findtext("Informacoes/ResponsavelRecolhimento") == "2"
    assert r.findtext("InformacoesIBSCBS/IndicadorOperacao") == "100301"
    assert r.findtext("InformacoesIBSCBS/ClassificacaoTributaria") == "200052"
    assert r.findtext("Informacoes/ClassificacaoCNAE") == "6920601"
    assert r.findtext("Tomador/Tipo") == "1"
    assert r.findtext("Tomador/InscricaoMunicipal") == "0"
    assert r.findtext("Endereco/CodigoPais") == "1058"


def test_producao_e_acentos_e_escape():
    rps = rps_exemplo(observacoes="Serviço de contabilidade & assessoria <mensal>")
    xml = gerar_envio(PRESTADOR, [rps], lote="1", producao=True, agora=AGORA)
    raiz = ET.fromstring(xml)
    assert raiz.findtext("Producao") == "2"
    assert raiz.findtext("ListaRps/Rps/Observacoes") == "Servico de contabilidade & assessoria <mensal>"
    xml.encode("ascii")  # tudo ASCII


def test_chave_seguranca():
    dt = "2026-10-01T09:30:15"
    esperado = base64.b64encode(hashlib.sha256(f"24875410000144{CHAVE}{dt}".encode()).hexdigest().encode()).decode()
    assert chave_seguranca_envio("24875410000144", CHAVE, dt) == esperado
    raiz = ET.fromstring(gerar_envio(PRESTADOR, [rps_exemplo()], lote="1", producao=False, agora=AGORA))
    assert raiz.findtext("ChaveSeguranca") == esperado
    canc = chave_seguranca_cancelamento("24875410000144", CHAVE, dt)
    assert base64.b64decode(canc) == hashlib.sha1(f"24875410000144{CHAVE}{dt}".encode()).digest()


def test_cancelamento_xml():
    raiz = ET.fromstring(gerar_cancelamento(PRESTADOR, "202600099003740", "Valor informado incorretamente",
                                            producao=False, agora=AGORA))
    assert raiz.tag == "CancelaNfse" and raiz.get("Id") == "202600099003740"
    assert filhos(raiz) == ["ChaveSeguranca", "Producao", "Prestador", "Nfse"]
    assert raiz.findtext("Nfse/IdentificacaoNfse/Numero") == "202600099003740"


@pytest.mark.parametrize("entrada,saida", [("1719", "17.19"), ("17.19", "17.19"), ("701", "07.01"),
                                           ("7.01", "07.01")])
def test_formatar_item(entrada, saida):
    assert formatar_item_lista(entrada) == saida


def test_retencoes_reduzem_liquido():
    rps = rps_exemplo(iss_retido="1", aliquota_iss="2.00")
    assert rps.responsavel == "1"
    rps.retencoes = Retencoes(valor_pis=Decimal("6.50"), valor_cofins=Decimal("30.00"), valor_csll=Decimal("10.00"),
                              valor_ir=Decimal("15.00"))
    assert rps.valor_liquido == Decimal("918.50")  # 1000 - 61.50 - ISS 20


# ------------------------------------------------------------------ validações

def _erros(rps):
    with pytest.raises(ErroValidacao) as e:
        validar(rps)
    return " ".join(e.value.erros)


def test_exemplo_valido():
    assert validar(rps_exemplo()) == []


def test_nbs_e_desdobro_obrigatorios():
    assert "NBS" in _erros(rps_exemplo(codigo_nbs=""))
    assert "desdobro" in _erros(rps_exemplo(codigo_desdobro=""))
    assert "não pertence" in _erros(rps_exemplo(codigo_desdobro="070201"))


def test_obra_obrigatoria_14_14():
    rps = rps_exemplo(item_lista_servico="14.14", codigo_desdobro="141403")
    assert "obra" in _erros(rps)
    rps.codigo_obra = "000123"
    validar(rps)
    rps.data_emissao = datetime(2026, 5, 31)
    rps.codigo_obra = ""
    validar(rps)  # antes de 01/06/2026 não exigia


def test_limites_do_layout():
    assert "190" in _erros(rps_exemplo(itens=[{"descricao": "X" * 191, "valor_unitario": 10}]))
    validar(rps_exemplo(itens=[{"descricao": "X" * 190, "valor_unitario": 10}]))
    assert "máximo 5" in _erros(rps_exemplo(itens=[{"descricao": "A", "valor_unitario": 1}] * 6))
    assert "alíquota efetiva" in _erros(rps_exemplo(iss_retido="1"))
    rps = rps_exemplo()
    rps.tomador.endereco.numero = "1234567"
    assert "numero" in _erros(rps)


def test_ibs_cbs_obrigatorio_desde_junho_2026():
    assert "IBS/CBS" in _erros(rps_exemplo(indicador_operacao="", classificacao_tributaria=""))
    rps = rps_exemplo(indicador_operacao="", classificacao_tributaria="")
    rps.data_emissao = datetime(2026, 5, 31)
    validar(rps)
    xml = gerar_envio(PRESTADOR, [rps], lote="1", producao=False, agora=AGORA)
    assert "InformacoesIBSCBS" not in xml


def test_alerta_pis_cofins():
    rps = rps_exemplo()
    rps.retencoes = Retencoes(valor_pis=Decimal("6.50"))
    assert any("005" in a for a in validar(rps))


# ------------------------------------------------------------------ webservice simulado

class Simulador(BaseHTTPRequestHandler):
    recebidos: list = []
    modo = "sucesso"
    esperado = None

    def do_POST(self):  # noqa: N802
        corpo = self.rfile.read(int(self.headers["Content-Length"]))
        msg = BytesParser(policy=politica).parsebytes(
            b"Content-Type: " + self.headers["Content-Type"].encode() + b"\r\n\r\n" + corpo)
        parte = next(msg.iter_parts())
        xml = parte.get_payload(decode=True).decode("cp1252")
        Simulador.recebidos.append((parte.get_filename(), xml))
        raiz = ET.fromstring(xml)
        dt = raiz.findtext("Prestador/DataEmissao")
        cnpj = raiz.findtext("Prestador/Cnpj")
        if raiz.tag == "CancelaNfse":
            ok = raiz.findtext("ChaveSeguranca") == chave_seguranca_cancelamento(cnpj, CHAVE, dt)
            resp = ("<retorno><numero_nfse>%s</numero_nfse><situacao_codigo_nfse>2</situacao_codigo_nfse>"
                    "<situacao_descricao_nfse>Cancelada</situacao_descricao_nfse></retorno>"
                    % raiz.findtext("Nfse/IdentificacaoNfse/Numero")) if ok else "Chave de seguranca invalida"
        elif raiz.findtext("ChaveSeguranca") != chave_seguranca_envio(cnpj, CHAVE, dt):
            resp = "Chave de seguranca invalida"
        elif Simulador.esperado and raiz.findtext("ListaRps/Rps/IdentificacaoRps/Numero") != str(Simulador.esperado):
            resp = ("<a><mensagem>ERRO em xml_ListaRps_Rps_IdentificacaoRps_Numero | Lote RPS j\u00e1 informado ou "
                    "N\u00famero do lote inv\u00e1lido! Este Lote possui o n\u00famero [%s] mas deveria ser [%s];"
                    "</mensagem></a>" % (raiz.findtext("ListaRps/Rps/IdentificacaoRps/Numero"), Simulador.esperado))
        elif Simulador.modo == "erro":
            resp = ("<?xml version='1.0'?><a><Rps><NumeroRPS>%s</NumeroRPS><EstadoDoRPS>Rejeitado</EstadoDoRPS>"
                    "<ListadeErros>Codigo NBS nao corresponde ao item 17.19</ListadeErros></Rps></a>"
                    % raiz.findtext("ListaRps/Rps/IdentificacaoRps/Numero"))
        else:
            num = raiz.findtext("ListaRps/Rps/IdentificacaoRps/Numero")
            resp = ("<?xml version='1.0' encoding='UTF-8'?><Retorno><Nfse><IdentificacaoRps><Numero>%s</Numero>"
                    "</IdentificacaoRps><NumeroNFSe>202600099009999</NumeroNFSe>"
                    "<DataEmissaoNFSe>2026-10-01</DataEmissaoNFSe><CodigoVerificacao>ABC123</CodigoVerificacao>"
                    "<LinkNFSe>https://prefeituradeitaborai.online/nota.php?a=1&amp;b=2</LinkNFSe></Nfse></Retorno>"
                    % num)
        dados = resp.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/xml; charset=utf-8")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def log_message(self, *a):
        pass


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Simulador)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(emissor, "RAIZ", tmp_path)
    for k, v in {"ITABORAI_CNPJ": "24.875.410/0001-44", "ITABORAI_IM": "1034265", "ITABORAI_CHAVE": CHAVE,
                 "ITABORAI_PROXIMO_RPS": "3400", "ITABORAI_AMBIENTE": "homologacao",
                 "ITABORAI_CIENTE_IRREVERSIVEL": "NAO"}.items():
        monkeypatch.setenv(k, v)
    Simulador.recebidos = []
    Simulador.modo = "sucesso"
    Simulador.esperado = None
    yield f"http://127.0.0.1:{srv.server_address[1]}/wsnfse/", tmp_path
    srv.shutdown()


def test_homologacao_nao_consome_rps(ambiente):
    url, pasta = ambiente
    resp = emissor.emitir(emissor.rps_de_dict(json.loads(EXEMPLO.read_text(encoding="utf-8"))), url=url)
    assert resp.sucesso
    seq = json.loads((pasta / "dados" / "sequencia.json").read_text())
    assert seq == {"proximo_rps": 3400, "proximo_lote": 2}


def test_emissao_ponta_a_ponta(ambiente, monkeypatch):
    url, pasta = ambiente
    monkeypatch.setenv("ITABORAI_AMBIENTE", "producao")
    monkeypatch.setenv("ITABORAI_CIENTE_IRREVERSIVEL", "SIM")
    rps = emissor.rps_de_dict(json.loads(EXEMPLO.read_text(encoding="utf-8")))
    resp = emissor.emitir(rps, producao=True, url=url)
    assert resp.sucesso, resp.erros
    assert resp.notas[0].numero_nfse == "202600099009999"
    assert resp.notas[0].numero_rps == "3400"
    assert resp.notas[0].link.endswith("a=1&b=2")
    nome, xml = Simulador.recebidos[0]
    assert nome == "1-env-lot.xml" and "<Producao>2</Producao>" in xml
    assert (Path(resp.pasta) / "NFSe_202600099009999.xml").exists()
    seq = json.loads((pasta / "dados" / "sequencia.json").read_text())
    assert seq == {"proximo_rps": 3401, "proximo_lote": 2}
    # próximo RPS sai numerado automaticamente
    resp2 = emissor.emitir(emissor.rps_de_dict(json.loads(EXEMPLO.read_text(encoding="utf-8"))), producao=True, url=url)
    assert resp2.notas[0].numero_rps == "3401"


def test_rejeicao_nao_consome_numero_do_rps(ambiente):
    url, pasta = ambiente
    Simulador.modo = "erro"
    resp = emissor.emitir(emissor.rps_de_dict(json.loads(EXEMPLO.read_text(encoding="utf-8"))), url=url)
    assert not resp.sucesso
    assert any("NBS" in e for e in resp.erros)
    seq = json.loads((pasta / "dados" / "sequencia.json").read_text())
    assert seq == {"proximo_rps": 3400, "proximo_lote": 2}


def test_chave_errada_retorna_texto(ambiente, monkeypatch):
    url, _ = ambiente
    monkeypatch.setenv("ITABORAI_CHAVE", "outra")
    resp = emissor.emitir(emissor.rps_de_dict(json.loads(EXEMPLO.read_text(encoding="utf-8"))), url=url)
    assert not resp.sucesso and resp.erros == ["Chave de seguranca invalida"]


def test_producao_bloqueada_sem_ciencia(ambiente):
    url, _ = ambiente
    rps = emissor.rps_de_dict(json.loads(EXEMPLO.read_text(encoding="utf-8")))
    with pytest.raises(emissor.ErroConfiguracao):
        emissor.emitir(rps, producao=True, url=url)
    assert Simulador.recebidos == []


def test_producao_liberada(ambiente, monkeypatch):
    url, _ = ambiente
    monkeypatch.setenv("ITABORAI_AMBIENTE", "producao")
    monkeypatch.setenv("ITABORAI_CIENTE_IRREVERSIVEL", "SIM")
    resp = emissor.emitir(emissor.rps_de_dict(json.loads(EXEMPLO.read_text(encoding="utf-8"))),
                          producao=True, url=url)
    assert resp.sucesso and "<Producao>2</Producao>" in Simulador.recebidos[0][1]


def test_cancelamento_ponta_a_ponta(ambiente):
    url, _ = ambiente
    resp = emissor.cancelar("202600099003740", "Valor informado incorretamente", url=url)
    assert resp.sucesso, resp.erros
    assert resp.situacao == "Cancelada"
    assert Simulador.recebidos[0][0] == "202600099003740-ped-can.xml"


def test_tela_conferir(ambiente):
    from nfse_itaborai.tela import tratar
    r = tratar("conferir", json.loads(EXEMPLO.read_text(encoding="utf-8")))
    assert r["sucesso"] and "<RpsNfse" in r["xml"]
    r = tratar("conferir", json.loads(EXEMPLO.read_text(encoding="utf-8")) | {"codigo_nbs": ""})
    assert not r["sucesso"] and any("NBS" in e for e in r["erros"])


def test_resposta_escapada_em_envelope():
    interno = "<Retorno><Nfse><NumeroNFSe>55</NumeroNFSe><CodigoVerificacao>X</CodigoVerificacao></Nfse></Retorno>"
    env = "<string>" + interno.replace("<", "&lt;").replace(">", "&gt;") + "</string>"
    resp = cliente.interpretar_emissao("", 200, env)
    assert resp.sucesso and resp.notas[0].numero_nfse == "55"


# ------------------------------------------------------------------ XSD oficial e retorno real

def test_xml_valido_no_xsd_oficial():
    from nfse_itaborai.xsd import disponivel, validar_xsd
    if not disponivel():
        pytest.skip("lxml não instalado")
    rps = rps_exemplo(itens=[{"descricao": "HONORARIOS", "quantidade": 2, "valor_unitario": "350.50"},
                             {"descricao": "ABERTURA DE EMPRESA", "valor_unitario": "800"}],
                      iss_retido="1", aliquota_iss="2.01", observacoes="Teste & <acentuação>")
    rps.retencoes = Retencoes(valor_ir=Decimal("15.00"), aliquota_ir=Decimal("1.50"))
    rps.codigo_obra = "123"
    assert validar_xsd(gerar_envio(PRESTADOR, [rps], lote="12", producao=True, agora=AGORA))
    sem_tomador = rps_exemplo()
    sem_tomador.tomador.cpf_cnpj = ""
    sem_tomador.tomador.razao_social = ""
    assert validar_xsd(gerar_envio(PRESTADOR, [sem_tomador], lote="1", producao=False, agora=AGORA))


def test_xsd_acusa_erro():
    from nfse_itaborai.xsd import disponivel, validar_xsd
    if not disponivel():
        pytest.skip("lxml não instalado")
    xml = gerar_envio(PRESTADOR, [rps_exemplo()], lote="1", producao=False, agora=AGORA)
    with pytest.raises(ErroValidacao) as e:
        validar_xsd(xml.replace("<ItemListaServico>17.19<", "<ItemListaServico>17.19.01<"))
    assert "ItemListaServico" in e.value.erros[0]


def test_le_retorno_real_do_webservice():
    real = (Path(__file__).parent / "dados" / "retorno_nfse_real.xml").read_text(encoding="utf-8")
    resp = cliente.interpretar_emissao("", 200, real)
    assert resp.sucesso, resp.erros
    n = resp.notas[0]
    assert n.numero_nfse == "99003740"
    assert n.numero_rps == "3385"
    assert n.codigo_verificacao == "6feec6225bc4a78ca1f4524208bf477a"
    assert n.link.startswith("https://prefeituradeitaborai.online/2via_online.php?sid=")


def test_corrige_numero_do_rps_informado_pela_prefeitura(ambiente, monkeypatch):
    """Resposta real de 30/09/2026: 'Este Lote possui o número [3481] mas deveria ser [3509]'."""
    url, pasta = ambiente
    monkeypatch.setenv("ITABORAI_PROXIMO_RPS", "3481")
    monkeypatch.setenv("ITABORAI_AMBIENTE", "producao")
    monkeypatch.setenv("ITABORAI_CIENTE_IRREVERSIVEL", "SIM")
    Simulador.esperado = 3509
    resp = emissor.emitir(emissor.rps_de_dict(json.loads(EXEMPLO.read_text(encoding="utf-8"))),
                          producao=True, url=url)
    assert resp.sucesso, resp.erros
    assert resp.notas[0].numero_rps == "3509"
    assert "3509" in resp.alertas[0]
    assert [ET.fromstring(x).findtext("ListaRps/Rps/IdentificacaoRps/Numero") for _, x in Simulador.recebidos] \
        == ["3481", "3509"]
    assert json.loads((pasta / "dados" / "sequencia.json").read_text())["proximo_rps"] == 3510


def test_numero_manual_nao_e_alterado(ambiente):
    url, _ = ambiente
    Simulador.esperado = 3509
    d = json.loads(EXEMPLO.read_text(encoding="utf-8")) | {"numero": "3481"}
    resp = emissor.emitir(emissor.rps_de_dict(d), url=url)
    assert not resp.sucesso and len(Simulador.recebidos) == 1
    assert emissor.rps_esperado(resp.erros) == 3509


def test_env_atualizado_prevalece_sobre_controle_local(ambiente, monkeypatch):
    url, pasta = ambiente
    (pasta / "dados").mkdir()
    (pasta / "dados" / "sequencia.json").write_text('{"proximo_rps": 3481, "proximo_lote": 5}')
    monkeypatch.setenv("ITABORAI_PROXIMO_RPS", "3509")
    assert emissor._ler_sequencia() == {"proximo_rps": 3509, "proximo_lote": 5}
