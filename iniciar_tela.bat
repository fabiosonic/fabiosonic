@echo off
cd /d "%~dp0"
call "%~dp0_python.bat" instalar || exit /b 1
%PY% -m nfse_itaborai tela
pause
