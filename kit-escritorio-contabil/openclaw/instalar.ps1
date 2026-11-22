# Instala e configura o OpenClaw para o escritório (Windows / PowerShell).
# Na pasta kit-escritorio-contabil\openclaw:
#   powershell -ExecutionPolicy Bypass -File .\instalar.ps1
$ErrorActionPreference = "Stop"
$Aqui = $PSScriptRoot
$Kit  = Split-Path -Parent $Aqui
$Home_OC = "$env:USERPROFILE\.openclaw"
$Carimbo = Get-Date -Format "yyyyMMdd-HHmmss"

if (-not (Test-Path "$Aqui\.env")) {
  Copy-Item "$Aqui\.env.exemplo" "$Aqui\.env"
  Write-Host "Criei openclaw\.env - preencha as chaves e rode este script de novo." -ForegroundColor Yellow
  notepad "$Aqui\.env"; exit
}

Write-Host "== 1/5 OpenClaw ==" -ForegroundColor Cyan
if (-not (Get-Command openclaw -ErrorAction SilentlyContinue)) {
  & ([scriptblock]::Create((iwr -useb https://openclaw.ai/install.ps1))) -NoOnboard
  $env:Path = [Environment]::GetEnvironmentVariable("Path","User") + ";" + [Environment]::GetEnvironmentVariable("Path","Machine")
} else { Write-Host "Já instalado: $(openclaw --version)" }

Write-Host "== 2/5 Chaves de API (variáveis de ambiente do usuário) ==" -ForegroundColor Cyan
Get-Content "$Aqui\.env" | Where-Object { $_ -match '^\s*[A-Z_]+=\S' } | ForEach-Object {
  $k, $v = ($_ -split '#')[0] -split '=', 2; $k=$k.Trim(); $v=$v.Trim()
  if ($v) { [Environment]::SetEnvironmentVariable($k, $v, "User"); Set-Item "env:$k" $v; Write-Host "  $k definido" }
}

Write-Host "== 3/5 Configuração (com backup) ==" -ForegroundColor Cyan
New-Item -ItemType Directory -Force $Home_OC | Out-Null
if (Test-Path "$Home_OC\openclaw.json") { Copy-Item "$Home_OC\openclaw.json" "$Home_OC\openclaw.json.bak-$Carimbo"; Write-Host "  backup: openclaw.json.bak-$Carimbo" }
Copy-Item "$Aqui\openclaw.json" "$Home_OC\openclaw.json" -Force

Write-Host "== 4/5 Workspace do escritório (com backup) ==" -ForegroundColor Cyan
$Ws = "$Home_OC\workspace"
if (Test-Path $Ws) { Copy-Item $Ws "$Ws.bak-$Carimbo" -Recurse; Write-Host "  backup: workspace.bak-$Carimbo" }
New-Item -ItemType Directory -Force "$Ws\skills","$Ws\memory","$Ws\clientes","$Ws\modelos" | Out-Null
Copy-Item "$Kit\workspace\*.md" $Ws -Force
Copy-Item "$Kit\workspace\skills\*" "$Ws\skills" -Recurse -Force

Write-Host "== 5/5 Diagnóstico ==" -ForegroundColor Cyan
openclaw doctor
openclaw onboard --install-daemon

Write-Host "`nPronto! Painel: http://127.0.0.1:18789" -ForegroundColor Green
Write-Host "Se algum provedor aparecer sem chave, feche e abra o PowerShell (ou reinicie o PC) para carregar as variáveis."
