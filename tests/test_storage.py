from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from app.storage import (
    ValidationError,
    create_item,
    ensure_schema,
    get_dashboard,
    get_report,
    record_earning,
    record_purchase,
    record_usage,
)


def _db(tmp_path: Path) -> Path:
    db_path = tmp_path / "app.db"
    ensure_schema({"db_path": db_path})
    return db_path


def test_moving_average_and_usage_expense(tmp_path: Path) -> None:
    db_path = _db(tmp_path)
    item = create_item({"db_path": db_path, "name": "Oil", "unit": "L", "description": ""})
    today = date.today()

    record_purchase(
        {
            "db_path": db_path,
            "item_id": item.id,
            "quantity": Decimal("10"),
            "unit_price": Decimal("120"),
            "purchased_on": today,
            "payment_method": "cash",
        }
    )
    record_purchase(
        {
            "db_path": db_path,
            "item_id": item.id,
            "quantity": Decimal("10"),
            "unit_price": Decimal("80"),
            "purchased_on": today,
            "payment_method": "online",
        }
    )
    record_usage(
        {
            "db_path": db_path,
            "item_id": item.id,
            "quantity": Decimal("5"),
            "used_on": today,
        }
    )

    dashboard = get_dashboard({"db_path": db_path})
    oil = next(i for i in dashboard.items if i.id == item.id)
    assert oil.quantity_on_hand == Decimal("15")
    assert oil.avg_unit_cost == Decimal("100")
    assert dashboard.month_usage_expense == Decimal("500")


def test_usage_cannot_exceed_stock(tmp_path: Path) -> None:
    db_path = _db(tmp_path)
    item = create_item({"db_path": db_path, "name": "Rice", "unit": "kg", "description": ""})
    try:
        record_usage(
            {
                "db_path": db_path,
                "item_id": item.id,
                "quantity": Decimal("1"),
                "used_on": date.today(),
            }
        )
        raise AssertionError("expected ValidationError")
    except ValidationError:
        pass


def test_daily_report_does_not_crash(tmp_path: Path) -> None:
    db_path = _db(tmp_path)
    create_item({"db_path": db_path, "name": "Salt", "unit": "kg", "description": ""})
    record_earning(
        {
            "db_path": db_path,
            "amount": Decimal("200"),
            "earned_on": date.today(),
            "payment_method": "cash",
        }
    )
    report = get_report({"db_path": db_path, "range": "daily"})
    assert report["title"] == "Daily report"
    assert report["totals"]["earnings"] == Decimal("200")
    monthly = get_report({"db_path": db_path, "range": "monthly"})
    last3 = get_report({"db_path": db_path, "range": "3months"})
    assert monthly["totals"]["earnings"] == Decimal("200")
    assert last3["totals"]["earnings"] == Decimal("200")
