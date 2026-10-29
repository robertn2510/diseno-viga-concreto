@echo off
REM Aplicacion de escritorio (Tkinter) del sistema de diseno E.060
REM Ejecutar en el mismo Windows donde esta abierto ETABS v20-v23.
cd /d "%~dp0"
title Diseno E.060 - escritorio

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] No se encontro Python en el PATH.
  echo Instale Python 3.8+ de 64 bits desde python.org y marque "Add Python to PATH".
  pause
  exit /b 1
)

python -c "import tkinter" >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Esta instalacion de Python no incluye Tkinter.
  echo Vuelva a ejecutar el instalador de Python y marque "tcl/tk and IDLE".
  echo Alternativa: use iniciar_web.bat (interfaz web) o python -m e060.cli.
  pause
  exit /b 1
)

python -c "import comtypes" >nul 2>nul
if errorlevel 1 (
  echo [AVISO] Sin comtypes no habra conexion en vivo con ETABS.
  echo         Instalela con:  pip install comtypes
)

python app_escritorio.py
pause
