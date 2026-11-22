# Alterna a cadeia de modelos do OpenClaw.
#   .\modo-sigiloso.ps1          -> SIGILOSO: Ollama local -> Haiku (dados de clientes não vão para planos gratuitos)
#   .\modo-sigiloso.ps1 -Normal  -> NORMAL:   gratuitos -> Haiku
param([switch]$Normal)
$Arq = "$env:USERPROFILE\.openclaw\openclaw.json"
$Txt = Get-Content $Arq -Raw
$Normal_P = 'primary: "google/gemini-3.8-flash"'
$Sigil_P  = 'primary: "ollama/qwen2.5:14b"'
if ($Normal) {
  $Txt = $Txt.Replace($Sigil_P, $Normal_P)
  $Txt = $Txt -replace '(?s)fallbacks:\s*\[[^\]]*\]', 'fallbacks: ["groq/openai/gpt-oss-120b", "openrouter/deepseek/deepseek-chat-v3-0324:free", "ollama/qwen2.5:14b", "anthropic/claude-haiku-5-5"]'
  Write-Host "Modo NORMAL ativo (gratuitos -> Haiku)." -ForegroundColor Green
} else {
  $Txt = $Txt.Replace($Normal_P, $Sigil_P)
  $Txt = $Txt -replace '(?s)fallbacks:\s*\[[^\]]*\]', 'fallbacks: ["anthropic/claude-haiku-5-5"]'
  Write-Host "Modo SIGILOSO ativo (Ollama local -> Haiku)." -ForegroundColor Yellow
}
Set-Content $Arq $Txt -Encoding UTF8   # o Gateway recarrega sozinho ao salvar
openclaw config get agents.defaults.model
