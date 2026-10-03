@echo off
rem Executado pelo Agendador do Windows (criado pelo INSTALAR.bat). Pode rodar manualmente tambem.
cd /d "%~dp0"
call "%~dp0_python.bat" || exit /b 1
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
if not exist dados mkdir dados
%PY% -m nfse_itaborai robo >> dados\robo.log 2>&1
