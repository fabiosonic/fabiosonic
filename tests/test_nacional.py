"""Canal NFS-e Nacional: DPS no leiaute v1.01, assinatura XMLDSig, mTLS e Sefin simulado."""

import base64
import gzip
import ipaddress
import json
import re
import ssl
import threading
from datetime import datetime, timedelta
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from lxml import etree

from nfse_itaborai import clientes, config, emissor, financeiro, lote, nacional
from nfse_itaborai.modelos import Endereco, ItemServico, Rps, Tomador
from nfse_itaborai.tela import tratar

CNPJ = "24875410000144"
NS = {"n": nacional.NS}
CLIENTE = {"cpf_cnpj": "32.396.063/0001-03", "razao_social": "RPS CONSULTORIA E SERVICOS DE ENGENHARIA LTDA",
           "email": "financeiro@rps.com.br", "telefone": "(21) 99999-8888",
           "endereco": {"logradouro": "AV PRESIDENTE VARGAS", "numero": "435", "bairro": "Centro",
                        "codigo_municipio": "3304557", "cep": "20071904", "uf": "RJ"}}


def _certificado(cn: str, ip: bool = False):
    chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    b = (x509.CertificateBuilder().subject_name(nome).issuer_name(nome).public_key(chave.public_key())
         .serial_number(x509.random_serial_number()).not_valid_before(datetime(2025, 1, 1))
         .not_valid_after(datetime.now() + timedelta(days=365)))
    if ip:
        b = b.add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), False)
    return chave, b.sign(chave, hashes.SHA256())


def _pem(chave, cert) -> bytes:
    return (chave.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption()) + cert.public_bytes(serialization.Encoding.PEM))


class Sefin(BaseHTTPRequestHandler):
    recebidos: list = []
    modo = "sucesso"
    cliente_cert = None

    def log_message(self, *a):
        pass

    def _responder(self, status: int, corpo: dict):
        dados = json.dumps(corpo).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def do_POST(self):
        Sefin.cliente_cert = self.connection.getpeercert(binary_form=True)
        corpo = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path.endswith("/eventos"):
            xml = gzip.decompress(base64.b64decode(corpo["pedidoRegistroEventoXmlGZipB64"])).decode()
            Sefin.recebidos.append(("evento", self.path, xml))
            evento = f'<evento xmlns="{nacional.NS}"><infEvento>ok</infEvento></evento>'
            return self._responder(201, {"eventoXmlGZipB64": base64.b64encode(gzip.compress(evento.encode())).decode()})
        xml = gzip.decompress(base64.b64decode(corpo["dpsXmlGZipB64"])).decode()
        Sefin.recebidos.append(("dps", self.path, xml))
        if not nacional.verificar_assinatura(xml):
            return self._responder(400, {"erros": [{"Codigo": "E0001", "Descricao": "Assinatura inválida"}]})
        n = etree.fromstring(xml.encode()).findtext(".//n:nDPS", namespaces=NS)
        if Sefin.modo == "erro":
            return self._responder(400, {"erros": [{"Codigo": "E0312", "Descricao": "Código de tributação nacional "
                                                    "inexistente", "Complemento": "cTribNac"}]})
        if Sefin.modo == "duplicada" and len([r for r in Sefin.recebidos if r[0] == "dps"]) == 1:
            return self._responder(400, {"erros": [{"codigo": "E0014", "descricao": "DPS já existente"}]})
        chave = f"33019002{CNPJ}" + n.zfill(28)
        nfse = (f'<NFSe xmlns="{nacional.NS}" versao="1.01"><infNFSe Id="NFS{chave}"><nNFSe>{n}</nNFSe>'
                "</infNFSe></NFSe>")
        self._responder(201, {"tipoAmbiente": 2, "versaoAplicativo": "SefinNacional_1.5", "idDps": f"DPS{n}",
                              "chaveAcesso": chave, "dataHoraProcessamento": "2026-10-02T10:00:00-03:00",
                              "nfseXmlGZipB64": base64.b64encode(gzip.compress(nfse.encode())).decode(),
                              "alertas": [{"Codigo": "A0001", "Descricao": "Aviso de teste"}]})


