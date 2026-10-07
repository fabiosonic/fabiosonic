"""Fixtures fictícias (LGPD: nenhum CNPJ/CPF real)."""
from __future__ import annotations

import io
import zipfile
from datetime import date
from email.message import EmailMessage

import pytest

from mo_autonomo.clientes.cadastro import Carteira, Empresa
from mo_autonomo.clientes.perfil import Perfis
from mo_autonomo.normas.catalogo import Catalogo
from mo_autonomo.util.documentos_id import gerar_cnpj, gerar_cpf

CNPJ_A = gerar_cnpj("900000010001")  # cliente Simples
CNPJ_B = gerar_cnpj("900000020001")  # cliente Presumido
CNPJ_C = gerar_cnpj("900000030001")  # cliente MEI
CNPJ_X = gerar_cnpj("800000010001")  # terceiro fora da carteira
CPF_1 = gerar_cpf("900000001")
HOJE = date(2026, 10, 7)

NS_NFE = "http://www.portalfiscal.inf.br/nfe"
NS_CTE = "http://www.portalfiscal.inf.br/cte"
NS_NFSE = "http://www.sped.fazenda.gov.br/nfse"


def chave_nfe(cnpj_emit: str, numero: int, modelo: str = "55", serie: int = 1) -> str:
    base = f"33{'2610'}{cnpj_emit}{modelo}{serie:03d}{numero:09d}1{numero:08d}"
    # dígito verificador módulo 11 (só para formar 44 dígitos plausíveis)
    pesos = [2, 3, 4, 5, 6, 7, 8, 9]
    s = sum(int(d) * pesos[i % 8] for i, d in enumerate(reversed(base)))
    dv = 11 - s % 11
    return base + str(0 if dv >= 10 else dv)


def nfe_xml(emit=CNPJ_A, dest=CNPJ_X, numero=1, modelo="55", crt="1", tp_nf="1", id_dest="1",
            itens=(("12345678", "5102", "100.00"),), total=None, emissao="2026-10-01T10:00:00-03:00",
            protocolo=True, fin="1", refs=(), serie=1) -> bytes:
    ch = chave_nfe(emit, numero, modelo, serie)
    dets = "".join(
        f'<det nItem="{i + 1}"><prod><cProd>P{i}</cProd><xProd>Produto {i}</xProd><NCM>{ncm}</NCM>'
        f'<CFOP>{cfop}</CFOP><vProd>{v}</vProd></prod><imposto><ICMS><ICMSSN102><CSOSN>102</CSOSN>'
        f'</ICMSSN102></ICMS></imposto></det>' for i, (ncm, cfop, v) in enumerate(itens))
    from decimal import Decimal
    vprod = total if total is not None else str(sum(Decimal(v) for _, _, v in itens))
    nfref = "".join(f"<NFref><refNFe>{r}</refNFe></NFref>" for r in refs)
    dest_xml = f"<dest><CNPJ>{dest}</CNPJ><enderDest><UF>RJ</UF></enderDest></dest>" if dest else ""
    inf = (f'<infNFe Id="NFe{ch}" versao="4.00"><ide><mod>{modelo}</mod><serie>{serie}</serie><nNF>{numero}</nNF>'
           f'<dhEmi>{emissao}</dhEmi><tpNF>{tp_nf}</tpNF><idDest>{id_dest}</idDest><finNFe>{fin}</finNFe>{nfref}</ide>'
           f'<emit><CNPJ>{emit}</CNPJ><enderEmit><UF>RJ</UF></enderEmit><CRT>{crt}</CRT></emit>{dest_xml}{dets}'
           f'<total><ICMSTot><vProd>{vprod}</vProd><vNF>{vprod}</vNF></ICMSTot></total></infNFe>')
    prot = f"<protNFe><infProt><chNFe>{ch}</chNFe><cStat>100</cStat></infProt></protNFe>" if protocolo else ""
    return (f'<?xml version="1.0" encoding="UTF-8"?><nfeProc xmlns="{NS_NFE}" versao="4.00">'
            f'<NFe>{inf}</NFe>{prot}</nfeProc>').encode()


def evento_xml(chave: str, tp="110111", autor=CNPJ_A, data="2026-10-02T09:00:00-03:00") -> bytes:
    return (f'<?xml version="1.0"?><procEventoNFe xmlns="{NS_NFE}"><evento><infEvento Id="ID{tp}{chave}01">'
            f'<CNPJ>{autor}</CNPJ><chNFe>{chave}</chNFe><dhEvento>{data}</dhEvento><tpEvento>{tp}</tpEvento>'
            f'</infEvento></evento><retEvento><infEvento><cStat>135</cStat></infEvento></retEvento></procEventoNFe>').encode()


