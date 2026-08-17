@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title Academia Servico
call "%~dp0_PYTHON.bat" || exit /b 1
%CMD% academia_servico.py
if %errorlevel% neq 0 (
  echo.
  echo   Academia Servico terminou com erro %errorlevel%.
  echo   O detalhe esta em Logs\crash_*.txt
  echo.
)
pause
