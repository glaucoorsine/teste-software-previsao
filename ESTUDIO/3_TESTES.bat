@echo off
chcp 65001 >nul
title ESTUDIO - testes
cd /d "%~dp0"
python RODAR_TESTES.py
pause
