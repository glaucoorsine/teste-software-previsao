@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title DESCOBERTA - testa metodos novos no historico
call "%~dp0_PYTHON.bat" || exit /b 1
%CMD% DESCOBERTA.py
echo.
pause
