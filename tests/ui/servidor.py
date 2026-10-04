"""Sobe a tela do sistema com dados de exemplo e o simulador do webservice, para a varredura no navegador.

Uso: python tests/ui/servidor.py <pasta_temporaria> <porta>
"""

import os
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RAIZ), str(RAIZ / "tests")]

pasta, porta = Path(sys.argv[1]), int(sys.argv[2])
pasta.mkdir(parents=True, exist_ok=True)
os.environ.update({"ITABORAI_CNPJ": "24875410000144", "ITABORAI_IM": "1034265", "ITABORAI_CHAVE": "chave-de-teste-123",
                   "ITABORAI_PROXIMO_RPS": "3509", "ITABORAI_AMBIENTE": "homologacao",
                   "ITABORAI_CIENTE_IRREVERSIVEL": "NAO", "ITABORAI_PASTA": str(pasta),
                   "NFSE_CHAVE_LOCAL": str(pasta / "chave_local.bin"), "APPDATA": str(pasta / "appdata")})

from nfse_itaborai import cliente, clientes, emissor, tela  # noqa: E402
from test_emissor import Simulador  # noqa: E402

emissor.BASE = pasta
emissor.RAIZ = emissor._Raiz(pasta)
sim = ThreadingHTTPServer(("127.0.0.1", 0), Simulador)
threading.Thread(target=sim.serve_forever, daemon=True).start()
cliente.URL_WEBSERVICE = f"http://127.0.0.1:{sim.server_address[1]}/wsnfse/"
_postar = cliente.postar
cliente.postar = lambda xml, nome, url=None, timeout=60: _postar(xml, nome, url=cliente.URL_WEBSERVICE)

for c in [{"cpf_cnpj": "32396063000103", "razao_social": "RPS CONSULTORIA E SERVICOS DE ENGENHARIA LTDA",
           "endereco": {"logradouro": "AV AVENIDA PRESIDENTE VARGAS", "numero": "435", "bairro": "Centro",
                        "codigo_municipio": "3304557", "cep": "20071904"}},
          {"cpf_cnpj": "35979895000132", "razao_social": "PORTAL RESOLVE ATIVIDADES DE INTERNET LTDA",
           "endereco": {"logradouro": "AV AVENIDA CHURCHILL", "numero": "94", "bairro": "Centro",
                        "codigo_municipio": "3304557", "cep": "20020050"}}]:
    clientes.salvar(c)

srv = ThreadingHTTPServer(("127.0.0.1", porta), tela._Handler)
print("pronto", flush=True)
srv.serve_forever()
