#!/bin/zsh
# One-click local development launcher for Frame Works Prints.
# Starts the FastAPI login/backend service and Expo Metro together.

set -eu

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
RUNTIME_DIR="$PROJECT_DIR/.tmp"
BACKEND_LOG="$RUNTIME_DIR/backend.log"
METRO_LOG="$RUNTIME_DIR/metro.log"

mkdir -p "$RUNTIME_DIR"

if ! /usr/bin/curl -fsS --max-time 2 http://127.0.0.1:8000/docs >/dev/null 2>&1; then
  (
    cd "$BACKEND_DIR"
    nohup .venv/bin/python -m uvicorn server:app --host 0.0.0.0 --port 8000 >"$BACKEND_LOG" 2>&1 &
  )
  sleep 2
fi

if ! /usr/bin/curl -fsS --max-time 4 http://127.0.0.1:8000/docs >/dev/null 2>&1; then
  echo "The login service did not start. See: $BACKEND_LOG"
  exit 1
fi

if ! /usr/sbin/lsof -tiTCP:8081 -sTCP:LISTEN >/dev/null 2>&1; then
  (
    cd "$FRONTEND_DIR"
    nohup npm run start -- --dev-client --port 8081 >"$METRO_LOG" 2>&1 &
  )
fi

SIMULATOR_NAME="iPhone 17"
APP_BUNDLE_ID="com.emergent.aiteedesigner.m7zqpa"

xcrun simctl boot "$SIMULATOR_NAME" >/dev/null 2>&1 || true
open -a Simulator
xcrun simctl bootstatus "$SIMULATOR_NAME" -b >/dev/null
xcrun simctl launch booted "$APP_BUNDLE_ID" >/dev/null

echo "Print Shop is open. The app and login service are running."
