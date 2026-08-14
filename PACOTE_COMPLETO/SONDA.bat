@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title Sonda - ate onde da pra puxar

set CMD=
python --version >nul 2>&1 && set CMD=python
if "%CMD%"=="" (py --version >nul 2>&1 && set CMD=py)
if "%CMD%"=="" (echo Python nao encontrado. Rode DIAGNOSTICO.bat & pause & exit /b 1)

cls
%CMD% SONDA.py
echo.
echo ==========================================================
echo   Mande um print desta janela inteira.
echo ==========================================================
pause
