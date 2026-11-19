@echo off
setlocal
chcp 65001 >nul
title M^&O XML Captador - Instalacao
cd /d "%~dp0.."
set RAIZ=%CD%
echo === M^&O XML Captador - instalacao ===

rem 1) Python: prefere 3.14; aceita 3.13/3.12 se as dependencias ainda nao tiverem wheel para 3.14
set PY=
for %%V in (3.14 3.13 3.12) do (
  if not defined PY ( py -%%V -c "import sys" >nul 2>&1 && set PY=py -%%V )
)
if not defined PY (
  echo [ERRO] Python 3.12+ nao encontrado. Instale em https://www.python.org/downloads/windows/ ^(marque "Add to PATH" e "py launcher"^).
  exit /b 1
)
echo Usando %PY%

rem 2) Ambiente virtual e dependencias
if not exist "%RAIZ%\backend\.venv\Scripts\python.exe" ( %PY% -m venv "%RAIZ%\backend\.venv" || exit /b 1 )
set VPY=%RAIZ%\backend\.venv\Scripts\python.exe
"%VPY%" -m pip install --upgrade pip >nul
"%VPY%" -m pip install -r "%RAIZ%\backend\requirements.txt" || exit /b 1
"%VPY%" -m pip install -e "%RAIZ%\backend" || exit /b 1

rem 3) Pasta de dados e configuracao (fora do repositorio)
set DADOS=%PROGRAMDATA%\MO-XML-Captador
if not exist "%DADOS%" mkdir "%DADOS%"
if not exist "%DADOS%\moxml.env" copy "%RAIZ%\windows\moxml.env.modelo" "%DADOS%\moxml.env" >nul
rem restringe a pasta de dados ao usuario atual + Administradores + SYSTEM
icacls "%DADOS%" /inheritance:r /grant:r "%USERNAME%:(OI)(CI)F" "Administradores:(OI)(CI)F" "SYSTEM:(OI)(CI)F" >nul 2>&1
icacls "%DADOS%" /inheritance:r /grant:r "%USERNAME%:(OI)(CI)F" "Administrators:(OI)(CI)F" "SYSTEM:(OI)(CI)F" >nul 2>&1

rem 4) Banco (migrations) e verificacao
set MOXML_HOME=%DADOS%
"%VPY%" -m moxml init || exit /b 1

rem 5) Inicializacao automatica (tarefa agendada no logon/boot, reinicio automatico)
powershell -NoProfile -ExecutionPolicy Bypass -File "%RAIZ%\windows\servico.ps1" -Acao instalar
echo.
echo Instalacao concluida. Painel: http://127.0.0.1:8765
echo Edite %DADOS%\moxml.env para definir MOXML_MODO=REAL quando for operar com certificados reais.
endlocal
