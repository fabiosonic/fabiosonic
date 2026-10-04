@echo off
chcp 65001 >nul
cd /d "%~dp0"
call "%~dp0_python.bat" instalar || exit /b 1
if not exist "IMPORTAR XML" mkdir "IMPORTAR XML"
echo.
echo  IMPORTAR CLIENTES E DADOS DAS NOTAS
echo  ------------------------------------------------------------------
echo  1. Na pasta que vai abrir (IMPORTAR XML), coloque os XML ou ZIP das
echo     NFS-e ja emitidas pela empresa (quanto mais meses, melhor).
echo  2. Volte aqui e tecle Enter.
echo.
echo  O sistema cadastra os clientes, os servicos (item LC 116, desdobro, NBS,
echo  codigo municipal, aliquota, carga tributaria), completa a empresa
echo  (nome, inscricao, municipio, numeracao) e as regras fiscais do regime.
echo.
start "" "%~dp0IMPORTAR XML"
pause
%PY% -m nfse_itaborai importar-clientes
echo.
pause
