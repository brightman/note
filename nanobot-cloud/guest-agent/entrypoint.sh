#!/bin/bash
# Runs inside the Firecracker VM.
# Order: start vsock receiver → wait for config injection → start nanobot.

set -euo pipefail

export NANOBOT_HOME="${NANOBOT_HOME:-/home/nanobot/.nanobot}"
VSOCK_SOCK="/tmp/vsock-1024.sock"
NANOBOT_LOG="/var/log/nanobot.log"
READY_MARKER="$NANOBOT_HOME/.ready"

mkdir -p "$NANOBOT_HOME/skills" "$NANOBOT_HOME/memory"

echo "[entrypoint] starting vsock receiver..."
python3 /app/vsock_receiver.py &
VSOCK_PID=$!

# Wait for vsock socket to appear
for i in $(seq 1 30); do
    [ -S "$VSOCK_SOCK" ] && break
    sleep 0.2
done

if [ ! -S "$VSOCK_SOCK" ]; then
    echo "[entrypoint] ERROR: vsock socket never appeared" >&2
    exit 1
fi

echo "[entrypoint] vsock receiver ready, waiting for config injection..."

# Wait for control plane to inject config.json
for i in $(seq 1 60); do
    [ -f "$NANOBOT_HOME/config.json" ] && break
    sleep 0.5
done

if [ ! -f "$NANOBOT_HOME/config.json" ]; then
    echo "[entrypoint] ERROR: config.json never arrived" >&2
    kill "$VSOCK_PID" 2>/dev/null
    exit 1
fi

echo "[entrypoint] config.json received, starting nanobot..."

# Start nanobot in gateway mode (OpenAI-compatible HTTP API on :8765)
nanobot gateway \
    --config "$NANOBOT_HOME/config.json" \
    --port 8765 \
    >> "$NANOBOT_LOG" 2>&1 &
NANOBOT_PID=$!

touch "$READY_MARKER"
echo "[entrypoint] nanobot started (pid=$NANOBOT_PID)"

# Keep container alive; forward signals
trap 'kill "$NANOBOT_PID" "$VSOCK_PID" 2>/dev/null; exit 0' SIGTERM SIGINT

wait "$NANOBOT_PID"
echo "[entrypoint] nanobot exited"
kill "$VSOCK_PID" 2>/dev/null
