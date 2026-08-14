@echo off
chcp 65001 >nul
cd /d "%~dp0"
where python >nul 2>&1 && (python PROGRESSO.py) || (py PROGRESSO.py)
echo.
pause
