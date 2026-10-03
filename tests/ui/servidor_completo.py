"""Sistema completo em MODO DE TESTE para o teste funcional de ponta a ponta (tests/ui/funcional.js).

Nada sai do computador: a prefeitura de Itaboraí, o Sefin/ADN Nacional, a API do Banco Inter (com TLS mútuo) e o
servidor de e-mail são simulados localmente. Uso: python tests/ui/servidor_completo.py <pasta_temporaria> <porta>
"""

import json
import os
import ssl
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RAIZ), str(RAIZ / "tests")]

pasta, porta = Path(sys.argv[1]), int(sys.argv[2])
(pasta / "dados" / "certificados").mkdir(parents=True, exist_ok=True)
(pasta / ".env").write_text("ITABORAI_CNPJ=24875410000144\nITABORAI_IM=1034265\nITABORAI_CHAVE=chave-de-teste-123\n"
                            "ITABORAI_PROXIMO_RPS=3509\nITABORAI_AMBIENTE=homologacao\nITABORAI_CIENTE_IRREVERSIVEL=NAO\n",
                            encoding="utf-8")
os.environ.update({"ITABORAI_PASTA": str(pasta), "NFSE_CHAVE_LOCAL": str(pasta / "chave_local.bin")})

from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.serialization import pkcs12  # noqa: E402

from nfse_itaborai import cliente, clientes, cobranca, config, emissor, nacional, tela  # noqa: E402
from test_boletos import FakeInter, FakeSMTP  # noqa: E402
from test_emissor import Simulador  # noqa: E402
from test_nacional import CNPJ, Sefin, _certificado, _pem  # noqa: E402

emissor.BASE = pasta
emissor.RAIZ = emissor._Raiz(pasta)
cert = pasta / "dados" / "certificados"


def _tls(cliente_pem: Path, nome: str) -> ssl.SSLContext:
    sk, sc = _certificado("127.0.0.1", ip=True)
    (cert / nome).write_bytes(_pem(sk, sc))
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert / nome)
    ctx.verify_mode = ssl.CERT_REQUIRED
    ctx.load_verify_locations(cliente_pem)
    return ctx


def _servir(handler, ctx=None) -> int:
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    if ctx:
        srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv.server_address[1]


# ---- prefeitura de Itaboraí (webservice simulado)
p_ita = _servir(Simulador)
cliente.URL_WEBSERVICE = f"http://127.0.0.1:{p_ita}/wsnfse/"
_postar = cliente.postar
cliente.postar = lambda xml, nome, url=None, timeout=60: _postar(xml, nome, url=cliente.URL_WEBSERVICE)

# ---- Sefin / ADN Nacional (mTLS com o certificado A1 da empresa)
ck, cc = _certificado(f"MORAES E OLIVEIRA CONTABILIDADE LTDA:{CNPJ}")
(cert / "cert.pfx").write_bytes(pkcs12.serialize_key_and_certificates(
    b"a1", ck, cc, None, serialization.BestAvailableEncryption(b"senha123")))
(cert / "a1.pem").write_bytes(cc.public_bytes(serialization.Encoding.PEM))


class SefinADN(Sefin):
    def do_GET(self):  # noqa: N802 — parâmetros do convênio do município (Testar certificado)
        self._responder(200, {"parametrosConvenio": {"tipoConvenio": 2, "aderenteAmbienteNacional": 1}})


p_sef = _servir(SefinADN, _tls(cert / "a1.pem", "sefin_srv.pem"))
srv_pem = str(cert / "sefin_srv.pem")
nacional.URLS = {k: (f"https://127.0.0.1:{p_sef}/SefinNacional", f"https://127.0.0.1:{p_sef}/adn") for k in (True, False)}
_ctx = nacional._contexto_ssl


def _contexto(c):
    ctx = _ctx(c)
    ctx.load_verify_locations(srv_pem)
    return ctx


nacional._contexto_ssl = _contexto

# ---- Banco Inter (API de cobrança e extrato, mTLS)
ik, ic = _certificado("MORAES OLIVEIRA:24875410000144")
(cert / "inter.crt").write_bytes(ic.public_bytes(serialization.Encoding.PEM))
(cert / "inter.key").write_bytes(ik.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
                                                  serialization.NoEncryption()))
p_inter = _servir(FakeInter, _tls(cert / "inter.crt", "inter_srv.pem"))
FakeInter.transacoes = [{"idTransacao": "t1", "dataTransacao": "2026-10-01", "tipoOperacao": "D", "valor": "89.90",
                         "titulo": "Pagamento", "descricao": "TARIFA PACOTE DE SERVICOS"}]

# ---- InfinitePay (cartão de crédito)
from test_cartao import FakeInfinitePay  # noqa: E402

p_infinite = _servir(FakeInfinitePay)

# ---- WhatsApp (API oficial da Meta)
from test_whatsapp import FakeMeta  # noqa: E402

p_meta = _servir(FakeMeta)

