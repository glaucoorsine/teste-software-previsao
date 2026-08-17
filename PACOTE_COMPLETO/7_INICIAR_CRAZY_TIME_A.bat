@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title Crazy Time A
call "%~dp0_PYTHON.bat" || exit /b 1
%CMD% crazy_time_a_combo.py
if %errorlevel% neq 0 (
  echo.
  echo   Crazy Time A terminou com erro %errorlevel%.
  echo   O detalhe esta em Logs\crash_*.txt
  echo.
)
pause
