@echo off
rem Ollama Cloud Dashboard - stop running server (locale-independent)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr /r "127.0.0.1:8765 .*0.0.0.0:0"') do (
    echo Stopping process %%a ...
    taskkill /F /PID %%a >nul 2>&1
)
echo Done.
pause