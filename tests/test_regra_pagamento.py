"""v3.4.4: a regra geral das configurações já existentes passa, uma única vez, a "emitir quando o cliente pagar"."""

import json

from nfse_itaborai import config, financeiro
from test_emissor import ambiente  # noqa: F401  (fixture)
from test_financeiro import base  # noqa: F401  (fixture)


def test_configuracao_antiga_passa_a_emitir_no_pagamento_uma_vez(base):  # noqa: F811
    arq = config._arquivo()
    salvo = json.loads(arq.read_text(encoding="utf-8"))
    salvo["emissao"].pop("migrado_regra_baixa")
    salvo["emissao"].update(nfse_quando="geracao", nfse_apos_pagamento=False)       # como estava na versão anterior
    arq.write_text(json.dumps(salvo), encoding="utf-8")
    assert financeiro.regra_geral() == "baixa"
    assert json.loads(arq.read_text(encoding="utf-8"))["emissao"]["migrado_regra_baixa"] is True
    config.salvar({"emissao": {"nfse_quando": "geracao", "nfse_apos_pagamento": False}})   # escritório volta pela tela
    assert financeiro.regra_geral() == "geracao" and financeiro.regra_geral() == "geracao"  # a escolha é mantida


def test_configuracao_nova_nao_e_alterada(base):  # noqa: F811
    assert financeiro.regra_geral() == "geracao"
