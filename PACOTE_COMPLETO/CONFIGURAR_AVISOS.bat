@echo off
chcp 65001 >nul
cd /d "%~dp0"
where python >nul 2>&1 && (python CONFIGURAR_AVISOS.py) || (py CONFIGURAR_AVISOS.py)
echo.
pause
