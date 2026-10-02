"""Servidor local do sistema (somente 127.0.0.1): páginas em nfse_itaborai/web e API JSON em /api/*."""

from __future__ import annotations

import json
import mimetypes
import os
import re
import webbrowser
from dataclasses import asdict
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import (asaas, automacao, clientes, cobranca, conciliacao, config, db, emissor, financeiro, importacao,
               lote, nacional, relatorios, whatsapp)
from .validacao import ErroValidacao

WEB = Path(__file__).resolve().parent / "web"


def _id(c: dict, k: str = "id") -> int:
    return int(c.get(k) or 0)


def _resultado(resp, titulo_ok: str, titulo_erro: str) -> dict:
    return {"sucesso": resp.sucesso, "titulo": titulo_ok if resp.sucesso else titulo_erro,
            "erros": resp.erros, "alertas": resp.alertas, "pasta": resp.pasta,
            "notas": [asdict(n) | {"xml": None} for n in resp.notas],
            "xml": "" if resp.sucesso else resp.xml_retorno}


def _emitir_item(it: dict) -> dict:
    cli = clientes.obter(str(it.get("cpf_cnpj", ""))) or {}
    base = {"cpf_cnpj": it.get("cpf_cnpj"), "cliente": cli.get("razao_social", it.get("cpf_cnpj")),
            "valor": str(it.get("valor"))}
    try:
        r = financeiro.emitir_avulsa(str(it.get("cpf_cnpj", "")), it.get("valor", 0), str(it.get("descricao", "")),
                                     str(it.get("vencimento", "")))
    except (ValueError, ErroValidacao, emissor.ErroConfiguracao) as ex:
        return base | {"sucesso": False, "erros": getattr(ex, "erros", None) or [str(ex)]}
    return base | {k: r.get(k) for k in ("sucesso", "erros", "alertas", "rps", "nfse", "link", "titulo_id",
                                         "canal", "chave")}


def _cancelar_nfse_titulo(tid: int, justificativa: str) -> dict:
    t = financeiro.obter_titulo(tid)
    if t["nfse_status"] == "emitida" and t["nfse_numero"]:
        if t.get("nfse_canal") == "nacional":
            resp = nacional.cancelar(t["nfse_chave"], justificativa, producao=emissor.em_producao())
        else:
            resp = emissor.cancelar(t["nfse_numero"], justificativa, producao=emissor.em_producao())
        if not resp.sucesso:
            return {"sucesso": False, "erros": resp.erros}
    if t["asaas_id"]:
        try:
            asaas.cancelar(t["asaas_id"])
        except asaas.ErroAsaas as ex:
            db.registrar("asaas", f"Cancelamento da cobrança {t['asaas_id']}: {ex}")
    financeiro.cancelar_titulo(tid, f"NFS-e cancelada: {justificativa}")
    return {"sucesso": True}


def _cancelar_avulso(c: dict):
    """Número curto = NFS-e municipal; chave de 50 caracteres = NFS-e nacional."""
    numero, just = str(c.get("numero", "")).strip(), str(c.get("justificativa", ""))
    if len(numero.replace(" ", "")) == 50:
        return nacional.cancelar(numero, just, producao=emissor.em_producao(), motivo=str(c.get("motivo", "1")))
    return emissor.cancelar(numero, just, producao=emissor.em_producao())


def _abrir_pasta(p: Path) -> dict:
    """Abre a pasta no Explorer (o servidor roda no próprio computador do escritório)."""
    p.mkdir(parents=True, exist_ok=True)
    if hasattr(os, "startfile"):
        os.startfile(p)  # noqa: S606 — só no Windows
    return {"pasta": str(p)}


