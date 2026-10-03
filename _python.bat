@echo off
rem Localiza o Python 3.10+ e grava o comando na variavel PY.
rem Uso: call "%~dp0_python.bat" [instalar]  -> com "instalar", instala o Python sozinho se faltar.
set "PY="
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
