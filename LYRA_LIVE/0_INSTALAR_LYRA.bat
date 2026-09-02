@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title LYRA LIVE - instalar

set CMD=
python --version >nul 2>&1 && set CMD=python
if "%CMD%"=="" (py --version >nul 2>&1 && set CMD=py)
if "%CMD%"=="" (
  echo O Windows nao encontra o Python.
  echo Instale em https://python.org e marque "Add Python to PATH".
  pause
  exit /b 1
)

cls
echo ==========================================================
echo   LYRA LIVE - instalando
echo ==========================================================
echo.
%CMD% --version
echo.

%CMD% -m pip install --upgrade pip
echo.
echo ----------------------------------------------------------
echo  [1/3] Essenciais
echo ----------------------------------------------------------
%CMD% -m pip install numpy opencv-python customtkinter Pillow requests
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
echo  [2/3] mediapipe - OPCIONAL (recorte de pessoa no fundo)
echo ----------------------------------------------------------
echo   Se falhar, NAO tem problema: o desfoque de fundo continua,
echo   pelo modo "Aprender fundo" ou pelo modo aproximado.
echo.
%CMD% -m pip install mediapipe
if %errorlevel% neq 0 (
  echo.
  echo   mediapipe NAO instalou - e isso esta OK.
  echo   Costuma ser Python mais novo do que as versoes publicadas.
  echo.
)

echo ----------------------------------------------------------
echo  [3/3] pyvirtualcam - OPCIONAL (webcam virtual)
echo ----------------------------------------------------------
echo   So e' preciso para aparecer como camera no navegador.
echo   Alem dele, instale o OBS Studio uma vez: e' o OBS que
echo   registra o dispositivo de camera virtual no Windows.
echo.
%CMD% -m pip install pyvirtualcam
echo.

echo ==========================================================
echo   FALTA O FFMPEG?
echo ==========================================================
where ffmpeg >nul 2>&1
if %errorlevel% neq 0 (
  echo   O ffmpeg NAO esta no PATH. Ele e' OBRIGATORIO para
  echo   transmitir para o YouTube. Instale com:
  echo.
  echo       winget install Gyan.FFmpeg
  echo.
  echo   Depois FECHE e ABRA esta janela de novo.
) else (
  echo   ffmpeg encontrado. Tudo pronto.
)
echo.
echo ==========================================================
echo   Agora rode DIAGNOSTICO.bat e depois 1_ABRIR_LYRA.bat
echo ==========================================================
echo.
pause
