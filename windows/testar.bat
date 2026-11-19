@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title M^&O XML Captador - Testes
cd /d "%~dp0..\backend"
echo === M^&O XML Captador - testes automatizados (laboratorio interno, sem acesso a SEFAZ) ===
echo.

rem 1) Ambiente: usa o .venv existente ou cria um na hora
set VPY=.venv\Scripts\python.exe
if not exist "%VPY%" (
  echo Preparando o ambiente pela primeira vez...
  set PY=
  for %%V in (3.14 3.13 3.12 3) do ( if not defined PY ( py -%%V -c "import sys" >nul 2>&1 && set PY=py -%%V ) )
  if not defined PY ( where python >nul 2>&1 && set PY=python )
  if not defined PY (
    echo [ERRO] Python 3 nao encontrado. Instale de https://www.python.org/downloads/windows/ ^(marque "Add to PATH"^).
    pause & exit /b 1
  )
  !PY! -m venv .venv || ( echo [ERRO] falha ao criar o ambiente. & pause & exit /b 1 )
)

rem 2) Dependencias: instala/atualiza so se o pytest ainda nao estiver la
"%VPY%" -c "import pytest, fastapi, lxml, cryptography" >nul 2>&1
if errorlevel 1 (
  echo Instalando dependencias ^(uma unica vez^)...
  "%VPY%" -m pip install --upgrade pip >nul
  "%VPY%" -m pip install -r requirements.txt -e . || ( echo [ERRO] falha ao instalar dependencias. & pause & exit /b 1 )
)

rem 3) Rodar os testes
echo.
"%VPY%" -m pytest tests -v -p no:warnings
set RC=%errorlevel%
echo.
if "%RC%"=="0" ( echo RESULTADO: todos os testes passaram. ) else ( echo RESULTADO: houve falhas ^(codigo %RC%^). )
echo.
pause
endlocal & exit /b %RC%
