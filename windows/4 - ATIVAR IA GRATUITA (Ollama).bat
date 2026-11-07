@echo off
chcp 65001 >nul
cd /d "%~dp0.."
title Ativar IA gratuita (Ollama)
where ollama >nul 2>&1
if errorlevel 1 (
  echo O Ollama nao esta instalado. Baixe gratis em https://ollama.com/download
  start https://ollama.com/download
  pause
  exit /b
)
echo Baixando o modelo recomendado (4,7 GB, so na primeira vez)...
ollama pull qwen2.5:7b
python -m swingbot ia-testar --configurar
pause
