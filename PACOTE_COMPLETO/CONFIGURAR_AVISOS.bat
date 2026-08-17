@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title Configurar avisos
call "%~dp0_PYTHON.bat" || exit /b 1
%CMD% CONFIGURAR_AVISOS.py
echo.
pause