ROTAS = {
    # gerais
    "estado": lambda c: {"clientes": clientes.listar(), "padrao": lote.servico_padrao(),
                         "producao": emissor.em_producao(), "config": config.publico(),
                         "canal": nacional.canal()},
    "ambiente": lambda c: (emissor.definir_ambiente(bool(c.get("producao"))), {"producao": emissor.em_producao()})[1],
    "painel": lambda c: relatorios.painel(),
    "log": lambda c: db.linhas("SELECT * FROM log ORDER BY id DESC LIMIT 200"),
    "robo/rodar": lambda c: automacao.rodar(forcar=True),
    "config": lambda c: config.publico(),
    "config/salvar": lambda c: config.salvar_da_tela(c),
    # emissão
    "emitir": lambda c: _emitir_item(c),
    "lote": lambda c: [_emitir_item(i) for i in _sem_duplicadas(c.get("itens", []))],
    "conferir": lambda c: _conferir(c),
    "cancelar": lambda c: _resultado(_cancelar_avulso(c), "Cancelamento processado", "Cancelamento não processado"),
    "nacional/testar": lambda c: nacional.testar_conexao(),
    "titulo/boleto": lambda c: {"arquivo": cobranca.baixar_boleto(_id(c), refazer=bool(c.get("refazer")))},
    "boletos/baixar": lambda c: cobranca.baixar_boletos(str(c.get("competencia", ""))),
    "boletos/abrir_pasta": lambda c: _abrir_pasta(cobranca.pasta_boletos()),
    # clientes
    "cnpj": lambda c: clientes.consultar_cnpj(str(c.get("cnpj", ""))),
    "cliente/salvar": lambda c: clientes.salvar(c),
    "cliente/excluir": lambda c: {"excluido": clientes.excluir(str(c.get("cpf_cnpj", "")))},
    # contas a receber
    "titulos": lambda c: financeiro.listar_titulos(c.get("filtro", "todos"), c.get("cpf_cnpj", ""),
                                                   c.get("competencia", "")),
    "titulo/novo": lambda c: _novo_titulo(c),
    "titulo/baixar": lambda c: financeiro.baixar(_id(c), c.get("data", ""), c.get("valor"), c.get("forma", "manual")),
    "titulo/estornar": lambda c: (financeiro.estornar(_id(c)), {"ok": True})[1],
    "titulo/cancelar": lambda c: (financeiro.cancelar_titulo(_id(c), c.get("motivo", "")), {"ok": True})[1],
    "titulo/cancelar_nfse": lambda c: _cancelar_nfse_titulo(_id(c), str(c.get("justificativa", ""))),
    "titulo/emitir_nfse": lambda c: financeiro.emitir_nfse_titulo(_id(c)),
    "titulo/pagamento": lambda c: cobranca.preparar_pagamento(_id(c)),
    "titulo/cobrar": lambda c: cobranca.cobrar_agora(_id(c)),
    "titulo/historico": lambda c: cobranca.historico(_id(c)),
    # contratos / recorrência
    "contratos": lambda c: financeiro.listar_contratos(),
    "contrato/salvar": lambda c: financeiro.salvar_contrato(c),
    "contrato/excluir": lambda c: (financeiro.excluir_contrato(_id(c)), {"ok": True})[1],
    "contratos/historico": lambda c: {"criados": financeiro.contratos_do_historico(c.get("dia_vencimento") or None)},
    "contratos/confirmar": lambda c: {"confirmados": importacao.confirmar_contratos(c.get("ids") or None)},
    "importacao/xml": lambda c: importacao.importar_xml(),
    "importacao/contatos": lambda c: {"atualizados": importacao.enriquecer_contatos(int(c.get("limite") or 25))},
    "resumo/enviar": lambda c: {"resultado": importacao.resumo_diario({}, forcar=True)},
    "whatsapp/testar": lambda c: (whatsapp.enviar(str(c.get("telefone", "")), "Teste do sistema financeiro: "
                                                  "WhatsApp automático funcionando."), {"ok": True})[1],
    "recorrencia/gerar": lambda c: {"gerados": len(financeiro.gerar_titulos(c.get("competencia") or None))},
    # cobrança
    "whatsapp/fila": lambda c: cobranca.fila_whatsapp(),
    "whatsapp/feito": lambda c: (cobranca.marcar_whatsapp_feito(_id(c)), {"ok": True})[1],
    "regua/rodar": lambda c: cobranca.rodar_regua(),
    "regua/historico": lambda c: db.linhas(
        "SELECT e.*, t.cliente_nome FROM eventos_cobranca e JOIN titulos t ON t.id=e.titulo_id "
        "ORDER BY e.id DESC LIMIT 200"),
    "email/testar": lambda c: (cobranca.enviar_email(str(c.get("para", "")), "Teste do emissor NFS-e",
                                                     "E-mail de teste: a configuração SMTP está funcionando."),
                               {"ok": True})[1],
    # contas a pagar
    "despesas": lambda c: financeiro.listar_despesas(c.get("filtro", "todos")),
    "despesa/salvar": lambda c: {"id": financeiro.salvar_despesa(c)},
    "despesa/pagar": lambda c: (financeiro.pagar_despesa(_id(c), c.get("data", "")), {"ok": True})[1],
    "despesa/excluir": lambda c: (financeiro.excluir_despesa(_id(c)), {"ok": True})[1],
    # conciliação
    "conciliacao/importar": lambda c: conciliacao.importar(str(c.get("ofx", ""))),
    "conciliacao/pendentes": lambda c: conciliacao.nao_conciliados(),
    "conciliacao/vincular": lambda c: (conciliacao.vincular(_id(c, "movimento"), _id(c, "titulo")), {"ok": True})[1],
    # relatórios
    "rel/aging": lambda c: relatorios.aging(),
    "rel/clientes": lambda c: relatorios.por_cliente(),
    "rel/fluxo": lambda c: relatorios.fluxo_caixa(dias=int(c.get("dias") or 90)),
    "rel/dre": lambda c: relatorios.dre(int(c.get("ano") or date.today().year)),
}


