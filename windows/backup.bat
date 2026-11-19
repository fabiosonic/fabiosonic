@echo off
setlocal
chcp 65001 >nul
set MOXML_HOME=%PROGRAMDATA%\MO-XML-Captador
rem Uso: backup.bat [pasta_destino]   (padrao: %MOXML_HOME%\backup, mantem os 30 mais recentes)
if "%~1"=="" ( "%~dp0..\backend\.venv\Scripts\python.exe" -m moxml backup ) else ( "%~dp0..\backend\.venv\Scripts\python.exe" -m moxml backup --destino "%~1" )
endlocal
