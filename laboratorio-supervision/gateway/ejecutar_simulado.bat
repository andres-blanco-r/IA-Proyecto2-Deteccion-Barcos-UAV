@echo off
REM Gateway SCADA en modo simulado (sin PLC). Para acelerar la planta suba factor_tiempo en config.toml
cd /d %~dp0
if not exist config.toml copy config.example.toml config.toml
python -m scada_gateway --config config.toml --simular
pause
