@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist "IMPORTAR XML" mkdir "IMPORTAR XML"
echo Coloque os XML (ou ZIP) das notas emitidas na pasta que vai abrir: IMPORTAR XML
echo Depois, no sistema, va em Clientes e clique em "Importar clientes dos XML".
echo (O robo tambem importa sozinho as notas de cada empresa cadastrada.)
start "" "%~dp0IMPORTAR XML"
timeout /t 8 >nul
