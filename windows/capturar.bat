@echo off
setlocal
chcp 65001 >nul
set MOXML_HOME=%PROGRAMDATA%\MO-XML-Captador
rem Execucao manual imediata (o servico ja executa automaticamente nos horarios de MOXML_HORARIOS_EXECUCAO)
"%~dp0..\backend\.venv\Scripts\python.exe" -m moxml capturar %*
endlocal
