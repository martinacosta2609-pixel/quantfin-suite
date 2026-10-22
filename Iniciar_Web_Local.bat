@echo off
title GameTheory Studio - Servidor Web Local
cd /d "%~dp0"
echo Abriendo GameTheory Studio en el navegador (http://localhost:5173)...
start http://localhost:5173
call npm.cmd run dev
pause
