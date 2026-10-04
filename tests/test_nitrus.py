"""Importação do relatório de Inadimplência do Nitrus (PDF) para o contas a receber.

O PDF de teste é montado aqui, no mesmo leiaute do Nitrus (colunas, nome e contato quebrados em várias linhas,
código do cliente numa linha própria), com clientes fictícios."""

import base64

import pytest

pypdf = pytest.importorskip("pypdf")

from nfse_itaborai import clientes, db, financeiro, nitrus  # noqa: E402
from test_emissor import ambiente  # noqa: F401,E402  (fixture)
from test_financeiro import CLI_A, base  # noqa: F401,E402  (fixture)


def _pdf(paginas: list[list[tuple[float, float, str]]]) -> bytes:
    """PDF mínimo com textos em posições fixas (Helvetica), uma lista de (x, y, texto) por página."""
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", None, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"]
    kids = []
    for itens in paginas:
        txt = "".join(f"BT /F1 7 Tf 1 0 0 1 {x} {y} Tm ({t.replace('(', chr(92) + '(').replace(')', chr(92) + ')')}) Tj ET\n"
                      for x, y, t in itens).encode("latin-1")
        objs.append(f"<< /Length {len(txt)} >>\nstream\n".encode() + txt + b"endstream")
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> "
                    f"/Contents {len(objs)} 0 R >>")
        kids.append(len(objs))
    objs[1] = f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count {len(kids)} >>"
    out, pos = bytearray(b"%PDF-1.4\n"), []
    for i, o in enumerate(objs, 1):
        pos.append(len(out))
        out += f"{i} 0 obj\n".encode() + (o if isinstance(o, bytes) else o.encode("latin-1")) + b"\nendobj\n"
    x = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode() + "".join(f"{p:010d} 00000 n \n" for p in pos).encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF".encode()
    return bytes(out)


CAB = [(249, 736, "Inadimplência"), (171, 695, "Total Original: R$ 1.560,00     Juros e Multa: R$ 39,30     Total a Receber: R$ 1.599,30"),
       (15.6, 640, "Cliente/Código"), (146, 640, " Contato"), (254.7, 640, " Vencimento"), (327.3, 640, " Valor Original"),
       (401.6, 640, " Juros e Multa"), (468.6, 640, " D. Atraso"), (532.3, 640, " Valor Total")]


def _linha(y, nome: list[str], contato: list[str], venc, valor, juros, dias, total):
    out = [(15.6, y + 5.5 - 11.5 * i, t) for i, t in enumerate(nome)] + [(146, y + 5.5 - 11.5 * i, t) for i, t in enumerate(contato)]
    return out + [(256.1, y, venc), (341.7, y, f" R$ {valor}"), (421, y, f" R$ {juros}"), (486.7, y, f" {dias}"), (534.5, y, f" R$ {total}")]


def relatorio() -> bytes:
    p1 = CAB + _linha(612, ["RPS CONSULTORIA E SERVICOS DE", "ENGENHARIA LTDA(134)"], ["fin@rps.co", "m.br", "(21) 98888-7777"],
                      "30/09/2026", "374,40", "7,86", "3", "382,26") \
        + _linha(560, ["Clinica Nova Vida Ltda(1201)"], ["contato@novavida.co", "m", "(21) 97777-6666"],
                 "10/09/2026", "800,00", "21,44", "23", "821,44") + [(567, 20, "1/2"), (18, 18, "nitrus")]
    p2 = CAB + _linha(612, ["Clinica Nova Vida Ltda", "(1201)"], ["contato@novavida.co", "m", "(21) 97777-6666"],
                      "10/08/2026", "385,60", "10,00", "54", "395,60") + [(15.6, 560, "Total de Registros: 3"), (567, 20, "2/2")]
    return _pdf([p1, p2])


def test_le_o_relatorio_e_confere_com_os_totais():
    r = nitrus.ler_inadimplencia(relatorio())
    assert r["conferido"] and r["lidos"] == {"original": 156000, "juros": 3930, "total": 159930}
    a, b, c = r["linhas"]
    assert (a["codigo"], a["nome"], a["email"], a["telefone"]) == ("134", "RPS CONSULTORIA E SERVICOS DE ENGENHARIA LTDA",
                                                                   "fin@rps.com.br", "(21) 98888-7777")
    assert (a["vencimento"], a["valor_cent"], a["juros_cent"], a["dias"], a["total_cent"]) == ("2026-09-30", 37440, 786, 3, 38226)
    assert (b["codigo"], b["nome"], b["email"]) == ("1201", "Clinica Nova Vida Ltda", "contato@novavida.com")
    assert (c["codigo"], c["vencimento"], c["valor_cent"]) == ("1201", "2026-08-10", 38560)    # código na linha de baixo


def test_rejeita_outro_relatorio():
    with pytest.raises(nitrus.ErroNitrus):
        nitrus.ler_inadimplencia(_pdf([[(100, 700, "Relação de Recebimentos")]]))