def cte_xml(emit=CNPJ_X, dest=CNPJ_A, numero=10) -> bytes:
    return (f'<?xml version="1.0"?><cteProc xmlns="{NS_CTE}"><CTe><infCte Id="CTe{"3" * 44}">'
            f'<ide><mod>57</mod><serie>1</serie><nCT>{numero}</nCT><dhEmi>2026-10-03T08:00:00-03:00</dhEmi></ide>'
            f'<emit><CNPJ>{emit}</CNPJ></emit><rem><CNPJ>{CNPJ_X}</CNPJ></rem><dest><CNPJ>{dest}</CNPJ></dest>'
            f'<vPrest><vTPrest>250.00</vTPrest></vPrest></infCte></CTe>'
            f'<protCTe><infProt><cStat>100</cStat></infProt></protCTe></cteProc>').encode()


def nfse_nacional_xml(prest=CNPJ_X, toma=CNPJ_A, valor="1000.00", ret="2", ctrib="010101",
                      fed: dict | None = None, numero=5) -> bytes:
    fedxml = ""
    if fed:
        fedxml = "<tribFed>" + "".join(f"<{k}>{v}</{k}>" for k, v in fed.items()) + "</tribFed>"
    return (f'<?xml version="1.0"?><NFSe xmlns="{NS_NFSE}"><infNFSe Id="NFS{"4" * 50}"><nNFSe>{numero}</nNFSe>'
            f'<cLocIncid>3304557</cLocIncid><dhProc>2026-10-04T10:00:00-03:00</dhProc>'
            f'<DPS><infDPS><dhEmi>2026-10-04T10:00:00-03:00</dhEmi><dCompet>2026-10-04</dCompet>'
            f'<prest><CNPJ>{prest}</CNPJ></prest><toma><CNPJ>{toma}</CNPJ></toma>'
            f'<serv><cServ><cTribNac>{ctrib}</cTribNac></cServ></serv>'
            f'<valores><vServPrest><vServ>{valor}</vServ></vServPrest><trib><tribMun><tpRetISSQN>{ret}</tpRetISSQN>'
            f'</tribMun>{fedxml}</trib></valores></infDPS></DPS></infNFSe></NFSe>').encode()


def nfse_abrasf_xml(prest=CNPJ_A, toma=CNPJ_B, valor="500.00", iss_retido="2", numero=77) -> bytes:
    return (f'<?xml version="1.0"?><CompNfse xmlns="http://www.abrasf.org.br/nfse.xsd"><Nfse><InfNfse>'
            f'<Numero>{numero}</Numero><CodigoVerificacao>ABC</CodigoVerificacao>'
            f'<DataEmissao>2026-10-05T11:00:00</DataEmissao><Competencia>2026-10-01</Competencia>'
            f'<Servico><Valores><ValorServicos>{valor}</ValorServicos></Valores><IssRetido>{iss_retido}</IssRetido>'
            f'<ItemListaServico>17.01</ItemListaServico></Servico>'
            f'<PrestadorServico><IdentificacaoPrestador><CpfCnpj><Cnpj>{prest}</Cnpj></CpfCnpj></IdentificacaoPrestador>'
            f'</PrestadorServico><TomadorServico><IdentificacaoTomador><CpfCnpj><Cnpj>{toma}</Cnpj></CpfCnpj>'
            f'</IdentificacaoTomador></TomadorServico></InfNfse></Nfse></CompNfse>').encode()


def ofx_bytes(banco="341", conta="12345", trans=(("20261005", "1500.00", "PIX RECEBIDO CLIENTE ALFA", "1"),
                                                 ("20261006", "-320.50", "TARIFA BANCARIA PACOTE", "2"))) -> bytes:
    linhas = ["OFXHEADER:100", "DATA:OFXSGML", "", "<OFX>", "<BANKMSGSRSV1><STMTTRNRS><STMTRS>",
              f"<BANKACCTFROM><BANKID>{banco}<BRANCHID>0001<ACCTID>{conta}</BANKACCTFROM>",
              "<BANKTRANLIST><DTSTART>20261001<DTEND>20261031"]
    for d, v, memo, fit in trans:
        linhas.append(f"<STMTTRN><TRNTYPE>OTHER<DTPOSTED>{d}<TRNAMT>{v}<FITID>{fit}<MEMO>{memo}</STMTTRN>")
    linhas += ["</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>"]
    return "\n".join(linhas).encode("latin-1")


