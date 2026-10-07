"""Revisão 9: guarda de dados pessoais antes da nuvem, folha na vigência da competência, auditoria do
Domínio sem engolir duplicidade/linha sem chave, IGNORADO informativo, .bak único, IRRF fora da faixa."""
from datetime import date
from decimal import Decimal

import pytest

from mo_autonomo.contabil.plano_dominio import escrever_plano
from mo_autonomo.dominio.auditoria import auditar
from mo_autonomo.dp.folha import conferir, irrf_mensal
from mo_autonomo.ia.cascata import _host_local, montar_cascata
from mo_autonomo.ia.mascaramento import Mascara, contem_dado_pessoal
from mo_autonomo.normas.catalogo import Catalogo
from mo_autonomo.__main__ import _mesma_competencia
from tests.conftest import CNPJ_A, catalogo_teste


@pytest.mark.parametrize("texto", [
    "CPF/CNPJ12.ABC.345/01DE-35", "Tomador CNPJ12ABC34501DE35", "CNPJ 12 ABC 345 01DE 35",
    "CPF 123,456,789,09", "CPF_123_456_789_09", "Fone: (21) 2765.4321", "contato fulano @ empresa.com.br",
    "contato fulano\\u0040empresa.com.br", "anexo " + "QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVo" * 2,
])
def test_guarda_bloqueia_dado_pessoal_disfarcado(texto):
    assert contem_dado_pessoal(texto)


def test_mascara_cobre_formatos_e_preserva_valores():
    m = Mascara()
    t = "Tomador CNPJ12ABC34501DE35 CPF_123_456_789_09 fone (21) 2765.4321 total R$ 1.500,00 2.300,00"
    out = m.mascarar(t)
    assert not contem_dado_pessoal(out) and "1.500,00 2.300,00" in out and m.desmascarar(out) == t


def test_local_true_so_para_endereco_local():
    assert _host_local("http://localhost:11434/v1") and _host_local("http://192.168.0.10:11434/v1")
    assert not _host_local("https://api.exemplo.com/v1")
    c = montar_cascata({"provedores": [{"nome": "x", "base_url": "https://api.exemplo.com/v1", "modelo": "m", "local": True}]})
    assert not c.provedores[0].local


def _cat_inss_2026():
    base = catalogo_teste()
    itens = []
    for n in base.normas.values():
        d = {"id": n.id, "titulo": n.titulo, "area": "teste", "parametros": dict(n.parametros), "status": n.status,
             "fonte_url": n.fonte_url, "conferido_por": n.conferido_por, "conferido_em": str(n.conferido_em)}
        if n.id == "TABELA_INSS_SEGURADO":
            d["vigencia"] = {"inicio": "2026-01-01"}
        itens.append(d)
    return Catalogo.de_lista(itens)


def test_folha_usa_tabela_vigente_na_competencia():
    l = {"cpf": "00000000191", "nome": "X", "competencia": "2025-12", "salario_contribuicao": Decimal("1500.00"),
         "inss_descontado": Decimal("1.00"), "base_irrf": Decimal("2800.00"), "dependentes": 0,
         "irrf_descontado": Decimal("60.00")}
    r = conferir([l], CNPJ_A, _cat_inss_2026())
    assert not [a for a in r["achados"] if a.regra == "DP_INSS_DIVERGENTE"]
    assert any("INSS 2025-12" in i for i in r["inativas"])


def test_irrf_acima_da_ultima_faixa_nao_zera():
    p = {"deducao_por_dependente": "0", "faixas": [{"ate": "1000", "aliquota": "0", "deduzir": "0"}]}
    with pytest.raises(ValueError):
        irrf_mensal(Decimal("5000"), 0, p)


def test_auditoria_aponta_duplicidade_e_linha_sem_chave():
    rel = [{"chave": "K1", "valor": Decimal("10"), "cnpj": CNPJ_A}, {"chave": "K1", "valor": Decimal("10"), "cnpj": CNPJ_A},
           {"chave": "", "valor": Decimal("100"), "cnpj": CNPJ_A}, {"chave": "", "valor": Decimal("200"), "cnpj": CNPJ_A}]
    regras = sorted(a.regra for a in auditar([], rel, CNPJ_A, "2026-10"))
    assert regras == ["DOMINIO_DUPLICADO", "DOMINIO_SEM_CHAVE", "DOMINIO_SEM_CHAVE", "DOMINIO_SEM_DOCUMENTO"]


def test_competencia_ilegivel_nao_e_descartada_em_silencio():
    assert _mesma_competencia("out/2026", "2026-10") is None
    assert _mesma_competencia("10/2026", "2026-10") is True and _mesma_competencia("2026-09", "2026-10") is False


def test_bak_unico_e_sem_bak_quando_igual(tmp_path):
    d = tmp_path / "plano_contas.csv"
    c = lambda n: [{"codigo": "1", "descricao": n, "analitica": True, "classificacao": "1", "grupo": ""}]
    escrever_plano(c("A"), d)
    escrever_plano(c("A"), d)  # igual: nada muda
    assert not list(tmp_path.glob("*.bak"))
    escrever_plano(c("B"), d, True)
    escrever_plano(c("C"), d, True)  # mesmo segundo: não pode perder o original
    baks = sorted(p.read_text(encoding="utf-8") for p in tmp_path.glob("*.bak"))
    assert len(baks) == 2 and any(";A;" in b for b in baks) and any(";B;" in b for b in baks)
