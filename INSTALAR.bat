@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
title Instalacao - Sistema Financeiro e NFS-e
echo ============================================================
echo  Instalacao do Sistema Financeiro e NFS-e (rode uma unica vez)
echo ============================================================
where python >nul 2>nul
if errorlevel 1 (
  echo Python nao encontrado. Instale pelo site que vai abrir, marque "Add Python to PATH" e rode este arquivo de novo.
  start https://www.python.org/downloads/
  pause
  exit /b 1
)
echo [1/5] Instalando o validador XSD...
python -m pip install --quiet --disable-pip-version-check lxml
echo [2/5] Configuracao (.env)...
if not exist ".env" python -m nfse_itaborai configurar
echo [3/5] Robo financeiro de hora em hora (Agendador do Windows)...
schtasks /create /f /sc hourly /mo 1 /tn "Robo Financeiro NFS-e Itaborai" /tr "\"%~dp0ROBO.bat\"" >nul
if errorlevel 1 (echo    Aviso: nao foi possivel agendar o robo. Rode como administrador.) else (echo    OK: robo agendado.)
echo [4/5] Abrir o sistema ao ligar o computador...
set "INICIO=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Sistema Financeiro NFS-e.bat"
> "%INICIO%" echo @echo off
>> "%INICIO%" echo cd /d "%~dp0"
>> "%INICIO%" echo start "Sistema Financeiro NFS-e" /min INICIAR.bat
echo    OK: o sistema abrira sozinho ao ligar o computador.
echo [5/5] Atalho na area de trabalho...
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Sistema Financeiro NFS-e.lnk');$s.TargetPath='%~dp0INICIAR.bat';$s.WorkingDirectory='%~dp0';$s.WindowStyle=7;$s.Save()" >nul 2>nul
echo    OK.
echo.
echo Pronto! Abrindo o sistema...
call INICIAR.bat