@pytest.fixture
def sefin(tmp_path, monkeypatch):
    monkeypatch.setattr(emissor, "RAIZ", tmp_path)
    for k, v in {"ITABORAI_CNPJ": CNPJ, "ITABORAI_IM": "1034265", "ITABORAI_CHAVE": "x",
                 "ITABORAI_AMBIENTE": "homologacao", "ITABORAI_CIENTE_IRREVERSIVEL": "NAO"}.items():
        monkeypatch.setenv(k, v)
    # certificado A1 do prestador (.pfx com senha) e certificado do "servidor" Sefin
    ck, cc = _certificado(f"MORAES E OLIVEIRA CONTABILIDADE LTDA:{CNPJ}")
    (tmp_path / "cert.pfx").write_bytes(pkcs12.serialize_key_and_certificates(
        b"a1", ck, cc, None, serialization.BestAvailableEncryption(b"senha123")))
    sk, sc = _certificado("127.0.0.1", ip=True)
    (tmp_path / "srv.pem").write_bytes(_pem(sk, sc))
    (tmp_path / "cli.pem").write_bytes(cc.public_bytes(serialization.Encoding.PEM))
    srv_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    srv_ctx.load_cert_chain(tmp_path / "srv.pem")
    srv_ctx.verify_mode = ssl.CERT_REQUIRED          # autenticação mútua, como no Sefin
    srv_ctx.load_verify_locations(tmp_path / "cli.pem")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Sefin)
    srv.socket = srv_ctx.wrap_socket(srv.socket, server_side=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    original = nacional._contexto_ssl

    def contexto(cert):
        ctx = original(cert)
        ctx.load_verify_locations(tmp_path / "srv.pem")
        return ctx
    monkeypatch.setattr(nacional, "_contexto_ssl", contexto)
    config.salvar({"emissao": {"canal": "nacional", "certificado_pfx": str(tmp_path / "cert.pfx"),
                               "certificado_senha": "senha123"}})
    Sefin.recebidos, Sefin.modo, Sefin.cliente_cert = [], "sucesso", None
    clientes.salvar(CLIENTE)
    yield f"https://127.0.0.1:{srv.server_address[1]}/SefinNacional", tmp_path, cc
    srv.shutdown()


def _rps(**kw):
    d = {"numero": "", "itens": [ItemServico("HONORARIOS CONTABEIS & ASSESSORIA", Decimal("374.40"))],
         "tomador": Tomador("32396063000103", "RPS CONSULTORIA", Endereco("AV PRESIDENTE VARGAS", "435", "Centro",
                                                                          "3304557", "RJ", "20071904")),
         "item_lista_servico": "17.19", "codigo_nbs": "113022100", "codigo_desdobro": "171901", "cnae": "6920601",
         "aliquota_iss": Decimal(0), "indicador_operacao": "100301", "classificacao_tributaria": "200052"}
    return Rps(**(d | kw))


def test_dps_no_leiaute_nacional(sefin):
    xml, numero, _ = nacional.preparar(_rps(observacoes="Competência 09/2026"), producao=False)
    raiz = etree.fromstring(xml.encode())
    inf = raiz.find("n:infDPS", NS)
    assert inf.get("Id") == f"DPS33019002{CNPJ}00900{'1'.zfill(15)}" and len(inf.get("Id")) == 45
    assert [etree.QName(c).localname for c in inf] == ["tpAmb", "dhEmi", "verAplic", "serie", "nDPS", "dCompet",
                                                       "tpEmit", "cLocEmi", "prest", "toma", "serv", "valores",
                                                       "IBSCBS"]
    v = lambda p: raiz.findtext(p, namespaces=NS)  # noqa: E731
    assert v(".//n:tpAmb") == "2" and v(".//n:serie") == "900" and numero == "1"
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d-03:00", v(".//n:dhEmi"))
    assert [v(".//n:regTrib/n:" + t) for t in ("opSimpNac", "regApTribSN", "regEspTrib")] == ["3", "2", "6"]
    assert v(".//n:cTribNac") == "171901" and v(".//n:cNBS") == "113022100"
    assert v(".//n:xDescServ") == "HONORARIOS CONTABEIS & ASSESSORIA"
    assert v(".//n:vServ") == "374.40" and v(".//n:tpRetISSQN") == "1" and raiz.find(".//n:pAliq", NS) is None
    assert v(".//n:toma/n:CNPJ") == "32396063000103" and v(".//n:endNac/n:CEP") == "20071904"
    assert v(".//n:gIBSCBS/n:CST") == "200" and v(".//n:gIBSCBS/n:cClassTrib") == "200052"
    assert v(".//n:xInfComp") == "Competência 09/2026"
    assert raiz.find(".//n:pTotTribSN", NS) is not None


def test_iss_retido_informa_aliquota_e_pf_sem_endereco(sefin):
    rps = _rps(iss_retido="1", aliquota_iss=Decimal("2.00"),
               tomador=Tomador("52998224725", "FULANO DE TAL", Endereco("", "", "", "3301900", "RJ", "24800000")))
    raiz = etree.fromstring(nacional.preparar(rps, producao=False)[0].encode())
    assert raiz.findtext(".//n:tpRetISSQN", namespaces=NS) == "2"
    assert raiz.findtext(".//n:pAliq", namespaces=NS) == "2.00"
    assert raiz.findtext(".//n:toma/n:CPF", namespaces=NS) == "52998224725"
    assert raiz.find(".//n:toma/n:end", NS) is None      # endereço incompleto: omitido (é opcional no leiaute)


def test_numeracoes_municipal_e_nacional_independentes(sefin):
    url, pasta, _ = sefin
    assert lote.emitir_um("32396063000103", "100", producao=False, url=url)["sucesso"]
    emissor._avancar_sequencia("5", None)          # um envio pelo canal municipal regrava o arquivo
    seq = json.loads((pasta / "dados" / "sequencia.json").read_text())
    assert seq["proximo_dps"] == 2 and seq["proximo_lote"] == 6


def test_assinatura_valida_e_detecta_adulteracao(sefin):
    cert = nacional.carregar_certificado()
    xml, _, _ = nacional.preparar(_rps(), producao=False, cert=cert)
    assert nacional.verificar_assinatura(xml)
    assert not nacional.verificar_assinatura(xml.replace("374.40", "1374.40"))
    sig = etree.fromstring(xml.encode())[1]
    assert etree.QName(sig).localname == "Signature" and etree.QName(sig).namespace == nacional.DS
    # canonicalização sem xmlns="" espúrio (defeito do c14n do libxml2 em subárvores)
    assert b'xmlns=""' not in nacional._c14n(sig.find(f"{{{nacional.DS}}}SignedInfo"))


def test_certificado_senha_errada_e_cnpj_diferente(sefin):
    _, pasta, _ = sefin
    config.salvar({"emissao": {"certificado_senha": "errada"}})
    with pytest.raises(nacional.ErroCertificado, match="senha"):
        nacional.carregar_certificado()
    config.salvar({"emissao": {"certificado_senha": "senha123"}})
    info = nacional.info_certificado()
    assert info["cnpj"] == CNPJ and not info["vencido"]
    ck, cc = _certificado("OUTRA EMPRESA:11222333000181")
    (pasta / "outro.pfx").write_bytes(pkcs12.serialize_key_and_certificates(b"x", ck, cc, None,
                                                                            serialization.NoEncryption()))
    config.salvar({"emissao": {"certificado_pfx": str(pasta / "outro.pfx"), "certificado_senha": ""}})
    with pytest.raises(nacional.ErroCertificado, match="CNPJ"):
        nacional.preparar(_rps(), producao=False, cert=nacional.carregar_certificado())


def test_emissao_pelo_canal_nacional_com_mtls(sefin):
    url, pasta, cert_cliente = sefin
    r = lote.emitir_um("32396063000103", "374,40", producao=False, url=url)
    assert r["sucesso"], r
    assert r["canal"] == "nacional" and r["nfse"] == "1" and len(r["chave"]) == 50
    assert r["link"].startswith(nacional.CONSULTA_PUBLICA) and "A0001 - Aviso de teste" in r["alertas"]
    # o servidor recebeu o certificado A1 do prestador no handshake TLS
    assert Sefin.cliente_cert == cert_cliente.public_bytes(serialization.Encoding.DER)
    tipo, caminho, xml = Sefin.recebidos[0]
    assert caminho == "/SefinNacional/nfse" and nacional.verificar_assinatura(xml)
    nacional.validar_xsd(xml)
    assert json.loads((pasta / "dados" / "sequencia.json").read_text())["proximo_dps"] == 2
    assert list(pasta.glob("saida/*/DPS_1/NFSe_*.xml"))
    # a numeração do RPS municipal não é afetada
    assert "proximo_rps" not in json.loads((pasta / "dados" / "sequencia.json").read_text())


def test_rejeicao_mostra_codigo_e_nao_consome_numero(sefin):
    url, pasta, _ = sefin
    Sefin.modo = "erro"
    r = lote.emitir_um("32396063000103", "100", producao=False, url=url)
    assert not r["sucesso"] and r["erros"] == ["E0312 - Código de tributação nacional inexistente - cTribNac"]
    assert not (pasta / "dados" / "sequencia.json").exists()


def test_dps_duplicada_avanca_e_reenvia(sefin):
    url, pasta, _ = sefin
    Sefin.modo = "duplicada"
    r = lote.emitir_um("32396063000103", "100", producao=False, url=url)
    assert r["sucesso"] and r["nfse"] == "2"
    assert "já existia" in r["alertas"][0]
    assert json.loads((pasta / "dados" / "sequencia.json").read_text())["proximo_dps"] == 3


def test_financeiro_guarda_chave_e_cancela_pelo_nacional(sefin, monkeypatch):
    url, pasta, _ = sefin
    monkeypatch.setattr(nacional, "URLS", {True: (url, url), False: (url, url)})
    monkeypatch.setenv("ITABORAI_AMBIENTE", "producao")
    monkeypatch.setenv("ITABORAI_CIENTE_IRREVERSIVEL", "SIM")
    tid = financeiro.criar_titulo("32396063000103", "374,40", "HONORARIOS 09/2026")
    r = financeiro.emitir_nfse_titulo(tid)
    t = financeiro.obter_titulo(tid)
    assert r["sucesso"] and t["nfse_status"] == "emitida" and t["nfse_canal"] == "nacional"
    assert len(t["nfse_chave"]) == 50
    assert etree.fromstring(Sefin.recebidos[0][2].encode()).findtext(".//n:tpAmb", namespaces=NS) == "1"
    c = tratar("titulo/cancelar_nfse", {"id": tid, "justificativa": "Erro no valor da nota emitida"})
    assert c["sucesso"], c
    tipo, caminho, xml = Sefin.recebidos[-1]
    assert tipo == "evento" and caminho == f"/SefinNacional/nfse/{t['nfse_chave']}/eventos"
    nacional.validar_xsd(xml, "pedRegEvento_v1.01.xsd")
    assert nacional.verificar_assinatura(xml)
    inf = etree.fromstring(xml.encode()).find("n:infPedReg", NS)
    assert inf.get("Id") == f"PRE{t['nfse_chave']}101101"
    assert inf.findtext("n:e101101/n:cMotivo", namespaces=NS) == "1"
    assert financeiro.obter_titulo(tid)["status"] == "cancelado"
    assert list(pasta.glob("saida/*/CANCELAMENTO_*/evento_registrado.xml"))


def test_canal_municipal_continua_padrao(tmp_path, monkeypatch):
    monkeypatch.setattr(emissor, "RAIZ", tmp_path)
    assert nacional.canal() == "municipal"
    pub = config.publico(config.salvar({"emissao": {"certificado_senha": "x"}}))
    assert pub["emissao"]["certificado_senha"] == "••••••"


def test_sem_certificado_mensagem_clara(tmp_path, monkeypatch):
    monkeypatch.setattr(emissor, "RAIZ", tmp_path)
    config.salvar({"emissao": {"canal": "nacional"}})
    with pytest.raises(nacional.ErroCertificado, match="certificado A1"):
        nacional.carregar_certificado()
