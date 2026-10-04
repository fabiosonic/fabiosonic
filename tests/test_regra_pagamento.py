"""v3.4.4: na Moraes & Oliveira a regra geral passa, uma única vez, a "emitir quando o cliente pagar".
As demais empresas mantêm a regra de cada uma."""

import json

import pytest

from nfse_itaborai import config, financeiro
from test_emissor import ambiente  # noqa: F401  (fixture)
from test_financeiro import base  # noqa: F401  (fixture)


def _versao_anterior():
    arq = config._arquivo()
    salvo = json.loads(arq.read_text(encoding="utf-8"))
    salvo["emissao"].pop("migrado_regra_baixa")
    salvo["emissao"].update(nfse_quando="geracao", nfse_apos_pagamento=False)       # como estava na versão anterior
    arq.write_text(json.dumps(salvo), encoding="utf-8")
    return arq


def test_moraes_passa_a_emitir_no_pagamento_uma_vez(base, monkeypatch):  # noqa: F811
    arq = _versao_anterior()
    monkeypatch.setattr(config, "CNPJ_REGRA_BAIXA", {config._cnpj_da_pasta(arq)})
    assert config._cnpj_da_pasta(arq).isdigit()
    assert financeiro.regra_geral() == "baixa"
    assert json.loads(arq.read_text(encoding="utf-8"))["emissao"]["migrado_regra_baixa"] is True
    config.salvar({"emissao": {"nfse_quando": "geracao", "nfse_apos_pagamento": False}})   # escritório muda pela tela
    assert financeiro.regra_geral() == "geracao" and financeiro.regra_geral() == "geracao"  # a escolha é mantida


@pytest.mark.parametrize("regra", ["geracao", "lancar"])
def test_outras_empresas_mantem_a_regra(base, regra, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "CNPJ_REGRA_BAIXA", {"11222333000181"})        # outra empresa que não esta
    arq = _versao_anterior()
    config.salvar({"emissao": {"nfse_quando": regra}})
    s = json.loads(arq.read_text(encoding="utf-8")); s["emissao"].pop("migrado_regra_baixa"); arq.write_text(json.dumps(s))
    assert financeiro.regra_geral() == regra