def test_analisa_lanca_com_nfse_no_pagamento_e_nao_duplica(base):  # noqa: F811
    b64 = base64.b64encode(relatorio()).decode()
    a = nitrus.analisar(b64)
    rps, nova = a["grupos"][1], a["grupos"][0]           # sem cadastro vem primeiro
    assert rps["cpf_cnpj"] == CLI_A["cpf_cnpj"] and nova["cpf_cnpj"] == "" and nova["motivo"] == "não encontrado no cadastro"
    assert len(nova["titulos"]) == 2 and a["conferido"]
    nova["cnpj_novo"] = "11.222.333/0001-81"
    r = nitrus.lancar(a["grupos"])
    assert (r["lancados"], r["clientes_novos"], r["ja_existiam"]) == (3, 1, 0)
    c = clientes.obter("11222333000181")
    assert c["razao_social"] == "CLINICA NOVA VIDA LTDA" and c["email"] == "contato@novavida.com" and c["codigo_externo"] == "1201"
    assert clientes.obter(CLI_A["cpf_cnpj"])["endereco"]["logradouro"] == CLI_A["endereco"]["logradouro"]   # cadastro intacto
    assert clientes.obter(CLI_A["cpf_cnpj"])["codigo_externo"] == "134"
    ts = db.linhas("SELECT * FROM titulos ORDER BY vencimento")
    assert len(ts) == 3 and all(t["nfse_status"] == "apos_pagamento" and t["cobrar"] == 1 and t["boleto_situacao"] == "dispensado"
                                and not t["banco_id"] for t in ts)
    t = financeiro.enriquecer(next(x for x in ts if x["valor_cent"] == 37440), financeiro.hoje().replace(year=2026, month=10, day=3))
    assert t["situacao"] == "atrasado" and t["dias_atraso"] == 3 and t["competencia"] == "2026-09"
    # segunda importação: tudo já existe; o cliente novo agora é achado pelo código do Nitrus
    a2 = nitrus.analisar(b64)
    assert all(g["cpf_cnpj"] for g in a2["grupos"]) and all(t["existe"] for g in a2["grupos"] for t in g["titulos"])
    assert nitrus.lancar(a2["grupos"])["lancados"] == 0


def test_cnpj_invalido_nao_lanca(base):  # noqa: F811
    a = nitrus.analisar(base64.b64encode(relatorio()).decode())
    a["grupos"][0]["cnpj_novo"] = "11.222.333/0001-00"
    r = nitrus.lancar([a["grupos"][0]])
    assert r["lancados"] == 0 and "inválido" in r["avisos"][0]


def test_sem_cobranca_so_controla(base):  # noqa: F811
    a = nitrus.analisar(base64.b64encode(relatorio()).decode())
    r = nitrus.lancar([a["grupos"][1]], cobrar=False)
    t = db.linhas("SELECT * FROM titulos")[0]
    assert r["lancados"] == 1 and t["cobrar"] == 0 and not t["pix_copia_cola"]


def test_reimportar_recoloca_em_cobranca_o_que_estava_fora(base):  # noqa: F811
    """Caso real: títulos lançados antes sem meio de pagamento ou tirados da cobrança não apareciam em Atrasados.
    Reimportar o relatório mostra o estado de cada um e recoloca em cobrança os que estavam fora; pagos ficam."""
    from datetime import date

    from nfse_itaborai import financeiro as fin
    clientes.salvar({"cpf_cnpj": "11222333000181", "razao_social": "CLINICA NOVA VIDA LTDA", "codigo_externo": "1201"})
    pdf = base64.b64encode(relatorio()).decode()
    a = nitrus.analisar(pdf)
    rps = next(x for x in a["grupos"] if x["cpf_cnpj"] == CLI_A["cpf_cnpj"])["titulos"][0]
    nova = next(x for x in a["grupos"] if x["cpf_cnpj"] == "11222333000181")["titulos"][0]
    # rps: lançado à mão, sem boleto e fora da cobrança (cobrar=0); nova: lançado e pago
    a1 = fin.criar_titulo(CLI_A["cpf_cnpj"], fin.reais(rps["valor_cent"]), nitrus.DESCRICAO, vencimento=rps["vencimento"],
                          emitir_nfse=False, cobrar=False)
    a2 = fin.criar_titulo("11222333000181", fin.reais(nova["valor_cent"]), nitrus.DESCRICAO, vencimento=nova["vencimento"],
                          emitir_nfse=False)
    fin.baixar(a2, "2026-10-01", fin.reais(nova["valor_cent"]), "pix")
    a = nitrus.analisar(pdf)
    estados = {t["vencimento"]: t["estado"] for g in a["grupos"] for t in g["titulos"]}
    assert estados[rps["vencimento"]] == "fora" and estados[nova["vencimento"]] == "pago"
    assert a["situacao"] == {"novos": 1, "em_cobranca": 0, "fora_da_cobranca": 1, "pagos": 1}
    assert fin.situacao(fin.obter_titulo(a1), date(2026, 10, 5)) == "sem_cobranca"
    r = nitrus.lancar(a["grupos"])
    assert (r["recolocados"], r["lancados"], r["ja_existiam"]) == (1, 1, 2)
    t = fin.obter_titulo(a1)
    assert (t["cobrar"], t["boleto_situacao"], t["nfse_status"]) == (1, "dispensado", "apos_pagamento")
    assert fin.situacao(t, date(2026, 10, 5)) == "atrasado"
    assert fin.obter_titulo(a2)["status"] == "pago"                       # pago não é mexido
    atras = [x["id"] for x in fin.listar_titulos("atrasado", em=date(2026, 10, 5))]
    assert a1 in atras and len(atras) == 2                                # todos os do relatório em cobrança, menos o pago
    assert nitrus.lancar(nitrus.analisar(pdf)["grupos"])["recolocados"] == 0   # segunda vez: nada a fazer
