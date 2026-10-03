"""Servidor local do sistema (somente 127.0.0.1): páginas em nfse_itaborai/web e API JSON em /api/*."""

from __future__ import annotations

import json
import mimetypes
import os
import re
import time
import webbrowser
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import (acesso, assistente, atualizacao, automacao, backup, clientes, fiscal, cobranca, conciliacao, contabil, config, db, emissor, financeiro, importacao,
               empresas, importador, inter, lote, migracao, nacional, relatorios, saude, servicos)
from . import __version__
from .validacao import ErroValidacao

INICIO = time.time()           # identifica este processo (a tela percebe quando o sistema reabriu)
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
                                     str(it.get("vencimento", "")), servico_id=str(it.get("servico_id", "")),
                                     cobrar=it.get("cobrar", True) is not False,
                                     regra=str(it.get("regra") or ("baixa" if it.get("apos_pagamento") else "")),
                                     recorrente=bool(it.get("recorrente")), recorrente_ate=str(it.get("recorrente_ate") or ""),
                                     extras=it.get("extras") or None)
    except (ValueError, ErroValidacao, emissor.ErroConfiguracao) as ex:
        return base | {"sucesso": False, "erros": getattr(ex, "erros", None) or [str(ex)]}
    return base | {k: r.get(k) for k in ("sucesso", "erros", "alertas", "rps", "nfse", "link", "titulo_id",
                                         "canal", "chave", "aguardando_pagamento", "sem_nota", "boleto",
                                         "contrato_id")}


def _cancelar_nfse_titulo(tid: int, justificativa: str) -> dict:
    t = financeiro.obter_titulo(tid)
    if len(justificativa.strip()) < 15:
        return {"sucesso": False, "erros": ["A justificativa precisa ter pelo menos 15 caracteres."]}
    if t["status"] == "pago":
        return {"sucesso": False, "erros": ["Esta conta já foi paga: faça o estorno do pagamento antes de cancelar a nota."]}
    if t.get("origem") == "importado":
        return {"sucesso": False, "erros": ["Nota emitida fora do sistema (importada do XML): cancele no portal em que foi "
                                            "emitida."]}
    if t["nfse_status"] == "emitida" and t["nfse_numero"]:
        if t.get("nfse_canal") == "nacional":
            resp = nacional.cancelar(t["nfse_chave"], justificativa, producao=emissor.em_producao())
        else:
            resp = emissor.cancelar(t["nfse_numero"], justificativa, producao=emissor.em_producao())
        if not resp.sucesso:
            return {"sucesso": False, "erros": resp.erros}
        financeiro.atualizar_titulo(tid, nfse_status="cancelada")
        db.registrar("nfse", f"NFS-e {t['nfse_numero']} ({t['cliente_nome']}) cancelada: {justificativa}")
    if t["status"] == "aberto":
        cobranca.cancelar_boleto(t, "NFS-e cancelada")
    financeiro.cancelar_titulo(tid, f"NFS-e cancelada: {justificativa}")
    return {"sucesso": True}


def _cancelar_avulso(c: dict):
    """Número curto = NFS-e municipal; chave de 50 caracteres = NFS-e nacional."""
    numero, just = str(c.get("numero", "")).strip(), str(c.get("justificativa", ""))
    if len(numero.replace(" ", "")) == 50:
        return nacional.cancelar(numero, just, producao=emissor.em_producao(), motivo=str(c.get("motivo", "1")))
    return emissor.cancelar(numero, just, producao=emissor.em_producao())


def _cnpj_prestador() -> str:
    emissor.carregar_env()
    return emissor.so_digitos(emissor.env("ITABORAI_CNPJ"))


