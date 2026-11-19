@echo off
setlocal
chcp 65001 >nul
title M^&O XML Captador - Importar pasta de XMLs
cd /d "%~dp0.."
set VPY=%CD%\backend\.venv\Scripts\python.exe
set MOXML_HOME=%PROGRAMDATA%\MO-XML-Captador
if not exist "%VPY%" ( echo [ERRO] Rode INSTALAR.bat primeiro. & pause & exit /b 1 )

rem Uso:  importar-pasta.bat "C:\caminho\da\pasta\de\xmls" [id_empresa]
rem A empresa e identificada pelo CNPJ dentro de cada XML; o id so e necessario
rem se quiser forcar o vinculo. Pode arrastar a pasta para cima deste arquivo.
set PASTA=%~1
if "%PASTA%"=="" set /p PASTA=Caminho da pasta com os XMLs: 
if "%~2"=="" (
  "%VPY%" -m moxml importar "%PASTA%"
) else (
  "%VPY%" -m moxml importar "%PASTA%" --empresa %~2
)
echo.
echo Importacao concluida. Abra o painel (INICIAR.bat) para ver os documentos.
pause
endlocal
