@echo off
REM Gateway SCADA - doble clic para arrancar (PLC real, usa config.toml)
cd /d %~dp0
if not exist config.toml copy config.example.toml config.toml
python -m scada_gateway --config config.toml
pause
