@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title CENTRAL DAS IAS
call "%~dp0_PYTHON.bat" || exit /b 1
%CMD% central_ias.py
if %errorlevel% neq 0 (
  echo.
  echo   CENTRAL DAS IAS terminou com erro %errorlevel%.
  echo   O detalhe esta em Logs\crash_*.txt
  echo.
)
pause
