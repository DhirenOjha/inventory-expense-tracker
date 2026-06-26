from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, TypedDict, cast


class NotFoundError(Exception):
    pass


class ValidationError(Exception):
    pass


class ConflictError(Exception):
    pass


PaymentMethod = Literal["cash", "online"]


class EnsureSchemaIn(TypedDict):
    db_path: Path


class CreateItemIn(TypedDict):
    db_path: Path
    name: str
    unit: str
    description: str


class ListItemsIn(TypedDict):
    db_path: Path


class GetItemIn(TypedDict):
    db_path: Path
    item_id: int


class RecordPurchaseIn(TypedDict):
    db_path: Path
    item_id: int
    quantity: Decimal
    unit_price: Decimal
    purchased_on: date
    payment_method: PaymentMethod


class RecordUsageIn(TypedDict):
    db_path: Path
    item_id: int
    quantity: Decimal
    used_on: date


class RecordEarningIn(TypedDict):
    db_path: Path
    amount: Decimal
    earned_on: date
    payment_method: PaymentMethod


class ListEarningsIn(TypedDict):
    db_path: Path
    limit: int


class UpdateEarningIn(TypedDict):
    db_path: Path
    earning_id: int
    amount: Decimal
    earned_on: date
    payment_method: PaymentMethod


class DeleteEarningIn(TypedDict):
    db_path: Path
    earning_id: int


class DeleteItemIn(TypedDict):
    db_path: Path
    item_id: int


class DeletePurchaseIn(TypedDict):
    db_path: Path
    item_id: int
    purchase_id: int


class DeleteUsageIn(TypedDict):
    db_path: Path
    item_id: int
    usage_id: int


class GetDashboardIn(TypedDict):
    db_path: Path


class GetReportIn(TypedDict):
    db_path: Path
    range: Literal["daily", "monthly", "3months"]


@dataclass(frozen=True)
class Item:
    id: int
    name: str
    unit: str
    description: str
    quantity_on_hand: Decimal
    avg_unit_cost: Decimal
    updated_at: str


@dataclass(frozen=True)
class Purchase:
    id: int
    item_id: int
    quantity: Decimal
    unit_price: Decimal
    purchased_on: str
    payment_method: str
    created_at: str


@dataclass(frozen=True)
class Usage:
    id: int
    item_id: int
    quantity: Decimal
    unit_cost: Decimal
    expense_amount: Decimal
    used_on: str
    created_at: str


@dataclass(frozen=True)
class Earning:
    id: int
    amount: Decimal
    earned_on: str
    payment_method: str
    created_at: str


@dataclass(frozen=True)
class ItemDetail:
    item: Item
    purchases: list[Purchase]
    usages: list[Usage]


@dataclass(frozen=True)
class Dashboard:
    items: list[Item]
    total_inventory_value: Decimal
    month: str
    month_usage_expense: Decimal
    month_purchase_expense_cash: Decimal
    month_purchase_expense_online: Decimal
    month_earnings_cash: Decimal
    month_earnings_online: Decimal
    month_profit_overall: Decimal
    month_profit_cash: Decimal
    month_profit_online: Decimal
    monthly_rows: list[dict[str, Any]]


