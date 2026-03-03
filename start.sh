#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "=== LLM Council ==="
echo ""

# Kill anything already on our ports
for port in 8001 5173; do
  pid=$(lsof -ti:$port 2>/dev/null || true)
  if [ -n "$pid" ]; then
    echo "Freeing port $port (pid $pid)..."
    kill -9 $pid 2>/dev/null || true
    sleep 0.5
  fi
done

# Install backend deps if needed
if ! python3 -c "import fastapi" 2>/dev/null; then
  echo "Installing backend dependencies..."
  pip3 install -q -e .
fi

# Install frontend deps if needed
if [ ! -d frontend/node_modules ]; then
  echo "Installing frontend dependencies..."
  (cd frontend && npm install --silent)
fi

# Start backend
echo "Starting backend on http://localhost:8001..."
python3 -m backend.main &
BACKEND_PID=$!

sleep 2

# Start frontend
echo "Starting frontend on http://localhost:5173..."
(cd frontend && npm run dev -- --host 2>/dev/null) &
FRONTEND_PID=$!

echo ""
echo "LLM Council is running!"
echo "  App:      http://localhost:5173"
echo "  API:      http://localhost:8001"
echo "  Settings: http://localhost:5173/#settings"
echo ""
echo "Press Ctrl+C to stop"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" SIGINT SIGTERM
wait
