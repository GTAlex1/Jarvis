@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  py -m venv .venv || goto error
)
.venv\Scripts\python.exe -c "import discord, tkinter" >nul 2>&1
if errorlevel 1 (
  .venv\Scripts\python.exe -m pip install -r requirements.txt || goto error
)
.venv\Scripts\python.exe server_builder_gui.py
if errorlevel 1 goto error
exit /b 0
:error
echo No se pudo abrir Nexora Server Builder.
pause
exit /b 1
