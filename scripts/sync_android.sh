#!/usr/bin/env bash
set -euo pipefail

# Copy the desktop FastAPI app + templates/static into the Android project.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ANDROID_APP="$ROOT/android_apk/inventory_app/app/src/main"

mkdir -p "$ANDROID_APP/python/app"
mkdir -p "$ANDROID_APP/assets/inventory/templates"
mkdir -p "$ANDROID_APP/assets/inventory/static"

cp -R "$ROOT/app/." "$ANDROID_APP/python/app/"
cp -R "$ROOT/templates/." "$ANDROID_APP/assets/inventory/templates/"
cp -R "$ROOT/static/." "$ANDROID_APP/assets/inventory/static/"

echo "Synced app/, templates/, and static/ into android_apk/inventory_app"
