"""Robô financeiro: rotina idempotente que pode rodar a cada hora (tela aberta) e 1x/dia (Agendador do Windows).

Ordem: backup → XML (clientes, notas externas, contratos detectados)
       → despesas recorrentes → títulos do mês (contratos) → NFS-e → cobrança (boleto Inter / PIX)
       → baixa automática (Inter) → extratos OFX da pasta → régua de cobrança → resumo diário por e-mail.
Cada etapa é isolada: uma falha não impede as demais e fica registrada no log.
"""

from __future__ import annotations

import contextlib
import os
import threading
import time
from datetime import date

from . import backup, cobranca, config, db, emissor, financeiro, importacao, importador, inter, saude


TRAVA_MAX_SEG = 2 * 3600


@contextlib.contextmanager
def _trava():
    """Só um robô por vez (tela aberta + Agendador do Windows podem coincidir)."""
    arq = db.caminho().parent / "robo.lock"
    arq.parent.mkdir(parents=True, exist_ok=True)
    if arq.exists() and time.time() - arq.stat().st_mtime > TRAVA_MAX_SEG:
        arq.unlink(missing_ok=True)                    # trava abandonada (queda de energia etc.)
    try:
        fd = os.open(arq, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        yield False
        return
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        yield True
    finally:
        arq.unlink(missing_ok=True)


def rodar(em: date | None = None, forcar: bool = False, url: str | None = None) -> dict:
    from . import licenca
    lic = licenca.situacao()
    if not lic["liberado"]:
        return {"executado": False, "motivo": lic["mensagem"]}
    with _trava() as livre:
        if not livre:
            return {"executado": False, "motivo": "Outra execução do robô está em andamento."}
        return _rodar(em, forcar, url)


def rodar_todas(em: date | None = None, forcar: bool = False) -> dict:
    """Multiempresa: roda a rotina de cada empresa cadastrada, cada uma com a sua pasta (dados e credenciais)."""
    from . import empresas, licenca
    lic = licenca.situacao()
    if not lic["liberado"]:          # licença vencida: o robô não emite, não cobra e não envia nada
        db.registrar("licenca", f"Robô parado: {lic['mensagem']}")
        return {"executado": False, "motivo": lic["mensagem"]}
    res = {}
    for e in empresas.listar():
        with emissor.usar_empresa(empresas.pasta(e)):
            try:
                res[e["nome"]] = rodar(em, forcar)
            except Exception as ex:  # noqa: BLE001 — uma empresa com problema não para as outras
                db.registrar("robo_erro", str(ex))
                res[e["nome"]] = {"executado": False, "motivo": f"erro: {ex}"}
    return res


def _rodar(em: date | None = None, forcar: bool = False, url: str | None = None) -> dict:
    em = em or financeiro.hoje()
    cfg = config.carregar()
    auto = cfg["automacao"]
    if not auto["ativa"] and not forcar:
        return {"executado": False, "motivo": "Automação desligada (Configurações > Robô)."}
    res: dict = {"executado": True, "data": em.isoformat()}

    def etapa(nome, ligado, func):
        if not ligado:
            return
        try:
            res[nome] = func()
        except Exception as ex:  # noqa: BLE001 — o robô nunca para por causa de uma etapa
            res[nome] = f"erro: {ex}"
            db.registrar("robo_erro", f"{nome}: {ex}")

    etapa("backup", auto["backup"], lambda: (db.backup(), backup.automatico())[1])
    etapa("caixa_xml", auto.get("importar_xml"), importador.importar_automatico)
    etapa("importacao_xml", auto.get("importar_xml"), lambda: importacao.importar_xml(em))
    etapa("despesas_recorrentes", auto["despesas_recorrentes"], lambda: financeiro.gerar_despesas_recorrentes(em))
    etapa("titulos_gerados", auto["gerar_titulos"] and em.day >= int(cfg["financeiro"]["dia_geracao"]),
          lambda: len(financeiro.gerar_titulos(em=em)))

    etapa("decimo_terceiro", auto["gerar_titulos"] and cfg["decimo_terceiro"].get("ativo"),
          lambda: len(financeiro.gerar_decimo_terceiro(em)))

    def nfse():
        if not emissor.em_producao():
            return "ambiente de homologação: o robô só emite NFS-e em produção"
        ok = erro = 0
        for t in financeiro.listar_titulos("sem_nfse", em=em):
            pago_aguardando = t["status"] == "pago" and t["nfse_status"] == "pendente"   # nota após o pagamento
            if not pago_aguardando and (t["nfse_status"] not in ("pendente", "teste") or t["status"] != "aberto"):
                continue                      # erros ficam para revisão humana, sem reenvio infinito
            r = financeiro.emitir_nfse_titulo(t["id"], url=url)
            ok, erro = ok + bool(r["sucesso"]), erro + (not r["sucesso"])
        return {"emitidas": ok, "erros": erro}
    etapa("nfse", auto["emitir_nfse"], nfse)

    def cobrancas():
        n, erros = 0, []
        boleto = cfg["cobranca"]["provedor"] == "inter" and inter.configurado(cfg)
        sql = ("SELECT * FROM titulos WHERE status='aberto' AND cobrar=1 AND COALESCE(juridico_em,'')='' AND banco_id=''"
               " AND COALESCE(boleto_situacao,'')=''"
               + ("" if boleto else " AND pix_copia_cola=''"))
        for t in db.linhas(sql):
            if t["nfse_status"] in ("pendente", "erro", "teste"):
                continue                      # cobra junto com a nota válida
            if str(t["cpf_cnpj"]).startswith("99") and len(str(t["cpf_cnpj"])) == 9:
                continue                      # cliente do exterior: sem boleto (recebe por câmbio, baixa manual)
            try:
                financeiro_t = cobranca.preparar_pagamento(t["id"], cfg)
            except Exception as ex:  # noqa: BLE001 — um cadastro incompleto não trava os demais boletos
                erros.append(f"{t['cliente_nome']}: {ex}")
                financeiro.atualizar_titulo(t["id"], cobranca_erro=str(ex)[:300])
                db.registrar("boleto_erro", f"Título {t['id']} ({t['cliente_nome']}): {ex}")
                continue
            n += bool(financeiro_t["pix_copia_cola"] or financeiro_t["banco_id"])
        return {"criadas": n, "erros": erros} if erros else n
    etapa("cobrancas_criadas", auto["criar_cobranca"] and cfg["cobranca"]["provedor"] != "nenhum", cobrancas)
    etapa("baixas_banco", auto.get("sincronizar_banco", True) and cfg["cobranca"]["provedor"] == "inter",
          lambda: cobranca.sincronizar_banco(cfg))
    from . import cartao
    etapa("cartao_links_encerrados", cartao.configurado(cfg), lambda: cartao.encerrar_links(cfg))
    etapa("boletos_pdf", auto.get("baixar_boletos", True) and cfg["cobranca"]["provedor"] == "inter",
          lambda: cobranca.salvar_boletos(cfg=cfg))
    etapa("extratos", auto.get("importar_extratos"), importacao.importar_extratos)
    etapa("extrato_inter", auto.get("extrato_inter", True) and cfg["cobranca"]["provedor"] == "inter"
          and inter.configurado(cfg), importacao.importar_extrato_inter)
    etapa("regua", auto["regua"], lambda: cobranca.rodar_regua(em, cfg))
    from . import whatsapp_web
    etapa("whatsapp_web", auto["regua"] and whatsapp_web.ativo(cfg), lambda: whatsapp_web.enviar_fila(cfg))
    etapa("resumo", auto.get("resumo_diario"), lambda: importacao.resumo_diario(res, em))
    etapa("fechamento", auto.get("fechamento_mensal", True), lambda: saude.fechamento_mensal(em))
    db.registrar("robo", f"Rotina executada: { {k: v for k, v in res.items() if k not in ('executado', 'data')} }")
    return res


# ---------------------------------------------------------------- rotina rápida (pagamentos)

INTERVALO_PAGAMENTOS_MIN = 15
AGENDA = {"ultima": "", "proxima": "", "resultado": ""}


def _intervalo(cfg: dict) -> int:
    try:
        return max(5, int(cfg["automacao"].get("intervalo_extrato_min") or INTERVALO_PAGAMENTOS_MIN))
    except (TypeError, ValueError):
        return INTERVALO_PAGAMENTOS_MIN


def _rodar_pagamentos(em: date) -> dict:
    """Extrato do Inter e .ofx da pasta, baixas dos boletos, NFS-e de quem pagou e envio da nota/agradecimento."""
    cfg = config.carregar()
    auto = cfg["automacao"]
    if not auto["ativa"]:
        return {"executado": False}
    res: dict = {}

    def etapa(nome, ligado, func):
        if not ligado:
            return
        try:
            res[nome] = func()
        except Exception as ex:  # noqa: BLE001
            res[nome] = f"erro: {ex}"
            db.registrar("robo_erro", f"{nome} (rotina rápida): {ex}")
    inter_ok = cfg["cobranca"]["provedor"] == "inter" and inter.configurado(cfg)
    # recorrência: o título do mês não depende só da rodada de hora em hora (o boleto/NFS-e saem na rodada do robô)
    etapa("titulos_gerados", auto["gerar_titulos"] and em.day >= int(cfg["financeiro"]["dia_geracao"]),
          lambda: len(financeiro.gerar_titulos(em=em)))
    etapa("baixas_banco", auto.get("sincronizar_banco", True) and inter_ok, lambda: cobranca.sincronizar_banco(cfg))
    etapa("extrato_inter", auto.get("extrato_inter", True) and inter_ok, importacao.importar_extrato_inter)
    etapa("extratos", auto.get("importar_extratos"), importacao.importar_extratos)

    def notas_pagas():
        if not emissor.em_producao():
            return 0
        n = 0
        for t in db.linhas("SELECT id FROM titulos WHERE status='pago' AND nfse_status='pendente'"):
            n += bool(financeiro.emitir_nfse_titulo(t["id"])["sucesso"])
        return n
    etapa("nfse", auto["emitir_nfse"], notas_pagas)
    etapa("envio_notas", auto["regua"], lambda: cobranca.enviar_pos_pagamento(em, cfg))
    from . import whatsapp_web
    etapa("whatsapp_web", auto["regua"] and whatsapp_web.ativo(cfg), lambda: whatsapp_web.enviar_fila(cfg))
    return res


def rodar_pagamentos(em: date | None = None) -> dict:
    """Rotina rápida de todas as empresas (a cada 15 min com o sistema aberto). Não roda junto com o robô completo."""
    from . import empresas, licenca
    if not licenca.situacao()["liberado"]:
        return {"executado": False}
    em = em or financeiro.hoje()
    res = {}
    for e in empresas.listar():
        with emissor.usar_empresa(empresas.pasta(e)):
            with _trava() as livre:
                if not livre:
                    res[e["nome"]] = {"executado": False, "motivo": "robô em andamento"}
                    continue
                try:
                    res[e["nome"]] = _rodar_pagamentos(em)
                except Exception as ex:  # noqa: BLE001
                    db.registrar("robo_erro", f"rotina rápida: {ex}")
    from datetime import datetime
    AGENDA["ultima"] = datetime.now(emissor.FUSO).strftime("%Y-%m-%d %H:%M")
    return res


def disparar_pagamentos() -> None:
    """Roda a rotina rápida agora, em segundo plano (depois de uma baixa ou emissão pela tela)."""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return                                   # testes: sem rotina paralela mexendo no banco
    threading.Thread(target=lambda: _seguro(rodar_pagamentos), daemon=True, name="pagamentos-agora").start()


def disparar_robo() -> None:
    """Rodada completa do robô agora, em segundo plano (ex.: recorrência salva gerou o título do mês)."""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return
    threading.Thread(target=lambda: _seguro(rodar_todas), daemon=True, name="robo-agora").start()


def _seguro(f):
    try:
        f()
    except Exception as ex:  # noqa: BLE001
        db.registrar("robo_erro", f"rotina rápida: {ex}")


_thread_rapida: threading.Thread | None = None


_thread: threading.Thread | None = None


def iniciar_em_segundo_plano(intervalo_min: int = 60) -> None:
    """Enquanto a tela estiver aberta, roda a rotina ao abrir e depois a cada hora."""
    global _thread
    if _thread and _thread.is_alive():
        return

    def laco():
        while True:
            try:
                rodar_todas()
            except Exception as ex:  # noqa: BLE001
                db.registrar("robo_erro", str(ex))
            time.sleep(intervalo_min * 60)

    _thread = threading.Thread(target=laco, daemon=True, name="robo-financeiro")
    _thread.start()
    global _thread_rapida
    if _thread_rapida and _thread_rapida.is_alive():
        return

    def laco_rapido():
        from datetime import datetime, timedelta as td
        time.sleep(120)                                  # o robô completo já roda ao abrir
        while True:
            minutos = _intervalo(config.carregar())
            _seguro(rodar_pagamentos)
            AGENDA["proxima"] = (datetime.now(emissor.FUSO) + td(minutes=minutos)).strftime("%Y-%m-%d %H:%M")
            time.sleep(minutos * 60)
    _thread_rapida = threading.Thread(target=laco_rapido, daemon=True, name="pagamentos-15min")
    _thread_rapida.start()
