@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title LYRA LIVE - diagnostico

set CMD=
python --version >nul 2>&1 && set CMD=python
if "%CMD%"=="" (py --version >nul 2>&1 && set CMD=py)
if "%CMD%"=="" (
  echo O Windows nao encontra o Python.
  echo Instale em https://python.org e marque "Add Python to PATH".
  pause
  exit /b 1
)

%CMD% lyra.py --diagnostico
echo.
pause
