import contextlib
import io
import json
import os
import tempfile
import unittest
import zipfile
from decimal import Decimal

from mo_dominio import lancamentos, matriz, rotinas
from mo_dominio.ofx import ler_ofx
from mo_dominio.xmlfiscal import direcao_para, parse_bytes

SIMPLES = "11111111000111"   # 86-RTX, Simples
PRESUMIDO = "22222222000122"  # 90-ALFA, Presumido
FORN = "33333333000133"
TRANSP = "44444444000144"

CARTEIRA = f"""codigo;apelido;cnpj;regime
86;RTX;{SIMPLES};SIMPLES
90;ALFA;{PRESUMIDO};PRESUMIDO
1;EXEMPLO LTDA;55555555000155;SIMPLES
"""


def nfe(chave, emit, emit_uf, dest, cfop, csosn_ou_cst, data="2026-08-14", fin="1", crt="1", vnf="100.00", cstat="100"):
    icms = (f"<ICMSSN102><orig>0</orig><CSOSN>{csosn_ou_cst}</CSOSN></ICMSSN102>" if crt == "1"
            else f"<ICMS00><orig>0</orig><CST>{csosn_ou_cst}</CST><vICMS>18.00</vICMS></ICMS00>")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe"><NFe><infNFe Id="NFe{chave}" versao="4.00">
<ide><mod>55</mod><serie>1</serie><nNF>123</nNF><dhEmi>{data}T10:00:00-03:00</dhEmi><tpNF>1</tpNF><finNFe>{fin}</finNFe></ide>
<emit><CNPJ>{emit}</CNPJ><xNome>EMITENTE</xNome><enderEmit><UF>{emit_uf}</UF></enderEmit><CRT>{crt}</CRT></emit>
<dest><CNPJ>{dest}</CNPJ><xNome>DEST</xNome><enderDest><UF>SP</UF></enderDest></dest>
<det nItem="1"><prod><CFOP>{cfop}</CFOP><NCM>12345678</NCM><vProd>{vnf}</vProd></prod>
<imposto><ICMS>{icms}</ICMS><PIS><PISOutr><CST>49</CST></PISOutr></PIS><COFINS><COFINSOutr><CST>49</CST></COFINSOutr></COFINS></imposto></det>
<total><ICMSTot><vNF>{vnf}</vNF></ICMSTot></total>
<pag><detPag><tPag>01</tPag></detPag></pag>
</infNFe></NFe><protNFe><infProt><cStat>{cstat}</cStat></infProt></protNFe></nfeProc>""".encode()


def cte(chave, toma_xml, rem, dest):
    return f"""<cteProc xmlns="http://www.portalfiscal.inf.br/cte"><CTe><infCte Id="CTe{chave}">
<ide><CFOP>6352</CFOP><mod>57</mod><serie>1</serie><nCT>9</nCT><dhEmi>2026-08-10T08:00:00-03:00</dhEmi><modal>01</modal><tpCTe>0</tpCTe>{toma_xml}</ide>
<emit><CNPJ>{TRANSP}</CNPJ><xNome>TRANSP</xNome><enderEmit><UF>PR</UF></enderEmit></emit>
<rem><CNPJ>{rem}</CNPJ></rem><dest><CNPJ>{dest}</CNPJ></dest>
<vPrest><vTPrest>50.00</vTPrest></vPrest><imp><ICMS><ICMS00><CST>00</CST><vICMS>6.00</vICMS></ICMS00></ICMS></imp>
</infCte></CTe></cteProc>""".encode()


def nfse(prest, toma, tp_ret="2", chave="3550308211111111000111000000000000012260800000000"):
    return f"""<NFSe xmlns="http://www.sped.fazenda.gov.br/nfse"><infNFSe Id="NFS{chave}">
