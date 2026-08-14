@echo off
chcp 65001 >nul
cd /d "%~dp0"
where python >nul 2>&1 && (python TESTAR_FONTES.py) || (py TESTAR_FONTES.py)
echo.
pause
