@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
title Emissor NFS-e Itaborai
where python >nul 2>nul
if errorlevel 1 (
  echo Python nao encontrado. Instale pelo site que vai abrir e marque "Add Python to PATH".
  start https://www.python.org/downloads/
  pause
  exit /b 1
)
python -c "import lxml" 2>nul || python -m pip install --quiet --disable-pip-version-check lxml
if not exist ".env" python -m nfse_itaborai configurar
rem Atualiza o cadastro de clientes com os XML das notas ja emitidas (pasta configuravel no .env)
set "XMLS=%USERPROFILE%\Downloads\nfse\MORAES OLIVEIRA CONTABILIDADE LTDA"
for /f "usebackq tokens=1,* delims==" %%a in (".env") do if /i "%%a"=="ITABORAI_PASTA_XML" set "XMLS=%%b"
if exist "%XMLS%" (
  echo Atualizando clientes a partir de %XMLS% ...
  python -m nfse_itaborai importar-clientes "%XMLS%"
)
python -m nfse_itaborai tela
pause
