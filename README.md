# Inventory + Expense Tracker

Offline tracker for a small shop: raw materials, purchases, usage expense, and cash vs online earnings.

Runs as a local FastAPI app (laptop) or as an Android APK (on-device Python + WebView). No cloud account. Data stays in SQLite on the device.

## Features

- Items with quantity on hand and **moving-average unit cost**
- Purchases increase stock and update average cost (cash or online)
- Usage decreases stock and records expense at the current average
- Earnings (cash / online) and a dashboard with monthly profit splits
- Daily / monthly / last-3-months reports as HTML or Excel
- Fully **offline** — server binds to `127.0.0.1` only

## Run (laptop)

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

SQLite file: `data/app.db` (created on first run). Do not commit this file if it contains real shop data.

## Android APK (offline)

The APK embeds the same Python app with [Chaquopy](https://chaquo.com/chaquopy/), starts FastAPI on `127.0.0.1:8088`, and shows it in a WebView.

1. After changing Python or HTML/CSS, sync into the Android project:

   ```bash
   bash scripts/sync_android.sh
   ```

2. Open `android_apk/inventory_app` in Android Studio.
3. Copy `local.properties.example` → `local.properties` and set `sdk.dir`.
4. Build / sideload the APK.

Details: [`android_apk/README_ANDROID_APK.md`](android_apk/README_ANDROID_APK.md).

The `INTERNET` permission is only so the WebView can talk to localhost. The app does not call the public internet.

## Termux (optional)

```bash
bash scripts/termux_install.sh
bash scripts/termux_run.sh
```

Then open `http://127.0.0.1:8088`. Uses `requirements-mobile.txt` (plain uvicorn, easier on Android).

## Costing

On purchase:

`new_avg = (old_qty * old_avg + bought_qty * unit_price) / new_qty`

On usage:

`expense = qty_used * current_avg`

Deleting a purchase or usage **replays** remaining events so stock and average cost stay consistent.

## Tests

```bash
pip install -r requirements.txt pytest httpx
python -m pytest
```

## Tech

Python, FastAPI, SQLite, Jinja, openpyxl, Android (Kotlin WebView, Chaquopy).
