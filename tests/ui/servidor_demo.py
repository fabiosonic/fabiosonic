"""Sobe a tela com uma carteira de DEMONSTRAÇÃO (15 meses de honorários, pagamentos, atrasos e despesas) para revisar
o visual dos painéis e relatórios com dados realistas. Nada sai do computador.

Uso: python tests/ui/servidor_demo.py <pasta_temporaria> <porta>
"""

import os
import random
import sys
from datetime import date, timedelta
from http.server import ThreadingHTTPServer
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RAIZ), str(RAIZ / "tests")]

pasta, porta = Path(sys.argv[1]), int(sys.argv[2])
pasta.mkdir(parents=True, exist_ok=True)
(pasta / ".env").write_text("ITABORAI_CNPJ=24875410000144\nITABORAI_IM=1034265\nITABORAI_CHAVE=chave-de-teste-123\n"
                            "ITABORAI_PROXIMO_RPS=3509\nITABORAI_AMBIENTE=homologacao\n", encoding="utf-8")
os.environ.update({"ITABORAI_PASTA": str(pasta), "NFSE_CHAVE_LOCAL": str(pasta / "chave_local.bin")})

from nfse_itaborai import clientes, config, db, emissor, financeiro, tela  # noqa: E402

emissor.BASE = pasta
emissor.RAIZ = emissor._Raiz(pasta)
rnd = random.Random(7)
HOJE = financeiro.hoje()

config.salvar({"empresa": {"nome": "MORAES & OLIVEIRA CONTABILIDADE", "pix_chave": "24.875.410/0001-44"},
               "cobranca": {"provedor": "pix"}, "automacao": {"ativa": True}})

CARTEIRA = [("RPS CONSULTORIA E SERVICOS DE ENGENHARIA LTDA", 4800), ("PORTAL RESOLVE ATIVIDADES DE INTERNET LTDA", 2350),
            ("ESPACO CULTIVAR FONOAUDIOLOGIA LTDA", 980), ("CONSTRUTORA ALVORADA DO LESTE LTDA", 3900),
            ("PADARIA PAO DOURADO DE ITABORAI LTDA", 1200), ("CLINICA ODONTOLOGICA SORRISO PLENO LTDA", 1650),
            ("TRANSPORTES RIO BONITO LTDA", 2900), ("MERCADINHO BOA VIZINHANCA LTDA", 850),
            ("AUTO PECAS VENEZA LTDA", 1450), ("ACADEMIA CORPO EM FORMA LTDA", 760),
            ("ESCRITORIO DE ADVOCACIA LIMA E SOUZA", 1890), ("FARMACIA SAO JOSE DE ITABORAI LTDA", 1320),
            ("LABORATORIO ANALISE CERTA LTDA", 2100), ("RESTAURANTE SABOR DA SERRA LTDA", 940),
            ("IMOBILIARIA PORTO SEGURO LTDA", 1580), ("TECH SOLUCOES EM TI LTDA", 2650),
            ("CERAMICA ITABORAI INDUSTRIA LTDA", 3400), ("ESCOLA PEQUENO SABER LTDA", 1100)]
# perfil de pagamento: (probabilidade de atrasar, atraso máximo em dias, deixa de pagar os últimos N meses)
PERFIS = {2: (0.5, 25, 0), 4: (0.3, 12, 0), 7: (0.6, 40, 3), 9: (0.4, 20, 1), 13: (0.7, 35, 2), 11: (0.2, 8, 0)}


def mes_ant(d: date, k: int) -> date:
    a, m = d.year, d.month - k
    while m <= 0:
        a, m = a - 1, m + 12
    return date(a, m, 1)


for i, (nome, valor) in enumerate(CARTEIRA):
    doc = f"{11222333 + i * 7919:08d}0001{(i * 37) % 90 + 10:02d}"
    clientes.salvar({"cpf_cnpj": doc, "razao_social": nome, "email": f"financeiro{i}@cliente.teste",
                     "telefone": f"2198{i:03d}7777", "endereco": {"logradouro": "RUA DEMONSTRACAO", "numero": str(10 + i),
                                                                 "bairro": "Centro", "codigo_municipio": "3301900",
                                                                 "cep": "24800000"}})
    inicio = 15 if i < 12 else rnd.randint(4, 12)              # clientes novos entram depois (crescimento)
    k = financeiro.salvar_contrato({"cpf_cnpj": doc, "valor": f"{valor},00", "dia_vencimento": 10,
                                    "inicio": mes_ant(HOJE, inicio).isoformat()[:7]})
    with db.conexao() as con:
        con.execute("UPDATE contratos SET confirmado=1")
    prob, maximo, calote = PERFIS.get(i, (0.1, 5, 0))
    for m in range(inicio, -1, -1):
        comp = mes_ant(HOJE, m)
        venc = comp.replace(day=10)
        v = valor * (1.08 if comp.year == HOJE.year and comp.month >= 3 else 1)          # reajuste anual
        tid = financeiro.criar_titulo(doc, f"{v:.2f}".replace(".", ","), "HONORARIOS CONTABEIS",
                                      vencimento=venc.isoformat(), competencia=comp.isoformat()[:7], emitir_nfse=False)
        financeiro.atualizar_titulo(tid, nfse_status="emitida", nfse_numero=f"2026{tid:07d}",
                                    pix_copia_cola="000201demo", nfse_data=venc.replace(day=1).isoformat())
        if m < calote:
            continue
        if venc > HOJE:                                    # mês corrente: parte dos clientes paga antes do vencimento
            if rnd.random() < .45:
                financeiro.baixar(tid, (HOJE - timedelta(days=rnd.randint(0, HOJE.day - 1))).isoformat(), None, "pix")
            continue
        atraso = rnd.randint(1, maximo) if rnd.random() < prob else -rnd.randint(0, 4)
        pago = venc + timedelta(days=atraso)
        if pago <= HOJE and not (m == 0 and rnd.random() < 0.5):
            financeiro.baixar(tid, pago.isoformat(), None, "pix")

DESPESAS = [("Aluguel da sala", "Ocupação", 3200), ("Folha de pagamento", "Pessoal", 14500), ("Encargos (INSS/FGTS)", "Pessoal", 4300),
            ("Sistema contábil", "Tecnologia", 1290), ("Internet e telefonia", "Tecnologia", 420),
            ("DAS - Simples Nacional", "Tributos", 2400), ("Energia elétrica", "Ocupação", 610),
            ("Pró-labore", "Pessoal", 6000), ("Contador parceiro (DP)", "Serviços", 1800)]
for m in range(15, -1, -1):
    comp = mes_ant(HOJE, m)
    for desc, cat, v in DESPESAS:
        venc = comp.replace(day=rnd.choice([5, 10, 20]))
        did = financeiro.salvar_despesa({"descricao": desc, "categoria": cat, "valor": f"{v * rnd.uniform(.93, 1.07):.2f}".replace(".", ","),
                                         "vencimento": venc.isoformat(), "fornecedor": desc})
        if venc < HOJE - timedelta(days=2) or (venc <= HOJE and rnd.random() < .5):
            financeiro.pagar_despesa(did, venc.isoformat())

srv = ThreadingHTTPServer(("127.0.0.1", porta), tela._Handler)
print("pronto", flush=True)
srv.serve_forever()
