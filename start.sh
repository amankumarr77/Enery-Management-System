#!/bin/bash

# Find the directory where this script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

clear
echo "====================================================="
echo "        EMSJB Real-Time Trading Platform             "
echo "====================================================="
echo ""

# Free up ports if they are already in use from a previous run
echo "[1/4] Checking for existing server processes..."
lsof -ti:8000 | xargs kill -9 2>/dev/null
lsof -ti:5173 | xargs kill -9 2>/dev/null

# Start Backend
echo "[2/4] Starting FastAPI backend server..."
source .venv/bin/activate
uvicorn backend.main:app --host 127.0.0.1 --port 8000 > backend_launcher.log 2>&1 &
BACKEND_PID=$!

# Start Frontend
echo "[3/4] Starting React frontend server..."
cd frontend
npm run dev > frontend_launcher.log 2>&1 &
FRONTEND_PID=$!

echo "[4/4] Waiting for services to initialize..."
sleep 5

# Open browser
echo "-> Opening Dashboard in your browser..."
open http://localhost:5173/

echo ""
echo "====================================================="
echo "  SYSTEM IS LIVE!                                    "
echo "  DO NOT CLOSE THIS WINDOW while trading.            "
echo "  To stop the servers safely, press Ctrl+C or close this window."
echo "====================================================="

# Trap to ensure background processes are killed when terminal closes
trap "echo -e '\nShutting down servers...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" EXIT INT TERM

# Wait forever to keep the script running
wait
