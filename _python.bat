@echo off
rem Localiza o Python 3.10+ e grava o comando na variavel PY.
rem Uso: call "%~dp0_python.bat" [instalar]  -> com "instalar", instala o Python sozinho se faltar.
set "PY="
rem 1) Python que vem DENTRO do pacote (pasta python\), ja com todos os componentes: nao precisa de internet.
if exist "%~dp0python\python.exe" goto :embutido
python -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>nul && set "PY=python"
if not defined PY py -3 -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>nul && set "PY=py -3"
if not defined PY for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do if exist "%%~D\python.exe" set PY="%%~D\python.exe"
if defined PY exit /b 0
if /i not "%~1"=="instalar" exit /b 1
echo Python nao encontrado. Instalando automaticamente, so para este usuario. Aguarde alguns minutos...
winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements >nul 2>nul
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do if exist "%%~D\python.exe" set PY="%%~D\python.exe"
if defined PY exit /b 0
echo Baixando o instalador oficial do Python em python.org...
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol='Tls12'; $f=Join-Path $env:TEMP 'python-instalador.exe'; Invoke-WebRequest 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' -OutFile $f -UseBasicParsing; Start-Process $f -ArgumentList '/quiet InstallAllUsers=0 PrependPath=1 Include_test=0' -Wait"
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do if exist "%%~D\python.exe" set PY="%%~D\python.exe"
if defined PY exit /b 0
echo Nao foi possivel instalar o Python automaticamente.
echo Instale pelo site que vai abrir, marque "Add Python to PATH" e rode este arquivo de novo.
start https://www.python.org/downloads/
exit /b 1

:embutido
set PY="%~dp0python\python.exe"
set "PYTHONNOUSERSITE=1"
rem O motor do WhatsApp automatico (node.exe) vem em 2 pedacos nas partes 2 e 3 do pacote: junta na primeira vez.
set "NODEDIR=%~dp0python\Lib\site-packages\playwright\driver"
if exist "%NODEDIR%\node.exe" exit /b 0
if not exist "%NODEDIR%\node.exe.parte1" exit /b 0
if not exist "%NODEDIR%\node.exe.parte2" exit /b 0
copy /b "%NODEDIR%\node.exe.parte1"+"%NODEDIR%\node.exe.parte2" "%NODEDIR%\node.exe" >nul
if exist "%NODEDIR%\node.exe" del "%NODEDIR%\node.exe.parte1" "%NODEDIR%\node.exe.parte2"
exit /b 0
