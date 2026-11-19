@echo off
setlocal
chcp 65001 >nul
title Agente coletor M^&O XML Captador
cd /d "%~dp0"
echo === Agente coletor - instalacao na origem (cliente) ===

set PY=
for %%V in (3.14 3.13 3.12 3.11 3) do ( if not defined PY ( py -%%V -c "import sys" >nul 2>&1 && set PY=py -%%V ) )
if not defined PY ( where python >nul 2>&1 && set PY=python )
if not defined PY (
  echo [ERRO] Python 3 nao encontrado. Instale de https://www.python.org/downloads/windows/ (marque "Add to PATH").
  exit /b 1
)
echo Usando %PY% (o agente usa apenas a biblioteca padrao: nenhum pacote a instalar).

if not exist "%~dp0agente.ini" (
  copy "%~dp0agente.ini.modelo" "%~dp0agente.ini" >nul
  echo.
  echo >>> Edite agente.ini com a URL do servidor, o token e as pastas do ERP/PDV. <<<
  notepad "%~dp0agente.ini"
)
icacls "%~dp0agente.ini" /inheritance:r /grant:r "%USERNAME%:F" "Administradores:F" "SYSTEM:F" >nul 2>&1
icacls "%~dp0agente.ini" /inheritance:r /grant:r "%USERNAME%:F" "Administrators:F" "SYSTEM:F" >nul 2>&1

echo Testando um ciclo...
%PY% "%~dp0moxml_agente.py" --uma-vez || ( echo [ERRO] Verifique agente.ini e a conexao com o servidor. & exit /b 1 )

rem Tarefa agendada: inicia com o Windows e reinicia em falha (roda continuo, sem console).
for /f "tokens=*" %%P in ('%PY% -c "import sys,os;print(sys.executable.replace(chr(92)+'python.exe',chr(92)+'pythonw.exe'))"') do set PYW=%%P
schtasks /Create /TN "MO XML Agente Coletor" /SC ONSTART /RL LIMITED /F ^
  /TR "\"%PYW%\" \"%~dp0moxml_agente.py\"" >nul
schtasks /Run /TN "MO XML Agente Coletor" >nul
echo.
echo Agente instalado. Ele envia os XMLs novos ao escritorio automaticamente.
echo Log: %~dp0agente.log
endlocal
