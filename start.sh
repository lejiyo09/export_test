#!/bin/sh
set -eu

# If YouTube cookies are supplied through Render's YOUTUBE_COOKIES_B64 secret,
# convert the Netscape cookie export used by yt-dlp into Cobalt's cookies.json format.
if [ -n "${YOUTUBE_COOKIES_B64:-}" ]; then
  python3 - <<'PY'
import base64
import json
import os

raw = os.environ.get("YOUTUBE_COOKIES_B64", "").strip()
try:
    data = base64.b64decode(raw, validate=True).decode("utf-8", errors="replace")
except Exception as exc:
    print("[cookies] invalid YOUTUBE_COOKIES_B64:", exc, flush=True)
    raise SystemExit(0)

pairs = []
for line in data.splitlines():
    if not line or line.startswith("#"):
        continue
    parts = line.split("\t")
    if len(parts) < 7:
        continue
    domain, _, _, _, _, name, value = parts[:7]
    domain = domain.lower()
    if "youtube.com" not in domain and "youtube-nocookie.com" not in domain:
        continue
    pairs.append(f"{name}={value}")

if pairs:
    with open("/opt/cobalt-api/cookies.json", "w", encoding="utf-8") as f:
        json.dump({"youtube": ["; ".join(pairs)]}, f)
    print(f"[cookies] loaded {len(pairs)} YouTube cookies for Cobalt", flush=True)
else:
    print("[cookies] no YouTube cookies found in YOUTUBE_COOKIES_B64", flush=True)
PY
else
  echo "[cookies] YOUTUBE_COOKIES_B64 is not set; Cobalt will use an empty cookie store" >&2
fi

# Cobalt expects cookies.json to exist when COOKIE_PATH is set.
# Keep an empty valid file when no secret is configured so startup stays clean.
if [ ! -f /opt/cobalt-api/cookies.json ]; then
  printf '%s\n' '{}' > /opt/cobalt-api/cookies.json
fi

export COOKIE_PATH=/opt/cobalt-api/cookies.json

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
