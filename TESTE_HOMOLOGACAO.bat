@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
title Teste em homologacao - NFS-e Itaborai
python -c "import lxml" 2>nul || python -m pip install --quiet --disable-pip-version-check lxml
echo Enviando RPS de TESTE em HOMOLOGACAO (sem validade fiscal)...
python -m nfse_itaborai emitir exemplos\rps_exemplo.json > resultado_teste.txt 2>&1
type resultado_teste.txt
echo.
echo Resultado salvo em resultado_teste.txt - envie esse arquivo (ou um print) no chat.
pause
