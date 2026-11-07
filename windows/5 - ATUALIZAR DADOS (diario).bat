@echo off
chcp 65001 >nul
cd /d "%~dp0.."
title Atualizando dados
python pesquisa\baixar.py
python pesquisa\baixar_dividendos.py
python pesquisa\baixar_consenso.py
python -m swingbot rodar
echo Dados atualizados.
pause
