<#
.SYNOPSIS
  Localiza e desinstala os programas apontados pelos atalhos M&O da Area de Trabalho:
  "Colocar XML aqui", "INTEGRA TOTAL", "Reiniciar Apurador" e "Simples Nacional...".

.USO
  1) So descobrir onde estao (nao apaga nada):
       powershell -ExecutionPolicy Bypass -File .\Desinstalar-Atalhos-MO.ps1
  2) Desinstalar (pede confirmacao item a item):
       powershell -ExecutionPolicy Bypass -File .\Desinstalar-Atalhos-MO.ps1 -Desinstalar

  Rode o PowerShell como Administrador se algum programa estiver em C:\Program Files.
  Um relatorio fica salvo em Relatorio-Atalhos-MO.txt na Area de Trabalho.
#>
param([switch]$Desinstalar)

$ErrorActionPreference = 'Continue'
$padroes = @('Colocar XML*', 'INTEGRA TOTAL*', 'Reiniciar Apurador*', 'Simples Nacional*')

$desktops = @([Environment]::GetFolderPath('Desktop'),
              [Environment]::GetFolderPath('CommonDesktopDirectory')) | Where-Object { $_ -and (Test-Path $_) }

# Interpretadores: o programa real e o script passado nos argumentos, nao o .exe
$interpretadores = 'python.exe','pythonw.exe','py.exe','cmd.exe','powershell.exe','pwsh.exe',
                   'wscript.exe','cscript.exe','node.exe','java.exe','javaw.exe','explorer.exe'

