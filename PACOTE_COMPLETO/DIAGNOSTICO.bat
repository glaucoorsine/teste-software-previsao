@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
cls
echo ==========================================================
echo   DIAGNOSTICO - Python neste PC
echo ==========================================================
echo.

set ACHOU=0

echo [1] Procurando o comando "python"...
python --version 2>nul
if %errorlevel%==0 (
  echo     ENCONTRADO
  set ACHOU=1
  set CMD=python
) else (
  echo     NAO responde
)
echo.

echo [2] Procurando o comando "py" ^(lancador oficial do Windows^)...
py --version 2>nul
if %errorlevel%==0 (
  echo     ENCONTRADO
  if "%ACHOU%"=="0" set CMD=py
  set ACHOU=1
) else (
  echo     NAO responde
)
echo.

if "%ACHOU%"=="0" (
  echo ==========================================================
  echo   O PYTHON NAO ESTA ACESSIVEL
  echo ==========================================================
  echo.
  echo   Ele pode ate estar instalado, mas o Windows nao o encontra.
  echo   A causa quase sempre e uma destas duas:
  echo.
  echo   A^) Instalado SEM marcar "Add python.exe to PATH"
  echo      Solucao: reinstale de python.org/downloads e MARQUE
  echo      essa caixa na PRIMEIRA tela do instalador.
  echo.
  echo   B^) O atalho da Microsoft Store esta no caminho
  echo      Sintoma: digitar "python" abre a Loja da Microsoft.
  echo      Solucao: Configuracoes ^> Aplicativos ^> Aliases de
  echo      execucao de aplicativo ^> DESLIGUE python.exe e python3.exe
  echo.
  echo   Me mande um print desta janela.
  echo.
  pause
  exit /b 1
)

echo [3] Onde ele esta instalado:
where %CMD% 2>nul
echo.

echo [4] Testando o pip ^(instalador de pacotes^)...
%CMD% -m pip --version 2>nul
if %errorlevel% neq 0 (
  echo     pip NAO responde - tentando reparar...
  %CMD% -m ensurepip --upgrade
)
echo.

echo [5] Instalando o que o coletor precisa ^(so "requests"^)...
%CMD% -m pip install requests
echo.

echo [6] Conferindo se ficou tudo certo...
%CMD% -c "import requests; print('   requests OK -', requests.__version__)"
if %errorlevel% neq 0 (
  echo     FALHOU - me mande um print desta janela.
  pause
  exit /b 1
)
echo.

echo [7] Conferindo se os arquivos do pacote estao aqui...
if exist COLETAR.py (
  echo    COLETAR.py .............. OK
) else (
  echo    COLETAR.py .............. NAO ENCONTRADO
  echo.
  echo    Este .bat precisa estar DENTRO da pasta PACOTE_COMPLETO,
  echo    junto com COLETAR.py. Mova-o para la e rode de novo.
  pause
  exit /b 1
)
if exist fluxo_captura.py (echo    fluxo_captura.py ........ OK) else (echo    fluxo_captura.py ........ FALTANDO)
echo.

echo ==========================================================
echo   TUDO PRONTO
echo ==========================================================
echo.
echo   Comando para iniciar a coleta neste PC:
echo.
echo       %CMD% COLETAR.py
echo.
echo   Quer comecar agora? Feche esta janela e rode INICIAR_COLETA.bat
echo.
pause
