#!/usr/bin/env bash
# bash scripts/iniciar.sh            -> "contabil"
# bash scripts/iniciar.sh sigiloso   -> "contabil-sigiloso"
set -euo pipefail
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
set -a; source "$RAIZ/.env"; set +a
if ! curl -sf http://localhost:4000/health/liveliness >/dev/null; then
  nohup litellm --config "$RAIZ/litellm/config.yaml" --port 4000 > "$RAIZ/litellm.log" 2>&1 &
  for _ in $(seq 30); do sleep 2; curl -sf http://localhost:4000/health/liveliness >/dev/null && break; done
fi
export CLAUDE_CODE_USE_OPENAI=1
export OPENAI_BASE_URL=http://localhost:4000/v1
export OPENAI_API_KEY="$LITELLM_MASTER_KEY"
export OPENAI_MODEL="${MODELO_PADRAO:-contabil}"
[ "${1:-}" = "sigiloso" ] && export OPENAI_MODEL=contabil-sigiloso
export CLAUDE_CODE_OPENAI_CONTEXT_WINDOWS='{"contabil":128000,"contabil-sigiloso":32000}'
cd "$HOME/Escritorio-Contabil"
echo "OpenClaude usando modelo: $OPENAI_MODEL"
exec openclaude
