@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title Gerar arquivo para enviar

set CMD=
python --version >nul 2>&1 && set CMD=python
if "%CMD%"=="" (py --version >nul 2>&1 && set CMD=py)
if "%CMD%"=="" (
  echo O Windows nao encontra o Python. Rode o DIAGNOSTICO.bat.
  pause
  exit /b 1
)

cls
echo ==========================================================
echo   Gerando o arquivo para enviar
echo ==========================================================
echo.
%CMD% COLETAR.py --exportar
echo.
echo ==========================================================
echo   Procure o arquivo  coleta_completa.zip  nesta pasta
echo   e mande ele no chat.
echo ==========================================================
echo.
pause
