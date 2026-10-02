@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set "MODO=%~1"
title Emissor NFS-e Itaborai
where python >nul 2>nul
if errorlevel 1 (
  start https://www.python.org/downloads/
  if /i "%MODO%"=="oculto" exit /b 1
  echo Python nao encontrado. Instale pelo site que abriu e marque "Add Python to PATH".
  pause
  exit /b 1
)
if not exist dados mkdir dados
python -c "import lxml, cryptography" 2>nul || python -m pip install --quiet --disable-pip-version-check lxml cryptography
rem Se esta versao ja esta aberta (mesma pasta), so abre o navegador nela
python -m nfse_itaborai ja-aberto 2>nul && exit /b 0
rem Fecha telas de versoes antigas/outras pastas para nao abrir o sistema velho no navegador
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'nfse_itaborai\s+tela' } | ForEach-Object { Invoke-CimMethod -InputObject $_ -MethodName Terminate | Out-Null }" >nul 2>nul
rem Robo agendado, abertura com o Windows e atalho apontam para ESTA pasta e rodam sem janela
schtasks /create /f /sc hourly /mo 1 /tn "Robo Financeiro NFS-e Itaborai" /tr "wscript.exe \"%~dp0SISTEMA.vbs\" robo" >nul 2>nul
powershell -NoProfile -Command "$st=[Environment]::GetFolderPath('Startup'); $old=Join-Path $st 'Sistema Financeiro NFS-e.bat'; $lnk=Join-Path $st 'Sistema Financeiro NFS-e.lnk'; if ((Test-Path $old) -or (Test-Path $lnk)) { Remove-Item $old -ErrorAction SilentlyContinue; $s=(New-Object -ComObject WScript.Shell).CreateShortcut($lnk); $s.TargetPath='wscript.exe'; $s.Arguments='\"%~dp0SISTEMA.vbs\"'; $s.WorkingDirectory='%~dp0'; $s.Save() }" >nul 2>nul
powershell -NoProfile -Command "$p=[Environment]::GetFolderPath('Desktop')+'\Sistema Financeiro NFS-e.lnk'; if (Test-Path $p) { $s=(New-Object -ComObject WScript.Shell).CreateShortcut($p); $s.TargetPath='wscript.exe'; $s.Arguments='\"%~dp0SISTEMA.vbs\"'; $s.WorkingDirectory='%~dp0'; $s.IconLocation='%SystemRoot%\System32\shell32.dll,165'; $s.Save() }" >nul 2>nul
if not exist ".env" python -m nfse_itaborai configurar
if /i "%MODO%"=="oculto" (
  python -m nfse_itaborai tela >> dados\tela.log 2>&1
  exit /b 0
)
python -m nfse_itaborai tela
pause
