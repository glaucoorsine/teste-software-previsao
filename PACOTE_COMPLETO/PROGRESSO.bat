@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title Progresso
call "%~dp0_PYTHON.bat" || exit /b 1
%CMD% PROGRESSO.py
echo.
pause
