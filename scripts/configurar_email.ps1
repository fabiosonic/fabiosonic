# Configura a caixa fiscal@ no mo_autonomo a partir do programa já existente no PC.
# Roda NO PC DO ESCRITÓRIO (PowerShell), dentro da pasta do projeto.
# - Procura servidor/porta IMAP nos arquivos de D:\AUTOMAÇÕES FUNCIONANDO\email_backup
#   SEM exibir linhas de senha.
# - A senha vai direto para o Cofre de Credenciais do Windows (keyring); nunca para arquivo.
# - Grava host/porta/usuário em config\config.yaml (modo continua SIMULAÇÃO).
param(
    [string]$Origem = "D:\AUTOMAÇÕES FUNCIONANDO\email_backup",
    [string]$Usuario = "fiscal@moraeseoliveiracontabil.com.br"
)
$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz
$py = Join-Path $raiz ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { throw "Rode antes scripts\instalar_windows.ps1" }

Write-Host "Procurando servidor/porta em $Origem (linhas com senha/password são ocultadas)..." -ForegroundColor Cyan
if (Test-Path $Origem) {
    Get-ChildItem -Path $Origem -Recurse -File -Include *.py,*.json,*.ini,*.cfg,*.conf,*.yaml,*.yml,*.txt,*.env,*.toml -ErrorAction SilentlyContinue |
        Select-String -Pattern 'imap|host|server|servidor|port|porta' -ErrorAction SilentlyContinue |
        Where-Object { $_.Line -notmatch '(?i)senha|pass|pwd|secret|token|key' } |
        ForEach-Object { "{0}:{1}: {2}" -f $_.Path, $_.LineNumber, $_.Line.Trim() } |
        Select-Object -First 40
} else {
    Write-Host "Pasta não encontrada: $Origem" -ForegroundColor Yellow
}

$imapHost = Read-Host "Servidor IMAP (ex.: imap.dominio.com.br)"
$porta = Read-Host "Porta IMAP (normalmente 993 com SSL)"
if (-not $porta) { $porta = "993" }

Write-Host "Digite a senha da caixa $Usuario (não aparece na tela; vai para o Cofre do Windows):"
& $py -c "import keyring,getpass; keyring.set_password('mo_autonomo_imap','$Usuario', getpass.getpass('Senha: '))"

& $py -c @"
import yaml, pathlib
p = pathlib.Path('config/config.yaml')
cfg = yaml.safe_load(p.read_text(encoding='utf-8')) or {}
e = cfg.setdefault('email', {})
e.update({'tipo': 'imap', 'host': '$imapHost', 'porta': int('$porta'), 'ssl': True,
          'usuario': '$Usuario', 'pasta': 'INBOX', 'keyring_servico': 'mo_autonomo_imap'})
e.pop('senha', None)
p.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding='utf-8')
print('config/config.yaml atualizado (modo:', cfg.get('modo', 'simulacao'), ')')
"@

Write-Host "Testando conexão (somente leitura: EXAMINE + BODY.PEEK)..." -ForegroundColor Cyan
& $py -m mo_autonomo imap testar --config config\config.yaml