# ---- WhatsApp Web do escritório (envio automático; QR Code simulado)
from test_whatsapp_web import FakeWhatsAppWeb, _navegador  # noqa: E402

p_waweb = _servir(FakeWhatsAppWeb)

# ---- e-mail (SMTP simulado: guarda as mensagens em dados/emails_enviados.json)
caixa = pasta / "dados" / "emails_enviados.json"


class SMTPTeste(FakeSMTP):
    def send_message(self, msg):
        super().send_message(msg)
        caixa.write_text(json.dumps([{"para": m["To"], "assunto": m["Subject"]} for m in FakeSMTP.enviados],
                                    ensure_ascii=False), encoding="utf-8")
        # cópia completa (texto, HTML e anexos) para conferir o modelo dos e-mails
        import base64
        partes = {"para": msg["To"], "de": msg["From"], "assunto": msg["Subject"], "texto": "", "html": "", "anexos": []}
        for parte in msg.walk():
            tipo = parte.get_content_type()
            if parte.get_filename():
                partes["anexos"].append({"nome": parte.get_filename(), "tipo": tipo,
                                         "b64": base64.b64encode(parte.get_payload(decode=True)).decode()})
            elif tipo == "text/plain" and not partes["texto"]:
                partes["texto"] = parte.get_content()
            elif tipo == "text/html":
                partes["html"] = parte.get_content()
        completo = pasta / "dados" / "emails_completos.json"
        lst = json.loads(completo.read_text(encoding="utf-8")) if completo.exists() else []
        completo.write_text(json.dumps(lst + [partes], ensure_ascii=False), encoding="utf-8")


cobranca.smtplib.SMTP = SMTPTeste
cobranca.smtplib.SMTP_SSL = SMTPTeste

config.salvar({
    "empresa": {"nome": "MORAES & OLIVEIRA CONTABILIDADE", "pix_chave": "24.875.410/0001-44"},
    "smtp": {"host": "smtp.teste", "porta": 587, "usuario": "financeiro@moraes.teste", "senha": "senha-smtp",
             "remetente": "MORAES"},
    "resumo": {"email_dono": "dono@moraes.teste"},
    "cobranca": {"provedor": "inter", "inter_client_id": "cli", "inter_client_secret": "segredo",
                 "inter_certificado": "dados/certificados/inter.crt", "inter_chave": "dados/certificados/inter.key",
                 "inter_url": f"https://127.0.0.1:{p_inter}", "inter_ca": str(cert / "inter_srv.pem"), "inter_sandbox": True,
                 "whatsapp_api": False, "whatsapp_token": "EAAG-teste", "whatsapp_phone_id": "123456",
                 "whatsapp_api_url": f"http://127.0.0.1:{p_meta}",
                 "whatsapp_web_url": f"http://127.0.0.1:{p_waweb}", "whatsapp_web_navegador": _navegador(),
                 "whatsapp_web_intervalo": 0,
                 "cartao_provedor": "infinitepay", "cartao_infinitepay_tag": "moraes_contab",
                 "cartao_infinitepay_url": f"http://127.0.0.1:{p_infinite}"},
    "emissao": {"certificado_pfx": "dados/certificados/cert.pfx", "certificado_senha": "senha123"},
    "automacao": {"ativa": False},
})
for c in [{"cpf_cnpj": "32396063000103", "razao_social": "RPS CONSULTORIA E SERVICOS DE ENGENHARIA LTDA",
           "email": "fin@rps.teste", "telefone": "21988887777",
           "endereco": {"tipo_logradouro": "AV", "logradouro": "PRESIDENTE VARGAS", "numero": "435", "bairro": "Centro",
                        "codigo_municipio": "3304557", "cep": "20071904", "uf": "RJ"}},
          {"cpf_cnpj": "35979895000132", "razao_social": "PORTAL RESOLVE ATIVIDADES DE INTERNET LTDA",
           "email": "contato@portal.teste",
           "endereco": {"tipo_logradouro": "AV", "logradouro": "CHURCHILL", "numero": "94", "bairro": "Centro",
                        "codigo_municipio": "3304557", "cep": "20020050", "uf": "RJ"}}]:
    clientes.salvar(c)

tela.ROTAS["teste/infinitepay_pagar"] = lambda c: (FakeInfinitePay.pagos.__setitem__(
    (c["order_nsu"], c["transaction_nsu"], c["slug"]), int(c["valor"])), {"ok": True})[1]
tela.ROTAS["teste/whatsapp_enviados"] = lambda c: {"enviados": FakeMeta.enviados}
tela.ROTAS["teste/whatsapp_web_logar"] = lambda c: (setattr(FakeWhatsAppWeb, "logado", True), {"ok": True})[1]
tela.ROTAS["teste/whatsapp_web_enviados"] = lambda c: {"enviados": FakeWhatsAppWeb.enviados}
srv = ThreadingHTTPServer(("127.0.0.1", porta), tela._Handler)
print("pronto", flush=True)
srv.serve_forever()
