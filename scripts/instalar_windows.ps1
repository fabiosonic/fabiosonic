# Instalação no PC do escritório (rodar no PowerShell, dentro da pasta do projeto).
# Não toca na caixa de e-mail nem no D: — só prepara o ambiente em modo SIMULAÇÃO.
$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz

if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw "Instale o Python 3.12+ (python.org) marcando 'Add to PATH'." }
if (-not (Test-Path .venv)) { py -3 -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Testes falharam: não prossiga." }

if (-not (Test-Path config\config.yaml)) { Copy-Item config\config.exemplo.yaml config\config.yaml; Write-Host "Criado config\config.yaml (modo simulacao). Edite antes de usar." }
New-Item -ItemType Directory -Force dados\entrada_eml, dados\rfb, dados\dominio | Out-Null

Write-Host "`nSenha do IMAP (fica no Cofre de Credenciais do Windows, nunca em arquivo):"
Write-Host "  .\.venv\Scripts\python.exe -c `"import keyring,getpass; keyring.set_password('mo_autonomo_imap','fiscal@moraeseoliveiracontabil.com.br', getpass.getpass())`""

# Agendamentos (criados DESATIVADOS; ative no Agendador depois de conferir a simulação)
$py = (Resolve-Path .venv\Scripts\python.exe).Path
$acaoCiclo = New-ScheduledTaskAction -Execute $py -Argument "-m mo_autonomo ciclo --config config\config.yaml" -WorkingDirectory $raiz
$gatilhos = 7..20 | ForEach-Object { New-ScheduledTaskTrigger -Daily -At ("{0:00}:05" -f $_) }
Register-ScheduledTask -TaskName "MO Autonomo - Ciclo" -Action $acaoCiclo -Trigger $gatilhos -Force | Out-Null
Disable-ScheduledTask -TaskName "MO Autonomo - Ciclo" | Out-Null
$acaoPerfil = New-ScheduledTaskAction -Execute $py -Argument "-m mo_autonomo perfil atualizar --config config\config.yaml" -WorkingDirectory $raiz
Register-ScheduledTask -TaskName "MO Autonomo - Perfis RFB" -Action $acaoPerfil -Trigger (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 06:10) -Force | Out-Null
Disable-ScheduledTask -TaskName "MO Autonomo - Perfis RFB" | Out-Null
Write-Host "Tarefas criadas e DESATIVADAS: 'MO Autonomo - Ciclo' (7h-20h) e 'MO Autonomo - Perfis RFB'."
