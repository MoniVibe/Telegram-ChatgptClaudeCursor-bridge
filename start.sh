#!/bin/bash
# Start the orchestrator system on Unix/Linux/Mac

echo "Starting Orchestrator System..."
echo

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python3 not found. Please install Python 3.10+"
    exit 1
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "First time setup detected..."
    python3 setup.py
    echo
fi

# Function to cleanup on exit
cleanup() {
    echo -e "\nStopping services..."
    kill $BRIDGE_PID $RUNNER_PID 2>/dev/null
    wait $BRIDGE_PID $RUNNER_PID 2>/dev/null
    echo "Services stopped."
    exit 0
}

# Set trap for cleanup
trap cleanup INT TERM

# Start services
echo "Starting Bridge Bot..."
python3 bridge_bot.py &
BRIDGE_PID=$!

sleep 2

echo "Starting Claude Runner..."
python3 claude_runner.py &
RUNNER_PID=$!

echo
echo "✅ Orchestrator is running!"
echo
echo "Send commands to your Telegram bot:"
echo "  /task - Create a new task"
echo "  /status - Check system status"
echo "  /help - Show all commands"
echo
echo "Press Ctrl+C to stop all services..."

# Wait for processes
wait
