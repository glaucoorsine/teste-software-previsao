@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title CENTRAL - as quatro mesas em uma janela so
call "%~dp0_PYTHON.bat" || exit /b 1
%CMD% CENTRAL.py
echo.
pause
