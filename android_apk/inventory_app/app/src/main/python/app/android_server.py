from __future__ import annotations

import threading


def start_server(host: str = "127.0.0.1", port: int = 8088) -> None:
    """
    Start the FastAPI server in a background thread.
    Intended for Android (Chaquopy) where we want a single-process app + WebView.
    """
    import uvicorn

    def _run() -> None:
        config = uvicorn.Config(
            "app.main:app",
            host=host,
            port=int(port),
            log_level="info",
            access_log=False,
        )
        server = uvicorn.Server(config)
        server.run()

    thread = threading.Thread(target=_run, name="uvicorn", daemon=True)
    thread.start()


def wait_forever() -> None:
    """
    Keep the Python VM alive if needed.
    """
    import time

    while True:
        time.sleep(3600)

