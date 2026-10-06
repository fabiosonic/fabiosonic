"""Cliente com mais de um e-mail e mais de um WhatsApp: todas as mensagens vão para todos."""

from datetime import date

from nfse_itaborai import clientes, cobranca, financeiro, whatsapp_web
from nfse_itaborai.tela import tratar
from test_emissor import ambiente  # noqa: F401  (fixture)
from test_financeiro import CLI_A, base  # noqa: F401  (fixture)


def _extras():
    return clientes.salvar(CLI_A | {"email": "fin@rps.com.br", "emails_extras": "socio@rps.com.br; FIN@rps.com.br",
                                    "whatsapps_extras": "(21) 97777-6666; 21988887777"})


def test_cadastro_guarda_e_valida_os_contatos_adicionais(base):  # noqa: F811
    c = _extras()
    assert c["emails_extras"] == ["socio@rps.com.br", "fin@rps.com.br"]
    assert clientes.emails(c) == ["fin@rps.com.br", "socio@rps.com.br"]             # sem repetir o principal
    assert clientes.whatsapps(c) == ["21988887777", "21977776666"]
    assert "inválido" in tratar("cliente/salvar", CLI_A | {"emails_extras": "socio@"})["erro"]
    assert "inválido" in tratar("cliente/salvar", CLI_A | {"whatsapps_extras": "123"})["erro"]
    clientes.salvar({k: v for k, v in CLI_A.items()} | {"razao_social": "RPS NOVA"})   # importação sem os campos
    assert clientes.obter(CLI_A["cpf_cnpj"])["emails_extras"] == ["socio@rps.com.br", "fin@rps.com.br"]


def test_cobranca_vai_para_todos_os_emails_e_whatsapp(base, monkeypatch):  # noqa: F811
    _extras()
    env = []
    monkeypatch.setattr(cobranca, "enviar_email", lambda para, assunto, texto, cfg=None, anexos=None, **k:
                        env.append(para))
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "500", vencimento="2026-10-20", emitir_nfse=False)
    cobranca.preparar_pagamento(tid)
    cobranca.rodar_regua(date(2026, 10, 1))
    assert env == ["fin@rps.com.br, socio@rps.com.br"]
    fila = cobranca.fila_whatsapp()
    assert len(fila) == 1                                       # um evento; o envio sai para os dois números
    itens = whatsapp_web._para_todos_os_numeros(
        [{"eventos": [fila[0]["id"]], "numero": "5521988887777", "texto": "x", "titulo_id": tid}])
    assert [i["numero"] for i in itens] == ["5521988887777", "5521977776666"]
    assert itens[0]["eventos"] == [fila[0]["id"]] and itens[1]["eventos"] == []
