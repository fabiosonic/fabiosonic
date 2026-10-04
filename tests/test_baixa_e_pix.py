"""Pagamento → NFS-e na hora (banco, extrato ou baixa manual) e PIX copia e cola só quando o boleto não vai junto."""

from datetime import date

from nfse_itaborai import cobranca, config, emissor, financeiro, inter
from test_emissor import ambiente  # noqa: F401  (fixture)
from test_financeiro import CLI_A, base  # noqa: F401  (fixture)


def _producao(monkeypatch):
    emitidas = []

    def emitir(tid, url=None):
        emitidas.append(tid)
        financeiro.atualizar_titulo(tid, nfse_status="emitida", nfse_numero=f"2026{tid:06d}")
        return {"sucesso": True, "erros": [], "titulo": financeiro.obter_titulo(tid)}
    monkeypatch.setattr(emissor, "em_producao", lambda: True)
    monkeypatch.setattr(financeiro, "emitir_nfse_titulo", emitir)
    return emitidas


def test_boleto_pago_no_inter_emite_a_nota_na_hora(base, monkeypatch):  # noqa: F811
    emitidas = _producao(monkeypatch)
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "500", vencimento="2026-10-10", emitir_nfse=False)
    financeiro.atualizar_titulo(tid, nfse_status="apos_pagamento", banco_id="cod-inter-1")
    monkeypatch.setattr(inter, "consultar", lambda codigo, cfg=None: {"pago": True, "baixado": False, "situacao": "RECEBIDO",
                                                                    "data_pagamento": "2026-10-08", "valor_pago": "500.00"})
    assert cobranca.sincronizar_banco() == 1
    t = financeiro.obter_titulo(tid)
    assert emitidas == [tid] and (t["status"], t["nfse_status"], t["forma_pagamento"]) == ("pago", "emitida", "inter")


def test_baixa_manual_emite_a_nota_e_avisa(base, monkeypatch):  # noqa: F811
    emitidas = _producao(monkeypatch)
    a = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "300", vencimento="2026-10-10", emitir_nfse=False)
    b = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "200", vencimento="2026-10-10", emitir_nfse=False)
    financeiro.atualizar_titulo(a, nfse_status="apos_pagamento")
    financeiro.atualizar_titulo(b, nfse_status="pendente")              # nota que ainda não tinha saído
    r = financeiro.baixar(a, "2026-10-05", "300", "pix")
    assert r["nfse_resultado"] == f"NFS-e nº 2026{a:06d} emitida." and r["nfse_status"] == "emitida"
    financeiro.baixar(b, "2026-10-05", "200", "dinheiro")
    assert emitidas == [a, b]
    c = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "100", vencimento="2026-10-10", emitir_nfse=False)
    financeiro.atualizar_titulo(c, nfse_status="nao_emitir")
    assert financeiro.baixar(c, "2026-10-05", "100")["nfse_resultado"] == "" and emitidas == [a, b]


def test_baixa_em_homologacao_deixa_a_nota_pendente(base, monkeypatch):  # noqa: F811
    monkeypatch.setattr(emissor, "em_producao", lambda: False)
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "300", vencimento="2026-10-10", emitir_nfse=False)
    financeiro.atualizar_titulo(tid, nfse_status="apos_pagamento")
    r = financeiro.baixar(tid, "2026-10-05", "300", "pix")
    assert r["nfse_status"] == "pendente" and "homologação" in r["nfse_resultado"]


def _titulo(**k):
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "500", vencimento="2026-10-20", emitir_nfse=False)
    financeiro.atualizar_titulo(tid, pix_copia_cola="000201PIXCOPIAECOLA", linha_digitavel="07790.00116 1", **k)
    return financeiro.obter_titulo(tid)


def test_pix_copia_e_cola_so_sem_o_boleto(base):  # noqa: F811
    cfg = config.carregar()
    t = _titulo(banco_id="cod-inter-2")                                  # boleto do Inter: o PDF traz o QR Code
    texto = cobranca.mensagem(t, -3, cfg, date(2026, 10, 17))[1]
    assert "000201PIXCOPIAECOLA" not in texto and "QR Code do PIX impresso no boleto" in texto and "07790.00116 1" in texto
    assert "000201PIXCOPIAECOLA" not in cobranca.mensagem_html(t, -3, cfg, date(2026, 10, 17))
    cfg["cobranca"]["whatsapp_web"] = True                                       # WhatsApp automático conectado
    zap = cobranca.mensagem(t, -3, cfg, date(2026, 10, 17), "whatsapp")[1]
    assert "000201PIXCOPIAECOLA" not in zap and "vai logo a seguir" in zap          # WhatsApp automático manda o PDF
    cfg["cobranca"]["whatsapp_web"] = False                                      # link manual: sem PDF, vai o PIX
    assert "000201PIXCOPIAECOLA" in cobranca.mensagem(t, -3, cfg, date(2026, 10, 17), "whatsapp")[1]
    cfg = config.carregar()
    cfg["cobranca"]["pix_nas_mensagens"] = True                                  # opção ligada: repete o PIX
    assert "000201PIXCOPIAECOLA" in cobranca.mensagem(t, -3, cfg, date(2026, 10, 17))[1]
    so_pix = _titulo()                                                           # PIX avulso (sem boleto)
    assert "000201PIXCOPIAECOLA" in cobranca.mensagem(so_pix, -3, config.carregar(), date(2026, 10, 17))[1]
