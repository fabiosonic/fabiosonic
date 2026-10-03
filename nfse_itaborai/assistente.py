"""Assistente de validação: testa, com as credenciais reais da empresa, cada integração do sistema.

Nada aqui usa o ambiente de produção da NFS-e: as emissões de teste saem SEMPRE em homologação
(Itaboraí) ou na Produção Restrita (Sefin Nacional) e são canceladas logo em seguida. O boleto de teste
só é criado no sandbox do Inter; em produção o teste do banco apenas autentica e consulta.
Os resultados ficam gravados (tabela `validacoes`) para mostrar o que já foi conferido e quando.
"""

from __future__ import annotations

import json
import sqlite3
import time
import zipfile
from contextlib import closing
from datetime import datetime, timedelta

from . import backup, clientes, config, db, emissor, inter, lote, nacional

JUSTIFICATIVA = "Teste do assistente de validacao do emissor (homologacao)"
DESCRICAO = "TESTE DE HOMOLOGACAO - SEM VALOR FISCAL"

PASSOS = [
    {"id": "email", "titulo": "E-mail (SMTP)",
     "descricao": "Envia um e-mail de teste com a configuração de Configurações › E-mail."},
    {"id": "certificado", "titulo": "Certificado A1 e Sefin Nacional",
     "descricao": "Abre o certificado, confere CNPJ e validade e conecta ao ADN (Produção Restrita)."},
    {"id": "itaborai", "titulo": "Emissão e cancelamento — Itaboraí (homologação)",
     "descricao": "Emite um RPS de teste em homologação no webservice da prefeitura e cancela a nota."},
    {"id": "nacional", "titulo": "Emissão e cancelamento — NFS-e Nacional (Produção Restrita)",
     "descricao": "Emite uma DPS de teste na Produção Restrita e registra o evento de cancelamento."},
    {"id": "inter", "titulo": "Banco Inter",
     "descricao": "Autentica e consulta cobranças. No sandbox também registra e cancela um boleto de teste."},
    {"id": "backup", "titulo": "Backup",
     "descricao": "Gera um backup, confere o arquivo .zip, o manifesto e a integridade do banco de dados."},
]

_ESQUEMA = """CREATE TABLE IF NOT EXISTS validacoes (
    id INTEGER PRIMARY KEY, passo TEXT NOT NULL, quando TEXT NOT NULL, situacao TEXT NOT NULL,
    mensagem TEXT NOT NULL, detalhes TEXT NOT NULL DEFAULT '[]')"""


class Pulado(Exception):
    """O passo não se aplica (integração não configurada)."""


def _resultado(situacao: str, mensagem: str, detalhes: list[str] | None = None) -> dict:
    return {"situacao": situacao, "mensagem": mensagem, "detalhes": detalhes or []}


# ---------------------------------------------------------------- passos

def _email(c: dict) -> dict:
    s = config.carregar()["smtp"]
    if not s.get("host"):
        raise Pulado("SMTP não configurado (Configurações › E-mail).")
    from . import cobranca
    para = str(c.get("para") or s.get("usuario") or "").strip()
    if "@" not in para:
        raise ValueError("Informe o e-mail que vai receber o teste.")
    cobranca.enviar_email(para, "Teste do assistente de validação",
                          "Se você recebeu este e-mail, o envio de cobranças e notas por e-mail está funcionando.")
    return _resultado("ok", f"E-mail enviado para {para}. Confira a caixa de entrada (e o spam).")


def _certificado(c: dict) -> dict:
    if not nacional.configuracao().get("certificado_pfx"):
        raise Pulado("Certificado A1 não informado (Configurações › Emissão).")
    r = nacional.testar_conexao(producao=False)
    det = [f"Titular: {r['titular']}", f"Validade: {r['validade']} ({r['dias_restantes']} dias)"]
    cnpj = emissor.so_digitos(emissor.env("ITABORAI_CNPJ"))
    if r.get("cnpj") and cnpj and r["cnpj"] != cnpj:
        return _resultado("erro", f"O certificado é do CNPJ {r['cnpj']}, diferente da empresa ({cnpj}).", det)
    if r["vencido"]:
        return _resultado("erro", "Certificado vencido.", det)
    if not r["conexao"]:
        return _resultado("erro", r["mensagem"], det)
    if r["dias_restantes"] < 30:
        return _resultado("alerta", f"Conexão OK, mas o certificado vence em {r['dias_restantes']} dias.", det)
    return _resultado("ok", "Certificado válido e conexão com o ADN OK.", det)


