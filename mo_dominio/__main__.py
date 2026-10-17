"""
Integração Portal M&O ↔ Domínio Sistemas.

  python -m mo_dominio matriz   ...   matriz de regras de importação a partir dos XML (configurar o Domínio)
  python -m mo_dominio rotinas  ...   descompacta/organiza XML no leiaute da Rotina Automática do Domínio
  python -m mo_dominio ofx      ...   extrato OFX → TXT de lançamentos contábeis

`python -m mo_dominio <comando> --help` mostra as opções de cada um.
"""
import sys

from . import lancamentos, matriz, rotinas

COMANDOS = {"matriz": matriz.main, "rotinas": rotinas.main, "ofx": lancamentos.main}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in COMANDOS:
        print(__doc__.strip())
        return 0 if argv and argv[0] in ("-h", "--help") else 2
    COMANDOS[argv[0]](argv[1:])
    return 0


if __name__ == "__main__":
    sys.exit(main())
