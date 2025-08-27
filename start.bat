@echo off
REM Start the orchestrator system on Windows

echo Starting Orchestrator System...
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.10+
    pause
    exit /b 1
)

REM Check if .env exists
if not exist ".env" (
    echo First time setup detected...
    python setup.py
    echo.
)

REM Start services in separate windows
echo Starting Bridge Bot...
start "Bridge Bot" cmd /k python bridge_bot.py

timeout /t 2 >nul

echo Starting Claude Runner...
start "Claude Runner" cmd /k python claude_runner.py

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

REM Kill Python processes
taskkill /F /FI "WINDOWTITLE eq Bridge Bot*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Claude Runner*" >nul 2>&1

echo Services stopped.
pause
