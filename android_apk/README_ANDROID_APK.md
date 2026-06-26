## Build an offline APK (sideload)

This builds an Android APK which runs the app **fully offline** by:
- copying `templates/` + `static/` into app private storage on first run
- running the FastAPI app on `127.0.0.1:8088`
- opening a WebView to `http://127.0.0.1:8088`
- storing SQLite at app-private `files/` (offline)

### Prereqs (on your Mac/PC)
- Android Studio (latest)
- Android SDK installed via Android Studio

### Why this approach
Customers should not need Termux or a terminal. APK is a single installable app.

### Project choice
This scaffold uses **Chaquopy** to run Python inside the Android app process.

### Steps (high level)
0. From the repo root, sync Python + templates + CSS into the Android project:
   `bash scripts/sync_android.sh`
1. Open Android Studio → Open project folder `android_apk/inventory_app`
2. Copy `local.properties.example` → `local.properties` and set your Android SDK path.
3. Plug in a device (Developer mode + USB debugging) OR build an APK.
4. Build → Build Bundle(s) / APK(s) → Build APK(s)
5. Sideload the APK on the device.

Templates and static files also live under `app/src/main/assets/inventory/` (copied by the sync script). Do not commit `local.properties` (machine-specific SDK path).

### Notes
- The Android app will set environment variables:
  - `INVENTORY_BASE_DIR` = extracted assets dir containing `templates/` and `static/`
  - `INVENTORY_DB_PATH` = app-private sqlite file
- Server binds to `127.0.0.1` only (not exposed to LAN).

