# Sobe o proxy LiteLLM (gratuitos -> Claude Haiku 5.5) para o OpenBot usar como
# "servidor compatível com OpenAI": http://127.0.0.1:4000/v1
# Pré-requisitos: Python 3.11+ e  python -m pip install "litellm[proxy]"
# As chaves ficam em proxy\.env (criado a partir de .env.exemplo na 1ª execução).
$Aqui = $PSScriptRoot
$Env = "$Aqui\.env"
if (-not (Test-Path $Env)) { Copy-Item "$Aqui\.env.exemplo" $Env; notepad $Env; Write-Host "Preencha o .env e rode de novo."; exit }
Get-Content $Env | Where-Object { $_ -match '^\s*[^#].*=' } | ForEach-Object {
  $k, $v = $_ -split '=', 2; [Environment]::SetEnvironmentVariable($k.Trim(), $v.Trim(), "Process")
}
Write-Host "Proxy em http://127.0.0.1:4000/v1  | chave: $env:LITELLM_MASTER_KEY | modelos: contabil, contabil-sigiloso" -ForegroundColor Green
litellm --config "$Aqui\config.yaml" --host 127.0.0.1 --port 4000
