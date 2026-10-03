"""Assistente de validação: cada passo grava o resultado; emissões de teste nunca saem em produção."""

import xml.etree.ElementTree as ET

from nfse_itaborai import assistente, config, emissor, nacional
from test_emissor import Simulador, ambiente  # noqa: F401  (fixture)
from test_financeiro import CLI_A, base  # noqa: F401  (fixture)


def test_itaborai_emite_e_cancela_em_homologacao(base):  # noqa: F811
    config.salvar({"fiscal": {"regime": "simples"}})
    seq_antes = emissor._ler_sequencia()["proximo_rps"]
    r = assistente.rodar("itaborai", {"cpf_cnpj": CLI_A["cpf_cnpj"]})
    assert r["situacao"] == "ok", r
    envio, canc = Simulador.recebidos[-2][1], Simulador.recebidos[-1][1]
    assert ET.fromstring(envio).findtext("Producao") == "1"          # homologação (1 no leiaute de Itaboraí), mesmo com produção ligada
    assert ET.fromstring(canc).tag == "CancelaNfse"
    assert assistente.DESCRICAO in envio
    assert emissor._ler_sequencia()["proximo_rps"] == seq_antes     # numeração real intacta
    s = assistente.situacao()
    passo = next(p for p in s["passos"] if p["id"] == "itaborai")
    assert passo["ultimo"]["situacao"] == "ok" and s["concluidos"] == 1


def test_passos_nao_configurados_sao_pulados(base):  # noqa: F811
    for passo in ("email", "certificado", "nacional", "inter"):
        assert assistente.rodar(passo)["situacao"] == "pulado"
    assert assistente.situacao()["concluidos"] == 0


def test_backup_conferido(base):  # noqa: F811
    assistente.rodar("email")                     # grava algo no banco antes do backup
    r = assistente.rodar("backup")
    assert r["situacao"] == "ok" and any("íntegro" in d for d in r["detalhes"])


def test_email_de_teste(base, monkeypatch):  # noqa: F811
    from nfse_itaborai import cobranca
    enviados = []
    monkeypatch.setattr(cobranca, "enviar_email", lambda para, assunto, texto, **k: enviados.append(para))
    config.salvar({"smtp": {"host": "smtp.exemplo.com", "usuario": "eu@exemplo.com"}})
    assert assistente.rodar("email")["situacao"] == "ok" and enviados == ["eu@exemplo.com"]
    assert assistente.rodar("email", {"para": "outro@exemplo.com"})["situacao"] == "ok" and enviados[-1] == "outro@exemplo.com"


def test_falha_vira_erro_registrado(base, monkeypatch):  # noqa: F811
    def quebra(*a, **k):
        raise OSError("sem rede")
    monkeypatch.setattr(emissor, "emitir", quebra)
    r = assistente.rodar("itaborai")
    assert r["situacao"] == "erro" and "sem rede" in r["mensagem"]
    assert assistente.historico()[0]["situacao"] == "erro"


def test_nacional_usa_numero_proprio(base, monkeypatch):  # noqa: F811
    from nfse_itaborai.cliente import NotaEmitida, Resposta
    chamadas = {}
    config.salvar({"emissao": {"certificado_pfx": "cert.pfx"}})

    def emitir(rps, producao=False, numero=None, **k):
        chamadas.update(producao=producao, numero=numero)
        return Resposta(True, "", "", notas=[NotaEmitida(codigo_verificacao="X" * 50)])
    monkeypatch.setattr(nacional, "emitir", emitir)
    monkeypatch.setattr(nacional, "cancelar", lambda chave, j, producao=False, **k: Resposta(True, "", "", situacao="cancelada"))
    r = assistente.rodar("nacional")
    assert r["situacao"] == "ok" and chamadas["producao"] is False and str(chamadas["numero"]).startswith("9")


def test_rota_da_tela(base):  # noqa: F811
    from nfse_itaborai import tela
    assert tela.tratar("validacao", {})["total"] == len(assistente.PASSOS)
    assert tela.tratar("validacao/rodar", {"passo": "backup"})["situacao"] == "ok"
