"""Gera um lote de demonstração (dados 100% fictícios) em exemplos/demo/lote_demo.zip.

Cenário: comércio de perfumaria/medicamentos do Simples Nacional (SP) que também presta
serviços, com 14 meses de notas, extrato OFX dos 3 últimos meses e folha para o Fator R.
Problemas típicos injetados: lacuna de numeração, nota sem protocolo, nota cancelada,
CFOP errado, retenção indevida sobre optante, ISS retido, depósitos sem nota.

Uso:  python exemplos/gerar_demo.py && python -m portal_contabil auditar exemplos/demo/lote_demo.zip
"""
from __future__ import annotations

import io
import random
import sys
import zipfile
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from portal_contabil import fabrica as fb  # noqa: E402

random.seed(42)
EMP = (fb.gerar_cnpj("123456780001"), "Comercial Exemplo Ltda", "SP")
CLIENTES = [(fb.gerar_cnpj(f"{n:08d}0001"), f"Cliente {n} Ltda", uf)
            for n, uf in ((20304050, "SP"), (30405060, "SP"), (40506070, "RJ"), (50607080, "MG"))]
TOMADOR_GRANDE = (fb.gerar_cnpj("607080900001"), "Rede Hospitalar Modelo SA", "SP")
CONTADOR = (fb.gerar_cnpj("708090100001"), "Contabilidade Parceira Ltda", "SP")
LIMPEZA = (fb.gerar_cnpj("809010200001"), "Limpeza Total Servicos SA", "SP")
PRODUTOS = [("30049099", "Medicamento genérico"), ("33049910", "Creme hidratante"),
            ("33051000", "Shampoo"), ("84713012", "Notebook"), ("85176277", "Roteador")]


def meses():
    d = date(2025, 10, 1)
    while d <= date(2026, 11, 1):
        yield d
        d = (d + timedelta(days=32)).replace(day=1)


def gerar() -> bytes:
    buf = io.BytesIO()
    z = zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED)
    numero, nfse_num = 1000, 1
    recebiveis = []  # (data, valor) para montar o extrato

    for m in meses():
        pasta = f"{m:%Y-%m}"
        for _ in range(random.randint(10, 14)):
            numero += 1
            if numero in (1037, 1038):  # lacuna: notas não enviadas ao escritório
                continue
            dia = m + timedelta(days=random.randint(0, 26))
            cli = random.choice(CLIENTES)
            itens = []
            for _ in range(random.randint(1, 3)):
                ncm, desc = random.choice(PRODUTOS)
                mono = ncm[:4] in ("3004", "3304", "3305")
                cfop = ("5" if cli[2] == "SP" else "6") + ("405" if mono else "102")
                itens.append({"ncm": ncm, "descricao": desc, "cfop": cfop,
                              "valor": f"{random.randint(800, 9000)}.{random.randint(0, 99):02d}",
                              "csosn": "500" if mono else "102"})
            if numero == 1050:  # CFOP de entrada numa nota de saída
                itens[0]["cfop"] = "1102"
            xml = fb.nfe_xml(numero, dia, EMP, cli, itens, protocolo=(numero != 1061))
            z.writestr(f"{pasta}/NFe_{numero}.xml", xml)
            if numero == 1072:
                chave = fb.gerar_chave("SP", dia, EMP[0], "55", 1, numero)
                z.writestr(f"{pasta}/Canc_{numero}.xml", fb.evento_cancelamento_xml(chave, dia + timedelta(days=1)))
            elif numero != 1061:
                total = sum(Decimal(i["valor"]) for i in itens)
                recebiveis.append((dia + timedelta(days=random.choice([0, 7, 14, 28])), total))

        # serviços prestados (NFS-e nacional)
        for _ in range(2):
            dia = m + timedelta(days=random.randint(1, 25))
            valor = Decimal(random.randint(3000, 12000))
            if nfse_num % 4 == 0:  # hospital retém tributos federais de um optante (indevido) e o ISS
                ret = {"irrf": valor * Decimal("0.015"), "pis": valor * Decimal("0.0065"),
                       "cofins": valor * Decimal("0.03"), "csll": valor * Decimal("0.01")}
                ret = {k: v.quantize(Decimal("0.01")) for k, v in ret.items()}
                xml = fb.nfse_nacional_xml(nfse_num, dia, EMP, TOMADOR_GRANDE, valor, iss_retido=True, **ret)
                liquido = valor - sum(ret.values()) - (valor * Decimal("0.02")).quantize(Decimal("0.01"))
            else:
                xml = fb.nfse_nacional_xml(nfse_num, dia, EMP, random.choice(CLIENTES), valor)
                liquido = valor
            z.writestr(f"{pasta}/NFSe_{nfse_num}.xml", xml)
            recebiveis.append((dia + timedelta(days=10), liquido))
            nfse_num += 1

        # serviços tomados
        z.writestr(f"{pasta}/Tomada_contabil_{m:%m%y}.xml",
                   fb.nfse_nacional_xml(int(f"9{m:%y%m}"), m + timedelta(days=4), CONTADOR, EMP, "1800"))
        z.writestr(f"{pasta}/Tomada_limpeza_{m:%m%y}.xml",
                   fb.nfse_nacional_xml(int(f"8{m:%y%m}"), m + timedelta(days=6), LIMPEZA, EMP, "4200",
                                        op_simples="1"))

    # extrato de set-nov/2026
    ini = date(2026, 9, 1)
    lanc = [(d, f"{v:.2f}", "PIX RECEBIDO" if i % 2 else "LIQUIDACAO COBRANCA")
            for i, (d, v) in enumerate(recebiveis) if ini <= d <= date(2026, 11, 30)]
    lanc += [(ini, "-1250.00", "PAGTO FORNECEDOR"), (date(2026, 9, 15), "8500.00", "DEPOSITO EM DINHEIRO"),
             (date(2026, 10, 3), "30000.00", "EMPRESTIMO SOCIO JOAO"), (date(2026, 10, 20), "4730.00", "TED RECEBIDA"),
             (date(2026, 11, 8), "12000.00", "PIX RECEBIDO FULANO"), (date(2026, 11, 12), "6420.55", "CIELO VENDAS"),
             (date(2026, 11, 30), "-89.90", "TARIFA PACOTE")]
    z.writestr("banco/extrato_set_nov_2026.ofx", fb.ofx(lanc))

    folha = [(f"{m:%m/%Y}", 4200, 1518, 1350) for m in meses()]
    z.writestr("folha/resumo_folha.csv", fb.folha_csv(folha))
    z.close()
    return buf.getvalue()


if __name__ == "__main__":
    destino = Path(__file__).parent / "demo" / "lote_demo.zip"
    destino.parent.mkdir(exist_ok=True)
    destino.write_bytes(gerar())
    print(f"Lote de demonstração gerado em {destino}")
