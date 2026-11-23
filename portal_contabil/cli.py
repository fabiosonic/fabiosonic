"""Linha de comando: python -m portal_contabil auditar <pastas|zips|arquivos> [opções]."""
from __future__ import annotations

import argparse
import sys

from .auditoria import auditar
from .importadores import importar
from .relatorio import ROTULO_SEV, salvar
from .util import fmt_doc, moeda


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="portal_contabil", description="Importa e audita documentos fiscais.")
    sub = p.add_subparsers(dest="comando", required=True)

    a = sub.add_parser("auditar", help="importa arquivos (XML, ZIP, OFX, CSV) e gera o relatório")
    a.add_argument("entradas", nargs="+", help="pastas, arquivos ZIP ou arquivos soltos")
    a.add_argument("--cnpj", help="CNPJ da empresa auditada (padrão: o mais frequente nos documentos)")
    a.add_argument("--regime", choices=["auto", "simples", "mei", "normal"], default="auto")
    a.add_argument("--saida", default="relatorio_auditoria", help="pasta de saída dos relatórios")

    w = sub.add_parser("web", help="sobe o portal web de upload e auditoria")
    w.add_argument("--host", default="127.0.0.1")
    w.add_argument("--porta", type=int, default=8000)

    args = p.parse_args(argv)
    if args.comando == "web":
        import uvicorn
        uvicorn.run("portal_contabil.web.app:app", host=args.host, port=args.porta)
        return 0

    lote = importar(*args.entradas)
    res = auditar(lote, cnpj=args.cnpj, regime=args.regime)
    arquivos = salvar(res, args.saida)

    emp = res.empresa
    print(f"Empresa: {emp.nome or '-'} | CNPJ {fmt_doc(emp.cnpj)} | regime: {emp.regime}")
    print(f"Arquivos lidos: {lote.arquivos_lidos} | documentos: {len(lote.documentos)} | "
          f"lançamentos: {len(lote.lancamentos)} | erros: {len(lote.erros)}")
    print(f"Índice de conformidade: {res.indice_conformidade}/100")
    for s, n in res.por_severidade().items():
        if n:
            print(f"  {ROTULO_SEV[s]:<12} {n}")
    print("\nPrincipais achados:")
    for ach in res.achados[:10]:
        valor = f" [{moeda(ach.valor)}]" if ach.valor else ""
        print(f"  [{ach.severidade}] {ach.codigo} {ach.titulo}{valor}")
    print("\nRelatórios:")
    for tipo, caminho in arquivos.items():
        print(f"  {tipo.upper():<5} {caminho}")
    return 2 if any(x.severidade == "CRITICO" for x in res.achados) else 0


if __name__ == "__main__":
    sys.exit(main())
