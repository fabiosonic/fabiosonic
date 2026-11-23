"""Gera XMLs/OFX/CSV sintéticos e válidos para testes e demonstração.

Nenhum dado é real: CNPJs são gerados com dígito verificador correto a partir de bases fictícias.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from xml.sax.saxutils import escape

from .util import _valor_char, dv_modulo11

UF_CODIGO = {"SP": "35", "RJ": "33", "MG": "31", "PR": "41", "SC": "42", "RS": "43", "GO": "52", "BA": "29"}


def gerar_cnpj(base12: str) -> str:
    base = base12.upper()
    for pesos in ([5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]):
        resto = sum(_valor_char(c) * p for c, p in zip(base, pesos)) % 11
        base += str(0 if resto < 2 else 11 - resto)
    return base


def gerar_chave(uf: str, data: date, cnpj: str, modelo: str, serie: int, numero: int, cnf: int = 12345678) -> str:
    base = (f"{UF_CODIGO.get(uf, '35')}{data:%y%m}{cnpj}{modelo}{serie:03d}{numero:09d}1{cnf:08d}")
    return base + str(dv_modulo11(base))


def _v(x) -> str:
    return f"{Decimal(str(x)):.2f}"


def nfe_xml(numero: int, data: date, emit: tuple, dest: tuple, itens: list[dict], *, serie: int = 1,
            modelo: str = "55", crt: str = "1", tp_nf: str = "1", protocolo: bool = True,
            vnf_informado=None, ibscbs: bool = False, chave: str | None = None, cstat: str = "100") -> str:
    """emit/dest = (documento, nome, uf). itens: ncm, cfop, valor, desconto, csosn|cst, vicms."""
    e_doc, e_nome, e_uf = emit
    d_doc, d_nome, d_uf = dest
    chave = chave or gerar_chave(e_uf, data, e_doc, modelo, serie, numero)
    dets, vprod, vdesc = [], Decimal(0), Decimal(0)
    for n, it in enumerate(itens, start=1):
        valor, desc = Decimal(str(it["valor"])), Decimal(str(it.get("desconto", 0)))
        vprod += valor
        vdesc += desc
        if "cst" in it:
            icms = f'<ICMS00><orig>0</orig><CST>{it["cst"]}</CST><vICMS>{_v(it.get("vicms", 0))}</vICMS></ICMS00>'
        else:
            icms = f'<ICMSSN102><orig>0</orig><CSOSN>{it.get("csosn", "102")}</CSOSN></ICMSSN102>'
        ibs = ("<IBSCBS><CST>000</CST><cClassTrib>000001</cClassTrib><gIBSCBS><vBC>"
               f"{_v(valor - desc)}</vBC></gIBSCBS></IBSCBS>") if ibscbs else ""
        dets.append(
            f'<det nItem="{n}"><prod><cProd>P{n:03d}</cProd><cEAN>SEM GTIN</cEAN>'
            f'<xProd>{escape(it.get("descricao", f"Produto {n}"))}</xProd><NCM>{it.get("ncm", "84713012")}</NCM>'
            f'<CFOP>{it["cfop"]}</CFOP><uCom>UN</uCom><qCom>1.0000</qCom><vUnCom>{_v(valor)}</vUnCom>'
            f'<vProd>{_v(valor)}</vProd>' + (f'<vDesc>{_v(desc)}</vDesc>' if desc else "") +
            f'<indTot>1</indTot></prod><imposto><ICMS>{icms}</ICMS>'
            f'<PIS><PISOutr><CST>{it.get("cst_pis", "49")}</CST><vPIS>0.00</vPIS></PISOutr></PIS>'
            f'<COFINS><COFINSOutr><CST>{it.get("cst_pis", "49")}</CST><vCOFINS>0.00</vCOFINS></COFINSOutr></COFINS>'
            f'{ibs}</imposto></det>')
    vnf = vprod - vdesc if vnf_informado is None else Decimal(str(vnf_informado))
    tag_doc_dest = "CPF" if len(d_doc) == 11 else "CNPJ"
    inf = (f'<infNFe versao="4.00" Id="NFe{chave}"><ide><cUF>{UF_CODIGO.get(e_uf, "35")}</cUF><natOp>VENDA</natOp>'
           f'<mod>{modelo}</mod><serie>{serie}</serie><nNF>{numero}</nNF><dhEmi>{data.isoformat()}T10:00:00-03:00</dhEmi>'
           f'<tpNF>{tp_nf}</tpNF><idDest>{"1" if e_uf == d_uf else "2"}</idDest><tpEmis>1</tpEmis></ide>'
           f'<emit><CNPJ>{e_doc}</CNPJ><xNome>{escape(e_nome)}</xNome><enderEmit><xMun>Cidade</xMun><UF>{e_uf}</UF>'
           f'</enderEmit><CRT>{crt}</CRT></emit>'
           f'<dest><{tag_doc_dest}>{d_doc}</{tag_doc_dest}><xNome>{escape(d_nome)}</xNome><enderDest><xMun>Cidade</xMun>'
           f'<UF>{d_uf}</UF></enderDest></dest>{"".join(dets)}'
           f'<total><ICMSTot><vBC>0.00</vBC><vICMS>0.00</vICMS><vICMSDeson>0.00</vICMSDeson><vFCPST>0.00</vFCPST>'
           f'<vST>0.00</vST><vProd>{_v(vprod)}</vProd><vFrete>0.00</vFrete><vSeg>0.00</vSeg><vDesc>{_v(vdesc)}</vDesc>'
           f'<vII>0.00</vII><vIPI>0.00</vIPI><vIPIDevol>0.00</vIPIDevol><vPIS>0.00</vPIS><vCOFINS>0.00</vCOFINS>'
           f'<vOutro>0.00</vOutro><vNF>{_v(vnf)}</vNF></ICMSTot></total></infNFe>')
    nfe = f'<NFe xmlns="http://www.portalfiscal.inf.br/nfe">{inf}</NFe>'
    if not protocolo:
        return f'<?xml version="1.0" encoding="UTF-8"?>{nfe}'
    prot = (f'<protNFe versao="4.00"><infProt><tpAmb>1</tpAmb><chNFe>{chave}</chNFe>'
            f'<dhRecbto>{data.isoformat()}T10:01:00-03:00</dhRecbto><nProt>1352{numero:011d}</nProt>'
            f'<cStat>{cstat}</cStat><xMotivo>Autorizado o uso da NF-e</xMotivo></infProt></protNFe>')
    return (f'<?xml version="1.0" encoding="UTF-8"?><nfeProc versao="4.00" '
            f'xmlns="http://www.portalfiscal.inf.br/nfe">{nfe}{prot}</nfeProc>')


def evento_cancelamento_xml(chave: str, data: date) -> str:
    return (f'<?xml version="1.0" encoding="UTF-8"?><procEventoNFe versao="1.00" xmlns="http://www.portalfiscal.inf.br/nfe">'
            f'<evento versao="1.00"><infEvento Id="ID110111{chave}01"><cOrgao>35</cOrgao><tpAmb>1</tpAmb>'
            f'<CNPJ>{chave[6:20]}</CNPJ><chNFe>{chave}</chNFe><dhEvento>{data.isoformat()}T12:00:00-03:00</dhEvento>'
            f'<tpEvento>110111</tpEvento><nSeqEvento>1</nSeqEvento><verEvento>1.00</verEvento>'
            f'<detEvento versao="1.00"><descEvento>Cancelamento</descEvento><nProt>1</nProt>'
            f'<xJust>Erro na emissao do documento</xJust></detEvento></infEvento></evento>'
            f'<retEvento versao="1.00"><infEvento><cStat>135</cStat><chNFe>{chave}</chNFe></infEvento></retEvento>'
            f'</procEventoNFe>')


def nfse_nacional_xml(numero: int, data: date, prest: tuple, toma: tuple, valor, *, op_simples: str = "3",
                      aliq_iss="2.00", iss_retido: bool = False, irrf=0, pis=0, cofins=0, csll=0, inss=0,
                      vliq=None) -> str:
    """prest/toma = (documento, nome, uf). op_simples: 1 não optante, 2 MEI, 3 ME/EPP."""
    p_doc, p_nome, p_uf = prest
    t_doc, t_nome, _ = toma
    valor = Decimal(str(valor))
    v_iss = (valor * Decimal(str(aliq_iss)) / 100).quantize(Decimal("0.01"))
    ret_fed = sum(Decimal(str(x)) for x in (irrf, pis, cofins, csll, inss))
    liquido = valor - ret_fed - (v_iss if iss_retido else 0) if vliq is None else Decimal(str(vliq))
    chave = f"3550308{p_doc}{numero:013d}".ljust(50, "0")[:50]
    tag_t = "CPF" if len(t_doc) == 11 else "CNPJ"
    piscofins = (f'<piscofins><CST>01</CST><vBCPisCofins>{_v(valor)}</vBCPisCofins><vPis>{_v(pis)}</vPis>'
                 f'<vCofins>{_v(cofins)}</vCofins><tpRetPisCofins>1</tpRetPisCofins></piscofins>') if (pis or cofins) else ""
    return (f'<?xml version="1.0" encoding="UTF-8"?><NFSe versao="1.00" xmlns="http://www.sped.fazenda.gov.br/nfse">'
            f'<infNFSe Id="NFS{chave}"><xLocEmi>Cidade</xLocEmi><nNFSe>{numero}</nNFSe>'
            f'<dhProc>{data.isoformat()}T09:00:00-03:00</dhProc>'
            f'<emit><CNPJ>{p_doc}</CNPJ><xNome>{escape(p_nome)}</xNome><enderNac><UF>{p_uf}</UF></enderNac></emit>'
            f'<valores><vBC>{_v(valor)}</vBC><pAliqAplic>{aliq_iss}</pAliqAplic><vISSQN>{_v(v_iss)}</vISSQN>'
            f'<vTotalRet>{_v(ret_fed)}</vTotalRet><vLiq>{_v(liquido)}</vLiq></valores>'
            f'<DPS versao="1.00"><infDPS Id="DPS{chave[:45]}"><dhEmi>{data.isoformat()}T09:00:00-03:00</dhEmi>'
            f'<serie>1</serie><nDPS>{numero}</nDPS>'
            f'<prest><CNPJ>{p_doc}</CNPJ><regTrib><opSimpNac>{op_simples}</opSimpNac></regTrib></prest>'
            f'<toma><{tag_t}>{t_doc}</{tag_t}><xNome>{escape(t_nome)}</xNome></toma>'
            f'<serv><cServ><cTribNac>170101</cTribNac><xDescServ>Assessoria e consultoria</xDescServ></cServ></serv>'
            f'<valores><vServPrest><vServ>{_v(valor)}</vServ></vServPrest><trib><tribMun><tribISSQN>1</tribISSQN>'
            f'<tpRetISSQN>{"2" if iss_retido else "1"}</tpRetISSQN><pAliq>{aliq_iss}</pAliq></tribMun>'
            f'<tribFed>{piscofins}' + (f'<vRetCP>{_v(inss)}</vRetCP>' if inss else "")
            + (f'<vRetIRRF>{_v(irrf)}</vRetIRRF>' if irrf else "") + (f'<vRetCSLL>{_v(csll)}</vRetCSLL>' if csll else "")
            + '</tribFed></trib></valores></infDPS></DPS></infNFSe></NFSe>')


def nfse_abrasf_xml(numero: int, data: date, prest: tuple, toma: tuple, valor, *, optante: bool = True,
                    aliquota="0.03", iss_retido: bool = False, ir=0) -> str:
    p_doc, p_nome, _ = prest
    t_doc, t_nome, t_uf = toma
    valor = Decimal(str(valor))
    v_iss = (valor * Decimal(aliquota)).quantize(Decimal("0.01"))
    liquido = valor - Decimal(str(ir)) - (v_iss if iss_retido else 0)
    return (f'<?xml version="1.0" encoding="UTF-8"?><ConsultarNfseResposta xmlns="http://www.abrasf.org.br/nfse.xsd">'
            f'<ListaNfse><CompNfse><Nfse versao="2.02"><InfNfse><Numero>{numero}</Numero>'
            f'<CodigoVerificacao>AB{numero:06d}</CodigoVerificacao><DataEmissao>{data.isoformat()}T08:00:00</DataEmissao>'
            f'<ValoresNfse><BaseCalculo>{_v(valor)}</BaseCalculo><Aliquota>{aliquota}</Aliquota><ValorIss>{_v(v_iss)}</ValorIss>'
            f'<ValorLiquidoNfse>{_v(liquido)}</ValorLiquidoNfse></ValoresNfse>'
            f'<PrestadorServico><IdentificacaoPrestador><CpfCnpj><Cnpj>{p_doc}</Cnpj></CpfCnpj></IdentificacaoPrestador>'
            f'<RazaoSocial>{escape(p_nome)}</RazaoSocial></PrestadorServico>'
            f'<DeclaracaoPrestacaoServico><InfDeclaracaoPrestacaoServico><Competencia>{data.isoformat()}</Competencia>'
            f'<Servico><Valores><ValorServicos>{_v(valor)}</ValorServicos>' + (f'<ValorIr>{_v(ir)}</ValorIr>' if ir else "")
            + f'</Valores><IssRetido>{"1" if iss_retido else "2"}</IssRetido><ItemListaServico>17.01</ItemListaServico>'
            f'<Discriminacao>Consultoria</Discriminacao></Servico>'
            f'<Prestador><CpfCnpj><Cnpj>{p_doc}</Cnpj></CpfCnpj></Prestador>'
            f'<TomadorServico><IdentificacaoTomador><CpfCnpj><Cnpj>{t_doc}</Cnpj></CpfCnpj></IdentificacaoTomador>'
            f'<RazaoSocial>{escape(t_nome)}</RazaoSocial><Endereco><Uf>{t_uf}</Uf></Endereco></TomadorServico>'
            f'<OptanteSimplesNacional>{"1" if optante else "2"}</OptanteSimplesNacional>'
            f'</InfDeclaracaoPrestacaoServico></DeclaracaoPrestacaoServico></InfNfse></Nfse></CompNfse></ListaNfse>'
            f'</ConsultarNfseResposta>')


def ofx(lancamentos: list[tuple], banco: str = "0341", conta: str = "12345-6") -> str:
    """lancamentos: (data, valor, memo[, fitid])."""
    blocos = []
    for n, l in enumerate(lancamentos):
        d, valor, memo = l[:3]
        fitid = l[3] if len(l) > 3 else f"{d:%Y%m%d}{n:05d}"
        tipo = "CREDIT" if Decimal(str(valor)) > 0 else "DEBIT"
        blocos.append(f"<STMTTRN>\n<TRNTYPE>{tipo}\n<DTPOSTED>{d:%Y%m%d}120000[-3:BRT]\n<TRNAMT>{_v(valor)}\n"
                      f"<FITID>{fitid}\n<MEMO>{memo}\n</STMTTRN>")
    ini = min(l[0] for l in lancamentos)
    fim = max(l[0] for l in lancamentos)
    return ("OFXHEADER:100\nDATA:OFXSGML\nVERSION:102\nENCODING:USASCII\nCHARSET:1252\n\n<OFX>\n<BANKMSGSRSV1>"
            f"<STMTTRNRS><STMTRS><CURDEF>BRL\n<BANKACCTFROM><BANKID>{banco}\n<ACCTID>{conta}\n<ACCTTYPE>CHECKING\n"
            f"</BANKACCTFROM><BANKTRANLIST><DTSTART>{ini:%Y%m%d}\n<DTEND>{fim:%Y%m%d}\n"
            + "\n".join(blocos) + "\n</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>\n")


def folha_csv(linhas: list[tuple]) -> str:
    """linhas: (competencia 'MM/AAAA', salarios, pro_labore, encargos)."""
    corpo = "\n".join(f"{c};{_v(s).replace('.', ',')};{_v(p).replace('.', ',')};{_v(e).replace('.', ',')}"
                      for c, s, p, e in linhas)
    return "competencia;salarios;pro_labore;encargos\n" + corpo + "\n"
