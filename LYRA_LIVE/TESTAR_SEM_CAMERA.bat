@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title LYRA LIVE - teste da esteira

set CMD=
python --version >nul 2>&1 && set CMD=python
if "%CMD%"=="" (py --version >nul 2>&1 && set CMD=py)
if "%CMD%"=="" (
  echo O Windows nao encontra o Python. Rode 0_INSTALAR_LYRA.bat primeiro.
  pause
  exit /b 1
)

echo Medindo o que esta maquina aguenta, sem camera e sem transmitir...
echo.
%CMD% lyra.py --teste --segundos 10 --resolucao 1280x720
echo.
pause
