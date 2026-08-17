@echo off
rem ---------------------------------------------------------------------------
rem  Descobre como o Python se chama NESTE computador e devolve em %CMD%.
rem  Mesmo arquivo do outro pacote, pelo mesmo motivo: em maquina onde o
rem  instalador nao marcou "Add to PATH" so existe o "py", e a janela abria,
rem  reclamava e sumia junto com o texto.
rem ---------------------------------------------------------------------------
set CMD=
python --version >nul 2>&1 && set CMD=python
if "%CMD%"=="" (py --version >nul 2>&1 && set CMD=py)
if "%CMD%"=="" (py -3 --version >nul 2>&1 && set CMD=py -3)
if "%CMD%"=="" (
  echo.
  echo   O Windows nao encontra o Python neste computador.
  echo   Instale de python.org marcando "Add Python to PATH".
  echo.
  pause
  exit /b 1
)
exit /b 0
