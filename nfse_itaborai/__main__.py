"""Linha de comando: python -m nfse_itaborai {conferir,emitir,cancelar,tela} ..."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import cliente, emissor
from .validacao import ErroValidacao


def _imprimir(resp: cliente.Resposta) -> int:
    for a in resp.alertas:
        print(f"ALERTA: {a}")
    if resp.sucesso:
        for n in resp.notas:
            print(f"NFS-e {n.numero_nfse} emitida | RPS {n.numero_rps} | verificação {n.codigo_verificacao}")
            if n.link:
                print(f"  {n.link}")
        if resp.situacao:
            print(f"Situação: {resp.situacao}")
    else:
        print("NÃO EMITIDA / NÃO PROCESSADA:")
        for e in resp.erros:
            print(f"  - {e}")
    print(f"Arquivos em: {resp.pasta}")
    return 0 if resp.sucesso else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="nfse_itaborai", description="Emissor de NFS-e de Itaboraí/RJ via webservice")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("conferir", help="valida o RPS e mostra o XML, sem enviar")
    c.add_argument("arquivo", type=Path)

    e = sub.add_parser("emitir", help="envia o RPS e converte em NFS-e")
    e.add_argument("arquivo", type=Path)
    e.add_argument("--producao", action="store_true", help="envia em produção (padrão: homologação)")

    x = sub.add_parser("cancelar", help="cancela uma NFS-e")
    x.add_argument("numero_nfse")
    x.add_argument("justificativa")
    x.add_argument("--producao", action="store_true")

    t = sub.add_parser("tela", help="abre a tela de emissão no navegador (http://127.0.0.1:8765)")
    t.add_argument("--porta", type=int, default=8765)

    a = ap.parse_args(argv)
    try:
        if a.cmd == "conferir":
            rps = emissor.rps_de_dict(json.loads(a.arquivo.read_text(encoding="utf-8")))
            xml, lote, alertas = emissor.preparar(rps, emissor.prestador_do_ambiente(), producao=False)
            for al in alertas:
                print(f"ALERTA: {al}", file=sys.stderr)
            print(xml)
            print(f"\nOK: RPS {rps.numero} válido | serviços {rps.valor_servicos} | ISS {rps.valor_iss} "
                  f"| líquido {rps.valor_liquido}", file=sys.stderr)
            return 0
        if a.cmd == "emitir":
            rps = emissor.rps_de_dict(json.loads(a.arquivo.read_text(encoding="utf-8")))
            return _imprimir(emissor.emitir(rps, producao=a.producao))
        if a.cmd == "cancelar":
            return _imprimir(emissor.cancelar(a.numero_nfse, a.justificativa, producao=a.producao))
        if a.cmd == "tela":
            from .tela import servir
            servir(a.porta)
            return 0
    except ErroValidacao as ex:
        print("RPS com pendências (nada foi enviado):")
        for err in ex.erros:
            print(f"  - {err}")
        return 2
    except (emissor.ErroConfiguracao, ValueError, KeyError) as ex:
        print(f"Erro: {ex}")
        return 2
    except OSError as ex:
        print(f"Falha de comunicação com o webservice: {ex}")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