# Pastas que nunca podem ser apagadas
$protegidas = @($env:SystemRoot, $env:ProgramFiles, ${env:ProgramFiles(x86)}, $env:ProgramData,
                $env:USERPROFILE, $env:APPDATA, $env:LOCALAPPDATA, $env:PUBLIC) + $desktops +
              (Get-PSDrive -PSProvider FileSystem | ForEach-Object { $_.Root.TrimEnd('\') }) |
              Where-Object { $_ } | ForEach-Object { $_.TrimEnd('\').ToLower() }

$relatorio = Join-Path $desktops[0] 'Relatorio-Atalhos-MO.txt'
function Log($msg, $cor = 'Gray') { Write-Host $msg -ForegroundColor $cor; Add-Content -Path $relatorio -Value $msg }
Set-Content -Path $relatorio -Value "Relatorio atalhos M&O - $(Get-Date)`r`n"

$wsh = New-Object -ComObject WScript.Shell
$atalhos = foreach ($d in $desktops) { foreach ($p in $padroes) { Get-ChildItem -Path $d -Filter "$p.lnk" -ErrorAction SilentlyContinue } }
$atalhos = $atalhos | Sort-Object FullName -Unique

if (-not $atalhos) { Log 'Nenhum dos atalhos foi encontrado na Area de Trabalho.' 'Yellow'; return }

# Programas registrados no Windows (Painel de Controle > Programas)
$chavesUninstall = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
                   'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
                   'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*'
$instalados = Get-ItemProperty $chavesUninstall -ErrorAction SilentlyContinue | Where-Object DisplayName

$itens = foreach ($a in $atalhos) {
    $lnk = $wsh.CreateShortcut($a.FullName)
    $alvo = $lnk.TargetPath
    $pasta = $null; $tipo = 'programa'

    if ($alvo -and (Test-Path $alvo -PathType Container)) {
        $pasta = $alvo; $tipo = 'PASTA DE DADOS'
    } elseif ($alvo -and ($interpretadores -contains (Split-Path $alvo -Leaf).ToLower())) {
        # pega o primeiro caminho existente nos argumentos (ex.: python.exe "C:\MO\apurador.py")
        $script = [regex]::Matches($lnk.Arguments, '"([^"]+)"|(\S+)') |
                  ForEach-Object { if ($_.Groups[1].Value) { $_.Groups[1].Value } else { $_.Groups[2].Value } } |
                  Where-Object { $_ -match '^[a-zA-Z]:\\' -and (Test-Path $_) } | Select-Object -First 1
        if ($script) { $pasta = if (Test-Path $script -PathType Container) { $script } else { Split-Path $script } }
        elseif ($lnk.WorkingDirectory) { $pasta = $lnk.WorkingDirectory }
    } elseif ($alvo) {
        $pasta = Split-Path $alvo
    }

    $registro = $null
    if ($pasta) {
        $registro = $instalados | Where-Object { $_.InstallLocation -and
            $pasta.TrimEnd('\').ToLower().StartsWith($_.InstallLocation.TrimEnd('\').ToLower()) } | Select-Object -First 1
    }

    [pscustomobject]@{
        Atalho = $a.FullName; Alvo = $alvo; Argumentos = $lnk.Arguments
        PastaInicio = $lnk.WorkingDirectory; Pasta = $pasta; Tipo = $tipo; Registro = $registro
    }
}

Log "===== ONDE ESTAO INSTALADOS =====" 'Cyan'
foreach ($i in $itens) {
    Log "`r`nAtalho     : $($i.Atalho)" 'White'
    Log "Alvo       : $($i.Alvo) $($i.Argumentos)"
    Log "Pasta      : $($i.Pasta)  [$($i.Tipo)]"
    if ($i.Registro) { Log "Registrado : $($i.Registro.DisplayName) -> $($i.Registro.UninstallString)" 'Green' }
    if ($i.Pasta -and (Test-Path $i.Pasta)) {
        $arqs = Get-ChildItem $i.Pasta -Recurse -File -ErrorAction SilentlyContinue
        Log ("Conteudo   : {0} arquivos, {1:N1} MB ({2} XML)" -f $arqs.Count, (($arqs | Measure-Object Length -Sum).Sum / 1MB),
             ($arqs | Where-Object Extension -eq '.xml').Count)
    }
}

if (-not $Desinstalar) {
    Log "`r`nNada foi apagado. Para desinstalar, rode de novo com -Desinstalar." 'Yellow'
    Log "Relatorio salvo em: $relatorio"
    return
}

Log "`r`n===== DESINSTALACAO =====" 'Cyan'
foreach ($i in $itens) {
    Log "`r`n>> $([IO.Path]::GetFileNameWithoutExtension($i.Atalho))" 'White'

    if ($i.Registro -and $i.Registro.UninstallString) {
        if ((Read-Host "Executar o desinstalador oficial de '$($i.Registro.DisplayName)'? (S/N)") -match '^[sS]') {
            $cmd = $i.Registro.UninstallString
            if ($cmd -match 'msiexec') { $cmd = $cmd -replace '/I', '/X' }
            Start-Process cmd.exe -ArgumentList "/c $cmd" -Wait
            Log "Desinstalador executado." 'Green'
        }
    } elseif ($i.Pasta -and (Test-Path $i.Pasta)) {
        $p = (Resolve-Path $i.Pasta).Path.TrimEnd('\')
        if ($protegidas -contains $p.ToLower()) {
            Log "Pasta '$p' e do sistema/perfil - NAO sera apagada. Removendo so o atalho." 'Red'
        } else {
            $aviso = if ($i.Tipo -eq 'PASTA DE DADOS') { ' ATENCAO: e pasta de DADOS (pode conter XMLs de clientes).' } else { '' }
            if ((Read-Host "Apagar a pasta '$p'?$aviso (S/N)") -match '^[sS]') {
                # encerra processos rodando de dentro da pasta
                Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.Path -and $_.Path.ToLower().StartsWith($p.ToLower() + '\') } |
                    ForEach-Object { Log "Encerrando processo $($_.Name) ($($_.Id))"; Stop-Process -Id $_.Id -Force }
                # tarefas agendadas que chamam algo dessa pasta
                Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object {
                    ($_.Actions | ForEach-Object { "$($_.Execute) $($_.Arguments) $($_.WorkingDirectory)" }) -match [regex]::Escape($p) } |
                    ForEach-Object { Log "Removendo tarefa agendada $($_.TaskPath)$($_.TaskName)"; Unregister-ScheduledTask -TaskName $_.TaskName -TaskPath $_.TaskPath -Confirm:$false }
                # itens de inicializacao (Run) que apontam para a pasta
                foreach ($run in 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run','HKLM:\Software\Microsoft\Windows\CurrentVersion\Run') {
                    $props = Get-ItemProperty $run -ErrorAction SilentlyContinue
                    if ($props) { $props.PSObject.Properties | Where-Object { "$($_.Value)" -match [regex]::Escape($p) } |
                        ForEach-Object { Log "Removendo inicializacao $run\$($_.Name)"; Remove-ItemProperty $run -Name $_.Name } }
                }
                Remove-Item -LiteralPath $p -Recurse -Force -ErrorAction Continue
                if (Test-Path $p) { Log "Nao consegui apagar tudo em '$p' (arquivo em uso ou sem permissao de Administrador)." 'Red' }
                else { Log "Pasta '$p' apagada." 'Green' }
            } else { Log 'Pasta mantida.' }
        }
    } else {
        Log 'O alvo do atalho nao existe mais - removendo so o atalho.' 'Yellow'
    }

    Remove-Item -LiteralPath $i.Atalho -Force -ErrorAction Continue
    Log "Atalho removido: $($i.Atalho)" 'Green'
}
Log "`r`nConcluido. Relatorio salvo em: $relatorio" 'Cyan'
