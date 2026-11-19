@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0..\backend"
rem Testes automatizados: usam somente o laboratorio SIMULADO (nenhuma chamada a SEFAZ)
".venv\Scripts\python.exe" -m pytest tests -q
endlocal
