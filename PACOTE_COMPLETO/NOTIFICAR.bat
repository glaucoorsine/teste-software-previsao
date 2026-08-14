@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title Configurar notificacao no celular

set CMD=
python --version >nul 2>&1 && set CMD=python
if "%CMD%"=="" (py --version >nul 2>&1 && set CMD=py)
if "%CMD%"=="" (echo Python nao encontrado. Rode DIAGNOSTICO.bat & pause & exit /b 1)

cls
echo ==========================================================
echo   AVISO NO CELULAR QUANDO SAIR UM SINAL
echo ==========================================================
echo.
echo   1. Instale o app "ntfy" no celular (gratis, iOS e Android)
echo   2. Abra o app, toque em + e assine um topico
echo      Escolha um nome UNICO - quem souber o nome recebe
echo      os avisos. Ex: roleta-gco-8842-xyz
echo   3. Abra o arquivo notificacoes.json neste computador
echo      e deixe assim, com o SEU topico:
echo.
echo        { "canal": "ntfy", "topico": "roleta-gco-8842-xyz" }
echo.
echo   4. Salve o arquivo e volte aqui
echo.
echo ==========================================================
pause
cls
echo Enviando aviso de teste...
echo.
%CMD% notificador.py
echo.
echo ==========================================================
echo   Se chegou no celular, esta pronto.
echo   A partir de agora, todo sinal novo vira notificacao.
echo ==========================================================
echo.
pause
