@echo off
title QUANTFIN CLOUD SUITE
cd /d "%~dp0"
echo ===================================================
echo   Iniciando QuantFin Cloud Suite...
echo   Abriendo Hub Central en: http://localhost:8000/
echo ===================================================
timeout /t 2 /nobreak >nul
start "" "http://localhost:8000/"
py server.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Ocurrio un error al ejecutar el servidor.
    pause
)
