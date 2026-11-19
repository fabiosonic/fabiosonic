<#
  M&O XML Captador - gerenciamento do servico no Windows (Agendador de Tarefas).

  O captador roda como TAREFA AGENDADA "MO XML Captador", disparada na inicializacao do Windows,
  com o MESMO usuario Windows que cadastra os certificados (exigencia do DPAPI: o cofre so abre
  para o usuario que cifrou). Continua rodando com o navegador/painel fechado e sem ninguem logado.

  Uso: powershell -ExecutionPolicy Bypass -File servico.ps1 -Acao instalar|remover|iniciar|parar|status
#>
param([Parameter(Mandatory = $true)][ValidateSet("instalar", "remover", "iniciar", "parar", "status")] [string]$Acao)

$ErrorActionPreference = "Stop"
$Tarefa = "MO XML Captador"
$Raiz = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Raiz "backend"
$PyW = Join-Path $Backend ".venv\Scripts\pythonw.exe"

function Parar-Processos {
    Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
        Where-Object { $_.CommandLine -match "moxml" -and $_.CommandLine -match "servidor" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}

switch ($Acao) {
    "instalar" {
        if (-not (Test-Path $PyW)) { throw "Ambiente Python nao encontrado em $PyW. Execute instalar.bat primeiro." }
        $usuario = "$env:USERDOMAIN\$env:USERNAME"
        Write-Host "A tarefa sera executada como $usuario (mesmo usuario que guarda os certificados no cofre DPAPI)."
        $cred = Get-Credential -UserName $usuario -Message "Senha do Windows de $usuario (necessaria para rodar sem ninguem logado)"
        $acao = New-ScheduledTaskAction -Execute $PyW -Argument "-m moxml servidor" -WorkingDirectory $Backend
        $gatilhos = @((New-ScheduledTaskTrigger -AtStartup), (New-ScheduledTaskTrigger -AtLogOn -User $usuario))
        $config = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
            -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) `
            -MultipleInstances IgnoreNew
        Register-ScheduledTask -TaskName $Tarefa -Action $acao -Trigger $gatilhos -Settings $config `
            -User $cred.UserName -Password $cred.GetNetworkCredential().Password -RunLevel Limited -Force | Out-Null
        Write-Host "Tarefa '$Tarefa' registrada (inicia com o Windows e reinicia em caso de falha)."
        Start-ScheduledTask -TaskName $Tarefa
    }
    "remover" {
        Parar-Processos
        Unregister-ScheduledTask -TaskName $Tarefa -Confirm:$false -ErrorAction SilentlyContinue
        Write-Host "Tarefa removida. Dados em $env:PROGRAMDATA\MO-XML-Captador foram preservados."
    }
    "iniciar" {
        if (Get-ScheduledTask -TaskName $Tarefa -ErrorAction SilentlyContinue) { Start-ScheduledTask -TaskName $Tarefa }
        else { Start-Process -FilePath $PyW -ArgumentList "-m moxml servidor" -WorkingDirectory $Backend -WindowStyle Hidden }
        Write-Host "Servico iniciado."
    }
    "parar" {
        if (Get-ScheduledTask -TaskName $Tarefa -ErrorAction SilentlyContinue) { Stop-ScheduledTask -TaskName $Tarefa }
        Parar-Processos
        Write-Host "Servico parado."
    }
    "status" {
        $t = Get-ScheduledTask -TaskName $Tarefa -ErrorAction SilentlyContinue
        if ($t) { Write-Host "Tarefa: $($t.State)" } else { Write-Host "Tarefa nao instalada." }
        try { $r = Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/saude" -TimeoutSec 5; Write-Host "API: OK (modo $($r.modo), versao $($r.versao))" }
        catch { Write-Host "API: sem resposta em http://127.0.0.1:8765" }
    }
}
