from datetime import date

from mo_autonomo.clientes.perfil import Perfis
from mo_autonomo.documentos.classificador import classificar
from mo_autonomo.especialista.modelo import APONTAMENTO, CONTROLE, INDICIO
from mo_autonomo.especialista.motor import avaliar_competencia, avaliar_documento, cobertura
from tests.conftest import (CNPJ_A, CNPJ_B, CNPJ_X, HOJE, carteira_teste, catalogo_teste, chave_nfe, evento_xml,
                            nfe_xml, nfse_abrasf_xml, nfse_nacional_xml)


def doc(xml, sha="s"):
    d = classificar(xml)["doc"]
    d["_sha256"] = sha
    return d


def regras_de(xml, cnpj=CNPJ_A, catalogo=None):
    cat = catalogo or catalogo_teste()
    perfil = Perfis(carteira_teste(), {}, cat).em(cnpj, date(2026, 10, 1))
    return avaliar_documento(doc(xml), perfil, cat, HOJE)


def ids(achados):
    return sorted(a.regra for a in achados)


def test_nota_limpa_sem_achados():
    assert ids(regras_de(nfe_xml())) == []


def test_soma_itens_divergente_e_controle():
    a = regras_de(nfe_xml(itens=(("12345678", "5102", "60.00"),), total="70.00"))
    assert ids(a) == ["NFE_SOMA_ITENS"] and a[0].natureza == CONTROLE and a[0].bloqueia


def test_sem_protocolo():
    assert "DFE_SEM_PROTOCOLO" in ids(regras_de(nfe_xml(protocolo=False)))


def test_crt_x_regime_apontamento():
    a = [x for x in regras_de(nfe_xml(crt="3")) if x.regra == "NFE_CRT_REGIME"]
    assert a and a[0].natureza == APONTAMENTO and a[0].normas[0]["status"] == "CONFERIDO"


def test_crt_regra_inativa_sem_parametro():
    cat = catalogo_teste(conferidas=[], pendentes_com_param=True)  # parâmetro proposto, não conferido
    assert "NFE_CRT_REGIME" not in ids(regras_de(nfe_xml(crt="3"), catalogo=cat))
    inativas = {c["regra"] for c in cobertura(cat) if not c["ativa"]}
    assert "NFE_CRT_REGIME" in inativas and "NFE_SOMA_ITENS" not in inativas


def test_crt_so_para_emitente():
    # nota de terceiro (CRT 3) contra a empresa: CRT é do emitente, não da empresa
    assert "NFE_CRT_REGIME" not in ids(regras_de(nfe_xml(emit=CNPJ_X, dest=CNPJ_A, crt="3")))


def test_cfop_tpnf_e_iddest():
    a = ids(regras_de(nfe_xml(itens=(("12345678", "1102", "10.00"),))))
    assert a == ["NFE_CFOP_TPNF"]  # 1xxx é interno (idDest 1 ok), mas é de entrada (tpNF 1 = saída)
    assert "NFE_CFOP_IDDEST" in ids(regras_de(nfe_xml(id_dest="2")))


def test_devolucao_sem_referencia():
    assert "NFE_DEVOLUCAO_SEM_REF" in ids(regras_de(nfe_xml(fin="4")))
    assert "NFE_DEVOLUCAO_SEM_REF" not in ids(regras_de(nfe_xml(fin="4", refs=(chave_nfe(CNPJ_X, 9),))))


def test_monofasico_so_simples_e_natureza_indicio_com_lc_pendente():
    xml = nfe_xml(itens=(("33030010", "5405", "40.00"),))
    a = [x for x in regras_de(xml) if x.regra == "SIMPLES_MONOFASICO"]
    assert a and a[0].natureza == APONTAMENTO and not a[0].bloqueia
    # Presumido emitindo o mesmo NCM: pré-condição de perfil não atende
    assert "SIMPLES_MONOFASICO" not in ids(regras_de(nfe_xml(emit=CNPJ_B, crt="3", itens=(("33030010", "5405", "40.00"),)), cnpj=CNPJ_B))
    # LC 123 não conferida -> INDÍCIO (não pode virar ação)
    cat = catalogo_teste(conferidas=[n for n in catalogo_teste().normas if n != "LC_123_2006"])
    a2 = [x for x in regras_de(xml, catalogo=cat) if x.regra == "SIMPLES_MONOFASICO"]
    assert a2[0].natureza == INDICIO


def test_iss_retido_tomador_nacional_e_abrasf():
    a = ids(regras_de(nfse_nacional_xml(ret="2")))
    assert "NFSE_ISS_RETIDO_NACIONAL" in a
    assert "NFSE_ISS_RETIDO_NACIONAL" not in ids(regras_de(nfse_nacional_xml(ret="1")))
    assert "NFSE_ISS_RETIDO_ABRASF" in ids(regras_de(nfse_abrasf_xml(iss_retido="1"), cnpj=CNPJ_B))
    # prestador não recebe o achado do tomador
    assert "NFSE_ISS_RETIDO_ABRASF" not in ids(regras_de(nfse_abrasf_xml(iss_retido="1"), cnpj=CNPJ_A))


def test_retencoes_federais_ausentes():
    xml = nfse_abrasf_xml(prest=CNPJ_X, toma=CNPJ_B)
    assert "NFSE_RETENCOES_FEDERAIS" in ids(regras_de(xml, cnpj=CNPJ_B))
    # Simples como tomador: regime fora da lista do parâmetro
    assert "NFSE_RETENCOES_FEDERAIS" not in ids(regras_de(nfse_abrasf_xml(prest=CNPJ_X, toma=CNPJ_A), cnpj=CNPJ_A))
    com_ret = nfse_nacional_xml(toma=CNPJ_B, ctrib="170101", fed={"vRetCSLL": "10.00"})
    assert "NFSE_RETENCOES_FEDERAIS" not in ids(regras_de(com_ret, cnpj=CNPJ_B))


def test_competencia_fora_da_rotina_e_emissao_futura():
    assert "DOC_COMPETENCIA_ROTINA" in ids(regras_de(nfe_xml(emissao="2026-07-10T10:00:00-03:00")))
    assert "DOC_COMPETENCIA_ROTINA" not in ids(regras_de(nfe_xml(emissao="2026-09-10T10:00:00-03:00")))
    assert "DOC_EMISSAO_FUTURA" in ids(regras_de(nfe_xml(emissao="2026-11-10T10:00:00-03:00")))


def test_cnpj_invalido():
    assert "DOC_CNPJ_INVALIDO" in ids(regras_de(nfe_xml(dest="12345678000100")))


def test_regras_de_competencia():
    cat = catalogo_teste()
    perfil = Perfis(carteira_teste(), {}, cat).em(CNPJ_A, date(2026, 10, 1))
    docs = [doc(nfe_xml(numero=n), f"s{n}") for n in (1, 2, 5)]
    docs.append(doc(nfe_xml(numero=1, itens=(("12345678", "5102", "99.00"),)), "outro"))
    docs.append(doc(evento_xml(chave_nfe(CNPJ_A, 2)), "ev"))
    a = avaliar_competencia(docs, perfil, "2026-10", cat, HOJE)
    regras = ids(a)
    assert regras == ["COMP_CANCELAMENTO", "COMP_DUPLICIDADE", "COMP_SEQUENCIA"]
    seq = [x for x in a if x.regra == "COMP_SEQUENCIA"][0]
    assert "3, 4" in seq.mensagem