def zip_bytes(arquivos: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for nome, dados in arquivos.items():
            z.writestr(nome, dados)
    return buf.getvalue()


def eml_bytes(anexos: dict[str, bytes], assunto="Notas do mês", remetente="cliente@exemplo.test") -> bytes:
    m = EmailMessage()
    m["From"], m["To"], m["Subject"] = remetente, "fiscal@exemplo.test", assunto
    m["Message-ID"] = f"<{abs(hash(assunto + str(len(anexos))))}@exemplo.test>"
    m.set_content("Segue em anexo.")
    for nome, dados in anexos.items():
        tipo = ("application", "zip") if nome.endswith(".zip") else \
               ("application", "pdf") if nome.endswith(".pdf") else ("application", "octet-stream")
        m.add_attachment(dados, maintype=tipo[0], subtype=tipo[1], filename=nome)
    return bytes(m)


CONFERIDA = {"status": "CONFERIDO", "fonte_url": "https://www.gov.br/teste-ficticio",
             "conferido_por": "Pessoa de Teste", "conferido_em": "2026-10-01"}

PARAMS_TESTE = {  # valores fictícios só para exercitar o código
    "MOC_NFE": {"crt_por_regime": {"1": ["SIMPLES"], "2": ["SIMPLES"], "3": ["PRESUMIDO", "REAL"], "4": ["MEI"]},
                "tp_evento_cancelamento": ["110111"], "fin_nfe_devolucao": ["4"], "cstat_autorizado": ["100"],
                "tp_nf_saida": "1"},
    "TABELA_CFOP": {"cfop_digitos_por_tpnf": {"0": ["1", "2", "3"], "1": ["5", "6", "7"]},
                    "cfop_digito_por_iddest": {"1": ["1", "5"], "2": ["2", "6"], "3": ["3", "7"]}},
    "LEIAUTE_NFSE_NACIONAL": {"codigos_iss_retido": ["2"]},
    "LEIAUTE_NFSE_ABRASF": {"codigos_iss_retido": ["1"]},
    "TABELA_NCM_MONOFASICO": {"ncm_prefixos_monofasicos": ["3303"]},
    "LEI_10833_ART30": {"codigos_servico_sujeitos": ["17"], "regimes_tomador_obrigados": ["PRESUMIDO", "REAL"]},
    "DICIONARIO_DADOS_ABERTOS_CNPJ": {"codigo_situacao_ativa": "02", "valor_opcao_sim": "S"},
    "TABELA_INSS_SEGURADO": {"faixas": [{"ate": "1000.00", "aliquota": "0.10"}, {"ate": "2000.00", "aliquota": "0.20"}]},
    "TABELA_IRRF_MENSAL": {"faixas": [{"ate": "2000.00", "aliquota": "0", "deduzir": "0"},
                                      {"ate": None, "aliquota": "0.10", "deduzir": "200.00"}],
                           "deducao_por_dependente": "100.00",
                           "redutor": {"zera_ate": "2500.00", "faixa_ate": "3000.00", "constante": "300.00",
                                       "coeficiente": "0.10"}},
}

TODAS = ["MOC_NFE", "TABELA_CFOP", "LEIAUTE_NFSE_NACIONAL", "LEIAUTE_NFSE_ABRASF", "LC_116_2003",
         "LEI_10833_ART30", "LC_123_2006", "RES_CGSN_140_2018", "TABELA_NCM_MONOFASICO",
         "DICIONARIO_DADOS_ABERTOS_CNPJ", "TABELA_INSS_SEGURADO", "TABELA_IRRF_MENSAL"]


def catalogo_teste(conferidas=None, pendentes_com_param=False) -> Catalogo:
    conferidas = TODAS if conferidas is None else conferidas
    itens = []
    for nid in TODAS:
        item = {"id": nid, "titulo": nid, "area": "teste", "parametros": PARAMS_TESTE.get(nid, {})}
        if nid in conferidas:
            item.update(CONFERIDA)
        elif not pendentes_com_param:
            item["parametros"] = {}
        itens.append(item)
    return Catalogo.de_lista(itens)


def carteira_teste() -> Carteira:
    return Carteira([
        Empresa("101", "ALFA COMERCIO", CNPJ_A, "SIMPLES", "9101", "RJ", "3304557"),
        Empresa("102", "BETA SERVICOS", CNPJ_B, "PRESUMIDO", "9102", "RJ", "3304557"),
        Empresa("103", "GAMA MEI", CNPJ_C, "MEI", None, "RJ", "3304557"),
    ])


@pytest.fixture
def catalogo():
    return catalogo_teste()


@pytest.fixture
def carteira():
    return carteira_teste()


@pytest.fixture
def perfis(carteira, catalogo):
    return Perfis(carteira, {}, catalogo)


def pdf_com_texto(texto: str) -> bytes:
    """PDF mínimo válido com uma linha de texto (para extração com pypdf)."""
    conteudo = f"BT /F1 12 Tf 50 750 Td ({texto}) Tj ET".encode("latin-1")
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
            b"/Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length " + str(len(conteudo)).encode() + b" >>\nstream\n" + conteudo + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    saida, offsets = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, start=1):
        offsets.append(len(saida))
        saida += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(saida)
    saida += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    saida += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    saida += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return saida
