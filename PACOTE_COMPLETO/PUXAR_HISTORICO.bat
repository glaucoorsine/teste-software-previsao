@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title Puxar historico completo

set CMD=
python --version >nul 2>&1 && set CMD=python
if "%CMD%"=="" (py --version >nul 2>&1 && set CMD=py)
if "%CMD%"=="" (
  echo O Windows nao encontra o Python. Rode o DIAGNOSTICO.bat.
  pause
  exit /b 1
)

cls
echo ==========================================================
echo   Puxando TODO o historico disponivel das 4 mesas
echo   Leva cerca de um minuto.
echo ==========================================================
echo.
%CMD% COLETAR.py --fundo
echo.
echo ==========================================================
echo   Agora rode EXPORTAR.bat e mande o coleta_completa.zip
echo ==========================================================
echo.
pause