def _connect(*, db_path: Path) -> sqlite3.Connection:
    if not isinstance(db_path, Path):
        raise ValueError("db_path must be a Path")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def ensure_schema(input: EnsureSchemaIn) -> None:
    db_path = input["db_path"]
    conn = _connect(db_path=db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL UNIQUE,
              unit TEXT NOT NULL,
              description TEXT NOT NULL DEFAULT '',
              quantity_on_hand TEXT NOT NULL DEFAULT '0',
              avg_unit_cost TEXT NOT NULL DEFAULT '0',
              updated_at TEXT NOT NULL
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS purchases (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              item_id INTEGER NOT NULL,
              quantity TEXT NOT NULL,
              unit_price TEXT NOT NULL,
              purchased_on TEXT NOT NULL,
              payment_method TEXT NOT NULL DEFAULT 'cash',
              created_at TEXT NOT NULL,
              FOREIGN KEY(item_id) REFERENCES items(id) ON DELETE CASCADE
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS usages (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              item_id INTEGER NOT NULL,
              quantity TEXT NOT NULL,
              unit_cost TEXT NOT NULL,
              expense_amount TEXT NOT NULL,
              used_on TEXT NOT NULL,
              created_at TEXT NOT NULL,
              FOREIGN KEY(item_id) REFERENCES items(id) ON DELETE CASCADE
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS earnings (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              amount TEXT NOT NULL,
              earned_on TEXT NOT NULL,
              payment_method TEXT NOT NULL DEFAULT 'cash',
              created_at TEXT NOT NULL
            );
            """
        )

        item_cols = {str(r["name"]) for r in conn.execute("PRAGMA table_info(items)").fetchall()}
        if "description" not in item_cols:
            conn.execute("ALTER TABLE items ADD COLUMN description TEXT NOT NULL DEFAULT ''")

        purchase_cols = {str(r["name"]) for r in conn.execute("PRAGMA table_info(purchases)").fetchall()}
        if "payment_method" not in purchase_cols:
            conn.execute("ALTER TABLE purchases ADD COLUMN payment_method TEXT NOT NULL DEFAULT 'cash'")

        earnings_cols = {str(r["name"]) for r in conn.execute("PRAGMA table_info(earnings)").fetchall()}
        if "payment_method" not in earnings_cols:
            conn.execute("ALTER TABLE earnings ADD COLUMN payment_method TEXT NOT NULL DEFAULT 'cash'")

        conn.execute("CREATE INDEX IF NOT EXISTS idx_earnings_earned_on ON earnings(earned_on);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_earnings_payment_method ON earnings(payment_method);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_purchases_purchased_on ON purchases(purchased_on);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_purchases_payment_method ON purchases(payment_method);")
        conn.commit()
    finally:
        conn.close()


def create_item(input: CreateItemIn) -> Item:
    db_path = input["db_path"]
    name = (input["name"] or "").strip()
    unit = (input["unit"] or "").strip()
    description = (input.get("description") or "").strip()
    if not name:
        raise ValidationError("name is required")
    if not unit:
        raise ValidationError("unit is required")

    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    conn = _connect(db_path=db_path)
    try:
        try:
            conn.execute(
                """
                INSERT INTO items (name, unit, description, quantity_on_hand, avg_unit_cost, updated_at)
                VALUES (?, ?, ?, '0', '0', ?)
                """,
                (name, unit, description, now),
            )
        except sqlite3.IntegrityError as exc:
            raise ConflictError("item name must be unique") from exc
        conn.commit()
        item_id = int(conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])
        return get_item({"db_path": db_path, "item_id": item_id}).item
    finally:
        conn.close()


def list_items(input: ListItemsIn) -> list[Item]:
    conn = _connect(db_path=input["db_path"])
    try:
        rows = conn.execute(
            """
            SELECT id, name, unit, description, quantity_on_hand, avg_unit_cost, updated_at
            FROM items
            ORDER BY name ASC
            """
        ).fetchall()
        return [_row_to_item(row) for row in rows]
    finally:
        conn.close()


def get_item(input: GetItemIn) -> ItemDetail:
    item_id = input["item_id"]
    conn = _connect(db_path=input["db_path"])
    try:
        row = conn.execute(
            """
            SELECT id, name, unit, description, quantity_on_hand, avg_unit_cost, updated_at
            FROM items
            WHERE id = ?
            """,
            (item_id,),
        ).fetchone()
        if row is None:
            raise NotFoundError("item not found")

        purchase_rows = conn.execute(
            """
            SELECT id, item_id, quantity, unit_price, purchased_on, payment_method, created_at
            FROM purchases
            WHERE item_id = ?
            ORDER BY purchased_on DESC, id DESC
            LIMIT 50
            """,
            (item_id,),
        ).fetchall()
        usage_rows = conn.execute(
            """
            SELECT id, item_id, quantity, unit_cost, expense_amount, used_on, created_at
            FROM usages
            WHERE item_id = ?
            ORDER BY used_on DESC, id DESC
            LIMIT 50
            """,
            (item_id,),
        ).fetchall()

        return ItemDetail(
            item=_row_to_item(row),
            purchases=[_row_to_purchase(r) for r in purchase_rows],
            usages=[_row_to_usage(r) for r in usage_rows],
        )
    finally:
        conn.close()


def record_purchase(input: RecordPurchaseIn) -> None:
    item_id = input["item_id"]
    quantity = input["quantity"]
    unit_price = input["unit_price"]
    purchased_on = input["purchased_on"]
    payment_method = input["payment_method"]
    if quantity <= 0:
        raise ValidationError("quantity must be > 0")
    if unit_price < 0:
        raise ValidationError("unit_price must be >= 0")
    if payment_method not in ("cash", "online"):
        raise ValidationError("payment_method must be cash or online")

    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    conn = _connect(db_path=input["db_path"])
    try:
        item_row = conn.execute(
            "SELECT quantity_on_hand, avg_unit_cost FROM items WHERE id = ?",
            (item_id,),
        ).fetchone()
        if item_row is None:
            raise NotFoundError("item not found")

        quantity_on_hand = Decimal(item_row["quantity_on_hand"])
        avg_unit_cost = Decimal(item_row["avg_unit_cost"])

        new_qty = quantity_on_hand + quantity
        if new_qty <= 0:
            new_avg = Decimal("0")
        else:
            total_value = (quantity_on_hand * avg_unit_cost) + (quantity * unit_price)
            new_avg = total_value / new_qty

        conn.execute(
            """
            INSERT INTO purchases (item_id, quantity, unit_price, purchased_on, payment_method, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (item_id, str(quantity), str(unit_price), purchased_on.isoformat(), payment_method, now),
        )
        conn.execute(
            """
            UPDATE items
            SET quantity_on_hand = ?, avg_unit_cost = ?, updated_at = ?
            WHERE id = ?
            """,
            (str(new_qty), str(new_avg), now, item_id),
        )
        conn.commit()
    finally:
        conn.close()


def record_usage(input: RecordUsageIn) -> None:
    item_id = input["item_id"]
    quantity = input["quantity"]
    used_on = input["used_on"]
    if quantity <= 0:
        raise ValidationError("quantity must be > 0")

    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    conn = _connect(db_path=input["db_path"])
    try:
        item_row = conn.execute(
            "SELECT quantity_on_hand, avg_unit_cost FROM items WHERE id = ?",
            (item_id,),
        ).fetchone()
        if item_row is None:
            raise NotFoundError("item not found")

        quantity_on_hand = Decimal(item_row["quantity_on_hand"])
        avg_unit_cost = Decimal(item_row["avg_unit_cost"])
        if quantity > quantity_on_hand:
            raise ValidationError("not enough stock for this usage")

        new_qty = quantity_on_hand - quantity
        unit_cost = avg_unit_cost
        expense_amount = quantity * unit_cost

        conn.execute(
            """
            INSERT INTO usages (item_id, quantity, unit_cost, expense_amount, used_on, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                item_id,
                str(quantity),
                str(unit_cost),
                str(expense_amount),
                used_on.isoformat(),
                now,
            ),
        )
        conn.execute(
            """
            UPDATE items
            SET quantity_on_hand = ?, updated_at = ?
            WHERE id = ?
            """,
            (str(new_qty), now, item_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_dashboard(input: GetDashboardIn) -> Dashboard:
    items = list_items({"db_path": input["db_path"]})
    conn = _connect(db_path=input["db_path"])
    try:
        today = date.today()
        month_start = date(today.year, today.month, 1).isoformat()
        month_key = f"{today.year:04d}-{today.month:02d}"

        month_usage_row = conn.execute(
            "SELECT COALESCE(SUM(expense_amount), 0) AS total FROM usages WHERE used_on >= ?",
            (month_start,),
        ).fetchone()
        month_usage_expense = Decimal(str(month_usage_row["total"]))

        month_purchases_cash_row = conn.execute(
            """
            SELECT COALESCE(SUM(CAST(quantity AS REAL) * CAST(unit_price AS REAL)), 0) AS total
            FROM purchases
            WHERE purchased_on >= ? AND payment_method = 'cash'
            """,
            (month_start,),
        ).fetchone()
        month_purchases_online_row = conn.execute(
            """
            SELECT COALESCE(SUM(CAST(quantity AS REAL) * CAST(unit_price AS REAL)), 0) AS total
            FROM purchases
            WHERE purchased_on >= ? AND payment_method = 'online'
            """,
            (month_start,),
        ).fetchone()
        month_purchase_expense_cash = Decimal(str(month_purchases_cash_row["total"]))
        month_purchase_expense_online = Decimal(str(month_purchases_online_row["total"]))

        month_earnings_cash_row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM earnings WHERE earned_on >= ? AND payment_method = 'cash'",
            (month_start,),
        ).fetchone()
        month_earnings_online_row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM earnings WHERE earned_on >= ? AND payment_method = 'online'",
            (month_start,),
        ).fetchone()
        month_earnings_cash = Decimal(str(month_earnings_cash_row["total"]))
        month_earnings_online = Decimal(str(month_earnings_online_row["total"]))

        month_earnings_total = month_earnings_cash + month_earnings_online
        month_profit_overall = month_earnings_total - month_usage_expense
        month_profit_cash = month_earnings_cash - month_purchase_expense_cash
        month_profit_online = month_earnings_online - month_purchase_expense_online

        monthly_rows_raw = conn.execute(
            """
            WITH months AS (
              SELECT strftime('%Y-%m', earned_on) AS bucket FROM earnings
              UNION
              SELECT strftime('%Y-%m', used_on) AS bucket FROM usages
              UNION
              SELECT strftime('%Y-%m', purchased_on) AS bucket FROM purchases
            ),
            e AS (
              SELECT strftime('%Y-%m', earned_on) AS bucket,
                     SUM(CASE WHEN payment_method='cash' THEN CAST(amount AS REAL) ELSE 0 END) AS earnings_cash,
                     SUM(CASE WHEN payment_method='online' THEN CAST(amount AS REAL) ELSE 0 END) AS earnings_online,
                     SUM(CAST(amount AS REAL)) AS earnings
              FROM earnings
              GROUP BY strftime('%Y-%m', earned_on)
            ),
            u AS (
              SELECT strftime('%Y-%m', used_on) AS bucket,
                     SUM(CAST(expense_amount AS REAL)) AS usage_expense
              FROM usages
              GROUP BY strftime('%Y-%m', used_on)
            ),
            p AS (
              SELECT strftime('%Y-%m', purchased_on) AS bucket,
                     SUM(CASE WHEN payment_method='cash' THEN CAST(quantity AS REAL) * CAST(unit_price AS REAL) ELSE 0 END) AS purchases_cash,
                     SUM(CASE WHEN payment_method='online' THEN CAST(quantity AS REAL) * CAST(unit_price AS REAL) ELSE 0 END) AS purchases_online,
                     SUM(CAST(quantity AS REAL) * CAST(unit_price AS REAL)) AS purchases
              FROM purchases
              GROUP BY strftime('%Y-%m', purchased_on)
            )
            SELECT
              m.bucket AS bucket,
              COALESCE(e.earnings, 0) AS earnings,
              COALESCE(e.earnings_cash, 0) AS earnings_cash,
              COALESCE(e.earnings_online, 0) AS earnings_online,
              COALESCE(p.purchases, 0) AS purchases,
              COALESCE(p.purchases_cash, 0) AS purchases_cash,
              COALESCE(p.purchases_online, 0) AS purchases_online,
              COALESCE(u.usage_expense, 0) AS usage_expense
            FROM months m
            LEFT JOIN e ON e.bucket = m.bucket
            LEFT JOIN u ON u.bucket = m.bucket
            LEFT JOIN p ON p.bucket = m.bucket
            ORDER BY m.bucket DESC
            LIMIT 36
            """
        ).fetchall()

        monthly_rows: list[dict[str, Any]] = []
        for r in monthly_rows_raw:
            earnings = Decimal(str(r["earnings"]))
            earnings_cash = Decimal(str(r["earnings_cash"]))
            earnings_online = Decimal(str(r["earnings_online"]))
            purchases_cash = Decimal(str(r["purchases_cash"]))
            purchases_online = Decimal(str(r["purchases_online"]))
            usage_expense = Decimal(str(r["usage_expense"]))
            monthly_rows.append(
                {
                    "month": str(r["bucket"]),
                    "earnings_cash": earnings_cash,
                    "earnings_online": earnings_online,
                    "earnings_total": earnings,
                    "purchase_expense_cash": purchases_cash,
                    "purchase_expense_online": purchases_online,
                    "usage_expense": usage_expense,
                    "profit_overall": earnings - usage_expense,
                    "profit_cash": earnings_cash - purchases_cash,
                    "profit_online": earnings_online - purchases_online,
                }
            )
    finally:
        conn.close()

    total_inventory_value = sum(
        (item.quantity_on_hand * item.avg_unit_cost for item in items),
        start=Decimal("0"),
    )
    return Dashboard(
        items=items,
        total_inventory_value=total_inventory_value,
        month=month_key,
        month_usage_expense=month_usage_expense,
        month_purchase_expense_cash=month_purchase_expense_cash,
        month_purchase_expense_online=month_purchase_expense_online,
        month_earnings_cash=month_earnings_cash,
        month_earnings_online=month_earnings_online,
        month_profit_overall=month_profit_overall,
        month_profit_cash=month_profit_cash,
        month_profit_online=month_profit_online,
        monthly_rows=monthly_rows,
    )


def get_report(input: GetReportIn) -> dict[str, Any]:
    report_range = input["range"]
    if report_range not in ("daily", "monthly", "3months"):
        raise ValidationError("range must be daily, monthly, or 3months")

    conn = _connect(db_path=input["db_path"])
    try:
        earnings_where = ""
        usage_where = ""
        purchases_where = ""
        query_params: tuple[Any, ...] = ()

        if report_range == "daily":
            days_cte = """
              WITH buckets AS (
                SELECT earned_on AS bucket FROM earnings
                UNION
                SELECT used_on AS bucket FROM usages
                UNION
                SELECT purchased_on AS bucket FROM purchases
              )
            """
            earnings_group = "earned_on"
            usage_group = "used_on"
            purchases_group = "purchased_on"
            bucket_label = "Day"
            title = "Daily report"
        else:
            days_cte = """
              WITH buckets AS (
                SELECT strftime('%Y-%m', earned_on) AS bucket FROM earnings
                UNION
                SELECT strftime('%Y-%m', used_on) AS bucket FROM usages
                UNION
                SELECT strftime('%Y-%m', purchased_on) AS bucket FROM purchases
              )
            """
            earnings_group = "strftime('%Y-%m', earned_on)"
            usage_group = "strftime('%Y-%m', used_on)"
            purchases_group = "strftime('%Y-%m', purchased_on)"
            bucket_label = "Month"
            title = "Monthly report" if report_range == "monthly" else "Last 3 months report"

            if report_range == "3months":
                today = date.today()
                start_month = date(today.year, today.month, 1)
                month = start_month.month - 2
                year = start_month.year
                while month <= 0:
                    month += 12
                    year -= 1
                start_date = date(year, month, 1).isoformat()
                earnings_where = "WHERE earned_on >= ?"
                usage_where = "WHERE used_on >= ?"
                purchases_where = "WHERE purchased_on >= ?"
                query_params = (start_date, start_date, start_date)

        rows = conn.execute(
            f"""
            {days_cte},
            e AS (
              SELECT {earnings_group} AS bucket,
                     SUM(CASE WHEN payment_method='cash' THEN CAST(amount AS REAL) ELSE 0 END) AS earnings_cash,
                     SUM(CASE WHEN payment_method='online' THEN CAST(amount AS REAL) ELSE 0 END) AS earnings_online,
                     SUM(CAST(amount AS REAL)) AS earnings
              FROM earnings
              {earnings_where}
              GROUP BY {earnings_group}
            ),
            u AS (
              SELECT {usage_group} AS bucket,
                     SUM(CAST(expense_amount AS REAL)) AS usage_expense
              FROM usages
              {usage_where}
              GROUP BY {usage_group}
            ),
            p AS (
              SELECT {purchases_group} AS bucket,
                     SUM(CASE WHEN payment_method='cash' THEN CAST(quantity AS REAL) * CAST(unit_price AS REAL) ELSE 0 END) AS purchases_cash,
                     SUM(CASE WHEN payment_method='online' THEN CAST(quantity AS REAL) * CAST(unit_price AS REAL) ELSE 0 END) AS purchases_online,
                     SUM(CAST(quantity AS REAL) * CAST(unit_price AS REAL)) AS purchases
              FROM purchases
              {purchases_where}
              GROUP BY {purchases_group}
            )
            SELECT
              b.bucket AS bucket,
              COALESCE(e.earnings, 0) AS earnings,
              COALESCE(e.earnings_cash, 0) AS earnings_cash,
              COALESCE(e.earnings_online, 0) AS earnings_online,
              COALESCE(p.purchases, 0) AS purchases,
              COALESCE(p.purchases_cash, 0) AS purchases_cash,
              COALESCE(p.purchases_online, 0) AS purchases_online,
              COALESCE(u.usage_expense, 0) AS usage_expense
            FROM buckets b
            LEFT JOIN e ON e.bucket = b.bucket
            LEFT JOIN u ON u.bucket = b.bucket
            LEFT JOIN p ON p.bucket = b.bucket
            ORDER BY b.bucket DESC
            LIMIT 92
            """,
            query_params,
        ).fetchall()

        report_rows: list[dict[str, Any]] = []
        totals = {
            "earnings": Decimal("0"),
            "earnings_cash": Decimal("0"),
            "earnings_online": Decimal("0"),
            "purchases": Decimal("0"),
            "purchases_cash": Decimal("0"),
            "purchases_online": Decimal("0"),
            "usage_expense": Decimal("0"),
        }

        for r in rows:
            earnings = Decimal(str(r["earnings"]))
            earnings_cash = Decimal(str(r["earnings_cash"]))
            earnings_online = Decimal(str(r["earnings_online"]))
            purchases = Decimal(str(r["purchases"]))
            purchases_cash = Decimal(str(r["purchases_cash"]))
            purchases_online = Decimal(str(r["purchases_online"]))
            usage_expense = Decimal(str(r["usage_expense"]))

            report_rows.append(
                {
                    "bucket": str(r["bucket"]),
                    "earnings": earnings,
                    "earnings_cash": earnings_cash,
                    "earnings_online": earnings_online,
                    "purchases": purchases,
                    "purchases_cash": purchases_cash,
                    "purchases_online": purchases_online,
                    "usage_expense": usage_expense,
                    "profit_overall": earnings - usage_expense,
                    "profit_cash": earnings_cash - purchases_cash,
                    "profit_online": earnings_online - purchases_online,
                }
            )

            totals["earnings"] += earnings
            totals["earnings_cash"] += earnings_cash
            totals["earnings_online"] += earnings_online
            totals["purchases"] += purchases
            totals["purchases_cash"] += purchases_cash
            totals["purchases_online"] += purchases_online
            totals["usage_expense"] += usage_expense

        totals_out = {
            **totals,
            "profit_overall": totals["earnings"] - totals["usage_expense"],
            "profit_cash": totals["earnings_cash"] - totals["purchases_cash"],
            "profit_online": totals["earnings_online"] - totals["purchases_online"],
        }

        return {
            "title": title,
            "bucket_label": bucket_label,
            "rows": report_rows,
            "totals": totals_out,
        }
    finally:
        conn.close()


def _row_to_item(row: sqlite3.Row) -> Item:
    return Item(
        id=int(row["id"]),
        name=str(row["name"]),
        unit=str(row["unit"]),
        description=str(row["description"] or ""),
        quantity_on_hand=Decimal(row["quantity_on_hand"]),
        avg_unit_cost=Decimal(row["avg_unit_cost"]),
        updated_at=str(row["updated_at"]),
    )


def _row_to_purchase(row: sqlite3.Row) -> Purchase:
    return Purchase(
        id=int(row["id"]),
        item_id=int(row["item_id"]),
        quantity=Decimal(row["quantity"]),
        unit_price=Decimal(row["unit_price"]),
        purchased_on=str(row["purchased_on"]),
        payment_method=str(row["payment_method"] or "cash"),
        created_at=str(row["created_at"]),
    )


def _row_to_usage(row: sqlite3.Row) -> Usage:
    return Usage(
        id=int(row["id"]),
        item_id=int(row["item_id"]),
        quantity=Decimal(row["quantity"]),
        unit_cost=Decimal(row["unit_cost"]),
        expense_amount=Decimal(row["expense_amount"]),
        used_on=str(row["used_on"]),
        created_at=str(row["created_at"]),
    )


def record_earning(input: RecordEarningIn) -> None:
    amount = input["amount"]
    earned_on = input["earned_on"]
    payment_method = input["payment_method"]
    if amount <= 0:
        raise ValidationError("earning amount must be > 0")
    if payment_method not in ("cash", "online"):
        raise ValidationError("payment_method must be cash or online")

    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    conn = _connect(db_path=input["db_path"])
    try:
        conn.execute(
            """
            INSERT INTO earnings (amount, earned_on, payment_method, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (str(amount), earned_on.isoformat(), payment_method, now),
        )
        conn.commit()
    finally:
        conn.close()


def list_earnings(input: ListEarningsIn) -> list[Earning]:
    limit = int(input["limit"])
    if limit <= 0 or limit > 200:
        raise ValidationError("limit must be between 1 and 200")
    conn = _connect(db_path=input["db_path"])
    try:
        rows = conn.execute(
            """
            SELECT id, amount, earned_on, payment_method, created_at
            FROM earnings
            ORDER BY earned_on DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [
            Earning(
                id=int(r["id"]),
                amount=Decimal(r["amount"]),
                earned_on=str(r["earned_on"]),
                payment_method=str(r["payment_method"] or "cash"),
                created_at=str(r["created_at"]),
            )
            for r in rows
        ]
    finally:
        conn.close()


def update_earning(input: UpdateEarningIn) -> None:
    earning_id = int(input["earning_id"])
    amount = input["amount"]
    earned_on = input["earned_on"]
    payment_method = input["payment_method"]
    if amount <= 0:
        raise ValidationError("earning amount must be > 0")
    if payment_method not in ("cash", "online"):
        raise ValidationError("payment_method must be cash or online")

    conn = _connect(db_path=input["db_path"])
    try:
        row = conn.execute("SELECT id FROM earnings WHERE id = ?", (earning_id,)).fetchone()
        if row is None:
            raise NotFoundError("earning not found")
        conn.execute(
            """
            UPDATE earnings
            SET amount = ?, earned_on = ?, payment_method = ?
            WHERE id = ?
            """,
            (str(amount), earned_on.isoformat(), payment_method, earning_id),
        )
        conn.commit()
    finally:
        conn.close()


def delete_earning(input: DeleteEarningIn) -> None:
    earning_id = int(input["earning_id"])
    conn = _connect(db_path=input["db_path"])
    try:
        row = conn.execute("SELECT id FROM earnings WHERE id = ?", (earning_id,)).fetchone()
        if row is None:
            raise NotFoundError("earning not found")
        conn.execute("DELETE FROM earnings WHERE id = ?", (earning_id,))
        conn.commit()
    finally:
        conn.close()


def delete_item(input: DeleteItemIn) -> None:
    conn = _connect(db_path=input["db_path"])
    try:
        row = conn.execute("SELECT id FROM items WHERE id = ?", (input["item_id"],)).fetchone()
        if row is None:
            raise NotFoundError("item not found")
        conn.execute("DELETE FROM items WHERE id = ?", (input["item_id"],))
        conn.commit()
    finally:
        conn.close()


def delete_purchase(input: DeletePurchaseIn) -> None:
    conn = _connect(db_path=input["db_path"])
    try:
        row = conn.execute(
            "SELECT id FROM purchases WHERE id = ? AND item_id = ?",
            (input["purchase_id"], input["item_id"]),
        ).fetchone()
        if row is None:
            raise NotFoundError("purchase not found")

        conn.execute(
            "DELETE FROM purchases WHERE id = ? AND item_id = ?",
            (input["purchase_id"], input["item_id"]),
        )
        _recompute_item_state(conn=conn, item_id=input["item_id"])
        conn.commit()
    finally:
        conn.close()


def delete_usage(input: DeleteUsageIn) -> None:
    conn = _connect(db_path=input["db_path"])
    try:
        row = conn.execute(
            "SELECT id FROM usages WHERE id = ? AND item_id = ?",
            (input["usage_id"], input["item_id"]),
        ).fetchone()
        if row is None:
            raise NotFoundError("usage not found")

        conn.execute(
            "DELETE FROM usages WHERE id = ? AND item_id = ?",
            (input["usage_id"], input["item_id"]),
        )
        _recompute_item_state(conn=conn, item_id=input["item_id"])
        conn.commit()
    finally:
        conn.close()


def _recompute_item_state(*, conn: sqlite3.Connection, item_id: int) -> None:
    """
    Rebuild quantity_on_hand + avg_unit_cost from remaining purchases/usages.
    Also rewrites usages.unit_cost and usages.expense_amount so totals stay consistent.
    """
    item_row = conn.execute(
        "SELECT id FROM items WHERE id = ?",
        (item_id,),
    ).fetchone()
    if item_row is None:
        raise NotFoundError("item not found")

    purchases = conn.execute(
        """
        SELECT id, quantity, unit_price, purchased_on
        FROM purchases
        WHERE item_id = ?
        ORDER BY purchased_on ASC, id ASC
        """,
        (item_id,),
    ).fetchall()
    usages = conn.execute(
        """
        SELECT id, quantity, used_on
        FROM usages
        WHERE item_id = ?
        ORDER BY used_on ASC, id ASC
        """,
        (item_id,),
    ).fetchall()

    events: list[tuple[str, str, int, Decimal, Decimal | None]] = []
    for r in purchases:
        events.append(
            ("purchase", cast(str, r["purchased_on"]), int(r["id"]), Decimal(r["quantity"]), Decimal(r["unit_price"]))
        )
    for r in usages:
        events.append(("usage", cast(str, r["used_on"]), int(r["id"]), Decimal(r["quantity"]), None))

    events.sort(key=lambda e: (e[1], e[2], 0 if e[0] == "purchase" else 1))

    quantity_on_hand = Decimal("0")
    avg_unit_cost = Decimal("0")
    usage_updates: list[tuple[str, str, int]] = []

    for event_type, event_date, event_id, quantity, unit_price in events:
        if event_type == "purchase":
            if quantity <= 0:
                raise ValidationError("invalid purchase quantity while recomputing")
            if unit_price is None or unit_price < 0:
                raise ValidationError("invalid purchase unit price while recomputing")

            new_qty = quantity_on_hand + quantity
            if new_qty <= 0:
                avg_unit_cost = Decimal("0")
                quantity_on_hand = Decimal("0")
            else:
                total_value = (quantity_on_hand * avg_unit_cost) + (quantity * unit_price)
                avg_unit_cost = total_value / new_qty
                quantity_on_hand = new_qty
            continue

        # usage
        if quantity <= 0:
            raise ValidationError("invalid usage quantity while recomputing")
        if quantity > quantity_on_hand:
            raise ValidationError(
                "cannot delete this record because it would make stock go negative at some point"
            )
        quantity_on_hand = quantity_on_hand - quantity
        unit_cost = avg_unit_cost
        expense_amount = quantity * unit_cost
        usage_updates.append((str(unit_cost), str(expense_amount), event_id))

    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    conn.executemany(
        "UPDATE usages SET unit_cost = ?, expense_amount = ? WHERE id = ? AND item_id = ?",
        [(u, e, usage_id, item_id) for (u, e, usage_id) in usage_updates],
    )
    conn.execute(
        """
        UPDATE items
        SET quantity_on_hand = ?, avg_unit_cost = ?, updated_at = ?
        WHERE id = ?
        """,
        (str(quantity_on_hand), str(avg_unit_cost), now, item_id),
    )