def _sem_duplicadas(itens: list[dict]) -> list[dict]:
    vistos, out = set(), []
    for it in itens:
        chave = (clientes._digitos(it.get("cpf_cnpj")), financeiro.cent(it.get("valor") or 0), it.get("descricao", ""))
        if chave not in vistos:
            vistos.add(chave)
            out.append(it)
    return out


def _novo_titulo(c: dict) -> dict:
    tid = financeiro.criar_titulo(c.get("cpf_cnpj", ""), c.get("valor"), c.get("descricao", ""),
                                  c.get("vencimento", ""), c.get("competencia", ""), bool(c.get("emitir_nfse")))
    if c.get("emitir_nfse"):
        return financeiro.emitir_nfse_titulo(tid) | {"titulo_id": tid}
    return {"sucesso": True, "titulo_id": tid}


def _conferir(c: dict) -> dict:
    rps = emissor.rps_de_dict(c)
    xml, _l, alertas = emissor.preparar(rps, emissor.prestador_do_ambiente(), producao=False)
    return {"sucesso": True, "titulo": f"RPS {rps.numero} válido — serviços R$ {rps.valor_servicos}, "
            f"ISS R$ {rps.valor_iss}, líquido R$ {rps.valor_liquido}", "alertas": alertas, "xml": xml}


def tratar(rota: str, corpo: dict):
    func = ROTAS.get(rota)
    if not func:
        return {"erro": "Rota inválida"}
    try:
        return func(corpo or {})
    except ErroValidacao as ex:
        return {"sucesso": False, "titulo": "Pendências (nada foi enviado)", "erros": ex.erros, "erro": "; ".join(ex.erros)}
    except (emissor.ErroConfiguracao, ValueError, KeyError, asaas.ErroAsaas, RuntimeError) as ex:
        return {"sucesso": False, "titulo": "Erro", "erros": [str(ex)], "erro": str(ex)}
    except OSError as ex:
        return {"sucesso": False, "titulo": "Falha de comunicação", "erros": [str(ex)], "erro": f"Falha de comunicação: {ex}"}


class _Handler(BaseHTTPRequestHandler):
    def _responder(self, codigo: int, corpo: bytes, tipo: str, extra: dict | None = None) -> None:
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):  # noqa: N802
        caminho = self.path.split("?")[0]
        if caminho == "/favicon.ico":
            return self._responder(204, b"", "image/x-icon")
        if caminho == "/export/titulos.csv":
            return self._responder(200, relatorios.csv_titulos().encode("utf-8"), "text/csv; charset=utf-8",
                                   {"Content-Disposition": 'attachment; filename="contas_a_receber.csv"'})
        m = re.fullmatch(r"/boleto/(\d+)\.pdf", caminho)
        if m:
            r = tratar("titulo/boleto", {"id": int(m.group(1))})
            if not r.get("arquivo"):
                return self._responder(404, (r.get("erro") or "boleto indisponível").encode("utf-8"),
                                       "text/plain; charset=utf-8")
            return self._responder(200, Path(r["arquivo"]).read_bytes(), "application/pdf",
                                   {"Content-Disposition": f'inline; filename="boleto_{m.group(1)}.pdf"'})
        nome = "index.html" if caminho in ("/", "") else caminho.lstrip("/")
        arq = (WEB / nome).resolve()
        if WEB not in arq.parents or not arq.is_file():
            return self._responder(404, b"nao encontrado", "text/plain")
        tipo = mimetypes.guess_type(arq.name)[0] or "application/octet-stream"
        self._responder(200, arq.read_bytes(), tipo + ("; charset=utf-8" if tipo.startswith("text") or
                                                        tipo.endswith("javascript") else ""))

    def do_POST(self):  # noqa: N802
        if not self.path.startswith("/api/"):
            return self._responder(404, b"{}", "application/json")
        tamanho = int(self.headers.get("Content-Length", 0))
        corpo = json.loads(self.rfile.read(tamanho) or b"{}")
        r = tratar(self.path[len("/api/"):], corpo)
        self._responder(200, json.dumps(r, ensure_ascii=False, default=str).encode("utf-8"),
                        "application/json; charset=utf-8")

    def log_message(self, *args):
        pass


def servir(porta: int = 8765, abrir: bool = True, robo: bool = True) -> None:
    srv = ThreadingHTTPServer(("127.0.0.1", porta), _Handler)
    url = f"http://127.0.0.1:{porta}"
    print(f"Sistema em {url} (deixe esta janela aberta; Ctrl+C para sair)")
    if robo:
        automacao.iniciar_em_segundo_plano()
    if abrir:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
