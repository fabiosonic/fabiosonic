"""Um boleto por título: a régua reenvia sempre o mesmo (cada registro no banco tem custo). Se o banco o derrubar
(prazo após o vencimento acabou), não se registra outro: as mensagens passam a levar o PIX do escritório."""

from datetime import date

from nfse_itaborai import automacao, cobranca, config, db, financeiro, inter
from test_emissor import ambiente  # noqa: F401  (fixture)
from test_financeiro import CLI_A, base  # noqa: F401  (fixture)


def _inter(monkeypatch, situacao="A_RECEBER"):
    registros = []

    def criar(t, cfg=None, espera=0, atualizado=None):
        registros.append(t["id"])
        return {"banco_id": f"cod-{t['id']}-{len(registros)}", "linha_digitavel": "07790.00116 1",
                "pix_copia_cola": "000201PIXDOBOLETO", "nosso_numero": "123"}
    monkeypatch.setattr(inter, "configurado", lambda cfg=None: True)
    monkeypatch.setattr(inter, "criar_cobranca", criar)
    monkeypatch.setattr(inter, "consultar", lambda cod, cfg=None: {"pago": False, "baixado": situacao in inter.BAIXADOS,
                                                                  "situacao": situacao})
    monkeypatch.setattr(cobranca, "salvar_boleto", lambda tid, cfg=None, refazer=False: "")
    monkeypatch.setattr(cobranca, "enviar_email", lambda *a, **k: None)
    config.salvar({"cobranca": {"provedor": "inter"}, "empresa": {"pix_chave": "24875410000144"}})
    return registros


def test_regua_reenvia_o_mesmo_boleto_sem_registrar_outro(base, monkeypatch):  # noqa: F811
    registros = _inter(monkeypatch)
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "500", vencimento="2026-08-10", emitir_nfse=False)
    cobranca.preparar_pagamento(tid)
    banco = financeiro.obter_titulo(tid)["banco_id"]
    for dia in (1, 3, 13, 23):                                     # meses de atraso, várias rodadas da régua
        cobranca.preparar_pagamento(tid)
        cobranca.rodar_regua(date(2026, 10, dia))
    assert registros == [tid] and financeiro.obter_titulo(tid)["banco_id"] == banco


def test_boleto_expirado_nao_e_refeito_e_a_cobranca_segue_pelo_pix(base, monkeypatch):  # noqa: F811
    registros = _inter(monkeypatch, "EXPIRADO")
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "500", vencimento="2026-07-10", emitir_nfse=False)
    cobranca.preparar_pagamento(tid)
    cobranca.sincronizar_banco()
    t = financeiro.obter_titulo(tid)
    assert t["boleto_situacao"] == "expirado"
    cobranca.preparar_pagamento(tid)                               # nada de boleto novo
    assert registros == [tid] and not db.linhas(
        "SELECT 1 FROM titulos WHERE status='aberto' AND cobrar=1 AND banco_id=''")   # o robô também não refaz
    assert cobranca._pdf_boleto(t, config.carregar()) == ""        # o PDF expirado não vai mais
    texto = cobranca.mensagem(t, 13, config.carregar(), date(2026, 10, 1))[1]
    assert "expirou no banco" in texto and "07790.00116 1" not in texto and "000201PIXDOBOLETO" not in texto
    assert "br.gov.bcb.pix" in texto.lower()                       # PIX da chave do escritório (valor atualizado)
    n = len(db.linhas("SELECT 1 FROM log WHERE mensagem LIKE '%EXPIRADO no Inter%'"))
    cobranca.sincronizar_banco()
    assert len(db.linhas("SELECT 1 FROM log WHERE mensagem LIKE '%EXPIRADO no Inter%'")) == n   # registra uma vez


def test_inadimplencia_antiga_do_nitrus_passa_a_emitir_no_pagamento(base):  # noqa: F811
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "300", "HONORÁRIOS CONTABEIS MENSAIS.", vencimento="2026-05-15",
                                  emitir_nfse=False)
    outro = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "300", "OUTRO SERVICO", vencimento="2026-05-15", emitir_nfse=False)
    with db.conexao() as con:
        con.execute("PRAGMA user_version=2")
        db._migrar(con)
    assert financeiro.obter_titulo(tid)["nfse_status"] == "apos_pagamento"
    assert financeiro.obter_titulo(outro)["nfse_status"] == "nao_emitir"


_ = automacao
