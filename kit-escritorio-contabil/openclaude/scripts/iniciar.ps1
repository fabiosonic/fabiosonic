# Inicia o proxy LiteLLM (janela separada) e abre o OpenClaude na pasta do escritório.
#   .\scripts\iniciar.ps1              -> modelo "contabil" (gratuito -> Haiku)
#   .\scripts\iniciar.ps1 -Sigiloso    -> modelo "contabil-sigiloso" (Ollama local -> Haiku)
param([switch]$Sigiloso)
$Raiz = Split-Path -Parent $PSScriptRoot

# Carrega o .env para o processo atual
Get-Content "$Raiz\.env" | Where-Object { $_ -match '^\s*[^#].*=' } | ForEach-Object {
  $k, $v = $_ -split '=', 2; [Environment]::SetEnvironmentVariable($k.Trim(), $v.Trim(), "Process")
}

# Sobe o proxy se ainda não estiver rodando
$ativo = $false
try { Invoke-WebRequest -UseBasicParsing "http://localhost:4000/health/liveliness" -TimeoutSec 2 | Out-Null; $ativo = $true } catch {}
if (-not $ativo) {
  Start-Process powershell -ArgumentList "-NoExit","-Command","litellm --config `"$Raiz\litellm\config.yaml`" --port 4000" -WindowStyle Minimized
  Write-Host "Aguardando o proxy subir..."
  for ($i=0; $i -lt 30; $i++) { Start-Sleep 2; try { Invoke-WebRequest -UseBasicParsing "http://localhost:4000/health/liveliness" -TimeoutSec 2 | Out-Null; break } catch {} }
}

# Aponta o OpenClaude para o proxy
$env:CLAUDE_CODE_USE_OPENAI = "1"
$env:OPENAI_BASE_URL = "http://localhost:4000/v1"
$env:OPENAI_API_KEY = $env:LITELLM_MASTER_KEY
$env:OPENAI_MODEL = if ($Sigiloso) { "contabil-sigiloso" } else { $env:MODELO_PADRAO }
# Contexto conservador: o menor da cadeia (Groq ~128k) para não estourar no fallback
$env:CLAUDE_CODE_OPENAI_CONTEXT_WINDOWS = '{"contabil":128000,"contabil-sigiloso":32000}'

Set-Location "$env:USERPROFILE\Escritorio-Contabil"
Write-Host "OpenClaude usando modelo: $env:OPENAI_MODEL" -ForegroundColor Green
openclaude