<nNFSe>12</nNFSe><dhProc>2026-08-20T10:00:00-03:00</dhProc><cLocIncid>3550308</cLocIncid>
<emit><CNPJ>{prest}</CNPJ><xNome>PREST</xNome></emit>
<DPS><infDPS Id="DPS1"><dhEmi>2026-08-20T10:00:00-03:00</dhEmi><dCompet>2026-08-31</dCompet><cLocEmi>3550308</cLocEmi>
<prest><CNPJ>{prest}</CNPJ></prest><toma><CNPJ>{toma}</CNPJ><xNome>TOMA</xNome><end><endNac><cMun>3550308</cMun></endNac></end></toma>
<serv><cServ><cTribNac>010101</cTribNac></cServ></serv>
<valores><vServPrest><vServ>1000.00</vServ></vServPrest><trib><tribMun><tribISSQN>1</tribISSQN><tpRetISSQN>{tp_ret}</tpRetISSQN></tribMun>
<tribFed><piscofins><tpRetPisCofins>0</tpRetPisCofins></piscofins></tribFed></trib></valores>
</infDPS></DPS></infNFSe></NFSe>""".encode()


def evento_canc(chave_nfe):
    return f"""<procEventoNFe xmlns="http://www.portalfiscal.inf.br/nfe"><evento><infEvento>
