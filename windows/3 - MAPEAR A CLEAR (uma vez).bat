@echo off
chcp 65001 >nul
cd /d "%~dp0.."
title Mapeamento do Home Broker da Clear
echo Uma janela do navegador vai abrir no Home Broker da Clear.
echo 1) Faca o seu login normalmente.
echo 2) Siga as instrucoes que aparecerem AQUI nesta janela.
echo Nenhuma ordem sera enviada.
echo.
python -m swingbot mapear
echo.
echo Se deu certo, o arquivo foi salvo em: logs\mapa_clear.json
echo Envie esse arquivo na conversa com o Claude.
explorer logs
pause
