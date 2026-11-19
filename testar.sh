#!/usr/bin/env bash
# Testes do M&O XML Captador (laboratório interno, nenhum acesso à SEFAZ).
# Uso: ./testar.sh            -> prepara o ambiente se preciso e roda tudo
#      ./testar.sh -k chave   -> repassa argumentos ao pytest (ex.: filtrar por nome)
set -euo pipefail
cd "$(dirname "$0")/backend"
PY=""
for c in python3.14 python3.13 python3.12 python3; do command -v "$c" >/dev/null 2>&1 && { PY="$c"; break; }; done
[ -n "$PY" ] || { echo "[ERRO] Python 3 não encontrado."; exit 1; }
if [ ! -x .venv/bin/python ]; then echo "Preparando o ambiente..."; "$PY" -m venv .venv; fi
VPY=.venv/bin/python
if ! "$VPY" -c "import pytest, fastapi, lxml, cryptography" >/dev/null 2>&1; then
  echo "Instalando dependências (uma única vez)..."
  "$VPY" -m pip install --upgrade pip >/dev/null
  "$VPY" -m pip install -r requirements.txt -e . >/dev/null
fi
echo
"$VPY" -m pytest tests -v -p no:warnings "$@"
