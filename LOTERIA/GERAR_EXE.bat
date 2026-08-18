@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title Loteria - gerar executaveis
call "%~dp0_PYTHON.bat" || exit /b 1
rem ---------------------------------------------------------------------------
rem  Gera LOTERIA.exe e PUXAR.exe NESTA maquina, com o PyInstaller.
rem
rem  Por que isto roda aqui e nao veio pronto: um .exe de Windows so nasce
rem  honesto numa maquina Windows, e o software foi escrito numa Linux. Um
rem  executavel que eu nao pude rodar nem uma vez nao e entrega -- e' chute.
rem  Este script existe para a SUA maquina fazer o .exe, e ai ele nasce testado
rem  onde vai viver.
rem
rem  Precisa de internet na primeira vez (baixa o PyInstaller do PyPI).
rem ---------------------------------------------------------------------------
echo.
echo   Instalando o PyInstaller (so na primeira vez)...
%CMD% -m pip install --quiet pyinstaller || (
  echo   Nao consegui instalar o PyInstaller. Confira a internet e rode de novo.
  pause & exit /b 1
)
echo   Gerando LOTERIA.exe ...
%CMD% -m PyInstaller --onefile --console --name LOTERIA JOGAR.py || (pause & exit /b 1)
echo   Gerando PUXAR.exe ...
%CMD% -m PyInstaller --onefile --console --name PUXAR PUXAR.py || (pause & exit /b 1)
echo.
echo   Prontos em: %~dp0dist\LOTERIA.exe  e  %~dp0dist\PUXAR.exe
echo   Use no terminal (cmd), com os mesmos argumentos dos .py:
echo     dist\LOTERIA.exe mega_sena --formular
echo     dist\PUXAR.exe mega_sena --ultimo
echo.
pause
