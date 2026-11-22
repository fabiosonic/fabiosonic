# Instalação no Windows (PowerShell). Rode na pasta openclaude-contabil:
#   powershell -ExecutionPolicy Bypass -File .\scripts\instalar.ps1
$ErrorActionPreference = "Stop"
$Raiz = Split-Path -Parent $PSScriptRoot

Write-Host "== 1/4 Verificando Node.js e Python ==" -ForegroundColor Cyan
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw "Instale o Node.js 24.22+ (recomendado 26): https://nodejs.org" }
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw "Instale o Python 3.11+: https://www.python.org (marque 'Add to PATH')" }
node --version; python --version

Write-Host "== 2/4 Instalando/atualizando OpenClaude ==" -ForegroundColor Cyan
npm uninstall -g @gitlawb/openclaude 2>$null   # pacote antigo, conflita com o novo
npm install -g @twigpine/openclaude@latest
if (-not (Get-Command rg -ErrorAction SilentlyContinue)) {
  Write-Host "ripgrep não encontrado; tentando instalar via winget..."
  winget install --id BurntSushi.ripgrep.MSVC -e --accept-source-agreements --accept-package-agreements
}

Write-Host "== 3/4 Instalando proxy LiteLLM ==" -ForegroundColor Cyan
python -m pip install --upgrade "litellm[proxy]"

Write-Host "== 4/4 Preparando .env e pasta do escritório ==" -ForegroundColor Cyan
if (-not (Test-Path "$Raiz\.env")) { Copy-Item "$Raiz\.env.exemplo" "$Raiz\.env"; Write-Host "Criado .env - ABRA E PREENCHA AS CHAVES." -ForegroundColor Yellow }
$Destino = "$env:USERPROFILE\Escritorio-Contabil"
if (-not (Test-Path $Destino)) {
  New-Item -ItemType Directory -Force "$Destino\.openclaude" | Out-Null
  Copy-Item "$Raiz\..\workspace\*.md" $Destino
  Copy-Item "$Raiz\..\workspace\AGENTS.md" "$Destino\CLAUDE.md"
  Copy-Item "$Raiz\..\workspace\skills" "$Destino\.openclaude\skills" -Recurse
  Write-Host "Pasta de trabalho criada em $Destino"
}

Write-Host "`nPronto. Preencha o .env e depois rode: .\scripts\iniciar.ps1" -ForegroundColor Green
