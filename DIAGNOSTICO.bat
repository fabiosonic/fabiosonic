@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
title Diagnostico - Sistema Financeiro e NFS-e
set "ARQ=%~dp0diagnostico.txt"
echo Diagnostico do Sistema Financeiro e NFS-e > "%ARQ%"
echo Pasta: %~dp0 >> "%ARQ%"
ver >> "%ARQ%"
call "%~dp0_python.bat"
echo Python: %PY% >> "%ARQ%"
if not defined PY goto :sem_python
%PY% -c "import sys; print('Versao do Python:', sys.version)" >> "%ARQ%" 2>&1
%PY% -m nfse_itaborai diagnostico >> "%ARQ%" 2>&1
goto :fim
:sem_python
echo PYTHON NAO ENCONTRADO: a pasta python nao esta junto do sistema. >> "%ARQ%"
:fim
type "%ARQ%"
start "" notepad "%ARQ%"
pause
