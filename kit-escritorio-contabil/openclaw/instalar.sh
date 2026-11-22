#!/usr/bin/env bash
# Linux / macOS / WSL2:  bash instalar.sh
set -euo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"; KIT="$(dirname "$AQUI")"
OC="$HOME/.openclaw"; TS="$(date +%Y%m%d-%H%M%S)"
[ -f "$AQUI/.env" ] || { cp "$AQUI/.env.exemplo" "$AQUI/.env"; echo "Preencha $AQUI/.env e rode de novo."; exit 0; }
command -v openclaw >/dev/null || curl -fsSL https://openclaw.ai/install.sh | bash -s -- --no-onboard
# Chaves no perfil do shell
PERFIL="$HOME/.bashrc"; [ -n "${ZSH_VERSION:-}" ] && PERFIL="$HOME/.zshrc"
grep -E '^[A-Z_]+=\S' "$AQUI/.env" | sed 's/#.*//' | while IFS='=' read -r k v; do
  v="$(echo "$v" | xargs)"; [ -n "$v" ] || continue
  sed -i.bak "/^export $k=/d" "$PERFIL"; echo "export $k=\"$v\"" >> "$PERFIL"; echo "  $k definido"
done
mkdir -p "$OC"
[ -f "$OC/openclaw.json" ] && cp "$OC/openclaw.json" "$OC/openclaw.json.bak-$TS"
cp "$AQUI/openclaw.json" "$OC/openclaw.json"
[ -d "$OC/workspace" ] && cp -r "$OC/workspace" "$OC/workspace.bak-$TS"
mkdir -p "$OC/workspace"/{skills,memory,clientes,modelos}
cp "$KIT"/workspace/*.md "$OC/workspace/"; cp -r "$KIT"/workspace/skills/* "$OC/workspace/skills/"
set -a; source "$AQUI/.env"; set +a
openclaw doctor
openclaw onboard --install-daemon
echo "Pronto! Painel: http://127.0.0.1:18789"
