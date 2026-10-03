<#
  inventario-atalhos.ps1 — FASE 1 (somente leitura, não apaga nada)
  Descobre para onde apontam os atalhos da Área de Trabalho e levanta tudo
  o que seria preciso remover: desinstalador oficial, processos, tarefas
  agendadas, inicialização automática, serviços e conteúdo das pastas.
  Uso: PowerShell como Administrador ->
       powershell -ExecutionPolicy Bypass -File .\inventario-atalhos.ps1
  Gera o relatório "inventario-atalhos.txt" na Área de Trabalho.
#>

$nomes = @('Colocar XML aqui', 'INTEGRA TOTAL', 'Reiniciar Apurador', 'Simples Nacional')

$desktops = @(
    [Environment]::GetFolderPath('Desktop'),
    [Environment]::GetFolderPath('CommonDesktopDirectory'),
    "$env:OneDrive\Desktop", "$env:OneDrive\Área de Trabalho"
) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -Unique

$protegidas = @($env:WINDIR, $env:ProgramFiles, ${env:ProgramFiles(x86)}, $env:ProgramData,
                $env:USERPROFILE, "$env:USERPROFILE\Desktop", "$env:LOCALAPPDATA\Programs\Python",
                "$env:SystemDrive\") | Where-Object { $_ }
$interpretadores = 'python.exe','pythonw.exe','py.exe','cmd.exe','powershell.exe','pwsh.exe','wscript.exe','cscript.exe','explorer.exe'

$sh  = New-Object -ComObject WScript.Shell
$out = New-Object System.Collections.Generic.List[string]
function Log($t) { $out.Add($t); Write-Host $t }

function Get-PastaAlvo($target, $args, $wd) {
    # Se o atalho chama python/cmd/etc., a pasta real é a do script nos argumentos ou a "Iniciar em"
    $exe = Split-Path $target -Leaf
    if ($interpretadores -contains $exe.ToLower()) {
        $m = [regex]::Matches($args, '"([^"]+)"|(\S+)') | ForEach-Object { $_.Value.Trim('"') } |
             Where-Object { Test-Path $_ -ErrorAction SilentlyContinue }
        if ($m) { $p = @($m)[0]; if (Test-Path $p -PathType Container) { return $p } else { return Split-Path $p } }
        if ($wd -and (Test-Path $wd)) { return $wd }
        return $null
    }
    if (Test-Path $target -PathType Container) { return $target }
    if ($target) { return Split-Path $target }
    return $wd
}

$uninstKeys = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
              'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
              'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*'
$programas = Get-ItemProperty $uninstKeys -ErrorAction SilentlyContinue | Where-Object DisplayName
$tarefas   = Get-ScheduledTask -ErrorAction SilentlyContinue
$runKeys   = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run','HKLM:\Software\Microsoft\Windows\CurrentVersion\Run',
             'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run'
$startups  = [Environment]::GetFolderPath('Startup'), [Environment]::GetFolderPath('CommonStartup')

foreach ($nome in $nomes) {
    Log ''; Log ('=' * 78); Log "ITEM: $nome"; Log ('=' * 78)
    $itens = foreach ($d in $desktops) { Get-ChildItem $d -Force | Where-Object { $_.Name -like "$nome*" } }
    if (-not $itens) { Log '  (não encontrado na Área de Trabalho)'; continue }

    foreach ($i in $itens) {
        Log "  Item na Área de Trabalho: $($i.FullName)"
        $pasta = $null
        if ($i.PSIsContainer) {
            Log '  TIPO: PASTA (não é atalho)'; $pasta = $i.FullName
        } elseif ($i.Extension -eq '.lnk') {
            $l = $sh.CreateShortcut($i.FullName)
            Log "  Destino     : $($l.TargetPath)"
            Log "  Argumentos  : $($l.Arguments)"
            Log "  Iniciar em  : $($l.WorkingDirectory)"
            $pasta = Get-PastaAlvo $l.TargetPath $l.Arguments $l.WorkingDirectory
        } elseif ($i.Extension -eq '.url') {
            Log "  Conteúdo .url:"; Get-Content $i.FullName | ForEach-Object { Log "    $_" }
        }
        if (-not $pasta) { Log '  Pasta alvo  : (não determinada)'; continue }
        $pasta = (Resolve-Path $pasta -ErrorAction SilentlyContinue).Path
        Log "  PASTA ALVO  : $pasta"
        if ($protegidas -contains $pasta.TrimEnd('\') -or $pasta -match '\\Python\d*' -or $pasta -like "$env:WINDIR*") {
            Log '  !!! PASTA PROTEGIDA (sistema/Python) — NÃO será apagada'
        }

        # Conteúdo
        $arqs = Get-ChildItem $pasta -Recurse -Force -File -ErrorAction SilentlyContinue
        $xml  = $arqs | Where-Object Extension -in '.xml','.zip'
        Log ("  Conteúdo    : {0} arquivos, {1:N1} MB, {2} XML/ZIP" -f $arqs.Count, (($arqs | Measure-Object Length -Sum).Sum/1MB), $xml.Count)
        Get-ChildItem $pasta -Force -ErrorAction SilentlyContinue | Select-Object -First 40 | ForEach-Object {
            Log ("    {0,-5} {1,-45} {2,12} {3:dd/MM/yyyy}" -f ($(if($_.PSIsContainer){'[DIR]'}else{''})), $_.Name, $(if(!$_.PSIsContainer){'{0:N0}' -f $_.Length}), $_.LastWriteTime)
        }
        if ($xml) {
            Log '  Amostra de XML (emitente/CNPJ):'
            $xml | Where-Object Extension -eq '.xml' | Select-Object -First 10 | ForEach-Object {
                $t = Get-Content $_.FullName -Raw -ErrorAction SilentlyContinue
                $cnpj = ([regex]::Match($t, '<CNPJ>(\d{14})</CNPJ>')).Groups[1].Value
                $nm   = ([regex]::Match($t, '<xNome>([^<]+)</xNome>')).Groups[1].Value
                Log "    $($_.Name) | $cnpj | $nm"
            }
        }

        # Desinstalador oficial
        $prog = $programas | Where-Object {
            ($_.InstallLocation -and $pasta -like "$($_.InstallLocation.TrimEnd('\'))*") -or
            ($_.UninstallString -and $_.UninstallString -like "*$pasta*") -or
            ($_.DisplayName -like "*$nome*") }
        foreach ($p in $prog) { Log "  DESINSTALADOR (registro): $($p.DisplayName) -> $($p.UninstallString)" }
        $uexe = Get-ChildItem $pasta -Recurse -Depth 1 -Include 'unins*.exe','uninstall*.exe','desinstal*.exe' -ErrorAction SilentlyContinue
        foreach ($u in $uexe) { Log "  DESINSTALADOR (arquivo) : $($u.FullName)" }
        if (-not $prog -and -not $uexe) { Log '  Desinstalador oficial   : NÃO encontrado' }

        # Processos (inclui python rodando script da pasta)
        Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -like "$pasta*" -or $_.CommandLine -like "*$pasta*" } |
            ForEach-Object { Log "  PROCESSO  : PID $($_.ProcessId) $($_.Name) | $($_.CommandLine)" }

        # Tarefas agendadas
        foreach ($t in $tarefas) {
            $txt = ($t.Actions | ForEach-Object { "$($_.Execute) $($_.Arguments) $($_.WorkingDirectory)" }) -join ' '
            if ($txt -like "*$pasta*" -or $t.TaskName -like "*$nome*") { Log "  TAREFA    : $($t.TaskPath)$($t.TaskName) | $txt" }
        }

        # Inicialização automática
        foreach ($k in $runKeys) {
            $v = Get-ItemProperty $k -ErrorAction SilentlyContinue
            if ($v) { $v.PSObject.Properties | Where-Object { $_.Value -is [string] -and $_.Value -like "*$pasta*" } |
                ForEach-Object { Log "  RUN       : $k -> $($_.Name) = $($_.Value)" } }
        }
        foreach ($s in $startups) {
            Get-ChildItem $s -Filter *.lnk -ErrorAction SilentlyContinue | ForEach-Object {
                $l = $sh.CreateShortcut($_.FullName)
                if ("$($l.TargetPath) $($l.Arguments) $($l.WorkingDirectory)" -like "*$pasta*") { Log "  STARTUP   : $($_.FullName)" }
            }
        }

        # Serviços
        Get-CimInstance Win32_Service | Where-Object PathName -like "*$pasta*" |
            ForEach-Object { Log "  SERVIÇO   : $($_.Name) ($($_.State)) | $($_.PathName)" }
    }
}

$rel = Join-Path ([Environment]::GetFolderPath('Desktop')) 'inventario-atalhos.txt'
$out | Set-Content $rel -Encoding UTF8
Write-Host "`nRelatório salvo em: $rel" -ForegroundColor Green
