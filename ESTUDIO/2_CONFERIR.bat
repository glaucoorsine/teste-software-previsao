@echo off
chcp 65001 >nul
title ESTUDIO - conferir a maquina
cd /d "%~dp0"
echo.
echo  Conferindo tudo SEM abrir a janela e SEM usar a webcam...
echo.
python CONFERIR.py
echo.
pause
