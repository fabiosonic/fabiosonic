#!/usr/bin/env bash
# Instalação em Linux/macOS. Rode na pasta openclaude-contabil: bash scripts/instalar.sh
set -euo pipefail
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
command -v node >/dev/null || { echo "Instale o Node.js 24.22+"; exit 1; }
command -v python3 >/dev/null || { echo "Instale o Python 3.11+"; exit 1; }
npm uninstall -g @gitlawb/openclaude 2>/dev/null || true
npm install -g @twigpine/openclaude@latest
command -v rg >/dev/null || echo "AVISO: instale o ripgrep (apt install ripgrep / brew install ripgrep)"
python3 -m pip install --upgrade "litellm[proxy]"
[ -f "$RAIZ/.env" ] || { cp "$RAIZ/.env.exemplo" "$RAIZ/.env"; echo "Criado .env - preencha as chaves."; }
if [ ! -d "$HOME/Escritorio-Contabil" ]; then
  mkdir -p "$HOME/Escritorio-Contabil/.openclaude"
  cp "$RAIZ"/../workspace/*.md "$HOME/Escritorio-Contabil/"
  cp "$RAIZ/../workspace/AGENTS.md" "$HOME/Escritorio-Contabil/CLAUDE.md"
  cp -r "$RAIZ/../workspace/skills" "$HOME/Escritorio-Contabil/.openclaude/skills"
fi
echo "Pronto. Preencha o .env e rode: bash scripts/iniciar.sh"
