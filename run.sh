#!/usr/bin/env bash
set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
RESET='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PORT=8421

ok()   { echo -e "${GREEN}✅ $1${RESET}"; }
fail() { echo -e "${RED}❌ $1${RESET}"; exit 1; }

# [1] app.py exists
if [ ! -f "$SCRIPT_DIR/app.py" ]; then
  fail "File app.py nggak ketemu. Pastikan kamu di folder yang benar."
fi

# [2] python3
if ! command -v python3 &>/dev/null; then
  fail "Python 3 nggak ketemu. Jalankan install.sh dulu."
fi

# [2] pytubefix
if ! python3 -c "import pytubefix" &>/dev/null; then
  fail "Ada dependency yang belum terinstall (pytubefix). Jalankan install.sh dulu."
fi

# [2] flask
if ! python3 -c "import flask" &>/dev/null; then
  fail "Ada dependency yang belum terinstall (flask). Jalankan install.sh dulu."
fi

# [2] ffmpeg
if ! command -v ffmpeg &>/dev/null; then
  fail "Ada dependency yang belum terinstall (ffmpeg). Jalankan install.sh dulu."
fi

# [3] downloads folder
mkdir -p "$SCRIPT_DIR/downloads"

# [4] Check port
if lsof -iTCP:"$PORT" -sTCP:LISTEN &>/dev/null; then
  fail "Port $PORT sudah dipakai. Tutup app lain di port itu dulu."
fi

# [4] Start app
cd "$SCRIPT_DIR"
python3 app.py &
APP_PID=$!

# Ctrl+C / kill → matiin Python juga
trap 'echo ""; echo "Menghentikan app..."; kill $APP_PID 2>/dev/null; wait $APP_PID 2>/dev/null; echo "App dihentikan."; exit 0' INT TERM

# [5] Wait
sleep 2

# [6] Open browser
open "http://localhost:$PORT" 2>/dev/null || true

# [7] Info
ok "App running di http://localhost:$PORT"
echo "   Tekan Ctrl+C untuk stop."
echo ""

# Wait for app process
wait $APP_PID
