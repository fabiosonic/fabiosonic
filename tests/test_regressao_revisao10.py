"""Revisão 10: NFS-e ABRASF 2.x (competência e lista de notas), guarda LGPD sem falso positivo em
documento comum, folha MM/AAAA, pasta IMAP que não abre."""
from datetime import date
from decimal import Decimal

import pytest

from mo_autonomo.documentos.xml_fiscal import DocumentoNaoReconhecido, ler_xml
from mo_autonomo.dp.folha import conferir
from mo_autonomo.entrada.fontes import FonteImap, FonteMultipla
from mo_autonomo.ia.mascaramento import Mascara, contem_dado_pessoal
from tests.conftest import CNPJ_A, CNPJ_B, catalogo_teste, eml_bytes, nfe_xml

NS = 'xmlns="http://www.abrasf.org.br/nfse.xsd"'


def _comp(num, emissao, competencia, valor, toma, cancel=False):
    c = (f"<CompNfse><Nfse versao=\"2.02\"><InfNfse Id=\"n{num}\"><Numero>{num}</Numero>"
         f"<CodigoVerificacao>AB{num}</CodigoVerificacao><DataEmissao>{emissao}</DataEmissao>"
         f"<PrestadorServico><IdentificacaoPrestador><CpfCnpj><Cnpj>{CNPJ_A}</Cnpj></CpfCnpj></IdentificacaoPrestador></PrestadorServico>"
         f"<DeclaracaoPrestacaoServico><InfDeclaracaoPrestacaoServico><Competencia>{competencia}</Competencia>"
         f"<Servico><Valores><ValorServicos>{valor}</ValorServicos></Valores><IssRetido>2</IssRetido></Servico>"
         f"<TomadorServico><IdentificacaoTomador><CpfCnpj><Cnpj>{toma}</Cnpj></CpfCnpj></IdentificacaoTomador></TomadorServico>"
         f"</InfDeclaracaoPrestacaoServico></DeclaracaoPrestacaoServico></InfNfse></Nfse>")
    if cancel:
        c += "<NfseCancelamento><Confirmacao/></NfseCancelamento>"
    return c + "</CompNfse>"


def _lista(*comps):
    return (f'<?xml version="1.0"?><ConsultarNfseServicoPrestadoResposta {NS}><ListaNfse>'
            + "".join(comps) + "</ListaNfse></ConsultarNfseServicoPrestadoResposta>").encode()


def test_abrasf_2_le_competencia_da_declaracao():
    d = ler_xml(_lista(_comp(101, "2026-10-01T09:00:00", "2026-09-01", "1000.00", CNPJ_B)))
    assert d["competencia"] == "2026-09" and d["totais"]["vServ"] == Decimal("1000.00")


def test_lista_com_varias_nfse_vira_pendencia_e_nao_perde_notas():
    x = _lista(_comp(201, "2026-09-05", "2026-09-01", "1000.00", CNPJ_B),
               _comp(202, "2026-09-10", "2026-09-01", "5000.00", CNPJ_B, cancel=True))
    with pytest.raises(DocumentoNaoReconhecido, match="2 NFS-e"):
        ler_xml(x)


@pytest.mark.parametrize("texto", [
    "05/09/2026 PIX RECEBIDO 001280 1.250,00",
    "DOCUMENTODEARRECADACAODOSIMPLESNACIONALPERIODODEAPURACAOSETEMBRO",
    "Autenticacao: 3f2a9c0b7e1d4a6f8b2c9e0d1a3b5c7d9e1f2a4b6c8d0e2f",
    "-" * 10 + "/" * 80,
    "Item 10,000 UN x 150,000 = 1.500,00",
])
def test_documento_comum_nao_bloqueia_a_nuvem(texto):
    m = Mascara()
    assert not contem_dado_pessoal(texto) and m.mascarar(texto) == texto


def test_valor_seguido_de_linha_numerica_nao_e_engolido():
    m = Mascara()
    out = m.mascarar("Totais 1.234,56\n85800000012345678901234567")
    assert "1.234,56" in out and not contem_dado_pessoal(out)


def test_base64_de_verdade_continua_bloqueado():
    assert contem_dado_pessoal("anexo " + "QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVowMTIzNDU2Nzg5YWJjZGVmZ2hpams=")


def test_folha_aceita_competencia_mm_aaaa():
    l = {"cpf": "00000000191", "nome": "X", "competencia": "09/2026", "salario_contribuicao": Decimal("1500.00"),
         "inss_descontado": Decimal("1.00"), "base_irrf": Decimal("2800.00"), "dependentes": 0,
         "irrf_descontado": Decimal("60.00")}
    r = conferir([l], CNPJ_A, catalogo_teste())
    assert [a.regra for a in r["achados"]] == ["DP_INSS_DIVERGENTE"]


def test_pasta_imap_que_nao_abre_nao_impede_as_outras():
    class Falso:
        atual = None

        def login(self, u, s): pass
        def logout(self): pass
        def list(self, *a): return "OK", [b'(\\HasNoChildren) "." "INBOX.Ruim"', b'(\\HasNoChildren) "." "INBOX.Boa"']
        def response(self, c): return c, [b"9"]

        def select(self, p, readonly=False):
            self.atual = p
            return ("NO", [b"sem acesso"]) if "Ruim" in p else ("OK", [b"1"])

        def uid(self, cmd, *a):
            if cmd == "search":
                return "OK", [b"1"]
            return "OK", [(b"x", eml_bytes({"a.xml": nfe_xml()}))]
    f = Falso()
    multi = FonteMultipla([FonteImap("h", 993, "u", "s", pasta="*", desde=date(2026, 10, 1), fabrica=lambda: f)])
    msgs = list(multi.mensagens())
    assert [m.uid.split(":")[2] for m in msgs] == ["INBOX.Boa"]
    assert any("INBOX.Ruim" in e for e in multi.erros)
