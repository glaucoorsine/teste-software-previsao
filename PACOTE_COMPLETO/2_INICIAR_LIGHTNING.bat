@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title Lightning
call "%~dp0_PYTHON.bat" || exit /b 1
%CMD% lightning_combo.py
if %errorlevel% neq 0 (
  echo.
  echo   Lightning terminou com erro %errorlevel%.
  echo   O detalhe esta em Logs\crash_*.txt
  echo.
)
pause
