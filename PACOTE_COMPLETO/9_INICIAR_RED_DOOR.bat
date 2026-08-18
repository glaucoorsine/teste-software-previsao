@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title Red Door
call "%~dp0_PYTHON.bat" || exit /b 1
%CMD% red_door_combo.py
if %errorlevel% neq 0 (
  echo.
  echo   Red Door terminou com erro %errorlevel%.
  echo   O detalhe esta em Logs\crash_*.txt
  echo.
)
pause
