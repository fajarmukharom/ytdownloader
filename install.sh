#!/usr/bin/env bash
set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RESET='\033[0m'

ok()   { echo -e "${GREEN}✅ $1${RESET}"; }
fail() { echo -e "${RED}❌ $1${RESET}"; exit 1; }
info() { echo -e "${BLUE}ℹ️  $1${RESET}"; }

echo ""
echo "========================================"
echo "  YouTube Downloader — Installer"
echo "========================================"
echo ""

# [1/6] Python 3
echo -n "[1/6] ⏳ Mengecek Python 3...          "
if command -v python3 &>/dev/null; then
  VER=$(python3 --version 2>&1 | awk '{print $2}')
  ok "Python $VER ditemukan"
else
  fail "Python 3 belum terinstall. Install dulu di python.org/downloads"
fi

# [2/6] Homebrew
echo -n "[2/6] ⏳ Mengecek Homebrew...           "
if command -v brew &>/dev/null; then
  ok "Homebrew sudah terinstall"
else
  echo ""
  echo -e "${YELLOW}⚠️  Homebrew belum ada, mencoba install...${RESET}"
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" \
    || fail "Gagal install Homebrew. Coba install manual di brew.sh"
  ok "Homebrew berhasil diinstall"
fi

# [3/6] FFmpeg
echo -n "[3/6] ⏳ Mengecek / menginstall FFmpeg... "
if command -v ffmpeg &>/dev/null; then
  ok "FFmpeg sudah terinstall"
else
  brew install ffmpeg \
    || fail "Gagal install FFmpeg. Coba manual: brew install ffmpeg"
  ok "FFmpeg terinstall"
fi

# [4/6] pytubefix
echo -n "[4/6] ⏳ Menginstall pytubefix...       "
pip3 install -U "pytubefix>=11.1.0" \
  || fail "Gagal install Python packages. Coba: pip3 install -U pytubefix flask"
ok "pytubefix terinstall (versi terbaru)"

# [5/6] Flask
echo -n "[5/6] ⏳ Menginstall Flask...           "
if python3 -c "import flask" &>/dev/null; then
  ok "Flask sudah terinstall"
else
  pip3 install flask \
    || fail "Gagal install Python packages. Coba: pip3 install pytubefix flask"
  ok "Flask terinstall"
fi

# [6/6] downloads folder
echo -n "[6/6] ⏳ Menyiapkan folder downloads... "
mkdir -p "$(dirname "$0")/downloads"
ok "Folder siap"

# Make run.sh executable
chmod +x "$(dirname "$0")/run.sh" 2>/dev/null || true

echo ""
echo "========================================"
echo -e "${GREEN}✅ Instalasi selesai!${RESET}"
echo "   Jalankan ./run.sh untuk mulai."
echo "========================================"
echo ""
