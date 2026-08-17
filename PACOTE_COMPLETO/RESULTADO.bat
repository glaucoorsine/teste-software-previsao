@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title RESULTADO - a taxa de acerto real
call "%~dp0_PYTHON.bat" || exit /b 1
%CMD% RESULTADO.py
echo.
pause
