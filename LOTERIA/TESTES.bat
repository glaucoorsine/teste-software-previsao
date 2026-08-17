@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title Loteria - testes
call "%~dp0_PYTHON.bat" || exit /b 1
%CMD% test_loteria.py
echo.
echo   Se a ultima linha for LOTERIA_BASE_OK, esta tudo provado.
echo.
pause
