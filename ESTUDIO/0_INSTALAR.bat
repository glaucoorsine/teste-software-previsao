@echo off
chcp 65001 >nul
title ESTUDIO - instalar dependencias
echo.
echo  Instalando o que o estudio precisa. Pode demorar alguns minutos.
echo.
python -m pip install --upgrade pip
python -m pip install -r "%~dp0requirements.txt"
echo.
echo  ------------------------------------------------------------------
echo   FALTA O FFMPEG?  Rode 2_CONFERIR.bat para saber. Se faltar, o
echo   LEIA_PRIMEIRO.md explica como resolver em tres linhas.
echo  ------------------------------------------------------------------
echo.
pause
