#!/bin/sh
set -eu

node /opt/bgutil-ytdlp-pot-provider/server/build/main.js --host 127.0.0.1 --port 4416 &
PROVIDER_PID=$!

cleanup() {
  kill "$PROVIDER_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

sleep 1
exec python /app/app.py
