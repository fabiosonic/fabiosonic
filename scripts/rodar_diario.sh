#!/usr/bin/env bash
# Rotina diária: produz e publica o que foi aprovado e busca pautas novas para revisão.
# Exemplo de agendamento (crontab -e), todo dia às 7h10:
#   10 7 * * * /caminho/para/o/repositorio/scripts/rodar_diario.sh >> /caminho/para/o/repositorio/data/rotina.log 2>&1
set -euo pipefail
cd "$(dirname "$0")/.."
[ -d .venv ] && source .venv/bin/activate

echo "=== $(date -Iseconds) ==="
python -m avatar_contabil.cli produzir
python -m avatar_contabil.cli publicar
python -m avatar_contabil.cli pautas
python -m avatar_contabil.cli fila --status pendente_revisao
