@echo off
REM Interfaz web local del sistema de diseno E.060 (Windows)
REM Requiere ETABS abierto con el modelo para la conexion COM/OAPI.
cd /d "%~dp0"
title Diseno E.060 - interfaz web

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] No se encontro Python en el PATH.
  echo Instale Python 3.8+ de 64 bits desde python.org y marque
  echo "Add Python to PATH" durante la instalacion.
  pause
  exit /b 1
)

python -c "import platform,sys; sys.exit(0 if platform.architecture()[0]=='64bit' else 1)" >nul 2>nul
if errorlevel 1 (
  echo [AVISO] Este Python es de 32 bits. ETABS de 64 bits exige Python de 64 bits
  echo         para la conexion COM. La importacion de tablas funciona igual.
)

python -c "import comtypes" >nul 2>nul
if errorlevel 1 (
  echo [AVISO] Sin la libreria comtypes no habra conexion en vivo con ETABS.
  echo         Instalela con:  pip install comtypes
  echo         Mientras tanto puede usar "Importar tablas" o el modelo demo.
)

echo.
echo  Abriendo la interfaz en http://localhost:8000
echo  (si el navegador se adelanta, recargue la pagina en 2 segundos)
start "" http://localhost:8000
python servidor.py %*
pause
