@echo off
title Dictado Local — mantén F9 y habla
cd /d "%~dp0"
set HF_HOME=C:\Users\DELL\.cache\huggingface
set HF_HUB_OFFLINE=1
echo ============================================
echo  Dictado Local - mantén F9 y habla
echo  (deja esta ventana abierta; Ctrl+C para salir)
echo ============================================
"%~dp0venv\Scripts\python.exe" "%~dp0dictado.py"
echo.
echo El dictado se cerró. Código de salida: %errorlevel%
pause