def _tirar_da_cobranca(tid: int) -> dict:
    """A nota continua válida; o título vira só faturamento (cancela o boleto, se houver, e sai da régua)."""
    t = financeiro.obter_titulo(tid)
    if t["status"] != "aberto":
        raise ValueError("Só título em aberto pode sair da cobrança.")
    if t.get("banco_id"):
        cobranca.cancelar_boleto(t, "Retirado da cobrança")
    financeiro.atualizar_titulo(tid, cobrar=0, pix_copia_cola="")
    db.registrar("cobranca", f"Título {tid} ({t['cliente_nome']}) retirado da cobrança; NFS-e mantida")
    return {"ok": True}


def _cancelar_titulo(tid: int, motivo: str) -> dict:
    t = financeiro.obter_titulo(tid)
    if t["status"] == "aberto":
        cobranca.cancelar_boleto(t, motivo)
    financeiro.cancelar_titulo(tid, motivo)
    return {"ok": True}


def _restaurar_arquivo(c: dict) -> dict:
    """Backup enviado pela tela: volta para a empresa dona dele (cadastra a empresa se ainda não existir)."""
    dados = backup.decodificar(str(c.get("arquivo", "")))
    m = backup.manifesto_de_bytes(dados)
    lst = empresas.listar()
    dona = next((e for e in lst if m.get("cnpj") and e.get("cnpj") == m["cnpj"]), None)
    if not dona:
        principal = next(e for e in lst if e["pasta"] == ".")
        if not m.get("cnpj") or not principal.get("cnpj"):
            dona = principal if not principal.get("cnpj") else empresas.ativa()
        else:   # computador novo: cadastra a empresa do backup e restaura nela
            empresas.criar({"nome": m.get("empresa") or m["cnpj"], "cnpj": m["cnpj"]})
            dona = next(e for e in empresas.listar() if e["cnpj"] == m["cnpj"])
    with emissor.usar_empresa(empresas.pasta(dona)):   # o arquivo só é gravado na pasta da empresa dona
        arq = backup.receber(dados)
        try:
            r = backup.restaurar(arq, senha=str(c.get("senha") or ""))
        except ValueError:
            arq.unlink(missing_ok=True)       # senha errada: não acumula cópias do arquivo enviado
            raise
    return r | {"empresa_id": dona["id"], "empresa_nome": dona.get("nome", "")}


def _b64(c: dict) -> bytes:
    import base64
    return base64.b64decode(str(c.get("arquivo", "")).split(",")[-1] or b"")


def _atualizar(c: dict, voltar: bool = False) -> dict:
    r = atualizacao.voltar(str(c.get("nome", ""))) if voltar else \
        atualizacao.aplicar(_b64(c), permitir_anterior=bool(c.get("permitir_anterior")))
    if c.get("reiniciar", True):
        atualizacao.reiniciar()
    return r


def _ctx_fiscal() -> dict:
    """O que a tela precisa para mostrar só os campos que o regime e a data exigem."""
    from datetime import date
    g = fiscal.geral()
    return {"regime": g["regime"], "ibscbs": fiscal.informar_ibscbs(g, date.today())}


def _abrir_pasta(p: Path) -> dict:
    """Abre a pasta no Explorer (o servidor roda no próprio computador do escritório)."""
    p.mkdir(parents=True, exist_ok=True)
    if hasattr(os, "startfile"):
        os.startfile(p)  # noqa: S606 — só no Windows
    return {"pasta": str(p)}


