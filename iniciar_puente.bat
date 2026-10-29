@echo off
REM Puente ETABS -> interfaz web (ejecutar en el Windows donde esta abierto ETABS)
cd /d "%~dp0"
title Puente ETABS v20-v23 - Diseno E.060
echo ============================================================
echo  Puente ETABS v20 - v23  ^|  Diseno E.060 (RNE - Peru)
echo ============================================================
echo.
echo  1) Exportar las barras SELECCIONADAS en ETABS y subirlas al servidor
echo  2) Exportar TODO el modelo y subirlo al servidor
echo  3) Solo exportar a la carpeta "salida" (cargar luego a mano)
echo  4) Probar el puente con el modelo demo (sin ETABS)
echo.
set /p OPC="Opcion [1-4]: "
if "%OPC%"=="1" (
  set /p URL="Direccion del servidor (ej. http://localhost:8000): "
  python puente_etabs.py --seleccionados --subir "%URL%"
)
if "%OPC%"=="2" (
  set /p URL="Direccion del servidor (ej. http://localhost:8000): "
  python puente_etabs.py --subir "%URL%"
)
if "%OPC%"=="3" python puente_etabs.py --seleccionados --carpeta salida
if "%OPC%"=="4" python puente_etabs.py --demo --carpeta salida
echo.
pause
