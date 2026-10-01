@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set "XMLS=%USERPROFILE%\Downloads\nfse\MORAES OLIVEIRA CONTABILIDADE LTDA"
if not "%~1"=="" set "XMLS=%~1"
echo Importando clientes dos XML em: %XMLS%
python -m nfse_itaborai importar-clientes "%XMLS%"
pause
