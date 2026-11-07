@echo off
chcp 65001 >nul
cd /d "%~dp0.."
title Painel Quant B3 - NAO FECHE ESTA JANELA enquanto usa o painel
echo O painel vai abrir no navegador em instantes (http://127.0.0.1:8050).
echo Para encerrar, feche esta janela.
python -m swingbot painel
pause
