@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0.."
set VPY=%CD%\backend\.venv\Scripts\python.exe
set MOXML_HOME=%PROGRAMDATA%\MO-XML-Captador
echo Fazendo backup antes de atualizar...
"%VPY%" -m moxml backup || exit /b 1
call "%~dp0parar.bat"
where git >nul 2>&1 && git pull --ff-only
"%VPY%" -m pip install -r backend\requirements.txt || exit /b 1
"%VPY%" -m pip install -e backend || exit /b 1
rem aplica migrations novas
"%VPY%" -m moxml init || exit /b 1
call "%~dp0iniciar.bat"
endlocal
