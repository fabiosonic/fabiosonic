@echo off
setlocal
chcp 65001 >nul
title M^&O XML Captador - Atualizar
cd /d "%~dp0.."
set VPY=%CD%\backend\.venv\Scripts\python.exe
set MOXML_HOME=%PROGRAMDATA%\MO-XML-Captador

if not exist "%VPY%" ( echo [ERRO] Sistema nao instalado. Rode INSTALAR.bat primeiro. & pause & exit /b 1 )

echo Fazendo backup dos dados antes de atualizar...
"%VPY%" -m moxml backup
echo Parando o servico...
call "%~dp0parar.bat"

rem Atualiza o codigo: so e possivel se a pasta foi obtida com Git.
if exist "%CD%\.git" (
  where git >nul 2>&1 && ( echo Baixando a versao mais recente... & git pull --ff-only ) || echo [AVISO] Git nao encontrado no PATH.
) else (
  echo.
  echo [IMPORTANTE] Esta pasta nao e um repositorio Git ^(foi baixada como ZIP^).
  echo Para pegar a correcao: baixe o ZIP novo do GitHub por cima desta pasta e rode este arquivo de novo.
  echo Seus dados ^(empresas, XMLs, certificados^) estao seguros em %MOXML_HOME% e nao sao afetados.
  echo.
)

echo Reinstalando dependencias e aplicando atualizacoes do banco...
"%VPY%" -m pip install -r backend\requirements.txt || ( pause & exit /b 1 )
"%VPY%" -m pip install -e backend || ( pause & exit /b 1 )
"%VPY%" -m moxml init || ( pause & exit /b 1 )

echo Reiniciando o programa...
call "%~dp0iniciar.bat"
echo.
echo Atualizacao concluida. O painel foi reaberto.
pause
endlocal
