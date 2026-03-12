#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/server.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "No server.pid found. Is the server running?"
    exit 1
fi

PID=$(cat "$PID_FILE")

if kill -0 "$PID" 2>/dev/null; then
    kill -TERM "$PID"
    echo "Server (PID $PID) stopped."
else
    echo "Process $PID not found (already stopped?)."
fi

rm -f "$PID_FILE"
