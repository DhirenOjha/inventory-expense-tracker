from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main
from app.storage import ensure_schema


def test_pages_and_daily_excel(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    main.DB_PATH = db_path
    main.DATA_DIR = tmp_path
    ensure_schema({"db_path": db_path})

    with TestClient(main.app) as client:
        home = client.get("/")
        assert home.status_code == 200
        assert "Dashboard" in home.text

        items = client.get("/items")
        assert items.status_code == 200

        created = client.post("/items", data={"name": "Flour", "unit": "kg", "description": ""}, follow_redirects=False)
        assert created.status_code == 303

        daily = client.get("/reports.xlsx?range=daily")
        assert daily.status_code == 200
        assert daily.headers["content-type"].startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
