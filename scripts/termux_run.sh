#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

# Start the app locally on the tablet.
# Then open: http://127.0.0.1:8088

# shellcheck disable=SC1091
source .venv/bin/activate

python -m uvicorn app.main:app --host 127.0.0.1 --port 8088