def _cliente_teste(c: dict) -> dict:
    doc = clientes._digitos(c.get("cpf_cnpj"))
    if doc:
        cli = clientes.obter(doc)
        if not cli:
            raise ValueError("Cliente escolhido para o teste não está no cadastro.")
        return cli
    for cli in clientes.listar():
        e = cli.get("endereco") or {}
        if len(clientes._digitos(cli.get("cpf_cnpj"))) in (11, 14) and e.get("logradouro") and e.get("cep"):
            return cli
    raise ValueError("Cadastre ao menos um cliente com endereço completo para usar nos testes.")


def _rps_teste(c: dict):
    cli = _cliente_teste(c)
    d = lote.montar_rps(cli["cpf_cnpj"], str(c.get("valor") or "10.00"), DESCRICAO)
    alertas = d.pop("_alertas_fiscais", [])
    rps = emissor.rps_de_dict(d)
    rps.observacoes = "Teste de homologação gerado pelo assistente de validação."
    return rps, cli, alertas


def _itaborai(c: dict) -> dict:
    emissor.carregar_env()
    if not (emissor.env("ITABORAI_CNPJ") and emissor.env("ITABORAI_CHAVE")):
        raise Pulado("Webservice de Itaboraí não configurado (CNPJ e chave no .env).")
    rps, cli, det = _rps_teste(c)
    resp = emissor.emitir(rps, producao=False)        # homologação: não consome a numeração real
    det = det + [f"Tomador do teste: {cli.get('razao_social')}"] + resp.alertas
    if not resp.sucesso:
        return _resultado("erro", "O webservice recusou o RPS de teste.", det + resp.erros)
    nota = resp.notas[0] if resp.notas else None
    num = nota.numero_nfse if nota else ""
    det.append(f"NFS-e de homologação nº {num or '(sem número no retorno)'} — arquivos em {resp.pasta}")
    if not num:
        return _resultado("alerta", "RPS aceito, mas a prefeitura não devolveu o número da nota para cancelar.", det)
    canc = emissor.cancelar(num, JUSTIFICATIVA, producao=False)
    if not canc.sucesso:
        return _resultado("alerta", "Emissão OK; o cancelamento em homologação foi recusado.", det + canc.erros)
    return _resultado("ok", f"Emissão e cancelamento em homologação OK (NFS-e de teste nº {num}).", det)


def _nacional(c: dict) -> dict:
    if not nacional.configuracao().get("certificado_pfx"):
        raise Pulado("Certificado A1 não informado: o canal nacional precisa dele.")
    rps, cli, det = _rps_teste(c)
    # número próprio do teste (data e hora): não usa nem altera a numeração de DPS da empresa
    numero = int("9" + datetime.now(emissor.FUSO).strftime("%y%m%d%H%M%S"))
    resp = nacional.emitir(rps, producao=False, numero=numero)
    det = det + [f"Tomador do teste: {cli.get('razao_social')}", f"DPS de teste nº {numero}"] + resp.alertas
    if not resp.sucesso:
        return _resultado("erro", "O Sefin Nacional (Produção Restrita) recusou a DPS de teste.", det + resp.erros)
    chave = resp.notas[0].codigo_verificacao if resp.notas else ""
    det.append(f"Chave da NFS-e de teste: {chave}")
    canc = nacional.cancelar(chave, JUSTIFICATIVA, producao=False)
    if not canc.sucesso:
        return _resultado("alerta", "Emissão OK; o cancelamento na Produção Restrita foi recusado.", det + canc.erros)
    return _resultado("ok", "Emissão e cancelamento na Produção Restrita OK.", det)


def _inter(c: dict) -> dict:
    cfg = config.carregar()
    if not inter.configurado(cfg):
        raise Pulado("Banco Inter não configurado (Configurações › Banco Inter).")
    r = inter.testar(cfg)
    det = [r["mensagem"]]
    if not cfg["cobranca"].get("inter_sandbox"):
        return _resultado("ok", "Conexão com o Inter OK. Em produção o assistente não cria boleto (seria cobrança real).",
                          det)
    cli = _cliente_teste(c)
    hoje = inter._hoje()
    titulo = {"id": f"V{int(time.time()) % 10**8}", "valor_cent": 250, "vencimento": (hoje + timedelta(days=5)).isoformat(),
              "cpf_cnpj": cli["cpf_cnpj"], "descricao": "Boleto de teste do assistente", "competencia": hoje.isoformat()[:7]}
    cob = inter.criar_cobranca(titulo, cfg)
    det.append(f"Boleto de teste registrado no sandbox (código {cob['banco_id']}).")
    if not cob.get("linha_digitavel"):
        det.append("O sandbox ainda não devolveu a linha digitável (registro assíncrono).")
    try:
        inter.cancelar(cob["banco_id"], "Teste do assistente", cfg)
        det.append("Boleto de teste cancelado.")
    except Exception as ex:  # noqa: BLE001
        return _resultado("alerta", "Boleto criado no sandbox, mas o cancelamento falhou.", det + [str(ex)])
    return _resultado("ok", "Sandbox do Inter OK: token, criação e cancelamento de boleto.", det)