ROTAS = {
    # gerais
    "empresas": lambda c: empresas.listar(),
    "migracao/procurar": lambda c: migracao.procurar(),
    "migracao/importar": lambda c: migracao.importar(str(c.get("pasta", ""))),
    "importador/analisar": lambda c: importador.analisar(),
    "importador/importar": lambda c: importador.importar(str(c.get("empresa_id", "")), str(c.get("cnpj", "")),
                                                         c.get("servico") or None, c.get("servicos") or None),
    "servicos": lambda c: servicos.listar(),
    "servico/excluir": lambda c: (servicos.excluir(str(c.get("id", ""))), {"ok": True})[1],
    "importador/abrir_pasta": lambda c: _abrir_pasta(importador.caixa()),
    "backup/listar": lambda c: {"backups": backup.listar(), "pasta": str(backup.pasta_backups()),
                                "copia": config.carregar()["pastas"].get("backup_copia", "")},
    "backup/criar": lambda c: backup.criar("manual"),
    "backup/restaurar": lambda c: backup.restaurar(backup.arquivo(str(c.get("nome", ""))), senha=str(c.get("senha") or "")),
    "backup/restaurar_arquivo": _restaurar_arquivo,
    "backup/abrir_pasta": lambda c: _abrir_pasta(backup.pasta_backups()),
    "empresa/criar": lambda c: (empresas.criar(c), {"empresas": empresas.listar()})[1],
    "empresa/ativar": lambda c: (empresas.ativar(str(c.get("id", ""))), {"ok": True})[1],
    "empresa/credenciais": lambda c: empresas.credenciais(),
    "empresa/credenciais/salvar": lambda c: empresas.salvar_credenciais(c),
    "servico/salvar": lambda c: empresas.salvar_servico(c),
    "estado": lambda c: {"versao": __version__, "empresa": empresas.ativa(), "empresas": empresas.listar(),"clientes": clientes.listar(), "padrao": lote.servico_padrao(),
                         "servicos": servicos.listar(), "regra_geral": financeiro.regra_geral(),
                         "regras_nfse": financeiro.regras_por_cliente(), "regras_nomes": financeiro.REGRAS_NFSE,
                         "fiscal_resumo": fiscal.resumo(fiscal.geral()), "regimes": fiscal.REGIMES,
                         "fiscal_ctx": _ctx_fiscal(),
                         "producao": emissor.em_producao(), "config": config.publico(),
                         "canal": nacional.canal(), "cnpj": _cnpj_prestador()},
    "ambiente": lambda c: (emissor.definir_ambiente(bool(c.get("producao"))), {"producao": emissor.em_producao()})[1],
    "painel": lambda c: relatorios.painel(),
    "log": lambda c: db.linhas("SELECT * FROM log ORDER BY id DESC LIMIT 200"),
    "robo/rodar": lambda c: automacao.rodar(forcar=True),
    "config": lambda c: config.publico(),
    "config/salvar": lambda c: (empresas.verificar_exclusividade(c), config.salvar_da_tela(c))[1],
    "certificado/enviar": lambda c: empresas.enviar_certificado(str(c.get("arquivo", "")), str(c.get("senha", ""))),
    "inter/arquivo": lambda c: empresas.enviar_arquivo_inter(str(c.get("tipo", "")), str(c.get("arquivo", ""))),
    # emissão
    "emitir": lambda c: _emitir_item(c),
    "lote": lambda c: [_emitir_item(i) for i in _sem_duplicadas(c.get("itens", []))],
    "conferir": lambda c: _conferir(c),
    "cancelar": lambda c: _resultado(_cancelar_avulso(c), "Cancelamento processado", "Cancelamento não processado"),
    "nacional/testar": lambda c: nacional.testar_conexao(),
    "titulo/boleto": lambda c: {"arquivo": cobranca.salvar_boleto(_id(c), refazer=bool(c.get("refazer")))},
    "boletos/baixar": lambda c: cobranca.salvar_boletos(str(c.get("competencia", ""))),
    "inter/testar": lambda c: inter.testar(),
    "boletos/abrir_pasta": lambda c: _abrir_pasta(cobranca.pasta_boletos()),
    # clientes
    "cliente/salvar": lambda c: clientes.salvar(c),
    "cliente/excluir": lambda c: {"excluido": clientes.excluir(str(c.get("cpf_cnpj", "")))},
    # contas a receber
    "titulos": lambda c: financeiro.listar_titulos(c.get("filtro", "todos"), c.get("cpf_cnpj", ""),
                                                   c.get("competencia", "")),
    "titulo/novo": lambda c: _novo_titulo(c),
    "titulo/baixar": lambda c: financeiro.baixar(_id(c), c.get("data", ""), c.get("valor"), c.get("forma", "manual")),
    "titulo/estornar": lambda c: (financeiro.estornar(_id(c)), {"ok": True})[1],
    "titulo/cancelar": lambda c: _cancelar_titulo(_id(c), c.get("motivo", "")),
    "titulo/sem_cobranca": lambda c: _tirar_da_cobranca(_id(c)),
    "titulo/gerar_cobranca": lambda c: (financeiro.atualizar_titulo(_id(c), cobrar=1), cobranca.preparar_pagamento(_id(c)))[1],
    "nfse/listar": lambda c: financeiro.listar_notas(str(c.get("competencia") or ""), str(c.get("situacao") or "validas"),
                                                     str(c.get("busca") or ""), str(c.get("servico_id") or "")),
    "sistema/encerrar": lambda c: _encerrar(),
    "cliente/fiscal": lambda c: clientes.salvar({**(clientes.obter(str(c.get("cpf_cnpj", ""))) or {}),
                                                 "fiscal": c.get("fiscal") or {"usar_geral": True}}),
    "titulo/cancelar_nfse": lambda c: _cancelar_nfse_titulo(_id(c), str(c.get("justificativa", ""))),
    "titulo/emitir_nfse": lambda c: financeiro.emitir_nfse_titulo(_id(c)),
    "titulo/pagamento": lambda c: cobranca.preparar_pagamento(_id(c)),
    "titulo/cobrar": lambda c: cobranca.cobrar_agora(_id(c)),
    "titulo/historico": lambda c: cobranca.historico(_id(c)),
    # contratos / recorrência
    "contratos": lambda c: financeiro.listar_contratos(),
    "contrato/salvar": lambda c: financeiro.salvar_contrato(c),
    "contrato/excluir": lambda c: (financeiro.excluir_contrato(_id(c)), {"ok": True})[1],
    "recorrencia": lambda c: {"preenchidos": financeiro.preencher_recorrencia(), "linhas": financeiro.lista_recorrencia(),
                              "regra_geral": financeiro.regra_geral(), "regras": financeiro.REGRAS_NFSE},
    "recorrencia/salvar": lambda c: financeiro.salvar_recorrencia(c.get("linhas") or []),
    "recorrencia/gerar": lambda c: {"gerados": len(financeiro.gerar_titulos(str(c.get("competencia") or "") or None))},
    "contratos/historico": lambda c: {"criados": financeiro.contratos_do_historico(c.get("dia_vencimento") or None)},
    "contratos/confirmar": lambda c: {"confirmados": importacao.confirmar_contratos(c.get("ids") or None)},
    "importacao/xml": lambda c: importacao.importar_xml(),
    "resumo/enviar": lambda c: {"resultado": importacao.resumo_diario({}, forcar=True)},
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
    "conciliacao/importar": lambda c: importacao.importar_manual(str(c.get("ofx", ""))),
    "conciliacao/inter": lambda c: importacao.importar_extrato_inter(int(c.get("dias") or 0) or None),
    "conciliacao/pendentes": lambda c: conciliacao.nao_conciliados(),
    "conciliacao/vincular": lambda c: (conciliacao.vincular(_id(c, "movimento"), _id(c, "titulo")), {"ok": True})[1],
    # atualização do sistema pelo ZIP da versão nova
    "atualizacao/analisar": lambda c: atualizacao.analisar(_b64(c)),
    "atualizacao/aplicar": lambda c: _atualizar(c),
    "atualizacao/versoes": lambda c: {"versao": __version__, "versoes": atualizacao.versoes_guardadas()},
    "atualizacao/voltar": lambda c: _atualizar(c, voltar=True),
    # assistente de validação com credenciais reais
    "validacao": lambda c: assistente.situacao(),
    "validacao/rodar": lambda c: assistente.rodar(str(c.get("passo", "")), c),
    "validacao/historico": lambda c: assistente.historico(),
    # relatórios
    "rel/aging": lambda c: relatorios.aging(),
    "rel/clientes": lambda c: relatorios.por_cliente(),
    "rel/fluxo": lambda c: relatorios.fluxo_caixa(dias=int(c.get("dias") or 90)),
    "rel/dre": lambda c: contabil.dre(int(c.get("ano") or financeiro.hoje().year)),
    "rel/indicadores": lambda c: contabil.indicadores(),
    "saude": lambda c: saude.checklist(),
    "fechamento/gerar": lambda c: {"resultado": saude.fechamento_mensal(forcar=True),
                                   "arquivo": str(saude.pasta_relatorios())},
    "relatorios/abrir_pasta": lambda c: _abrir_pasta(saude.pasta_relatorios()),
    "rel/fluxo_mensal": lambda c: contabil.fluxo_mensal(),
    "rel/livro_caixa": lambda c: contabil.livro_caixa(str(c.get("inicio") or financeiro.hoje().replace(day=1).isoformat()),
                                                      str(c.get("fim") or financeiro.hoje().isoformat())),
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
    nfse = c.get("nfse") or ("agora" if c.get("emitir_nfse") else "nao")   # agora | pagamento | nao
    tid = financeiro.criar_titulo(c.get("cpf_cnpj", ""), c.get("valor"), c.get("descricao", ""),
                                  c.get("vencimento", ""), c.get("competencia", ""), nfse != "nao",
                                  servico_id=str(c.get("servico_id", "")), cobrar=c.get("cobrar", True) is not False,
                                  apos_pagamento=nfse == "pagamento")
    if nfse == "agora":
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
    except (emissor.ErroConfiguracao, ValueError, KeyError, RuntimeError) as ex:
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
        if caminho == "/api/versao":
            return self._responder(200, json.dumps({"sistema": "nfse_itaborai", "versao": __version__,
                                                    "pasta": str(emissor.BASE), "inicio": INICIO}).encode(),
                                   "application/json")
        livres = caminho in ("/", "") or re.fullmatch(r"/[\w-]+\.(html|js|css|png|svg)", caminho)
        if not livres and not acesso.valido(acesso.token_do_cookie(self.headers.get("Cookie"))):
            return self._responder(401, "Sistema bloqueado: entre com o PIN.".encode("utf-8"), "text/plain; charset=utf-8")
        if caminho == "/export/titulos.csv":
            return self._responder(200, relatorios.csv_titulos().encode("utf-8"), "text/csv; charset=utf-8",
                                   {"Content-Disposition": 'attachment; filename="contas_a_receber.csv"'})
        f = re.fullmatch(r"/fechamento/(\d{4}-\d{2})\.html", caminho)
        if f:
            return self._responder(200, saude.relatorio_mensal_html(f.group(1)).encode("utf-8"), "text/html; charset=utf-8")
        b = re.fullmatch(r"/backup/([\w.-]+\.(?:zip|protegido))", caminho)
        if b:
            try:
                arq = backup.arquivo(b.group(1))
            except ValueError as ex:
                return self._responder(404, str(ex).encode("utf-8"), "text/plain; charset=utf-8")
            return self._responder(200, arq.read_bytes(), "application/zip" if arq.suffix == ".zip" else "application/octet-stream",
                                   {"Content-Disposition": f'attachment; filename="{arq.name}"'})
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
        rota = self.path[len("/api/"):]
        token = acesso.token_do_cookie(self.headers.get("Cookie"))
        extra: dict = {}
        if rota == "acesso/estado":
            r = acesso.estado(token)
        elif rota == "acesso/entrar":
            try:
                extra["Set-Cookie"] = acesso.cookie(acesso.entrar(str(corpo.get("pin", ""))))
                r = {"ok": True}
            except ValueError as ex:
                r = {"sucesso": False, "erro": str(ex)}
        elif rota == "acesso/sair":
            acesso.sair(token)
            extra["Set-Cookie"] = acesso.cookie("", apagar=True)
            r = {"ok": True}
        elif not acesso.valido(token):
            r = {"sucesso": False, "bloqueado": True, "erro": "Sistema bloqueado: entre com o PIN."}
        elif rota == "acesso/definir":
            try:
                r = acesso.definir(str(corpo.get("atual", "")), str(corpo.get("novo", "")), corpo.get("minutos"))
                if r["ativo"] and corpo.get("novo"):     # quem definiu o PIN continua dentro
                    extra["Set-Cookie"] = acesso.cookie(acesso.entrar(str(corpo["novo"])))
            except ValueError as ex:
                r = {"sucesso": False, "erro": str(ex)}
        else:
            r = tratar(rota, corpo)
        self._responder(200, json.dumps(r, ensure_ascii=False, default=str).encode("utf-8"),
                        "application/json; charset=utf-8", extra)

    def log_message(self, *args):
        pass


def _quem_esta_na_porta(porta: int) -> dict:
    """Identifica o programa que já ocupa a porta (versão antiga do sistema, esta mesma versão ou outro)."""
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{porta}/api/versao", timeout=2) as r:
            return json.loads(r.read().decode())
    except Exception:  # noqa: BLE001 — versão antiga não tem /api/versao
        return {}


def abrir_se_ja_aberto(porta: int = 8765) -> bool:
    """Se ESTA versão (mesma pasta) já está rodando, só abre o navegador nela."""
    for p in range(porta, porta + 20):
        outro = _quem_esta_na_porta(p)
        if outro.get("versao") == __version__ and outro.get("pasta") == str(emissor.BASE):
            webbrowser.open(f"http://127.0.0.1:{p}")
            return True
    return False


def _encerrar() -> dict:
    """Botão 'Encerrar o sistema': o servidor roda oculto, sem janela para fechar."""
    import threading
    db.registrar("sistema", "Sistema encerrado pela tela")
    threading.Timer(0.8, lambda: os._exit(0)).start()
    return {"ok": True}


def servir(porta: int = 8765, abrir: bool = True, robo: bool = True) -> None:
    srv = None
    for p in range(porta, porta + 20):
        try:
            srv = ThreadingHTTPServer(("127.0.0.1", p), _Handler)
            break
        except OSError:
            outro = _quem_esta_na_porta(p)
            if outro.get("versao") == __version__ and outro.get("pasta") == str(emissor.BASE):
                print(f"O sistema já está aberto em http://127.0.0.1:{p} — abrindo no navegador.")
                if abrir:
                    webbrowser.open(f"http://127.0.0.1:{p}")
                return
            print(f"Aviso: a porta {p} está ocupada por "
                  + (f"outra cópia do sistema (versão {outro.get('versao')}, pasta {outro.get('pasta')})"
                     if outro else "uma versão antiga do sistema ou outro programa")
                  + ". Feche a janela antiga. Usando a próxima porta livre.")
    if srv is None:
        raise SystemExit("Nenhuma porta livre entre 8765 e 8784.")
    porta = srv.server_address[1]
    empresas.aplicar_ativa()
    try:
        empresas.proteger_senhas()          # senhas antigas em texto passam a ficar protegidas
    except Exception as ex:  # noqa: BLE001 — nunca impede o sistema de abrir
        print(f"Aviso: não foi possível proteger as senhas agora ({ex}).")
    importador.caixa()  # cria a pasta IMPORTAR XML dentro da pasta do sistema
    url = f"http://127.0.0.1:{porta}"
    print(f"Sistema versão {__version__} em {url} (para fechar: botão “Encerrar o sistema” na tela)")
    if robo:
        automacao.iniciar_em_segundo_plano()
    if abrir:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
