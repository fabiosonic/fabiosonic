"""
Uso:
  python -m mo_openfinance importar-protocolo --db of.db --json resposta_protocolo.json
  python -m mo_openfinance webhook            --db of.db --json evento.json
  python -m mo_openfinance exportar           --db of.db --config config_empresa.json --saida lanc.txt \
                                              [--pendencias pendencias.csv] [--ate AAAA-MM-DD] [--competencia AAAA-MM]
  python -m mo_openfinance sincronizar        --db of.db --pagadores pagadores.json      (TecnoSpeed, usa a rede)
  python -m mo_openfinance demo                                                           (offline, com exemplos/)

Variáveis de ambiente (sincronizar): TECNOSPEED_CNPJ_SH, TECNOSPEED_TOKEN_SH, TECNOSPEED_AMBIENTE=homologacao|producao.
`pagadores.json` mapeia empresa → CPF/CNPJ do pagador cadastrado na TecnoSpeed.
"""
import argparse
import json
import os
import sys
import tempfile
from datetime import date

from . import contabil, sincronizar
from .banco import Banco
from .provedores import TecnoSpeed, normalizar_protocolo_tecnospeed

EXEMPLOS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "exemplos", "openfinance")


def _ler_json(caminho):
    with open(caminho, encoding="utf-8") as fh:
        return json.load(fh)


def importar_protocolo(db, caminho):
    status, motivo, novas = normalizar_protocolo_tecnospeed(_ler_json(caminho))
    if status != "SUCCESS":
        return f"protocolo {status}: {motivo}"
    return f"{db.gravar(novas)} transação(ões) nova(s) de {len(novas)} recebida(s)"


def exportar(db, cfg, saida, pendencias=None, ate=None, competencia=None, hoje=None):
    if competencia and not contabil.fechamento_liberado(competencia, hoje or date.today()):
        print(f"aviso: competência {competencia} ainda está na janela de reprocessamento do provedor "
              "(7 dias após o fim do mês); exclusões na origem ainda podem chegar", file=sys.stderr)
    contas = list(cfg.contas_banco)
    novas = [t for t in db.a_exportar(ate=ate) if t.conta in contas]
    estornos = [t for t in db.a_estornar() if t.conta in contas]
    linhas = [p for t in novas for p in contabil.partidas(t, cfg)]
    linhas += [p for t in estornos for p in contabil.partidas(t, cfg, estorno=True)]
    contabil.gravar_txt_dominio(saida, linhas)
    if pendencias:
        contabil.gravar_pendencias(pendencias, linhas)
    db.marcar_exportadas([t.id for t in novas])
    db.marcar_exportadas([t.id for t in estornos], estorno=True)
    n_pend = sum(1 for p in linhas if p.pendente)
    return f"{len(linhas)} partida(s) ({len(novas)} transação(ões), {len(estornos)} estorno(s)); {n_pend} pendência(s)"


def demo():
    pasta = tempfile.mkdtemp(prefix="mo_openfinance_")
    db = Banco(os.path.join(pasta, "of.db"))
    cfg = contabil.Configuracao.carregar(os.path.join(EXEMPLOS, "config_empresa.json"))
    print("1.", importar_protocolo(db, os.path.join(EXEMPLOS, "protocolo_bank.json")))
    print("2. reimportar o mesmo protocolo:", importar_protocolo(db, os.path.join(EXEMPLOS, "protocolo_bank.json")))
    print("3.", exportar(db, cfg, os.path.join(pasta, "lancamentos.txt"), os.path.join(pasta, "pendencias.csv")))
    print("4. webhook:", sincronizar.processar_webhook(db, _ler_json(os.path.join(EXEMPLOS, "webhook_transaction_deleted.json"))))
    print("5.", exportar(db, cfg, os.path.join(pasta, "estornos.txt")))
    for nome in ("lancamentos.txt", "pendencias.csv", "estornos.txt"):
        print(f"\n--- {nome}")
        with open(os.path.join(pasta, nome), encoding="cp1252" if nome.endswith(".txt") else "utf-8-sig") as fh:
            print(fh.read().rstrip())
    print(f"\narquivos em {pasta}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="mo_openfinance", description="Extrato Open Finance → lançamentos do Domínio")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for nome in ("importar-protocolo", "webhook"):
        s = sub.add_parser(nome)
        s.add_argument("--db", required=True)
        s.add_argument("--json", required=True)
    s = sub.add_parser("exportar")
    s.add_argument("--db", required=True)
    s.add_argument("--config", required=True)
    s.add_argument("--saida", required=True)
    s.add_argument("--pendencias")
    s.add_argument("--ate")
    s.add_argument("--competencia")
    s = sub.add_parser("sincronizar")
    s.add_argument("--db", required=True)
    s.add_argument("--pagadores", required=True)
    sub.add_parser("demo")
    a = ap.parse_args(argv)

    if a.cmd == "demo":
        return demo()
    db = Banco(a.db)
    if a.cmd == "importar-protocolo":
        print(importar_protocolo(db, a.json))
    elif a.cmd == "webhook":
        print(sincronizar.processar_webhook(db, _ler_json(a.json)))
    elif a.cmd == "exportar":
        print(exportar(db, contabil.Configuracao.carregar(a.config), a.saida, a.pendencias, a.ate, a.competencia))
    elif a.cmd == "sincronizar":
        prov, pag = TecnoSpeed(), _ler_json(a.pagadores)
        print("protocolos gerados:", sincronizar.solicitar_extratos(db, prov, pag))
        print("protocolos recolhidos:", sincronizar.recolher_protocolos(db, prov, pag))


if __name__ == "__main__":
    main()
