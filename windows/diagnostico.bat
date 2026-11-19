@echo off
setlocal
chcp 65001 >nul
set MOXML_HOME=%PROGRAMDATA%\MO-XML-Captador
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0servico.ps1" -Acao status
rem Uso: diagnostico.bat [id_empresa]  (com id, inspeciona o formulario do portal SVRS usando o A1 da empresa)
if "%~1"=="" ( "%~dp0..\backend\.venv\Scripts\python.exe" -m moxml diagnostico ) else ( "%~dp0..\backend\.venv\Scripts\python.exe" -m moxml diagnostico --empresa %1 )
pause
endlocal
