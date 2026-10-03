@echo off
chcp 65001 >nul
cd /d "%~dp0"
call "%~dp0_python.bat" instalar || exit /b 1
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
title Teste em homologacao - NFS-e Itaborai
%PY% -c "import lxml" 2>nul || %PY% -m pip install --quiet --disable-pip-version-check lxml
echo Enviando RPS de TESTE em HOMOLOGACAO (sem validade fiscal)...
set ARQ=exemplos\rps_exemplo.json
if exist "exemplos\rps_teste_homologacao.json" set ARQ=exemplos\rps_teste_homologacao.json
%PY% -m nfse_itaborai emitir %ARQ% > resultado_teste.txt 2>&1
type resultado_teste.txt
echo.
echo Resultado salvo em resultado_teste.txt - envie esse arquivo (ou um print) no chat.
pause