<chNFe>{chave_nfe}</chNFe><dhEvento>2026-08-15T09:00:00-03:00</dhEvento><tpEvento>110111</tpEvento>
<detEvento><descEvento>Cancelamento</descEvento></detEvento></infEvento></evento></procEventoNFe>""".encode()


def chave(cnpj, mod="55", n="1"):
    return ("35" + "2608" + cnpj + mod + "001" + n.zfill(9) + "1" + "00000000" + "0")[:44].ljust(44, "0")


CH_VENDA = chave(SIMPLES, n="1")
CH_COMPRA = chave(FORN, n="2")
CH_CTE_TOMA4 = chave(TRANSP, mod="57", n="3")
CH_CTE_PART = chave(TRANSP, mod="57", n="4")


class ParserTest(unittest.TestCase):
    def test_nfe_saida_simples(self):
        d = parse_bytes(nfe(CH_VENDA, SIMPLES, "SP", PRESUMIDO, "5102", "102"))
        self.assertEqual(d["tipo"], "NF-e")
        self.assertEqual(d["competencia"], "082026")
        self.assertEqual(d["valor_total"], Decimal("100.00"))
        self.assertEqual(d["itens"][0]["tipo_cst"], "CSOSN")
        self.assertEqual(direcao_para(d, SIMPLES), "saida")
        self.assertEqual(direcao_para(d, PRESUMIDO), "entrada")

    def test_cte_toma4_identifica_tomador(self):
        toma4 = f"<toma4><toma>4</toma><CNPJ>{SIMPLES}</CNPJ></toma4>"
        d = parse_bytes(cte(CH_CTE_TOMA4, toma4, FORN, PRESUMIDO))
        self.assertEqual(d["destinatario"], SIMPLES)

    def test_cte_toma3_destinatario(self):
        d = parse_bytes(cte(CH_CTE_PART, "<toma3><toma>3</toma></toma3>", SIMPLES, FORN))
        self.assertEqual(d["destinatario"], FORN)
        self.assertEqual(direcao_para(d, SIMPLES), "entrada")  # participante, filtrado na preparação

    def test_nfse_nacional_iss_retido(self):
        d = parse_bytes(nfse(SIMPLES, PRESUMIDO))
        self.assertEqual(d["tipo"], "NFS-e Nacional")
        self.assertEqual(d["tp_ret_issqn"], "2")
        self.assertEqual(d["competencia"], "082026")  # dCompet, não a data de emissão
        self.assertEqual(direcao_para(d, SIMPLES), "prestado")

    def test_xml_invalido(self):
        self.assertEqual(parse_bytes(b"<nao fecha")["tipo"], "NAO_RECONHECIDO")


class PastasTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        r = self.tmp.name
        self.carteira = os.path.join(r, "carteira.csv")
        with open(self.carteira, "w", encoding="utf-8") as fh:
            fh.write(CARTEIRA)
        self.origem = os.path.join(r, "XML NOTAS")
        os.makedirs(os.path.join(self.origem, "86-RTX"))
        with zipfile.ZipFile(os.path.join(self.origem, "86-RTX", "agosto.zip"), "w") as z:
            z.writestr("venda.xml", nfe(CH_VENDA, SIMPLES, "SP", PRESUMIDO, "5102", "102"))
            z.writestr("canc.xml", evento_canc(CH_VENDA))
            z.writestr("compra.xml", nfe(CH_COMPRA, FORN, "MG", SIMPLES, "6102", "00", crt="3"))
            z.writestr("cte_toma4.xml", cte(CH_CTE_TOMA4, f"<toma4><toma>4</toma><CNPJ>{SIMPLES}</CNPJ></toma4>", FORN, FORN))
            z.writestr("cte_part.xml", cte(CH_CTE_PART, "<toma3><toma>3</toma></toma3>", SIMPLES, FORN))
            z.writestr("nfse.xml", nfse(SIMPLES, PRESUMIDO))
            z.writestr("julho.xml", nfe(chave(SIMPLES, n="9"), SIMPLES, "SP", FORN, "5102", "102", data="2026-07-30"))

    def tearDown(self):
        self.tmp.cleanup()

    def _quieto(self, fn, argv):
        with contextlib.redirect_stdout(io.StringIO()):
            return fn(argv)

    def test_rotinas_leiaute_dominio(self):
        dest = os.path.join(self.tmp.name, "_ROTINAS")
        res = self._quieto(rotinas.main, ["--origem", self.origem, "--destino", dest, "--carteira", self.carteira,
                                          "--competencia", "082026"])
        def existe(*p):
            return os.path.exists(os.path.join(dest, *p))
        # venda: saída da 86 e entrada da 90 (cliente que vende para cliente)
        self.assertTrue(existe("NFE-SAIDA", "86-RTX", "082026", CH_VENDA + ".xml"))
        self.assertTrue(existe("NFE-ENTRADA", "90-ALFA", "082026", CH_VENDA + ".xml"))
        self.assertTrue(existe("NFE-SAIDA", "86-RTX", "082026", CH_VENDA + "_canc.xml"))
        self.assertTrue(existe("NFE-ENTRADA", "86-RTX", "082026", CH_COMPRA + ".xml"))
        self.assertTrue(existe("CTE", "86-RTX", "082026", CH_CTE_TOMA4 + ".xml"))
        self.assertFalse(existe("CTE", "86-RTX", "082026", CH_CTE_PART + ".xml"))
        self.assertTrue(existe("NFSE-NACIONAL-PRESTADA", "86-RTX", "082026"))
        self.assertTrue(existe("NFSE-NACIONAL-TOMADA", "90-ALFA", "082026"))
        self.assertEqual(res["fora_da_competencia"], 1)
        self.assertNotIn("1-EXEMPLO LTDA", json.dumps(res))  # empresa de exemplo fora da carteira
        # idempotente
        res2 = self._quieto(rotinas.main, ["--origem", self.origem, "--destino", dest, "--carteira", self.carteira,
                                           "--competencia", "082026"])
        self.assertEqual(res2["copiados"], 0)
        self.assertEqual(res2["ja_existiam"], res["copiados"])

    def test_matriz_alertas_e_modelo(self):
        saida = os.path.join(self.tmp.name, "matriz")
        res = self._quieto(matriz.main, ["--raiz", self.origem, "--carteira", self.carteira, "--saida", saida])
        self.assertEqual(res["modelos"]["SIMPLES"], "86-RTX")
        with open(os.path.join(saida, "matriz_86.md"), encoding="utf-8") as fh:
            md = fh.read()
        self.assertIn("ISS retido pelo tomador", md)
        self.assertIn("CT-e tomado", md)
        self.assertIn("CT-e em que a empresa é remetente/destinatária", md)
        self.assertIn("Simples não toma crédito", md)


OFX_SGML = b"""OFXHEADER:100
DATA:OFXSGML
VERSION:102
CHARSET:1252

