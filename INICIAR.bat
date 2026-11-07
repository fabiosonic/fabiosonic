@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title Painel Quant B3

rem ============================================================
rem  Painel Quant B3 - tudo em um clique (Windows)
rem  Na primeira vez instala o que falta; depois mostra o menu.
rem ============================================================

call :achar_python
if not defined PY call :instalar_python
if not defined PY exit /b

rem Ambiente ISOLADO na pasta .venv: nao altera nenhum outro programa do computador
if not exist ".venv\Scripts\python.exe" (
  echo Criando o ambiente isolado do painel...
  "%PY%" -m venv .venv
  if errorlevel 1 goto falha
)
set "PY=%~dp0.venv\Scripts\python.exe"

if not exist ".venv\.instalado" (
  call :instalar
  if errorlevel 1 goto falha
)
if not exist "dados_cache\pesquisa\_CDI.csv" call :baixar_dados
call :atalho

:menu
cls
echo ==================================================
echo              PAINEL QUANT B3  - gratuito
echo ==================================================
echo.
echo   1 - Abrir o painel
echo   2 - Atualizar os dados do mercado  - faca todo dia
echo   3 - Mapear o Home Broker da Clear  - so uma vez
echo   4 - Testar a boleta da Clear SEM enviar ordem
echo   5 - Ativar a IA gratuita - Ollama
echo   6 - Atualizar o programa
echo   0 - Sair
echo.
set "op="
set /p "op=Digite o numero e aperte Enter: "
if "%op%"=="1" goto painel
if "%op%"=="2" goto dados
if "%op%"=="3" goto mapear
if "%op%"=="4" goto ensaio
if "%op%"=="5" goto ia
if "%op%"=="6" goto atualizar
if "%op%"=="0" exit /b
goto menu

:painel
echo.
echo O painel vai abrir no navegador em instantes.
echo Enquanto estiver usando, NAO feche esta janela. Para encerrar, feche-a.
"%PY%" -m swingbot painel
pause
goto menu

:dados
call :baixar_dados
"%PY%" -m swingbot rodar
echo.
echo Dados atualizados.
pause
goto menu

:mapear
echo.
echo Uma janela do navegador vai abrir no Home Broker da Clear.
echo 1. Faca o seu login normalmente, inclusive o codigo de verificacao.
echo 2. O mapeamento comeca SOZINHO quando o Home Broker abrir.
echo 3. NAO mexa no navegador ate aparecer "Mapa salvo".
echo Nenhuma ordem sera enviada.
echo.
"%PY%" -m swingbot mapear
if exist "logs\mapa_clear.json" (
  echo.
  echo Pronto! Envie o arquivo mapa_clear.json na conversa com o Claude.
  explorer /select,"%cd%\logs\mapa_clear.json"
)
pause
goto menu

:ensaio
echo.
set "tk="
set /p "tk=Ativo para o teste, ex.: PETR4: "
if "%tk%"=="" set "tk=PETR4"
"%PY%" -m swingbot ensaio %tk% --preco 1.00
pause
goto menu

:ia
where ollama >nul 2>&1
if errorlevel 1 (
  echo.
  echo O Ollama nao esta instalado. Instalando automaticamente...
  winget install -e --id Ollama.Ollama --accept-package-agreements --accept-source-agreements
  echo.
  echo Quando terminar, FECHE esta janela, abra o INICIAR de novo e escolha a opcao 5.
  pause
  goto menu
)
echo.
echo Baixando o modelo de IA recomendado - 4,7 GB, so na primeira vez...
ollama pull qwen2.5:7b
"%PY%" -m swingbot ia-testar --configurar
pause
goto menu

:atualizar
where git >nul 2>&1
if errorlevel 1 (
  echo.
  echo O Git nao esta instalado: baixe a versao nova do projeto pelo site do GitHub.
  pause
  goto menu
)
git pull
call :instalar
echo.
echo Programa atualizado. FECHE esta janela e abra o INICIAR de novo.
pause
exit /b

rem ------------------------------------------------------------ rotinas
:achar_python
set "PY="
for %%C in (python py) do (
  if not defined PY (
    %%C --version 2>nul | findstr /r /c:"Python 3\.1[0-9]" >nul && set "PY=%%C"
  )
)
if not defined PY if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "PY=%LocalAppData%\Programs\Python\Python312\python.exe"
exit /b

:instalar_python
echo O Python nao foi encontrado. Instalando automaticamente...
winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
call :achar_python
if defined PY exit /b
echo.
echo Nao consegui instalar o Python automaticamente.
echo Instale pelo site que vai abrir. Na primeira tela MARQUE a caixa "Add python.exe to PATH".
echo Depois abra este arquivo INICIAR de novo.
start https://www.python.org/downloads/
pause
exit /b

:instalar
echo.
echo Instalando os componentes - pode levar alguns minutos...
"%PY%" -m pip install --upgrade pip
"%PY%" -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
"%PY%" -m playwright install chromium
if errorlevel 1 exit /b 1
echo ok> ".venv\.instalado"
exit /b 0

:baixar_dados
echo.
echo Baixando cotacoes, dividendos, CDI e consenso dos analistas - cerca de 1 minuto...
"%PY%" pesquisa\baixar.py
"%PY%" pesquisa\baixar_dividendos.py
"%PY%" pesquisa\baixar_consenso.py
exit /b

:atalho
powershell -NoProfile -Command "$d=[Environment]::GetFolderPath('Desktop'); $s=(New-Object -ComObject WScript.Shell).CreateShortcut(\"$d\Painel Quant B3.lnk\"); $s.TargetPath='%~f0'; $s.WorkingDirectory='%~dp0'; $s.IconLocation='%SystemRoot%\System32\shell32.dll,13'; $s.Save()" >nul 2>&1
exit /b

:falha
echo.
echo Algo deu errado. Tire uma foto desta tela e envie na conversa com o Claude.
pause
exit /b
