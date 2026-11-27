@echo off
setlocal
cd /d "%~dp0"
python -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>&1
if not errorlevel 1 goto python
py -3 -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>&1
if not errorlevel 1 goto py
echo No se encontro Python 3.10 o posterior.
echo Instala Python desde https://www.python.org/downloads/windows/
echo Luego vuelve a abrir este archivo.
pause
exit /b 1

:python
python jarvis_gui.py
goto result

:py
py -3 jarvis_gui.py

:result
set "jarvis_status=%errorlevel%"
if not "%jarvis_status%"=="0" pause
exit /b %jarvis_status%
