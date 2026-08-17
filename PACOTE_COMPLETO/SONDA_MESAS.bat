@echo off
chcp 65001 >nul
title SONDA DAS MESAS - mostra a resposta crua da API
cd /d "%~dp0"
echo.
echo  Isto NAO muda nada no software. So le as APIs e grava um arquivo pequeno.
echo  Leva cerca de um minuto.
echo.
call :python SONDA_MESAS.py
goto :eof
:python
if exist "_PYTHON.bat" (call _PYTHON.bat %*) else (python %*)
goto :eof
