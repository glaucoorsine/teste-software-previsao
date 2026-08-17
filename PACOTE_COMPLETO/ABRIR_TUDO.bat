@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title Laboratorio - Abrir Tudo

rem descobre se neste PC o comando e' "python" ou "py".
rem Antes era "python" fixo: em maquina sem PATH configurado, as seis janelas
rem abriam e fechavam na hora, sem dizer por que.
set CMD=
python --version >nul 2>&1 && set CMD=python
if "%CMD%"=="" (py --version >nul 2>&1 && set CMD=py)
if "%CMD%"=="" (
  cls
  echo ==========================================================
  echo   O Windows nao encontra o Python
  echo ==========================================================
  echo.
  echo   Rode o DIAGNOSTICO.bat - ele diz exatamente o que fazer.
  echo.
  pause
  exit /b 1
)

cls
echo ============================================
echo  Abrindo o laboratorio  ^(%CMD%^)
echo ============================================
echo.
echo  Cada jogo coleta os giros sozinho enquanto roda.
echo  No fim do dia, rode EXPORTAR.bat.
echo.

start "Academia Servico" cmd /c "cd /d "%~dp0" && %CMD% academia_servico.py"
timeout /t 2 /nobreak >nul

start "Mega Fire"  cmd /c "cd /d "%~dp0" && %CMD% mega_fire_combo.py"
timeout /t 1 /nobreak >nul
start "Lightning"  cmd /c "cd /d "%~dp0" && %CMD% lightning_combo.py"
timeout /t 1 /nobreak >nul
start "Crazy Time" cmd /c "cd /d "%~dp0" && %CMD% crazy_time_combo.py"
timeout /t 1 /nobreak >nul
rem A Immersive saiu do software por decisao dele, e o arquivo dela foi
rem apagado -- esta linha chamava immersive_combo.py, que nao existe mais.
rem No lugar dela entra a mesa que nunca teve janela: a Crazy Time A.
start "Crazy Time A" cmd /c "cd /d "%~dp0" && %CMD% crazy_time_a_combo.py"
timeout /t 1 /nobreak >nul

start "Assistente IA" cmd /c "cd /d "%~dp0" && %CMD% assistente_ia.py"
timeout /t 1 /nobreak >nul
start "Central IAs"   cmd /c "cd /d "%~dp0" && %CMD% central_ias.py"

echo.
echo  Tudo disparado em janelas separadas. Pode fechar esta.
echo.
pause
