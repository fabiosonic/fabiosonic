"""Linha de comando.

    python -m mo_obrigacoes init                     # cria o banco e carrega o catálogo
    python -m mo_obrigacoes importar empresas.csv    # importa a carteira
    python -m mo_obrigacoes agenda --competencia 2026-09
    python -m mo_obrigacoes sync [--completo]        # varre o Google Drive
    python -m mo_obrigacoes alertas                  # envia resumos e cobranças
    python -m mo_obrigacoes worker                   # rotina contínua (sync + agenda + alertas)
    python -m mo_obrigacoes serve --porta 8000       # painel web
    python -m mo_obrigacoes demo                     # dados de demonstração (Drive local)
"""
from __future__ import annotations

import argparse
import csv
import logging
import time
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import select

from .agenda import gerar_agenda
from .alertas import executar_alertas
from .calendario import competencia_anterior, competencia_str, somar_meses
from .catalogo import sincronizar_catalogo
from .classificador import so_digitos
from .config import get_config
from .db import criar_tabelas, sessao
from .drive import extrair_id_pasta
from .models import Empresa

log = logging.getLogger("mo_obrigacoes")


def cmd_init(_args) -> None:
    criar_tabelas()
    with sessao() as s:
        n = sincronizar_catalogo(s)
    print(f"Banco pronto. Catálogo com {n} obrigações.")


def _preparar_banco() -> None:
    """Cria tabelas, aplica migrações e carrega o catálogo atual (vigência, regras novas)."""
    criar_tabelas()
    with sessao() as s:
        sincronizar_catalogo(s)


def _bool(v: str) -> bool:
    return str(v).strip().lower() in {"1", "s", "sim", "x", "true", "yes"}


def cmd_importar(args) -> None:
    """CSV (separador ;) com colunas: codigo;razao_social;cnpj;regime;uf;municipio;comercio;industria;servicos;
    possui_funcionarios;possui_prolabore;retem_tributos;email_cliente;drive_folder_id"""
    _preparar_banco()
    novos = atualizados = 0
    with sessao() as s, open(args.arquivo, encoding="utf-8-sig") as f:
        for linha in csv.DictReader(f, delimiter=";"):
            cnpj = so_digitos(linha["cnpj"])
            emp = s.scalar(select(Empresa).where(Empresa.cnpj == cnpj))
            if emp is None:
                emp = Empresa(cnpj=cnpj)
                s.add(emp)
                novos += 1
            else:
                atualizados += 1
            emp.codigo = linha["codigo"].strip()
            emp.razao_social = linha["razao_social"].strip().upper()
            emp.regime = linha.get("regime", "SIMPLES").strip().upper() or "SIMPLES"
            for campo in ("uf", "municipio", "email_cliente", "drive_folder_id", "nome_fantasia", "whatsapp_cliente"):
                if linha.get(campo) is not None:
                    valor = linha[campo].strip()
                    setattr(emp, campo, extrair_id_pasta(valor) if campo == "drive_folder_id" else valor)
            for flag in ("comercio", "industria", "servicos", "possui_funcionarios", "possui_prolabore",
                         "retem_tributos", "area_saude", "atividade_imobiliaria"):
                if linha.get(flag) is not None:
                    setattr(emp, flag, _bool(linha[flag]))
    print(f"{novos} empresa(s) nova(s), {atualizados} atualizada(s).")


def cmd_agenda(args) -> None:
    _preparar_banco()
    with sessao() as s:
        r = gerar_agenda(s, args.competencia or competencia_anterior())
    print(f"Agenda {r['competencia']}: {r['tarefas_criadas']} tarefa(s) criada(s) para {r['empresas']} empresa(s).")


def cmd_sync(args) -> None:
    from .drive import criar_cliente
    from .monitor import Monitor

    _preparar_banco()
    with sessao() as s:
        r = Monitor(s, criar_cliente()).sincronizar(completo=args.completo)
    print(r.as_dict())


def cmd_alertas(_args) -> None:
    _preparar_banco()
    with sessao() as s:
        print(executar_alertas(s))


def cmd_worker(args) -> None:
    """Loop simples: varre o Drive a cada N minutos, gera a agenda e envia alertas 1x ao dia (7h)."""
    cfg = get_config()
    _preparar_banco()
    ultimo_alerta: date | None = None
    while True:
        agora = datetime.now()
        try:
            with sessao() as s:
                # anterior (fechamento), corrente e próxima: obrigações anuais da competência 12 com prazo
                # em novembro/dezembro (13º salário, DCTFWeb anual) precisam existir com antecedência
                for deslocamento in (-1, 0, 1):
                    ano, mes = somar_meses(agora.year, agora.month, deslocamento)
                    gerar_agenda(s, competencia_str(ano, mes))
            cmd_sync(argparse.Namespace(completo=False))
        except Exception:  # noqa: BLE001
            log.exception("Falha na agenda/sincronização do worker")
        if agora.hour >= args.hora_alertas and ultimo_alerta != agora.date():
            ultimo_alerta = agora.date()  # marca ANTES: uma falha não pode reenviar e-mails a cada ciclo
            try:
                cmd_alertas(None)
            except Exception:  # noqa: BLE001
                log.exception("Falha ao enviar alertas (não será repetido hoje)")
        if args.uma_vez:
            break
        time.sleep(cfg.sync_interval_minutes * 60)


def cmd_serve(args) -> None:
    import uvicorn

    uvicorn.run("mo_obrigacoes.web.app:app", host=args.host, port=args.porta, reload=False)


def cmd_demo(_args) -> None:
    """Cria empresas fictícias e um 'Drive' local com documentos de exemplo."""
    from .demo import criar_demo

    criar_tabelas()
    with sessao() as s:
        sincronizar_catalogo(s)
        print(criar_demo(s, Path(get_config().local_drive_path)))


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(prog="mo_obrigacoes", description="Monitor de obrigações - Moraes e Oliveira")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init").set_defaults(func=cmd_init)
    sp = sub.add_parser("importar")
    sp.add_argument("arquivo")
    sp.set_defaults(func=cmd_importar)
    sp = sub.add_parser("agenda")
    sp.add_argument("--competencia", help="AAAA-MM (padrão: mês anterior)")
    sp.set_defaults(func=cmd_agenda)
    sp = sub.add_parser("sync")
    sp.add_argument("--completo", action="store_true", help="reprocessa todos os arquivos")
    sp.set_defaults(func=cmd_sync)
    sub.add_parser("alertas").set_defaults(func=cmd_alertas)
    sp = sub.add_parser("worker")
    sp.add_argument("--hora-alertas", type=int, default=7)
    sp.add_argument("--uma-vez", action="store_true")
    sp.set_defaults(func=cmd_worker)
    sp = sub.add_parser("serve")
    sp.add_argument("--host", default="0.0.0.0")
    sp.add_argument("--porta", type=int, default=8000)
    sp.set_defaults(func=cmd_serve)
    sub.add_parser("demo").set_defaults(func=cmd_demo)
    args = p.parse_args(argv)
    args.func(args)

