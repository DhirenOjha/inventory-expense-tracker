from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

import os
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.storage import (
    create_item,
    delete_item,
    delete_purchase,
    delete_usage,
    delete_earning,
    ensure_schema,
    ConflictError,
    get_dashboard,
    get_item,
    get_report,
    list_earnings,
    list_items,
    NotFoundError,
    record_earning,
    record_purchase,
    record_usage,
    update_earning,
    ValidationError,
)
from app.types import Money, Quantity

import io
from openpyxl import Workbook

APP_DIR = Path(__file__).resolve().parent
DEFAULT_PROJECT_DIR = APP_DIR.parent
PROJECT_DIR = Path(os.environ.get("INVENTORY_BASE_DIR", str(DEFAULT_PROJECT_DIR))).resolve()
DATA_DIR = Path(os.environ.get("INVENTORY_DATA_DIR", str(PROJECT_DIR / "data"))).resolve()
DB_PATH = Path(os.environ.get("INVENTORY_DB_PATH", str(DATA_DIR / "app.db"))).resolve()

templates = Jinja2Templates(directory=str(PROJECT_DIR / "templates"))

app = FastAPI(title="Inventory + Expense Tracker")
app.mount("/static", StaticFiles(directory=str(PROJECT_DIR / "static")), name="static")


def _render(request: Request, name: str, context: dict[str, Any], status_code: int = 200) -> Any:
    """Render a Jinja page. Compatible with FastAPI 0.99 (Android/Chaquopy) and newer."""
    payload = {"request": request, **context}
    try:
        return templates.TemplateResponse(
            request=request, name=name, context=payload, status_code=status_code
        )
    except TypeError:
        return templates.TemplateResponse(name, payload, status_code=status_code)


@app.on_event("startup")
def _startup() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ensure_schema({"db_path": DB_PATH})


@app.exception_handler(NotFoundError)
def _handle_not_found(request: Request, exc: NotFoundError) -> HTMLResponse:
    return _render(request, "error.html", {"status_code": 404, "message": str(exc)}, status_code=404)


@app.exception_handler(ValidationError)
def _handle_validation(request: Request, exc: ValidationError) -> HTMLResponse:
    return _render(request, "error.html", {"status_code": 400, "message": str(exc)}, status_code=400)


@app.exception_handler(ConflictError)
def _handle_conflict(request: Request, exc: ConflictError) -> HTMLResponse:
    return _render(request, "error.html", {"status_code": 409, "message": str(exc)}, status_code=409)


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> Any:
    dashboard = get_dashboard({"db_path": DB_PATH})
    return _render(request, "dashboard.html", {"dashboard": dashboard})


@app.get("/reports", response_class=HTMLResponse)
def reports(request: Request, range: str = "daily") -> Any:
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    report_core = get_report({"db_path": DB_PATH, "range": range})  # type: ignore[arg-type]
    report = {
        **report_core,
        "generated_at": now,
        "table_title": "Summary",
    }

    html = templates.get_template("report.html").render({"request": request, "report": report})
    filename = f"report_{range}_{date.today().isoformat()}.html"
    return HTMLResponse(
        content=html,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        status_code=200,
    )


@app.get("/reports.xlsx")
def reports_xlsx(range: str = "daily") -> StreamingResponse:
    report = get_report({"db_path": DB_PATH, "range": range})  # type: ignore[arg-type]

    wb = Workbook()
    ws_summary = wb.active
    ws_summary.title = "Summary"
    ws_summary.append(["Title", report["title"]])
    ws_summary.append(["Generated (UTC)", datetime.utcnow().isoformat(timespec="seconds") + "Z"])
    ws_summary.append([])

    totals = report["totals"]
    ws_summary.append(["Overall"])
    ws_summary.append(["Earnings", str(totals["earnings"])])
    ws_summary.append(["Purchases", str(totals["purchases"])])
    ws_summary.append(["Usage expense", str(totals["usage_expense"])])
    ws_summary.append(["Profit (overall)", str(totals["profit_overall"])])
    ws_summary.append([])
    ws_summary.append(["Cash vs Online"])
    ws_summary.append(["Earnings (cash)", str(totals["earnings_cash"])])
    ws_summary.append(["Earnings (online)", str(totals["earnings_online"])])
    ws_summary.append(["Purchases (cash)", str(totals["purchases_cash"])])
    ws_summary.append(["Purchases (online)", str(totals["purchases_online"])])
    ws_summary.append(["Profit (cash)", str(totals["profit_cash"])])
    ws_summary.append(["Profit (online)", str(totals["profit_online"])])

    ws_rows = wb.create_sheet("Rows")
    ws_rows.append(
        [
            report["bucket_label"],
            "Earnings",
            "Purchases",
            "Usage expense",
            "Profit (overall)",
            "Earnings (cash)",
            "Earnings (online)",
            "Purchases (cash)",
            "Purchases (online)",
            "Profit (cash)",
            "Profit (online)",
        ]
    )
    for r in report["rows"]:
        ws_rows.append(
            [
                r["bucket"],
                str(r["earnings"]),
                str(r["purchases"]),
                str(r["usage_expense"]),
                str(r["profit_overall"]),
                str(r["earnings_cash"]),
                str(r["earnings_online"]),
                str(r["purchases_cash"]),
                str(r["purchases_online"]),
                str(r["profit_cash"]),
                str(r["profit_online"]),
            ]
        )

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = f"report_{range}_{date.today().isoformat()}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/items", response_class=HTMLResponse)
def items_page(request: Request) -> Any:
    items = list_items({"db_path": DB_PATH})
    return _render(request, "items.html", {"items": items})


