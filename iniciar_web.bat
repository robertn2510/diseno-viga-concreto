@echo off
REM Inicia la interfaz web local del sistema de diseno E.060 (Windows)
cd /d "%~dp0"
python servidor.py %*
pause
