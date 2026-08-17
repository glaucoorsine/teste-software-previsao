@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title Rodar os testes
call "%~dp0_PYTHON.bat" || exit /b 1
%CMD% RODAR_TESTES.py
echo.
pause
