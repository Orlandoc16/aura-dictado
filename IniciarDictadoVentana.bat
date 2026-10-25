@echo off
title Dictado Local (ventana)
cd /d "%~dp0"
set HF_HOME=C:\Users\DELL\.cache\huggingface
set HF_HUB_OFFLINE=1
"%~dp0venv\Scripts\python.exe" "%~dp0dictado-gui.py"
if errorlevel 1 pause
