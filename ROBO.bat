@echo off
rem Executado pelo Agendador do Windows (criado pelo INSTALAR.bat). Pode rodar manualmente tambem.
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
if not exist dados mkdir dados
python -m nfse_itaborai robo >> dados\robo.log 2>&1