def _backup(c: dict) -> dict:
    info = backup.criar("teste")
    arq = backup.pasta_backups() / info["nome"]
    det = [f"Arquivo: {arq}"]
    with zipfile.ZipFile(arq) as z:
        ruim = z.testzip()
        if ruim:
            return _resultado("erro", f"Backup corrompido: {ruim}.", det)
        manifesto = backup.ler_manifesto(arq)
        det.append(f"Empresa: {manifesto.get('empresa') or manifesto.get('cnpj')} — {manifesto.get('arquivos')} arquivo(s)")
        if "dados/sistema.db" in z.namelist():
            tmp = arq.with_suffix(".verifica.db")
            try:
                tmp.write_bytes(z.read("dados/sistema.db"))
                with closing(sqlite3.connect(tmp)) as con:
                    ok = con.execute("PRAGMA integrity_check").fetchone()[0]
            finally:
                tmp.unlink(missing_ok=True)
            if ok != "ok":
                return _resultado("erro", f"O banco de dados copiado não passou na verificação: {ok}.", det)
            det.append("Banco de dados íntegro (PRAGMA integrity_check).")
    if info.get("copia"):
        det.append(f"Cópia extra: {info['copia']}")
    return _resultado("ok", "Backup gerado e conferido.", det)


FUNCOES = {"email": _email, "certificado": _certificado, "itaborai": _itaborai, "nacional": _nacional,
           "inter": _inter, "backup": _backup}


# ---------------------------------------------------------------- execução e histórico

def _gravar(passo: str, r: dict) -> dict:
    with db.conexao() as con:
        con.execute(_ESQUEMA)
        con.execute("INSERT INTO validacoes (passo, quando, situacao, mensagem, detalhes) VALUES (?,?,?,?,?)",
                    (passo, db.agora(), r["situacao"], r["mensagem"], json.dumps(r["detalhes"], ensure_ascii=False)))
    db.registrar("validacao", f"{passo}: {r['situacao']} — {r['mensagem']}")
    return r | {"passo": passo, "quando": db.agora()}


def rodar(passo: str, c: dict | None = None) -> dict:
    if passo not in FUNCOES:
        raise ValueError("Passo de validação desconhecido.")
    try:
        r = FUNCOES[passo](c or {})
    except Pulado as ex:
        r = _resultado("pulado", str(ex))
    except Exception as ex:  # noqa: BLE001 — o assistente mostra qualquer falha, sem derrubar a tela
        erros = getattr(ex, "erros", None) or [str(ex) or ex.__class__.__name__]
        r = _resultado("erro", erros[0], erros[1:])
    return _gravar(passo, r)


def situacao() -> dict:
    """Último resultado de cada passo, para a tela do assistente."""
    with db.conexao() as con:
        con.execute(_ESQUEMA)
        ult = {r["passo"]: dict(r) for r in con.execute(
            "SELECT * FROM validacoes WHERE id IN (SELECT MAX(id) FROM validacoes GROUP BY passo)")}
    out = []
    for p in PASSOS:
        u = ult.get(p["id"])
        if u:
            u["detalhes"] = json.loads(u.get("detalhes") or "[]")
        out.append(p | {"ultimo": u})
    feitos = [p for p in out if p["ultimo"] and p["ultimo"]["situacao"] in ("ok", "alerta")]
    return {"passos": out, "concluidos": len(feitos), "total": len(PASSOS),
            "clientes": [{"cpf_cnpj": c["cpf_cnpj"], "razao_social": c.get("razao_social", "")} for c in clientes.listar()]}


def historico(limite: int = 50) -> list[dict]:
    with db.conexao() as con:
        con.execute(_ESQUEMA)
        return [dict(r) for r in con.execute("SELECT * FROM validacoes ORDER BY id DESC LIMIT ?", (limite,))]

