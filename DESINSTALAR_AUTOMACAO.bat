@echo off
chcp 65001 >nul
schtasks /delete /f /tn "Robo Financeiro NFS-e Itaborai" >nul 2>nul
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Sistema Financeiro NFS-e.bat" >nul 2>nul
echo Automacao removida (robo agendado e abertura automatica). Seus dados foram mantidos.
pause
