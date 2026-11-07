@echo off
chcp 65001 >nul
cd /d "%~dp0.."
title Instalando o Painel Quant B3
echo ============================================
echo   INSTALACAO DO PAINEL QUANT B3 (gratuito)
echo ============================================
echo.
python --version >nul 2>&1
if errorlevel 1 (
  echo [ERRO] O Python nao esta instalado.
  echo Instale em https://www.python.org/downloads/
  echo IMPORTANTE: na primeira tela marque "Add python.exe to PATH".
  echo Depois rode este arquivo de novo.
  start https://www.python.org/downloads/
  pause
  exit /b
)
echo [1/4] Instalando os componentes... (pode levar alguns minutos)
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt
if errorlevel 1 goto erro
echo [2/4] Instalando o navegador do robo...
python -m playwright install chromium
if errorlevel 1 goto erro
echo [3/4] Baixando cotacoes, dividendos e CDI... (cerca de 1 minuto)
python pesquisa\baixar.py
python pesquisa\baixar_dividendos.py
echo [4/4] Baixando o consenso dos analistas...
python pesquisa\baixar_consenso.py
echo.
echo ============================================
echo   PRONTO! Agora clique em "2 - ABRIR O PAINEL"
echo ============================================
pause
exit /b
:erro
echo.
echo [ERRO] Algo deu errado. Tire uma foto desta tela e envie na conversa.
pause
