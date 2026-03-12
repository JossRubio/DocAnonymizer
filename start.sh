#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/server.pid"

if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "Server already running (PID $OLD_PID). Run stop.sh first."
        exit 1
    else
        rm -f "$PID_FILE"
    fi
fi

cd "$SCRIPT_DIR/backend"
python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload &
echo $! > "$PID_FILE"
echo "Server started (PID $(cat "$PID_FILE")) at http://localhost:8001"
sleep 2
if command -v xdg-open &>/dev/null; then
    xdg-open http://localhost:8001
elif command -v open &>/dev/null; then
    open http://localhost:8001
else
    start http://localhost:8001
fi
