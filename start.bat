@echo off
REM Start the orchestrator system on Windows

REM Ensure we run from this script's folder
cd /d %~dp0

echo Starting Orchestrator System...
echo.

REM Check Python 3.11 via py launcher
py -3.11 -V >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python 3.11 not found by py launcher. Install Python 3.11.
    pause
    exit /b 1
)

REM Check if .env exists
if not exist ".env" (
    echo First time setup detected...
    py -3.11 setup.py
    echo.
)

REM Start services in separate windows
echo Starting Bridge Bot...
start "Orchestrator Bridge Bot" cmd /k py -3.11 bridge_bot.py

timeout /t 2 >nul

echo Starting Claude Desktop Runner...
start "Orchestrator Claude Runner" cmd /k py -3.11 claude_desktop_runner.py

echo.
echo ✅ Orchestrator is running!
echo.
echo Send commands to your Telegram bot:
echo   /task - Create a new task
echo   /status - Check system status
echo   /help - Show all commands
echo.
echo Press any key to stop all services...
pause >nul

REM Kill service windows by title
taskkill /F /FI "WINDOWTITLE eq Orchestrator Bridge Bot*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Orchestrator Claude Runner*" >nul 2>&1

echo Services stopped.
pause
