@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title Instalar dependencias

set CMD=
python --version >nul 2>&1 && set CMD=python
if "%CMD%"=="" (py --version >nul 2>&1 && set CMD=py)
if "%CMD%"=="" (
  echo O Windows nao encontra o Python. Rode o DIAGNOSTICO.bat primeiro.
  pause
  exit /b 1
)

cls
echo ==========================================================
echo   Instalando dependencias
echo ==========================================================
echo.
%CMD% --version
echo.

%CMD% -m pip install --upgrade pip
echo.

echo ----------------------------------------------------------
echo  [1/2] Essenciais - o software funciona so com estes
echo ----------------------------------------------------------
%CMD% -m pip install customtkinter requests numpy psutil Pillow pyflakes pypdf pywebview
if %errorlevel% neq 0 (
  echo.
  echo   FALHOU nos essenciais. Mande um print desta janela.
  pause
  exit /b 1
)
echo.
echo   Essenciais instalados.
echo.

echo ----------------------------------------------------------
echo  [2/2] torch - OPCIONAL (so a rede neural usa)
echo ----------------------------------------------------------
echo   Sao ~2,5 GB e pode demorar. Se falhar, NAO tem problema:
echo   a previsao sai pelo consenso das teorias do mesmo jeito.
echo.
%CMD% -m pip install torch
if %errorlevel% neq 0 (
  echo.
  echo ==========================================================
  echo   torch NAO instalou - e isso esta OK
  echo ==========================================================
  echo.
  echo   Causa mais comum: seu Python e' mais novo do que as
  echo   versoes que o PyTorch publicou ate agora.
  echo.
  echo   O software roda sem ele. Na tela vai aparecer
  echo   "[LSTM] SEM MODELO TREINADO" - e' aviso, nao erro.
  echo.
) else (
  echo.
  echo   torch instalado - a rede neural tambem vai rodar.
  echo.
)

echo ==========================================================
echo   PRONTO - agora abra CENTRAL.bat
echo   (as quatro mesas numa janela so). As janelas
echo   avulsas 1_ a 3_ mostram uma mesa por vez.
echo ==========================================================
echo.
pause
