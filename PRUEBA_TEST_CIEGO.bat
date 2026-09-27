@echo off
REM Abre la UI con test_ciego ya cargado y marcado con la clave (etiquetas reales del dataset)
cd /d "%~dp0"
python app.py --carpeta test_ciego --etiquetas clave_test_ciego.csv --modelo dev
pause
