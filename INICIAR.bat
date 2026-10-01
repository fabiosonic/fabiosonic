@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Emissor NFS-e Itaborai
where python >nul 2>nul
if errorlevel 1 (
  echo Python nao encontrado. Instale pelo site que vai abrir e marque "Add Python to PATH".
  start https://www.python.org/downloads/
  pause
  exit /b 1
)
python -c "import lxml" 2>nul || (
  echo Instalando validador XSD lxml - so na primeira vez...
  python -m pip install --quiet lxml
)
if not exist ".env" python -m nfse_itaborai configurar
python -m nfse_itaborai tela
pause
