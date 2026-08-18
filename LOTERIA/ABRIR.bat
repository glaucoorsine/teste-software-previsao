@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title Loteria
rem ---------------------------------------------------------------------------
rem  ESTE E' O UNICO ARQUIVO QUE VOCE PRECISA ABRIR.
rem
rem  Ele liga o programa e abre a tela no seu navegador. Tudo o que o software
rem  faz esta la dentro, nas abas: as loterias em cima, o que fazer na lateral.
rem
rem  Antes eram cinco arquivos clicaveis e ninguem sabia qual abrir -- com
rem  razao. Agora e' um so, e os outros viraram uma pasta chamada "avancado",
rem  para quem quiser linha de comando.
rem ---------------------------------------------------------------------------
call "%~dp0_PYTHON.bat" || exit /b 1
echo.
echo   Abrindo a tela no seu navegador...
echo   (se ele nao abrir sozinho, o endereco aparece abaixo)
echo.
%CMD% PAINEL.py
if %errorlevel% neq 0 (
  echo.
  echo   O programa terminou com erro %errorlevel%.
  echo   Me mostre esta janela que eu conserto.
  echo.
  pause
)
