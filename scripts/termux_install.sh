#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

# Offline-first local install for Android (Termux).
# Usage:
#   bash scripts/termux_install.sh

pkg update -y
pkg install -y python git openssl libffi

python -m pip install --upgrade pip setuptools wheel

if [ ! -d ".venv" ]; then
  python -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

pip install -r requirements-mobile.txt

echo
echo "Installed. Start the app with:"
echo "  bash scripts/termux_run.sh"

