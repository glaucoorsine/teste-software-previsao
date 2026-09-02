@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title LYRA LIVE

set CMD=
python --version >nul 2>&1 && set CMD=python
if "%CMD%"=="" (py --version >nul 2>&1 && set CMD=py)
if "%CMD%"=="" (
  echo O Windows nao encontra o Python. Rode 0_INSTALAR_LYRA.bat primeiro.
  pause
  exit /b 1
)

%CMD% LIVE.py
if %errorlevel% neq 0 (
  echo.
  echo   O painel fechou com erro. Rode DIAGNOSTICO.bat para ver o que falta.
  pause
)
