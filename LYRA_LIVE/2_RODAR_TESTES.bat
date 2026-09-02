@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title LYRA LIVE - testes

set CMD=
python --version >nul 2>&1 && set CMD=python
if "%CMD%"=="" (py --version >nul 2>&1 && set CMD=py)
if "%CMD%"=="" (
  echo O Windows nao encontra o Python. Rode 0_INSTALAR_LYRA.bat primeiro.
  pause
  exit /b 1
)

%CMD% RODAR_TESTES.py
echo.
pause
