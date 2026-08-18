@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0.."
title Loteria
call "%~dp0..\_PYTHON.bat" || exit /b 1
%CMD% JOGAR.py %*
if %errorlevel% neq 0 (
  echo.
  echo   Terminou com erro %errorlevel%.
  echo.
)
pause
