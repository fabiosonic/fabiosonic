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

from . import (acesso, contatos, mensagens, textos, licenca, assistente, atualizacao, automacao, cartao, nitrus, paises, whatsapp, whatsapp_web, backup, clientes, fiscal, cobranca, conciliacao, contabil, config, db, emissor, financeiro, importacao,
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
    if str((it.get("extras") or {}).get("tp_emit") or "") in ("2", "3"):
        # emitida por esta empresa como tomadora/intermediária: não é receita, não vai para o contas a receber
        r = lote.emitir_um(str(it.get("cpf_cnpj", "")), it.get("valor", 0), str(it.get("descricao", "")),
                           producao=emissor.em_producao(), canal="nacional", servico_id=str(it.get("servico_id", "")),
                           extras=it.get("extras"))
        if r.get("sucesso"):
            db.registrar("nfse_tomador", f"NFS-e emitida como {'tomador' if it['extras']['tp_emit'] == '2' else 'intermediário'}"
                                         f" — prestador {base['cliente']}, R$ {it.get('valor')}, chave {r.get('chave')}")
            r.setdefault("alertas", []).append("Nota emitida por esta empresa como tomadora/intermediária: não entra no "
                                               "contas a receber. O XML ficou na pasta saida.")
        return base | {k: r.get(k) for k in ("sucesso", "erros", "alertas", "nfse", "link", "chave", "canal")}
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


def _gerar_cobranca(tid: int) -> dict:
    """Gera o boleto/PIX agora; se o banco recusar, o motivo fica no título (e aparece na lista)."""
    antes = financeiro.obter_titulo(tid).get("boleto_situacao") or ""
    financeiro.atualizar_titulo(tid, cobrar=1, **({"boleto_situacao": ""} if antes == "dispensado" else {}))
    try:
        t = cobranca.preparar_pagamento(tid)
        if not financeiro.tem_meio_de_pagamento(t):
            raise ValueError("Boleto/PIX não gerado: configure o Banco Inter (ou a chave PIX do escritório) em Configurações.")
    except Exception as ex:
        # sem boleto, o título volta ao que era (cobrança sem boleto continua na régua) e guarda o motivo
        financeiro.atualizar_titulo(tid, cobranca_erro=str(ex)[:300], **({"boleto_situacao": antes} if antes else {}))
        raise
    return t


def _estornar(tid: int) -> dict:
    """Estorno: o saldo de um pagamento parcial ainda em aberto é cancelado junto (inclusive o boleto no banco)."""
    t = financeiro.obter_titulo(tid)
    if t.get("saldo_titulo_id"):
        saldo = financeiro.obter_titulo(t["saldo_titulo_id"])
        if saldo["status"] == "aberto":
            cobranca.cancelar_boleto(saldo, f"Estorno do pagamento do titulo {tid}")
    financeiro.estornar(tid)
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
    "migracao/misturas": lambda c: migracao.misturas(),
    "migracao/reparar": lambda c: migracao.reparar(),
    "migracao/identidade": lambda c: migracao.identidade(),
    "migracao/dados_anteriores": lambda c: migracao.dados_anteriores(),
    "migracao/trazer_dados": lambda c: migracao.trazer_dados(str(c.get("fonte", "")), list(c.get("campos") or [])),
    "migracao/usar_nome_oficial": lambda c: migracao.usar_nome_oficial(),
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
    "empresa/criar": lambda c: (_limite_empresas(), empresas.criar(c), {"empresas": empresas.listar()})[2],
    "licenca/status": lambda c: licenca.situacao(),
    "licenca/ativar": lambda c: licenca.ativar(str(c.get("chave") or "")),
    "empresa/ativar": lambda c: (empresas.ativar(str(c.get("id", ""))), {"ok": True})[1],
    "empresa/credenciais": lambda c: empresas.credenciais(),
    "empresa/credenciais/salvar": lambda c: empresas.salvar_credenciais(c),
    "servico/salvar": lambda c: empresas.salvar_servico(c),
    "estado": lambda c: {"versao": __version__, "licenca": licenca.situacao(), "empresa": empresas.ativa(), "empresas": empresas.listar(),"clientes": clientes.listar(), "padrao": lote.servico_padrao(),
                         "servicos": servicos.listar(), "regra_geral": financeiro.regra_geral(),
                         "regras_nfse": financeiro.regras_por_cliente(), "regras_nomes": financeiro.REGRAS_NFSE,
                         "fiscal_resumo": fiscal.resumo(fiscal.geral()), "regimes": fiscal.REGIMES,
                         "fiscal_ctx": _ctx_fiscal(), "paises": paises.PAISES, "moedas": paises.MOEDAS,
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
    "emitir": lambda c: _e_envia(_emitir_item(c)),
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
    "cliente/whatsapp": lambda c: clientes.salvar({**(clientes.obter(str(c.get("cpf_cnpj", ""))) or {}),
                                                   "whatsapp_cobranca": bool(c.get("ativo"))}),
    "cliente/excluir": lambda c: {"excluido": clientes.excluir(str(c.get("cpf_cnpj", "")))},
    # contas a receber
    "titulos": lambda c: financeiro.listar_titulos(c.get("filtro", "todos"), c.get("cpf_cnpj", ""),
                                                   c.get("competencia", "")),
    "titulo/novo": lambda c: _novo_titulo(c),
    "titulo/editar": lambda c: _editar_titulo(c),
    "contrato/aplicar_abertos": lambda c: financeiro.aplicar_contrato_aos_titulos(_id(c), str(c.get("a_partir") or "")),
    "contrato/abertos": lambda c: {"titulos": financeiro.titulos_abertos_do_contrato(_id(c), str(c.get("a_partir") or ""))},
    "titulo/baixar": lambda c: _e_envia(financeiro.baixar(_id(c), c.get("data", ""), c.get("valor"), c.get("forma", "manual"),
                                                 str(c.get("parcial") or ""))),
    "contatos/analisar": lambda c: contatos.analisar(contatos.de_base64(str(c.get("arquivo") or ""))),
    "contatos/aplicar": lambda c: contatos.aplicar(contatos.de_base64(str(c.get("arquivo") or "")), bool(c.get("substituir"))),
    "titulo/parcial": lambda c: financeiro.decidir_parcial(_id(c), str(c.get("decisao") or ""), str(c.get("vencimento") or "")),
    "titulo/estornar": lambda c: _estornar(_id(c)),
    "titulo/cancelar": lambda c: _cancelar_titulo(_id(c), c.get("motivo", "")),
    "titulo/sem_cobranca": lambda c: _tirar_da_cobranca(_id(c)),
    "titulo/juridico": lambda c: financeiro.enviar_juridico(_id(c), str(c.get("obs") or ""), bool(c.get("todos"))),
    "titulo/juridico_voltar": lambda c: financeiro.voltar_do_juridico(_id(c)),
    "titulo/gerar_cobranca": lambda c: _gerar_cobranca(_id(c)),
    "nfse/listar": lambda c: financeiro.listar_notas(str(c.get("competencia") or ""), str(c.get("situacao") or "validas"),
                                                     str(c.get("busca") or ""), str(c.get("servico_id") or "")),
    "nfse/ultima": lambda c: {"nota": financeiro.ultima_nota(str(c.get("cpf_cnpj", "")))},
    "nfse/dados": lambda c: financeiro.dados_da_nota(_id(c)),
    "sistema/encerrar": lambda c: _encerrar(),
    "cliente/fiscal": lambda c: clientes.salvar({**(clientes.obter(str(c.get("cpf_cnpj", ""))) or {}),
                                                 "fiscal": c.get("fiscal") or {"usar_geral": True}}),
    "titulo/cancelar_nfse": lambda c: _cancelar_nfse_titulo(_id(c), str(c.get("justificativa", ""))),
    "titulo/emitir_nfse": lambda c: _e_envia(financeiro.emitir_nfse_titulo(_id(c))),
    "titulo/forcar_nfse": lambda c: _e_envia(financeiro.forcar_nfse(_id(c), bool(c.get("conferido_portal")))),
    "titulo/pagamento": lambda c: cobranca.preparar_pagamento(_id(c)),
    "titulo/cartao": lambda c: cartao.gerar_link(_id(c), int(c.get("parcelas") or 0)),
    "cartao/simular": lambda c: cartao.valor_no_cartao(financeiro.cent(c.get("valor") or 0), int(c.get("parcelas") or 1)),
    "cartao/testar": lambda c: cartao.testar(),
    "whatsapp/testar": lambda c: whatsapp.testar(),
    "nitrus/analisar": lambda c: nitrus.analisar(str(c.get("pdf") or "")),
    "nitrus/lancar": lambda c: nitrus.lancar(c.get("grupos") or [], c.get("cobrar", True) is not False),
    "whatsapp_web/estado": lambda c: whatsapp_web.estado(),
    "whatsapp_web/conectar": lambda c: (whatsapp_web.em_segundo_plano(whatsapp_web.conectar), {"ok": True})[1],
    "whatsapp_web/desconectar": lambda c: whatsapp_web.desconectar(),
    "whatsapp_web/enviar_fila": lambda c: (whatsapp_web.em_segundo_plano(whatsapp_web.enviar_fila), {"ok": True})[1],
    "whatsapp_web/teste": lambda c: _whatsapp_teste(str(c.get("telefone", ""))),
    "whatsapp/modelos": lambda c: {k: {"nome": n, "texto": t} for k, (n, t) in whatsapp.MODELOS.items()},
    "titulo/pago_cartao": lambda c: cartao.confirmar_pagamento(_id(c), c.get("valor"), str(c.get("data") or ""),
                                                               str(c.get("comprovante") or "")),
    "titulo/cobrar": lambda c: cobranca.cobrar_agora(_id(c)),
    "titulo/historico": lambda c: cobranca.historico(_id(c)),
    # contratos / recorrência
    "contratos": lambda c: financeiro.listar_contratos(),
    "contrato/salvar": lambda c: _contrato_salvo(financeiro.salvar_contrato(c)),
    "contrato/ajustes": lambda c: financeiro.listar_ajustes(_id(c)),
    "contrato/ajuste_salvar": lambda c: financeiro.salvar_ajuste(c),
    "contrato/ajuste_excluir": lambda c: (financeiro.excluir_ajuste(_id(c)), {"ok": True})[1],
    "contrato/excluir": lambda c: (financeiro.excluir_contrato(_id(c)), {"ok": True})[1],
    "recorrencia": lambda c: {"preenchidos": financeiro.preencher_recorrencia(), "linhas": financeiro.lista_recorrencia(),
                              "regra_geral": financeiro.regra_geral(), "regras": financeiro.REGRAS_NFSE},
    "recorrencia/salvar": lambda c: _robo_se_gerou(financeiro.salvar_recorrencia(c.get("linhas") or [], bool(c.get("aplicar_abertos")))),
    "recorrencia/gerar": lambda c: {"gerados": len(financeiro.gerar_titulos(str(c.get("competencia") or "") or None))},
    "contratos/historico": lambda c: {"criados": financeiro.contratos_do_historico(c.get("dia_vencimento") or None)},
    "contratos/confirmar": lambda c: {"confirmados": importacao.confirmar_contratos(c.get("ids") or None)},
    "importacao/xml": lambda c: importacao.importar_xml(),
    "resumo/enviar": lambda c: {"resultado": importacao.resumo_diario({}, forcar=True)},
    "whatsapp/fila": lambda c: cobranca.fila_whatsapp(),
    "whatsapp/feito": lambda c: (cobranca.marcar_whatsapp_feito(_id(c)), {"ok": True})[1],
    "regua/rodar": lambda c: _rodar_regua(),
    "regua/historico": lambda c: db.linhas(
        "SELECT e.*, t.cliente_nome FROM eventos_cobranca e JOIN titulos t ON t.id=e.titulo_id "
        "ORDER BY e.id DESC LIMIT 200"),
    "email/testar": lambda c: (cobranca.enviar_email(str(c.get("para", "")), "Teste do emissor NFS-e",
                                                     "E-mail de teste: a configuração SMTP está funcionando.", teste=True),
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
    "despesas/categorias": lambda c: conciliacao.categorias_despesa(),
    "conciliacao/recategorizar": lambda c: conciliacao.recategorizar(_id(c, "movimento"), str(c.get("categoria") or ""),
                                                                     c.get("iguais", True) is not False, c.get("lembrar", True) is not False),
    "conciliacao/extrato": lambda c: conciliacao.extrato(str(c.get("inicio") or ""), str(c.get("fim") or "")),
    "conciliacao/classificar": lambda c: conciliacao.classificar(_id(c, "movimento"), str(c.get("tipo") or ""),
                                                                 c.get("iguais", True) is not False, str(c.get("categoria") or "")),
    "conciliacao/vincular": lambda c: _e_envia(conciliacao.vincular(_id(c, "movimento"), _id(c, "titulo"))),
    "conciliacao/agenda": lambda c: {"intervalo": automacao._intervalo(config.carregar()), **automacao.AGENDA},
    "titulo/enviar_nfse": lambda c: cobranca.enviar_nfse_titulo(_id(c)),
    "mensagens": lambda c: mensagens.listar(str(c.get("de") or ""), str(c.get("ate") or ""), str(c.get("canal") or ""),
                                            str(c.get("status") or "")),
    "mensagens/resumo": lambda c: mensagens.resumo(),
    "mensagem": lambda c: mensagens.obter(_id(c)),
    "mensagem/reenviar": lambda c: mensagens.reenviar(_id(c)),
    "modelos_msg": lambda c: textos.listar(),
    "cobranca/suspensao_previa": lambda c: cobranca.previa_suspensao(),
    "modelos_msg/salvar": lambda c: textos.salvar(str(c.get("chave", "")), str(c.get("assunto") or ""), str(c.get("texto") or "")),
    "modelos_msg/previa": lambda c: textos.previa(str(c.get("chave", "")), str(c.get("assunto") or ""), str(c.get("texto") or "")),
    "conciliacao/titulos": lambda c: conciliacao.titulos_para_vincular(str(c.get("busca") or "")),
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


def _robo_se_gerou(r: dict) -> dict:
    """Títulos da recorrência gerados agora: o robô roda em segundo plano para registrar o boleto/PIX e emitir a
    NFS-e conforme a regra (na geração ou na baixa), sem esperar a rodada de hora em hora."""
    if r.get("gerados"):
        automacao.disparar_robo()
    return r


def _contrato_salvo(k: dict) -> dict:
    return _robo_se_gerou(k | {"gerados": financeiro.gerar_do_mes_ao_salvar([k["id"]]) if k.get("ativo") else []})


def _rodar_regua() -> dict:
    r = cobranca.rodar_regua()
    if whatsapp_web.ativo() and cobranca.fila_whatsapp():
        whatsapp_web.em_segundo_plano(whatsapp_web.enviar_fila)      # WhatsApp sai sozinho, sem travar a tela
        r["whatsapp_automatico"] = True
    return r


def _whatsapp_teste(telefone: str) -> dict:
    """Mensagem de teste com o modelo real da cobrança (dados de exemplo), enviada pelo WhatsApp Web."""
    from datetime import date as _d
    cfg = config.carregar()
    venc = financeiro.hoje().isoformat()
    t = {"id": 0, "cliente_nome": "CLIENTE EXEMPLO LTDA", "descricao": "HONORARIOS CONTABEIS", "valor_cent": 35000,
         "vencimento": venc, "competencia": venc[:7], "status": "aberto", "nfse_numero": "", "nfse_link": "",
         "cobranca_link": "", "banco_id": "", "linha_digitavel": "07790.00116 12345.678901 23456.789012 1 99990000035000",
         "pix_copia_cola": "(PIX copia e cola do boleto)", "cartao_link": "", "cartao_status": ""}
    if cartao.configurado(cfg):
        t |= {"cartao_link": "(link do cartão do título)", "cartao_status": "aberto",
              "cartao_total_cent": cartao.valor_no_cartao(35000, 1, cfg)["total_cent"]}
    texto = "*[TESTE — modelo de cobrança do sistema]*\n\n" + cobranca.mensagem(t, 0, cfg, _d.fromisoformat(venc), "whatsapp")[1]
    numero = whatsapp_web.enviar_um(telefone, texto, cfg, so_horario_comercial=False)   # teste do próprio escritório
    return {"ok": True, "mensagem": f"Mensagem de teste enviada pelo WhatsApp para {numero}."}


def _editar_titulo(c: dict) -> dict:
    """Edita o título; se valor ou vencimento mudaram e ele tem boleto/PIX, a cobrança é refeita (boleto antigo
    cancelado no banco, novo registrado com o valor certo)."""
    r = financeiro.editar_titulo(_id(c), c.get("valor"), str(c.get("vencimento") or ""), str(c.get("competencia") or ""),
                                 str(c.get("descricao") or ""))
    t = r["titulo"]
    r["boleto_refeito"] = False
    if r["refazer"] and c.get("refazer", True) is not False and (t.get("banco_id") or t.get("pix_copia_cola") or t.get("cartao_link")):
        tinha_boleto = bool(t.get("banco_id"))
        t = cobranca.refazer_cobranca(t["id"], "Titulo alterado")
        r["boleto_refeito"] = tinha_boleto and bool(t.get("banco_id"))
        r["titulo"] = t
    return r


def _limite_empresas() -> None:
    lim = licenca.limite_empresas()
    if lim and len(empresas.listar()) >= lim:
        raise ValueError(f"A licença permite {lim} empresa(s) nesta instalação. Fale com o fornecedor para ampliar.")


def _novo_titulo(c: dict) -> dict:
    nfse = c.get("nfse") or ("agora" if c.get("emitir_nfse") else "nao")   # agora | pagamento | nao
    tid = financeiro.criar_titulo(c.get("cpf_cnpj", ""), c.get("valor"), c.get("descricao", ""),
                                  c.get("vencimento", ""), c.get("competencia", ""), nfse != "nao",
                                  servico_id=str(c.get("servico_id", "")), cobrar=c.get("cobrar", True) is not False,
                                  apos_pagamento=nfse == "pagamento")
    r = financeiro.emitir_nfse_titulo(tid) if nfse == "agora" else {"sucesso": True, "erros": [], "alertas": []}
    if c.get("cobrar", True) is not False and r.get("sucesso"):
        financeiro._cobrar_agora(tid, r)          # boleto/PIX na hora (não espera o robô)
    return r | {"titulo_id": tid}


def _conferir(c: dict) -> dict:
    rps = emissor.rps_de_dict(c)
    xml, _l, alertas = emissor.preparar(rps, emissor.prestador_do_ambiente(), producao=False)
    return {"sucesso": True, "titulo": f"RPS {rps.numero} válido — serviços R$ {rps.valor_servicos}, "
            f"ISS R$ {rps.valor_iss}, líquido R$ {rps.valor_liquido}", "alertas": alertas, "xml": xml}


def tratar(rota: str, corpo: dict):
    func = ROTAS.get(rota)
    if not func:
        return {"erro": "Rota inválida"}
    if rota not in licenca.ROTAS_LIVRES and not rota.startswith("teste/"):
        lic = licenca.situacao()
        if not lic["liberado"]:
            return {"sucesso": False, "licenca_bloqueada": True, "licenca": lic, "erro": lic["mensagem"]}
    try:
        return func(corpo or {})
    except ErroValidacao as ex:
        return {"sucesso": False, "titulo": "Pendências (nada foi enviado)", "erros": ex.erros, "erro": "; ".join(ex.erros)}
    except (emissor.ErroConfiguracao, ValueError, KeyError, RuntimeError) as ex:   # inclui ErroCartao/ErroInter
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
        livres = caminho in ("/", "") or re.fullmatch(r"/(js/)?[\w-]+\.(html|js|css|png|svg)", caminho)
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

    def _origem_confiavel(self) -> bool:
        """Só a própria tela (http://127.0.0.1:porta) pode chamar a API. Uma página de outro site aberta no mesmo
        computador não consegue: o navegador manda Origin/Sec-Fetch-Site de fora, e o pedido é recusado. Também
        barra "DNS rebinding" (Host que não é o endereço local)."""
        host = (self.headers.get("Host") or "").strip().lower()
        if host.split(":")[0] not in ("127.0.0.1", "localhost"):
            return False
        origem = (self.headers.get("Origin") or "").strip().lower()
        if origem and origem not in (f"http://{host}", "http://127.0.0.1:" + host.split(":")[-1], "http://localhost:" + host.split(":")[-1]):
            return False
        sfs = (self.headers.get("Sec-Fetch-Site") or "").strip().lower()
        if sfs and sfs not in ("same-origin", "none"):
            return False
        if (self.headers.get("Sec-Fetch-Mode") or origem) and self.headers.get("X-Requested-With") != "EmissorItaborai":
            return False                     # veio de um navegador, mas não da nossa tela (ela sempre manda esse cabeçalho)
        return True

    def do_POST(self):  # noqa: N802
        if not self.path.startswith("/api/"):
            return self._responder(404, b"{}", "application/json")
        if not self._origem_confiavel():
            return self._responder(403, json.dumps({"sucesso": False, "erro": "Pedido recusado: origem não autorizada."},
                                                   ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
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


def _e_envia(r):
    """Depois de baixa, emissão ou vínculo pela tela: a nota e o agradecimento saem já (rotina rápida em segundo
    plano), sem esperar a próxima rodada do robô."""
    automacao.disparar_pagamentos()
    return r


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
