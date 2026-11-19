@echo off
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0servico.ps1" -Acao iniciar
timeout /t 4 >nul
start "" http://127.0.0.1:8765
