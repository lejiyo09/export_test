#!/bin/sh
set -eu

# Start the current Cobalt API in the background.
cd /opt/cobalt-api
node src/cobalt &
COBALT_PID=$!

cleanup() {
  kill "$COBALT_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Wait until Cobalt accepts connections.
node - <<'NODE'
const http = require("http");
const deadline = Date.now() + 60000;

function retry() {
  if (Date.now() >= deadline) {
    console.error("Cobalt API did not start in time.");
    process.exit(1);
  }
  setTimeout(check, 1000);
}

function check() {
  const req = http.get("http://127.0.0.1:9000/", res => {
    res.resume();
    if (res.statusCode >= 200 && res.statusCode < 500) {
      process.exit(0);
    }
    retry();
  });
  req.on("error", retry);
  req.setTimeout(3000, () => {
    req.destroy();
    retry();
  });
}

check();
NODE

exec python /app/app.py
