@echo off
rem ---------------------------------------------------------------------------
rem  Descobre como o Python se chama NESTE computador e devolve em %CMD%.
rem
rem  As janelas numeradas chamavam "python" fixo. Em maquina onde o instalador
rem  nao marcou "Add to PATH" -- que e' o padrao do instalador -- so existe o
rem  "py". Ai a janela abria, o Windows dizia "python nao e reconhecido", e o
rem  pause fechava junto: piscava e sumia, sem nada para ler.
rem
rem  ABRIR_TUDO.bat ja fazia essa deteccao. As outras oito, nao. Agora e' um
rem  arquivo so, chamado por todas.
rem ---------------------------------------------------------------------------
set CMD=
python --version >nul 2>&1 && set CMD=python
if "%CMD%"=="" (py --version >nul 2>&1 && set CMD=py)
if "%CMD%"=="" (py -3 --version >nul 2>&1 && set CMD=py -3)
if "%CMD%"=="" (
  echo.
  echo   O Windows nao encontra o Python neste computador.
  echo   Rode o DIAGNOSTICO.bat -- ele diz o que falta.
  echo.
  pause
  exit /b 1
)
exit /b 0
