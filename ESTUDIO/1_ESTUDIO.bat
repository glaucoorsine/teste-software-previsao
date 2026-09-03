@echo off
chcp 65001 >nul
title ESTUDIO
cd /d "%~dp0"
python ESTUDIO.py
if errorlevel 1 pause
