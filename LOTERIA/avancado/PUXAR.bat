@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0.."
title Loteria - puxar resultados
call "%~dp0..\_PYTHON.bat" || exit /b 1
%CMD% PUXAR.py %*
echo.
pause
