@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem Agenda o robo financeiro para rodar todo dia as 08:00, mesmo com a tela fechada.
schtasks /create /f /sc daily /st 08:00 /tn "Robo Financeiro NFS-e Itaborai" /tr "cmd /c cd /d \"%~dp0\" && set PYTHONUTF8=1 && python -m nfse_itaborai robo >> dados\robo.log 2>&1"
if errorlevel 1 (echo Nao foi possivel agendar. Rode este arquivo como administrador.) else (echo Robo agendado para todo dia as 08:00.)
pause
