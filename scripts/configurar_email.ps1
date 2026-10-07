# Configura as caixas (fiscal@, moraes@, contabil@, dp@) no mo_autonomo a partir do programa já existente no PC.
# Roda NO PC DO ESCRITÓRIO (PowerShell), dentro da pasta do projeto.
# - Procura SÓ nomes de servidor IMAP e portas IMAP nos arquivos de email_backup. Nenhuma linha
#   de arquivo é exibida (assim nenhuma senha aparece na tela, nem por engano).
# - A senha é digitada por você e vai direto para o Cofre de Credenciais do Windows (keyring).
# - Grava host/porta/usuário em config\config.yaml (modo continua SIMULAÇÃO).
param(
    [string]$Origem = "D:\AUTOMAÇÕES FUNCIONANDO\email_backup",
    [string[]]$Caixas = @("fiscal@moraeseoliveiracontabil.com.br", "moraes@moraeseoliveiracontabil.com.br",
                          "contabil@moraeseoliveiracontabil.com.br", "dp@moraeseoliveiracontabil.com.br")
)
$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz
$py = Join-Path $raiz ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { throw "Rode antes scripts\instalar_windows.ps1" }

Write-Host "Procurando servidor/porta IMAP em $Origem (só os valores; nenhuma linha é exibida)..." -ForegroundColor Cyan
if (Test-Path -LiteralPath $Origem) {
    $arquivos = Get-ChildItem -LiteralPath $Origem -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Extension -in ".py",".json",".ini",".cfg",".conf",".yaml",".yml",".txt",".env",".toml" }
    $hosts = @{}; $portas = @{}
    foreach ($a in $arquivos) {
        $t = Get-Content -LiteralPath $a.FullName -Raw -ErrorAction SilentlyContinue
        if (-not $t) { continue }
        foreach ($m in [regex]::Matches($t, '(?i)\b[a-z0-9-]*imap[a-z0-9-]*(\.[a-z0-9-]+)+\.[a-z]{2,}\b')) { $hosts[$m.Value.ToLower()] = $a.Name }
        foreach ($m in [regex]::Matches($t, '\b(993|143)\b')) { $portas[$m.Value] = $a.Name }
    }
    if ($hosts.Count) { Write-Host "Servidores encontrados:"; $hosts.GetEnumerator() | ForEach-Object { "  {0}   (em {1})" -f $_.Key, $_.Value } }
    else { Write-Host "Nenhum servidor IMAP encontrado automaticamente." -ForegroundColor Yellow }
    if ($portas.Count) { Write-Host ("Portas encontradas: " + (($portas.Keys | Sort-Object) -join ", ")) }
} else {
    Write-Host "Pasta não encontrada: $Origem" -ForegroundColor Yellow
}

# padrão = servidor do motor_imap.py que o escritório já usa; o teste no fim confirma
do { $imapHost = (Read-Host "Servidor IMAP (Enter = mail.emailemnuvem.com.br)").Trim(); if (-not $imapHost) { $imapHost = "mail.emailemnuvem.com.br" } } until ($imapHost -match '^[A-Za-z0-9][A-Za-z0-9.-]{1,252}$')
do { $porta = (Read-Host "Porta IMAP (Enter = 993)").Trim(); if (-not $porta) { $porta = "993" } } until ($porta -match '^\d{1,5}$')

# valores vão por variável de ambiente (nada é interpolado dentro do código Python)
$env:MO_IMAP_HOST = $imapHost; $env:MO_IMAP_PORTA = $porta; $env:MO_IMAP_CAIXAS = ($Caixas -join ",")

foreach ($c in $Caixas) {
    $env:MO_IMAP_USUARIO = $c
    Write-Host "Senha da caixa $c (não aparece na tela; vai para o Cofre do Windows; Enter vazio = manter a atual):"
    & $py -c "import os,keyring,getpass; s=getpass.getpass('Senha: '); s and keyring.set_password('mo_autonomo_imap', os.environ['MO_IMAP_USUARIO'], s)"
}

& $py -c @"
import os, yaml, pathlib
p = pathlib.Path('config/config.yaml')
cfg = yaml.safe_load(p.read_text(encoding='utf-8')) or {}
e = cfg.setdefault('email', {})
e.update({'tipo': 'imap', 'host': os.environ['MO_IMAP_HOST'], 'porta': int(os.environ['MO_IMAP_PORTA']), 'ssl': True,
          'caixas': [{'usuario': u} for u in os.environ['MO_IMAP_CAIXAS'].split(',') if u],
          'pasta': '*', 'keyring_servico': 'mo_autonomo_imap'})
for k in ('senha', 'usuario', 'senha_env'):
    e.pop(k, None)
p.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding='utf-8')
print('config/config.yaml atualizado (modo:', cfg.get('modo', 'simulacao'), ')')
"@
Remove-Item Env:MO_IMAP_HOST, Env:MO_IMAP_PORTA, Env:MO_IMAP_USUARIO, Env:MO_IMAP_CAIXAS -ErrorAction SilentlyContinue

Write-Host "Testando conexão (somente leitura: EXAMINE + BODY.PEEK)..." -ForegroundColor Cyan
& $py -m mo_autonomo imap testar --config config\config.yaml
