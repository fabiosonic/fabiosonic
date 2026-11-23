"""Tabelas de referência usadas pelas regras.

ATENÇÃO: as listas de NCM são uma referência inicial. A incidência monofásica
depende do código NCM completo e, às vezes, de "Ex" da TIPI; valide antes de
retificar PGDAS-D ou pedir restituição.
"""
from decimal import Decimal

# CFOPs (3 últimos dígitos) que geram receita bruta de venda/serviço.
SUFIXOS_CFOP_RECEITA = {
    *(f"{n:03d}" for n in range(101, 126)),  # vendas de produção/mercadoria
    "401", "402", "403", "404", "405",       # vendas com ST
    "501", "502",                            # vendas com fim específico de exportação
    "651", "652", "653", "654", "655", "656", "667",  # combustíveis
    "932", "933",                            # prestação de serviço (ISS) em NF-e conjugada
}

# Devoluções de venda (entrada) que reduzem a receita bruta.
CFOP_DEVOLUCAO_VENDA_ENTRADA = {"1201", "1202", "1203", "1204", "1410", "1411",
                                "2201", "2202", "2203", "2204", "2410", "2411",
                                "3201", "3202"}
# As mesmas devoluções vistas na nota emitida pelo cliente (devolução de compra).
CFOP_DEVOLUCAO_VENDA_SAIDA_CLIENTE = {"5201", "5202", "5410", "5411",
                                      "6201", "6202", "6410", "6411"}

# Prefixos de NCM com PIS/COFINS concentrado (monofásico).
NCM_MONOFASICO = {
    "2710": "Combustíveis derivados de petróleo (Lei 9.718/1998)",
    "2711": "GLP / gás (Lei 9.718/1998)",
    "2207": "Álcool etílico (Lei 9.718/1998)",
    "3003": "Medicamentos (Lei 10.147/2000)",
    "3004": "Medicamentos (Lei 10.147/2000)",
    "3303": "Perfumes (Lei 10.147/2000)",
    "3304": "Maquiagem / cuidados da pele (Lei 10.147/2000)",
    "3305": "Preparações capilares (Lei 10.147/2000)",
    "3306": "Higiene bucal (Lei 10.147/2000)",
    "3307": "Barbear / desodorantes (Lei 10.147/2000)",
    "34011190": "Sabões de toucador (Lei 10.147/2000)",
    "34012010": "Sabões de toucador (Lei 10.147/2000)",
    "96032100": "Escovas de dentes (Lei 10.147/2000)",
    "4011": "Pneus novos (Lei 10.485/2002)",
    "4013": "Câmaras de ar (Lei 10.485/2002)",
    "8708": "Autopeças (Lei 10.485/2002)",
    "2201": "Águas (Lei 13.097/2015 - bebidas frias)",
    "2202": "Refrigerantes/bebidas não alcoólicas (Lei 13.097/2015)",
    "2203": "Cervejas (Lei 13.097/2015)",
    "21069010": "Preparações para bebidas (Lei 13.097/2015)",
}

CSOSN_ST_RETIDO_ANTERIORMENTE = {"500"}

LIMITE_SIMPLES = Decimal("4800000")
SUBLIMITE_SIMPLES = Decimal("3600000")
LIMITE_MEI = Decimal("81000")
TOLERANCIA_EXCESSO = Decimal("1.2")  # 20%
FATOR_R_MINIMO = Decimal("0.28")

# Créditos bancários que normalmente não são receita (exigem lastro, não nota).
PALAVRAS_NAO_OPERACIONAL = ("RESGATE", "APLICACAO", "APLIC ", "RENDIMENTO", "REND PAGO",
                            "ESTORNO", "EMPRESTIMO", "FINANCIAMENTO", "MUTUO", "APORTE",
                            "INTEGRALIZACAO", "CAPITAL", "MESMA TITULARIDADE",
                            "ENTRE CONTAS", "TRANSF PROPRIA", "SALDO")
PALAVRAS_ADQUIRENTE = ("CIELO", "REDE ", "REDECARD", "STONE", "GETNET", "PAGSEGURO",
                       "PAGBANK", "SUMUP", "MERCADO PAGO", "MERCADOPAGO", "SAFRAPAY",
                       "TON ", "INFINITEPAY", "VERO")
