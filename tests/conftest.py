from datetime import date

import pytest

from portal_contabil.fabrica import gerar_cnpj
from portal_contabil.importadores import Importador

EMPRESA = gerar_cnpj("123456780001")
CLIENTE = gerar_cnpj("987654320001")
FORNECEDOR = gerar_cnpj("555666770001")
E = (EMPRESA, "Empresa Auditada Ltda", "SP")
C = (CLIENTE, "Cliente Alfa SA", "SP")
F = (FORNECEDOR, "Fornecedor Beta Ltda", "SP")
D = date(2026, 3, 10)


def lote_de(*arquivos):
    """arquivos: (nome, conteudo str|bytes)."""
    imp = Importador()
    for nome, conteudo in arquivos:
        imp.importar_bytes(nome, conteudo.encode() if isinstance(conteudo, str) else conteudo)
    return imp.finalizar()


def codigos(res):
    return {a.codigo for a in res.achados}


@pytest.fixture
def venda():
    return [{"ncm": "84713012", "cfop": "5102", "valor": "1000.00"}]
