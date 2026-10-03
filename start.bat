@echo off
rem Ollama Cloud Dashboard - easy start
cd /d "%~dp0"
echo Starting Ollama Cloud Dashboard...
uv run python dashboard.py
pause