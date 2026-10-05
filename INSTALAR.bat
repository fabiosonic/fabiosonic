@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
title Instalacao - Sistema Financeiro e NFS-e
echo ============================================================
echo  Instalacao do Sistema Financeiro e NFS-e (rode uma unica vez)
echo ============================================================
echo [0/5] Python...
call "%~dp0_python.bat" instalar
if errorlevel 1 (
  pause
  exit /b 1
)
echo    OK: %PY%
echo [1/5] Componentes - validador XSD, criptografia, WhatsApp Web e leitura de PDF...
%PY% -c "import lxml, cryptography, playwright, pypdf" 2>nul && (echo    OK: ja incluidos no pacote.) || %PY% -m pip install --quiet --disable-pip-version-check lxml cryptography playwright pypdf
if exist "%~dp0python\python.exe" if not exist "%~dp0python\Lib\site-packages\playwright\driver\node.exe" echo    AVISO: faltam as partes 2 e 3 do pacote (WhatsApp automatico). Extraia as 3 partes na mesma pasta e rode de novo.
echo [2/5] Serial de liberacao e configuracao da empresa...
if not exist ".env" (%PY% -m nfse_itaborai configurar) else (%PY% -m nfse_itaborai serial)
echo [3/5] Robo financeiro de hora em hora, sem janela (Agendador do Windows)...
schtasks /create /f /sc hourly /mo 1 /tn "Robo Financeiro NFS-e Itaborai" /tr "wscript.exe \"%~dp0SISTEMA.vbs\" robo" >nul
if errorlevel 1 (echo    Aviso: nao foi possivel agendar o robo. Rode como administrador.) else (echo    OK: robo agendado.)
echo [4/5] Abrir o sistema (oculto) ao ligar o computador...
powershell -NoProfile -Command "$st=[Environment]::GetFolderPath('Startup'); Remove-Item (Join-Path $st 'Sistema Financeiro NFS-e.bat') -ErrorAction SilentlyContinue; $s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $st 'Sistema Financeiro NFS-e.lnk')); $s.TargetPath='wscript.exe'; $s.Arguments='\"%~dp0SISTEMA.vbs\"'; $s.WorkingDirectory='%~dp0'; $s.Save()" >nul 2>nul
echo    OK: o sistema abrira sozinho, sem janela, ao ligar o computador.
echo [5/5] Atalho na area de trabalho...
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Sistema Financeiro NFS-e.lnk'); $s.TargetPath='wscript.exe'; $s.Arguments='\"%~dp0SISTEMA.vbs\"'; $s.WorkingDirectory='%~dp0'; $s.IconLocation='%SystemRoot%\System32\shell32.dll,165'; $s.Save()" >nul 2>nul
echo    OK.
echo.
echo Pronto! O sistema vai abrir no navegador. Ele roda escondido, sem janela preta:
echo para fechar, use o botao "Encerrar o sistema" no menu da tela.
start "" wscript.exe "%~dp0SISTEMA.vbs"
timeout /t 5 >nul