<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><CURDEF>BRL
<BANKACCTFROM><BANKID>0341<BRANCHID>1234<ACCTID>56789-0</BANKACCTFROM>
<BANKTRANLIST><DTSTART>20260801<DTEND>20260831
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20260805120000[-3:BRT]<TRNAMT>1500.00<FITID>A1<MEMO>PIX RECEBIDO CLIENTE X</STMTTRN>
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260810<TRNAMT>-35.90<FITID>A2<MEMO>TARIFA PACOTE SERVI\xc7OS</STMTTRN>
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260812<TRNAMT>-800.00<FITID>A3<CHECKNUM>778<MEMO>PAG BOLETO FORNECEDOR; LTDA</STMTTRN>
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260812<TRNAMT>-800.00<FITID>A3<MEMO>PAG BOLETO FORNECEDOR; LTDA</STMTTRN>
</BANKTRANLIST><LEDGERBAL><BALAMT>664.10<DTASOF>20260831</LEDGERBAL>
</STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>
"""

DEPARA = """padrao;sentido;conta;historico;complemento
tarifa;D;520;15;Tarifa bancária {memo}
re:^PIX RECEBIDO;C;112;1;
"""


class OfxTest(unittest.TestCase):
    def test_ler_ofx_sgml(self):
        e = ler_ofx(OFX_SGML)
        self.assertEqual(e["banco"], "0341")
        self.assertEqual(len(e["transacoes"]), 4)
        self.assertEqual(e["transacoes"][1]["memo"], "TARIFA PACOTE SERVIÇOS")
        self.assertEqual(e["transacoes"][0]["data"], "2026-08-05")

    def test_gerar_lancamentos(self):
        with tempfile.TemporaryDirectory() as r:
            dp = os.path.join(r, "depara.csv")
            with open(dp, "w", encoding="utf-8") as fh:
                fh.write(DEPARA)
            linhas, pend, tot = lancamentos.gerar(ler_ofx(OFX_SGML), lancamentos.ler_depara(dp), "7", "999")
        self.assertEqual(linhas[0], "05/08/2026;7;112;1500,00;1;PIX RECEBIDO CLIENTE X")
        self.assertEqual(linhas[1], "10/08/2026;520;7;35,90;15;Tarifa bancária TARIFA PACOTE SERVIÇOS")
        self.assertEqual(linhas[2], "12/08/2026;999;7;800,00;;PAG BOLETO FORNECEDOR LTDA")  # ';' do memo removido
        self.assertEqual(len(linhas), 3)
        self.assertEqual(tot["duplicados"], 1)
        self.assertEqual(len(pend), 1)

    def test_cli_ofx_escreve_cp1252(self):
        with tempfile.TemporaryDirectory() as r:
            ofx, dp, out = (os.path.join(r, n) for n in ("x.ofx", "d.csv", "out/l.txt"))
            with open(ofx, "wb") as fh:
                fh.write(OFX_SGML)
            with open(dp, "w", encoding="utf-8") as fh:
                fh.write(DEPARA)
            with contextlib.redirect_stdout(io.StringIO()):
                res = lancamentos.main(["--ofx", ofx, "--depara", dp, "--conta-banco", "7", "--conta-transitoria", "999",
                                        "--saida", out])
            with open(out, "rb") as fh:
                raw = fh.read()
            self.assertIn("SERVIÇOS".encode("cp1252"), raw)
            self.assertIn(b"\r\n", raw)
            self.assertEqual(res["pendentes_conta_transitoria"], 1)
            self.assertEqual(res["movimento_liquido"], "664.10")


if __name__ == "__main__":
    unittest.main()
