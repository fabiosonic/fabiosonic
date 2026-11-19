@echo off
setlocal
chcp 65001 >nul
title M^&O XML Captador - Teste SVRS ao vivo
cd /d "%~dp0.."
set VPY=%CD%\backend\.venv\Scripts\python.exe
set MOXML_HOME=%PROGRAMDATA%\MO-XML-Captador
if not exist "%VPY%" ( echo [ERRO] Rode INSTALAR.bat primeiro. & pause & exit /b 1 )

rem Testa a SVRS ao vivo para a empresa informada (padrao: 1).
rem Verifica o Portal DF-e SVRS (inclusive CAPTCHA) e tenta baixar o XML de uma chave conhecida.
set EMP=%~1
if "%EMP%"=="" set EMP=1
echo Testando a SVRS para a empresa %EMP% (precisa do certificado A1 cadastrado)...
echo.
"%VPY%" -m moxml svrs --empresa %EMP%
echo.
echo O relatorio foi salvo em %MOXML_HOME%\evidencias\
echo Envie esse arquivo para analise.
pause
endlocal
