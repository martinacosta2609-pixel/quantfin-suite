@echo off
title ECONOMATO SUITE - SYNC & VERIFY (FASE 3)
cd /d "%~dp0"
set PYTHONDONTWRITEBYTECODE=1

echo ========================================================================
echo   1. Limpiando residuos __pycache__ y archivos temporales...
echo ========================================================================
powershell -NoProfile -Command "Get-ChildItem -Path . -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue"

echo ========================================================================
echo   2. Ejecutando Suite Automatizada de Verificacion Cuantitativa...
echo ========================================================================
python -B test_quant_suite.py
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Fallo en la bateria de pruebas cuantitativas.
    pause
    exit /b 1
)

echo ========================================================================
echo   3. Verificando limite de archivos para GitHub Web Upload (< 100)...
echo ========================================================================
powershell -NoProfile -Command "$c = (Get-ChildItem -Path . -Recurse -File).Count; Write-Host \"Total archivos en financial_suite: $c / 100\"; if ($c -ge 100) { exit 1 }"
if %ERRORLEVEL% NEQ 0 (
    echo [ALERTA] El repositorio supera los 100 archivos permitidos por GitHub Web Upload.
    pause
    exit /b 1
)

echo ========================================================================
echo   LISTO PARA SUBIR A GITHUB / RENDER (0 __pycache__, < 100 archivos)
echo ========================================================================
pause