@app.post("/items")
def items_create(
    name: str = Form(...),
    unit: str = Form(...),
    description: str = Form(""),
) -> RedirectResponse:
    create_item({"db_path": DB_PATH, "name": name, "unit": unit, "description": description})
    return RedirectResponse(url="/items", status_code=303)


@app.get("/items/{item_id}", response_class=HTMLResponse)
def item_detail(item_id: int, request: Request) -> Any:
    item = get_item({"db_path": DB_PATH, "item_id": item_id})
    return _render(request, "item_detail.html", {"item": item})


@app.post("/earnings")
def earnings_create(
    amount: str = Form(...),
    earned_on: Optional[str] = Form(None),
    payment_method: str = Form("cash"),
) -> RedirectResponse:
    money = Money(amount).value
    earned_on_date = date.fromisoformat(earned_on) if earned_on else date.today()
    record_earning(
        {"db_path": DB_PATH, "amount": money, "earned_on": earned_on_date, "payment_method": payment_method}
    )
    return RedirectResponse(url="/", status_code=303)


@app.get("/earnings", response_class=HTMLResponse)
def earnings_page(request: Request) -> Any:
    earnings = list_earnings({"db_path": DB_PATH, "limit": 100})
    return _render(request, "earnings.html", {"earnings": earnings})


@app.post("/earnings/{earning_id}/update")
def earnings_update(
    earning_id: int,
    amount: str = Form(...),
    earned_on: str = Form(...),
    payment_method: str = Form(...),
) -> RedirectResponse:
    money = Money(amount).value
    earned_on_date = date.fromisoformat(earned_on)
    update_earning(
        {
            "db_path": DB_PATH,
            "earning_id": earning_id,
            "amount": money,
            "earned_on": earned_on_date,
            "payment_method": payment_method,
        }
    )
    return RedirectResponse(url="/earnings", status_code=303)


@app.post("/earnings/{earning_id}/delete")
def earnings_delete(earning_id: int) -> RedirectResponse:
    delete_earning({"db_path": DB_PATH, "earning_id": earning_id})
    return RedirectResponse(url="/earnings", status_code=303)


@app.post("/items/{item_id}/purchase")
def item_purchase(
    item_id: int,
    quantity: str = Form(...),
    unit_price: str = Form(...),
    purchased_on: Optional[str] = Form(None),
    payment_method: str = Form("cash"),
) -> RedirectResponse:
    qty = Quantity(quantity).value
    price = Money(unit_price).value
    purchased_on_date = date.fromisoformat(purchased_on) if purchased_on else date.today()

    record_purchase(
        {
            "db_path": DB_PATH,
            "item_id": item_id,
            "quantity": qty,
            "unit_price": price,
            "purchased_on": purchased_on_date,
            "payment_method": payment_method,
        }
    )
    return RedirectResponse(url=f"/items/{item_id}", status_code=303)


@app.post("/items/{item_id}/use")
def item_use(
    item_id: int,
    quantity: str = Form(...),
    used_on: Optional[str] = Form(None),
) -> RedirectResponse:
    qty = Quantity(quantity).value
    used_on_date = date.fromisoformat(used_on) if used_on else date.today()

    record_usage(
        {
            "db_path": DB_PATH,
            "item_id": item_id,
            "quantity": qty,
            "used_on": used_on_date,
        }
    )
    return RedirectResponse(url=f"/items/{item_id}", status_code=303)


@app.post("/items/{item_id}/delete")
def item_delete(item_id: int) -> RedirectResponse:
    delete_item({"db_path": DB_PATH, "item_id": item_id})
    return RedirectResponse(url="/items", status_code=303)


@app.post("/items/{item_id}/purchases/{purchase_id}/delete")
def purchase_delete(item_id: int, purchase_id: int) -> RedirectResponse:
    delete_purchase({"db_path": DB_PATH, "item_id": item_id, "purchase_id": purchase_id})
    return RedirectResponse(url=f"/items/{item_id}", status_code=303)


@app.post("/items/{item_id}/usages/{usage_id}/delete")
def usage_delete(item_id: int, usage_id: int) -> RedirectResponse:
    delete_usage({"db_path": DB_PATH, "item_id": item_id, "usage_id": usage_id})
    return RedirectResponse(url=f"/items/{item_id}", status_code=303)

