@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
title Emissor NFS-e Itaborai
where python >nul 2>nul
if errorlevel 1 (
  echo Python nao encontrado. Instale pelo site que vai abrir e marque "Add Python to PATH".
  start https://www.python.org/downloads/
  pause
  exit /b 1
)
python -c "import lxml, cryptography" 2>nul || python -m pip install --quiet --disable-pip-version-check lxml cryptography
rem Fecha telas abertas de versoes antigas (de qualquer pasta) para nao abrir o sistema velho no navegador
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'nfse_itaborai\s+tela' } | ForEach-Object { Invoke-CimMethod -InputObject $_ -MethodName Terminate | Out-Null }" >nul 2>nul
rem Aponta robo agendado, inicializacao do Windows e atalho para ESTA pasta (corrige instalacoes antigas)
schtasks /create /f /sc hourly /mo 1 /tn "Robo Financeiro NFS-e Itaborai" /tr "\"%~dp0ROBO.bat\"" >nul 2>nul
set "INICIO=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Sistema Financeiro NFS-e.bat"
if exist "%INICIO%" (
  > "%INICIO%" echo @echo off
  >> "%INICIO%" echo cd /d "%~dp0"
  >> "%INICIO%" echo start "Sistema Financeiro NFS-e" /min INICIAR.bat
)
powershell -NoProfile -Command "$p=[Environment]::GetFolderPath('Desktop')+'\Sistema Financeiro NFS-e.lnk'; if (Test-Path $p) { $s=(New-Object -ComObject WScript.Shell).CreateShortcut($p); $s.TargetPath='%~dp0INICIAR.bat'; $s.WorkingDirectory='%~dp0'; $s.Save() }" >nul 2>nul
if not exist ".env" python -m nfse_itaborai configurar
rem Atualiza o cadastro de clientes com os XML das notas ja emitidas (pasta configuravel no .env)
set "XMLS=%USERPROFILE%\Downloads\nfse\MORAES OLIVEIRA CONTABILIDADE LTDA"
for /f "usebackq tokens=1,* delims==" %%a in (".env") do if /i "%%a"=="ITABORAI_PASTA_XML" set "XMLS=%%b"
if exist "%XMLS%" (
  echo Atualizando clientes a partir de %XMLS% ...
  python -m nfse_itaborai importar-clientes "%XMLS%"
)
python -m nfse_itaborai tela
pause
