"""Client Billing (RA Bills) — Phase B. Read-only links to DPR measurements and BOQ items."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from accounts_service import _safe_float

MODULE_ID = "client_billing"
RECORD_TABLE = "client_bills"

BILL_STATUSES = ("Draft", "Pending", "Certified", "Paid", "Outstanding")
EXTRA_LINE_TYPES = ("Extra Item", "Variation Item", "Non-BOQ Item")
ATTACHMENT_TYPES = (
    "RA Bill PDF",
    "Measurement Sheet",
    "DPR Copy",
    "Site Photos",
    "Supporting Document",
)
MAX_BILLING_UPLOAD_BYTES = 10 * 1024 * 1024
BILLING_ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx", ".xls", ".xlsx"}


def _table_exists(db, table: str) -> bool:
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _ensure_column(db, table: str, column: str, col_type: str) -> None:
    if not _table_exists(db, table):
        return
    try:
        cols = [row[1] for row in db.execute(f"PRAGMA table_info({table})").fetchall()]
        if column not in cols:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
    except Exception:
        pass


def _now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _round2(value: float) -> float:
    return round(float(value or 0), 2)


def ensure_client_billing_schema(db) -> None:
    """Idempotent client billing tables (Phase B)."""
    db.execute("""
        CREATE TABLE IF NOT EXISTS client_bills(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_number TEXT UNIQUE NOT NULL,
            ra_number TEXT,
            project_id INTEGER NOT NULL,
            client_id INTEGER,
            period_from TEXT,
            period_to TEXT,
            bill_date TEXT,
            remarks TEXT,
            subtotal_boq REAL DEFAULT 0,
            subtotal_extra REAL DEFAULT 0,
            gross_amount REAL DEFAULT 0,
            retention_percent REAL DEFAULT 0,
            retention_amount REAL DEFAULT 0,
            recovery_amount REAL DEFAULT 0,
            mobilization_recovery REAL DEFAULT 0,
            water_charges REAL DEFAULT 0,
            electricity_charges REAL DEFAULT 0,
            penalty_amount REAL DEFAULT 0,
            other_recovery REAL DEFAULT 0,
            total_deductions REAL DEFAULT 0,
            taxable_amount REAL DEFAULT 0,
            gst_percent REAL DEFAULT 0,
            gst_amount REAL DEFAULT 0,
            tds_percent REAL DEFAULT 0,
            tds_amount REAL DEFAULT 0,
            other_tax_amount REAL DEFAULT 0,
            net_payable REAL DEFAULT 0,
            bill_status TEXT DEFAULT 'Draft',
            paid_amount REAL DEFAULT 0,
            paid_at TEXT,
            certified_at TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            created_by TEXT,
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id),
            FOREIGN KEY(client_id) REFERENCES clients(id)
        )
    """)
    for col, ctype in (
        ("bill_number", "TEXT"), ("ra_number", "TEXT"), ("project_id", "INTEGER"),
        ("client_id", "INTEGER"), ("period_from", "TEXT"), ("period_to", "TEXT"),
        ("bill_date", "TEXT"), ("remarks", "TEXT"),
        ("subtotal_boq", "REAL DEFAULT 0"), ("subtotal_extra", "REAL DEFAULT 0"),
        ("gross_amount", "REAL DEFAULT 0"),
        ("retention_percent", "REAL DEFAULT 0"), ("retention_amount", "REAL DEFAULT 0"),
        ("recovery_amount", "REAL DEFAULT 0"), ("mobilization_recovery", "REAL DEFAULT 0"),
        ("water_charges", "REAL DEFAULT 0"), ("electricity_charges", "REAL DEFAULT 0"),
        ("penalty_amount", "REAL DEFAULT 0"), ("other_recovery", "REAL DEFAULT 0"),
        ("total_deductions", "REAL DEFAULT 0"), ("taxable_amount", "REAL DEFAULT 0"),
        ("gst_percent", "REAL DEFAULT 0"), ("gst_amount", "REAL DEFAULT 0"),
        ("tds_percent", "REAL DEFAULT 0"), ("tds_amount", "REAL DEFAULT 0"),
        ("other_tax_amount", "REAL DEFAULT 0"), ("net_payable", "REAL DEFAULT 0"),
        ("bill_status", "TEXT DEFAULT 'Draft'"), ("paid_amount", "REAL DEFAULT 0"),
        ("paid_at", "TEXT"), ("certified_at", "TEXT"),
        ("approval_status", "TEXT DEFAULT 'Pending Checker'"),
        ("created_by", "TEXT"), ("created_at", "TEXT"), ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "client_bills", col, ctype)

    db.execute("""
        CREATE TABLE IF NOT EXISTS client_bill_lines(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_bill_id INTEGER NOT NULL,
            line_no INTEGER DEFAULT 1,
            boq_item_id INTEGER,
            boq_number TEXT,
            boq_description TEXT,
            unit TEXT,
            boq_contract_qty REAL DEFAULT 0,
            previous_qty REAL DEFAULT 0,
            current_qty REAL DEFAULT 0,
            cumulative_qty REAL DEFAULT 0,
            balance_qty REAL DEFAULT 0,
            executed_qty REAL DEFAULT 0,
            rate REAL DEFAULT 0,
            amount REAL DEFAULT 0,
            dpr_measurement_ids TEXT,
            remarks TEXT,
            FOREIGN KEY(client_bill_id) REFERENCES client_bills(id) ON DELETE CASCADE,
            FOREIGN KEY(boq_item_id) REFERENCES boq_items(id)
        )
    """)
    for col, ctype in (
        ("client_bill_id", "INTEGER"), ("line_no", "INTEGER DEFAULT 1"),
        ("boq_item_id", "INTEGER"), ("boq_number", "TEXT"), ("boq_description", "TEXT"),
        ("unit", "TEXT"), ("boq_contract_qty", "REAL DEFAULT 0"),
        ("previous_qty", "REAL DEFAULT 0"), ("current_qty", "REAL DEFAULT 0"),
        ("cumulative_qty", "REAL DEFAULT 0"), ("balance_qty", "REAL DEFAULT 0"),
        ("executed_qty", "REAL DEFAULT 0"), ("rate", "REAL DEFAULT 0"),
        ("amount", "REAL DEFAULT 0"), ("dpr_measurement_ids", "TEXT"), ("remarks", "TEXT"),
    ):
        _ensure_column(db, "client_bill_lines", col, ctype)

    db.execute("""
        CREATE TABLE IF NOT EXISTS client_bill_extra_lines(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_bill_id INTEGER NOT NULL,
            line_type TEXT,
            description TEXT,
            unit TEXT,
            quantity REAL DEFAULT 0,
            rate REAL DEFAULT 0,
            amount REAL DEFAULT 0,
            remarks TEXT,
            FOREIGN KEY(client_bill_id) REFERENCES client_bills(id) ON DELETE CASCADE
        )
    """)
    for col, ctype in (
        ("client_bill_id", "INTEGER"), ("line_type", "TEXT"), ("description", "TEXT"),
        ("unit", "TEXT"), ("quantity", "REAL DEFAULT 0"), ("rate", "REAL DEFAULT 0"),
        ("amount", "REAL DEFAULT 0"), ("remarks", "TEXT"),
    ):
        _ensure_column(db, "client_bill_extra_lines", col, ctype)

    db.execute("""
        CREATE TABLE IF NOT EXISTS client_bill_deductions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_bill_id INTEGER NOT NULL,
            deduction_type TEXT,
            description TEXT,
            percent_value REAL DEFAULT 0,
            amount REAL DEFAULT 0,
            FOREIGN KEY(client_bill_id) REFERENCES client_bills(id) ON DELETE CASCADE
        )
    """)
    for col, ctype in (
        ("client_bill_id", "INTEGER"), ("deduction_type", "TEXT"),
        ("description", "TEXT"), ("percent_value", "REAL DEFAULT 0"), ("amount", "REAL DEFAULT 0"),
    ):
        _ensure_column(db, "client_bill_deductions", col, ctype)

    db.execute("""
        CREATE TABLE IF NOT EXISTS client_bill_attachments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_bill_id INTEGER NOT NULL,
            attachment_type TEXT,
            stored_filename TEXT,
            original_filename TEXT,
            uploaded_by TEXT,
            uploaded_at TEXT,
            FOREIGN KEY(client_bill_id) REFERENCES client_bills(id) ON DELETE CASCADE
        )
    """)
    for col, ctype in (
        ("client_bill_id", "INTEGER"), ("attachment_type", "TEXT"),
        ("stored_filename", "TEXT"), ("original_filename", "TEXT"),
        ("uploaded_by", "TEXT"), ("uploaded_at", "TEXT"),
    ):
        _ensure_column(db, "client_bill_attachments", col, ctype)


def _next_bill_number(db) -> str:
    year = datetime.now().strftime("%Y")
    base = f"RA-{year}-"
    if not _table_exists(db, "client_bills"):
        return f"{base}0001"
    row = db.execute(
        "SELECT bill_number FROM client_bills WHERE bill_number LIKE ? ORDER BY id DESC LIMIT 1",
        (f"{base}%",),
    ).fetchone()
    seq = 1
    if row and row[0]:
        m = re.search(r"-(\d+)$", str(row[0]))
        if m:
            seq = int(m.group(1)) + 1
    return f"{base}{seq:04d}"


def _billed_dpr_measurement_ids(db, exclude_bill_id: int | None = None) -> set[int]:
    """DPR measurement IDs already linked to certified (approved) client bills."""
    if not _table_exists(db, "client_bill_lines"):
        return set()
    sql = """
        SELECT l.dpr_measurement_ids
        FROM client_bill_lines l
        JOIN client_bills b ON l.client_bill_id = b.id
        WHERE b.approval_status = 'Approved'
    """
    params: list[Any] = []
    if exclude_bill_id:
        sql += " AND b.id != ?"
        params.append(exclude_bill_id)
    ids: set[int] = set()
    for row in db.execute(sql, params).fetchall():
        raw = row[0]
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                for item in parsed:
                    try:
                        ids.add(int(item))
                    except (TypeError, ValueError):
                        pass
        except (json.JSONDecodeError, TypeError):
            pass
    return ids


def get_previous_certified_qty(
    db, project_id: int, boq_item_id: int, exclude_bill_id: int | None = None
) -> float:
    if not _table_exists(db, "client_bill_lines"):
        return 0.0
    sql = """
        SELECT COALESCE(SUM(l.executed_qty), 0) AS qty
        FROM client_bill_lines l
        JOIN client_bills b ON l.client_bill_id = b.id
        WHERE b.project_id = ? AND l.boq_item_id = ? AND b.approval_status = 'Approved'
    """
    params: list[Any] = [project_id, boq_item_id]
    if exclude_bill_id:
        sql += " AND b.id != ?"
        params.append(exclude_bill_id)
    row = db.execute(sql, params).fetchone()
    return float(row[0] if row else 0)


def _get_boq_item(db, boq_item_id: int) -> dict[str, Any] | None:
    row = db.execute(
        "SELECT id, project_id, item_code, item_description, quantity, unit, rate, amount "
        "FROM boq_items WHERE id=? AND COALESCE(is_deleted, 0)=0",
        (boq_item_id,),
    ).fetchone()
    return dict(row) if row else None


def import_dpr_measurements(
    db,
    project_id: int,
    period_from: str,
    period_to: str,
    exclude_bill_id: int | None = None,
) -> list[dict[str, Any]]:
    """
    Read-only import from dpr_measurements + boq_items.
    Aggregates by BOQ item for the billing period; previous qty from prior certified bills.
    """
    if not period_from or not period_to:
        raise ValueError("Billing period from/to dates are required.")
    if period_from > period_to:
        raise ValueError("Period From cannot be after Period To.")

    already_billed = _billed_dpr_measurement_ids(db, exclude_bill_id)
    rows = db.execute(
        """
        SELECT m.id, m.boq_item_id, m.boq_number, m.boq_description, m.unit,
               m.calculated_quantity, m.report_date
        FROM dpr_measurements m
        WHERE m.project_id = ?
          AND m.report_date >= ? AND m.report_date <= ?
          AND m.bill_client = 1
          AND COALESCE(m.dpr_status, 'submitted') != 'draft'
        ORDER BY m.boq_item_id, m.report_date, m.id
        """,
        (project_id, period_from, period_to),
    ).fetchall()

    grouped: dict[int, dict[str, Any]] = {}
    for row in rows:
        r = dict(row)
        mid = int(r["id"])
        if mid in already_billed:
            continue
        boq_item_id = r.get("boq_item_id")
        if not boq_item_id:
            continue
        boq_item_id = int(boq_item_id)
        if boq_item_id not in grouped:
            boq = _get_boq_item(db, boq_item_id) or {}
            boq_no = r.get("boq_number") or boq.get("item_code") or ""
            grouped[boq_item_id] = {
                "boq_item_id": boq_item_id,
                "boq_number": boq_no,
                "boq_description": r.get("boq_description") or boq.get("item_description") or "",
                "unit": r.get("unit") or boq.get("unit") or "",
                "boq_contract_qty": _safe_float(boq.get("quantity")),
                "rate": _safe_float(boq.get("rate")),
                "current_qty": 0.0,
                "dpr_measurement_ids": [],
            }
        qty = _safe_float(r.get("calculated_quantity"))
        grouped[boq_item_id]["current_qty"] += qty
        grouped[boq_item_id]["dpr_measurement_ids"].append(mid)

    lines: list[dict[str, Any]] = []
    for boq_item_id, item in grouped.items():
        previous = get_previous_certified_qty(db, project_id, boq_item_id, exclude_bill_id)
        current = _round2(item["current_qty"])
        cumulative = _round2(previous + current)
        contract = _round2(item["boq_contract_qty"])
        balance = _round2(max(contract - cumulative, 0))
        executed = current
        rate = _round2(item["rate"])
        lines.append({
            "boq_item_id": boq_item_id,
            "boq_number": item["boq_number"],
            "boq_description": item["boq_description"],
            "unit": item["unit"],
            "boq_contract_qty": contract,
            "previous_qty": _round2(previous),
            "current_qty": current,
            "cumulative_qty": cumulative,
            "balance_qty": balance,
            "executed_qty": executed,
            "rate": rate,
            "amount": _round2(executed * rate),
            "dpr_measurement_ids": item["dpr_measurement_ids"],
            "remarks": "",
        })
    lines.sort(key=lambda x: (x.get("boq_number") or "", x.get("boq_item_id") or 0))
    return lines


def _parse_lines_from_form(form) -> list[dict[str, Any]]:
    boq_item_ids = form.getlist("line_boq_item_id[]")
    boq_numbers = form.getlist("line_boq_number[]")
    descriptions = form.getlist("line_boq_description[]")
    units = form.getlist("line_unit[]")
    contract_qtys = form.getlist("line_contract_qty[]")
    previous_qtys = form.getlist("line_previous_qty[]")
    current_qtys = form.getlist("line_current_qty[]")
    cumulative_qtys = form.getlist("line_cumulative_qty[]")
    balance_qtys = form.getlist("line_balance_qty[]")
    executed_qtys = form.getlist("line_executed_qty[]")
    rates = form.getlist("line_rate[]")
    dpr_ids_json = form.getlist("line_dpr_ids[]")
    remarks = form.getlist("line_remarks[]")

    lines: list[dict[str, Any]] = []
    count = max(
        len(boq_item_ids), len(executed_qtys), len(rates), len(boq_numbers), 1
    )
    for idx in range(count):
        executed = _safe_float(executed_qtys[idx] if idx < len(executed_qtys) else 0)
        rate = _safe_float(rates[idx] if idx < len(rates) else 0)
        if executed <= 0 and rate <= 0:
            continue
        boq_item_raw = boq_item_ids[idx] if idx < len(boq_item_ids) else ""
        try:
            boq_item_id = int(boq_item_raw) if boq_item_raw else None
        except ValueError:
            boq_item_id = None
        dpr_ids: list[int] = []
        if idx < len(dpr_ids_json) and dpr_ids_json[idx]:
            try:
                parsed = json.loads(dpr_ids_json[idx])
                if isinstance(parsed, list):
                    dpr_ids = [int(x) for x in parsed]
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
        lines.append({
            "boq_item_id": boq_item_id,
            "boq_number": boq_numbers[idx] if idx < len(boq_numbers) else "",
            "boq_description": descriptions[idx] if idx < len(descriptions) else "",
            "unit": units[idx] if idx < len(units) else "",
            "boq_contract_qty": _safe_float(contract_qtys[idx] if idx < len(contract_qtys) else 0),
            "previous_qty": _safe_float(previous_qtys[idx] if idx < len(previous_qtys) else 0),
            "current_qty": _safe_float(current_qtys[idx] if idx < len(current_qtys) else 0),
            "cumulative_qty": _safe_float(cumulative_qtys[idx] if idx < len(cumulative_qtys) else 0),
            "balance_qty": _safe_float(balance_qtys[idx] if idx < len(balance_qtys) else 0),
            "executed_qty": executed,
            "rate": rate,
            "amount": _round2(executed * rate),
            "dpr_measurement_ids": dpr_ids,
            "remarks": remarks[idx] if idx < len(remarks) else "",
        })
    return lines


def _parse_extra_lines_from_form(form) -> list[dict[str, Any]]:
    types = form.getlist("extra_type[]")
    descriptions = form.getlist("extra_description[]")
    units = form.getlist("extra_unit[]")
    quantities = form.getlist("extra_qty[]")
    rates = form.getlist("extra_rate[]")
    remarks = form.getlist("extra_remarks[]")
    lines: list[dict[str, Any]] = []
    for idx in range(len(descriptions)):
        desc = (descriptions[idx] or "").strip()
        if not desc:
            continue
        qty = _safe_float(quantities[idx] if idx < len(quantities) else 0)
        rate = _safe_float(rates[idx] if idx < len(rates) else 0)
        lines.append({
            "line_type": types[idx] if idx < len(types) else "Extra Item",
            "description": desc,
            "unit": units[idx] if idx < len(units) else "",
            "quantity": qty,
            "rate": rate,
            "amount": _round2(qty * rate),
            "remarks": remarks[idx] if idx < len(remarks) else "",
        })
    return lines


def calculate_bill_totals(header: dict[str, Any], lines: list[dict], extras: list[dict]) -> dict[str, float]:
    subtotal_boq = _round2(sum(_safe_float(l.get("amount")) for l in lines))
    subtotal_extra = _round2(sum(_safe_float(e.get("amount")) for e in extras))
    gross = _round2(subtotal_boq + subtotal_extra)

    retention_pct = _safe_float(header.get("retention_percent"))
    retention_amt = _round2(gross * retention_pct / 100) if retention_pct else _safe_float(header.get("retention_amount"))
    recovery = _safe_float(header.get("recovery_amount"))
    mobilization = _safe_float(header.get("mobilization_recovery"))
    water = _safe_float(header.get("water_charges"))
    electricity = _safe_float(header.get("electricity_charges"))
    penalty = _safe_float(header.get("penalty_amount"))
    other_rec = _safe_float(header.get("other_recovery"))
    total_deductions = _round2(
        retention_amt + recovery + mobilization + water + electricity + penalty + other_rec
    )
    taxable = _round2(max(gross - total_deductions, 0))
    gst_pct = _safe_float(header.get("gst_percent"))
    gst_amt = _round2(taxable * gst_pct / 100) if gst_pct else _safe_float(header.get("gst_amount"))
    tds_pct = _safe_float(header.get("tds_percent"))
    tds_amt = _round2(taxable * tds_pct / 100) if tds_pct else _safe_float(header.get("tds_amount"))
    other_tax = _safe_float(header.get("other_tax_amount"))
    net = _round2(taxable + gst_amt - tds_amt - other_tax)
    return {
        "subtotal_boq": subtotal_boq,
        "subtotal_extra": subtotal_extra,
        "gross_amount": gross,
        "retention_amount": retention_amt,
        "total_deductions": total_deductions,
        "taxable_amount": taxable,
        "gst_amount": gst_amt,
        "tds_amount": tds_amt,
        "net_payable": net,
    }


def _header_from_form(form) -> dict[str, Any]:
    return {
        "project_id": int(form.get("project_id") or 0),
        "client_id": int(form["client_id"]) if form.get("client_id") else None,
        "period_from": (form.get("period_from") or "").strip(),
        "period_to": (form.get("period_to") or "").strip(),
        "bill_date": (form.get("bill_date") or _today()).strip(),
        "ra_number": (form.get("ra_number") or "").strip(),
        "remarks": (form.get("remarks") or "").strip(),
        "retention_percent": _safe_float(form.get("retention_percent")),
        "retention_amount": _safe_float(form.get("retention_amount")),
        "recovery_amount": _safe_float(form.get("recovery_amount")),
        "mobilization_recovery": _safe_float(form.get("mobilization_recovery")),
        "water_charges": _safe_float(form.get("water_charges")),
        "electricity_charges": _safe_float(form.get("electricity_charges")),
        "penalty_amount": _safe_float(form.get("penalty_amount")),
        "other_recovery": _safe_float(form.get("other_recovery")),
        "gst_percent": _safe_float(form.get("gst_percent")),
        "gst_amount": _safe_float(form.get("gst_amount")),
        "tds_percent": _safe_float(form.get("tds_percent")),
        "tds_amount": _safe_float(form.get("tds_amount")),
        "other_tax_amount": _safe_float(form.get("other_tax_amount")),
    }


def _save_lines(db, bill_id: int, lines: list[dict[str, Any]]) -> None:
    db.execute("DELETE FROM client_bill_lines WHERE client_bill_id=?", (bill_id,))
    for idx, line in enumerate(lines, start=1):
        db.execute(
            """
            INSERT INTO client_bill_lines(
                client_bill_id, line_no, boq_item_id, boq_number, boq_description, unit,
                boq_contract_qty, previous_qty, current_qty, cumulative_qty, balance_qty,
                executed_qty, rate, amount, dpr_measurement_ids, remarks
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                bill_id, idx, line.get("boq_item_id"), line.get("boq_number"),
                line.get("boq_description"), line.get("unit"),
                line.get("boq_contract_qty"), line.get("previous_qty"), line.get("current_qty"),
                line.get("cumulative_qty"), line.get("balance_qty"),
                line.get("executed_qty"), line.get("rate"), line.get("amount"),
                json.dumps(line.get("dpr_measurement_ids") or []),
                line.get("remarks"),
            ),
        )


def _save_extra_lines(db, bill_id: int, extras: list[dict[str, Any]]) -> None:
    db.execute("DELETE FROM client_bill_extra_lines WHERE client_bill_id=?", (bill_id,))
    for extra in extras:
        db.execute(
            """
            INSERT INTO client_bill_extra_lines(
                client_bill_id, line_type, description, unit, quantity, rate, amount, remarks
            ) VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                bill_id, extra.get("line_type"), extra.get("description"), extra.get("unit"),
                extra.get("quantity"), extra.get("rate"), extra.get("amount"), extra.get("remarks"),
            ),
        )


def save_client_bill(db, form, username: str, bill_id: int | None = None) -> int:
    header = _header_from_form(form)
    if not header["project_id"]:
        raise ValueError("Project is required.")
    if not header["period_from"] or not header["period_to"]:
        raise ValueError("Billing period is required.")

    lines = _parse_lines_from_form(form)
    extras = _parse_extra_lines_from_form(form)
    if not lines and not extras:
        raise ValueError("Add at least one BOQ line or extra item.")

    totals = calculate_bill_totals(header, lines, extras)
    now = _now_ts()

    if bill_id:
        existing = db.execute("SELECT id FROM client_bills WHERE id=?", (bill_id,)).fetchone()
        if not existing:
            raise ValueError("Client bill not found.")
        db.execute(
            """
            UPDATE client_bills SET
                project_id=?, client_id=?, period_from=?, period_to=?, bill_date=?,
                ra_number=?, remarks=?,
                subtotal_boq=?, subtotal_extra=?, gross_amount=?,
                retention_percent=?, retention_amount=?, recovery_amount=?,
                mobilization_recovery=?, water_charges=?, electricity_charges=?,
                penalty_amount=?, other_recovery=?, total_deductions=?,
                taxable_amount=?, gst_percent=?, gst_amount=?,
                tds_percent=?, tds_amount=?, other_tax_amount=?, net_payable=?,
                modified_at=?
            WHERE id=?
            """,
            (
                header["project_id"], header["client_id"], header["period_from"],
                header["period_to"], header["bill_date"], header["ra_number"], header["remarks"],
                totals["subtotal_boq"], totals["subtotal_extra"], totals["gross_amount"],
                header["retention_percent"], totals["retention_amount"], header["recovery_amount"],
                header["mobilization_recovery"], header["water_charges"], header["electricity_charges"],
                header["penalty_amount"], header["other_recovery"], totals["total_deductions"],
                totals["taxable_amount"], header["gst_percent"], totals["gst_amount"],
                header["tds_percent"], totals["tds_amount"], header["other_tax_amount"],
                totals["net_payable"], now, bill_id,
            ),
        )
    else:
        bill_number = _next_bill_number(db)
        db.execute(
            """
            INSERT INTO client_bills(
                bill_number, ra_number, project_id, client_id, period_from, period_to, bill_date,
                remarks, subtotal_boq, subtotal_extra, gross_amount,
                retention_percent, retention_amount, recovery_amount, mobilization_recovery,
                water_charges, electricity_charges, penalty_amount, other_recovery,
                total_deductions, taxable_amount, gst_percent, gst_amount,
                tds_percent, tds_amount, other_tax_amount, net_payable,
                bill_status, approval_status, created_by, created_at, modified_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                bill_number, header["ra_number"], header["project_id"], header["client_id"],
                header["period_from"], header["period_to"], header["bill_date"], header["remarks"],
                totals["subtotal_boq"], totals["subtotal_extra"], totals["gross_amount"],
                header["retention_percent"], totals["retention_amount"], header["recovery_amount"],
                header["mobilization_recovery"], header["water_charges"], header["electricity_charges"],
                header["penalty_amount"], header["other_recovery"], totals["total_deductions"],
                totals["taxable_amount"], header["gst_percent"], totals["gst_amount"],
                header["tds_percent"], totals["tds_amount"], header["other_tax_amount"],
                totals["net_payable"], "Pending", "Pending Checker", username, now, now,
            ),
        )
        bill_id = int(db.execute("SELECT last_insert_rowid()").fetchone()[0])

    _save_lines(db, bill_id, lines)
    _save_extra_lines(db, bill_id, extras)
    return bill_id


def get_client_bill(db, bill_id: int) -> dict[str, Any] | None:
    row = db.execute(
        """
        SELECT b.*, p.project_code, p.project_name, p.private_client_name,
               p.work_order_number, p.work_order_date,
               c.company_name, c.client_name, c.gst_number, c.address AS client_address,
               c.pan_number AS client_pan, c.mobile AS client_phone
        FROM client_bills b
        LEFT JOIN projects p ON b.project_id = p.id
        LEFT JOIN clients c ON b.client_id = c.id
        WHERE b.id=?
        """,
        (bill_id,),
    ).fetchone()
    if not row:
        return None
    bill = dict(row)
    bill["client_display"] = (
        bill.get("company_name") or bill.get("client_name") or bill.get("private_client_name") or ""
    )
    lines = db.execute(
        "SELECT * FROM client_bill_lines WHERE client_bill_id=? ORDER BY line_no, id",
        (bill_id,),
    ).fetchall()
    bill["lines"] = []
    for line in lines:
        ld = dict(line)
        try:
            ld["dpr_measurement_ids"] = json.loads(ld.get("dpr_measurement_ids") or "[]")
        except (json.JSONDecodeError, TypeError):
            ld["dpr_measurement_ids"] = []
        bill["lines"].append(ld)
    bill["extra_lines"] = [
        dict(r) for r in db.execute(
            "SELECT * FROM client_bill_extra_lines WHERE client_bill_id=? ORDER BY id",
            (bill_id,),
        ).fetchall()
    ]
    bill["attachments"] = [
        dict(r) for r in db.execute(
            "SELECT * FROM client_bill_attachments WHERE client_bill_id=? ORDER BY id",
            (bill_id,),
        ).fetchall()
    ]
    return bill


def list_client_bills(db, search: str = "", project_id: int | None = None) -> list[dict[str, Any]]:
    clauses = ["1=1"]
    params: list[Any] = []
    if search:
        clauses.append(
            "(b.bill_number LIKE ? OR b.ra_number LIKE ? OR p.project_name LIKE ? OR p.project_code LIKE ?)"
        )
        like = f"%{search}%"
        params.extend([like, like, like, like])
    if project_id:
        clauses.append("b.project_id=?")
        params.append(project_id)
    sql = f"""
        SELECT b.*, p.project_code, p.project_name,
               c.company_name, c.client_name, p.private_client_name
        FROM client_bills b
        LEFT JOIN projects p ON b.project_id = p.id
        LEFT JOIN clients c ON b.client_id = c.id
        WHERE {' AND '.join(clauses)}
        ORDER BY b.bill_date DESC, b.id DESC
    """
    rows = db.execute(sql, params).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["client_display"] = (
            item.get("company_name") or item.get("client_name") or item.get("private_client_name") or ""
        )
        result.append(item)
    return result


def delete_client_bill(db, bill_id: int) -> None:
    db.execute("DELETE FROM client_bill_attachments WHERE client_bill_id=?", (bill_id,))
    db.execute("DELETE FROM client_bill_extra_lines WHERE client_bill_id=?", (bill_id,))
    db.execute("DELETE FROM client_bill_lines WHERE client_bill_id=?", (bill_id,))
    db.execute("DELETE FROM client_bill_deductions WHERE client_bill_id=?", (bill_id,))
    db.execute("DELETE FROM client_bills WHERE id=?", (bill_id,))


def save_bill_attachment(
    db, bill_id: int, attachment_type: str, stored_filename: str,
    original_filename: str, username: str,
) -> int:
    db.execute(
        """
        INSERT INTO client_bill_attachments(
            client_bill_id, attachment_type, stored_filename, original_filename, uploaded_by, uploaded_at
        ) VALUES(?,?,?,?,?,?)
        """,
        (bill_id, attachment_type, stored_filename, original_filename, username, _now_ts()),
    )
    return int(db.execute("SELECT last_insert_rowid()").fetchone()[0])


def delete_bill_attachment(db, attachment_id: int) -> str | None:
    row = db.execute(
        "SELECT stored_filename FROM client_bill_attachments WHERE id=?",
        (attachment_id,),
    ).fetchone()
    if not row:
        return None
    db.execute("DELETE FROM client_bill_attachments WHERE id=?", (attachment_id,))
    return row["stored_filename"]


def mark_bill_paid(db, bill_id: int, paid_amount: float | None = None) -> None:
    bill = db.execute(
        "SELECT net_payable, paid_amount FROM client_bills WHERE id=?",
        (bill_id,),
    ).fetchone()
    if not bill:
        raise ValueError("Bill not found.")
    net = _safe_float(bill["net_payable"])
    amount = _round2(paid_amount if paid_amount is not None else net)
    status = "Paid" if amount >= net else "Outstanding"
    db.execute(
        "UPDATE client_bills SET paid_amount=?, paid_at=?, bill_status=? WHERE id=?",
        (amount, _now_ts(), status, bill_id),
    )


def on_bill_certified(db, bill_id: int) -> None:
    """When workflow approves — mark certified and link DPR measurements as billed (read source only)."""
    now = _now_ts()
    db.execute(
        "UPDATE client_bills SET bill_status='Certified', certified_at=?, approval_status='Approved' WHERE id=?",
        (now, bill_id),
    )
    if not _table_exists(db, "dpr_measurements"):
        return
    lines = db.execute(
        "SELECT dpr_measurement_ids FROM client_bill_lines WHERE client_bill_id=?",
        (bill_id,),
    ).fetchall()
    for row in lines:
        raw = row[0]
        if not raw:
            continue
        try:
            ids = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(ids, list):
            continue
        for mid in ids:
            try:
                db.execute(
                    "UPDATE dpr_measurements SET billing_status='billed' WHERE id=?",
                    (int(mid),),
                )
            except Exception:
                pass


def list_billing_reports(
    db, report_type: str = "register", project_id: int | None = None, client_id: int | None = None
) -> list[dict[str, Any]]:
    clauses = ["1=1"]
    params: list[Any] = []
    if project_id:
        clauses.append("b.project_id=?")
        params.append(project_id)
    if client_id:
        clauses.append("b.client_id=?")
        params.append(client_id)

    if report_type == "pending":
        clauses.append("b.approval_status IN ('Pending Checker', 'Pending Approval')")
    elif report_type == "certified":
        clauses.append("b.approval_status='Approved' AND b.bill_status='Certified'")
    elif report_type == "paid":
        clauses.append("b.bill_status='Paid'")
    elif report_type == "outstanding":
        clauses.append(
            "(b.bill_status IN ('Certified', 'Outstanding') OR "
            "(b.approval_status='Approved' AND COALESCE(b.paid_amount,0) < COALESCE(b.net_payable,0)))"
        )

    sql = f"""
        SELECT b.*, p.project_code, p.project_name,
               c.company_name, c.client_name, p.private_client_name
        FROM client_bills b
        LEFT JOIN projects p ON b.project_id = p.id
        LEFT JOIN clients c ON b.client_id = c.id
        WHERE {' AND '.join(clauses)}
        ORDER BY b.bill_date DESC, b.id DESC
    """
    rows = db.execute(sql, params).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        net = _safe_float(item.get("net_payable"))
        paid = _safe_float(item.get("paid_amount"))
        item["outstanding_amount"] = _round2(max(net - paid, 0))
        item["client_display"] = (
            item.get("company_name") or item.get("client_name") or item.get("private_client_name") or ""
        )
        result.append(item)
    return result


def client_ledger_rows(db, client_id: int | None = None, project_id: int | None = None) -> list[dict[str, Any]]:
    """Simple client ledger from certified/paid bills."""
    clauses = ["b.approval_status='Approved'"]
    params: list[Any] = []
    if client_id:
        clauses.append("b.client_id=?")
        params.append(client_id)
    if project_id:
        clauses.append("b.project_id=?")
        params.append(project_id)
    sql = f"""
        SELECT b.bill_date, b.bill_number, b.ra_number, b.net_payable, b.paid_amount,
               b.bill_status, p.project_name,
               c.company_name, c.client_name, p.private_client_name
        FROM client_bills b
        LEFT JOIN projects p ON b.project_id = p.id
        LEFT JOIN clients c ON b.client_id = c.id
        WHERE {' AND '.join(clauses)}
        ORDER BY b.bill_date, b.id
    """
    rows = db.execute(sql, params).fetchall()
    ledger = []
    balance = 0.0
    for row in rows:
        item = dict(row)
        debit = _safe_float(item.get("net_payable"))
        credit = _safe_float(item.get("paid_amount"))
        balance = _round2(balance + debit - credit)
        item["debit"] = debit
        item["credit"] = credit
        item["balance"] = balance
        item["client_display"] = (
            item.get("company_name") or item.get("client_name") or item.get("private_client_name") or ""
        )
        ledger.append(item)
    return ledger


def list_projects_for_billing(db) -> list[dict[str, Any]]:
    rows = db.execute(
        "SELECT id, project_code, project_name, client_id, private_client_name "
        "FROM projects WHERE status IS NULL OR status != 'Inactive' "
        "ORDER BY project_name"
    ).fetchall()
    return [dict(r) for r in rows]


def list_clients_for_billing(db) -> list[dict[str, Any]]:
    rows = db.execute(
        "SELECT id, company_name, client_name FROM clients ORDER BY company_name, client_name"
    ).fetchall()
    return [dict(r) for r in rows]


def project_client_info(db, project_id: int) -> dict[str, Any]:
    row = db.execute(
        """
        SELECT p.id, p.client_id, p.private_client_name,
               c.company_name, c.client_name, c.gst_number, c.address
        FROM projects p
        LEFT JOIN clients c ON p.client_id = c.id
        WHERE p.id=?
        """,
        (project_id,),
    ).fetchone()
    if not row:
        return {}
    data = dict(row)
    data["client_display"] = (
        data.get("company_name") or data.get("client_name") or data.get("private_client_name") or ""
    )
    return data


def enrich_bill_for_print(bill: dict[str, Any]) -> dict[str, Any]:
    """Add computed RA bill print fields without changing billing logic."""
    lines = []
    current_total = 0.0
    upto_total = 0.0
    for line in bill.get("lines") or []:
        rate = _safe_float(line.get("rate"))
        prev = _safe_float(line.get("previous_qty"))
        current = _safe_float(line.get("current_qty") or line.get("executed_qty"))
        cumulative = _safe_float(line.get("cumulative_qty"))
        upto_amt = _round2(cumulative * rate)
        current_amt = _round2(current * rate)
        enriched = dict(line)
        enriched["upto_date_qty"] = cumulative
        enriched["upto_date_amount"] = upto_amt
        enriched["current_bill_qty"] = current
        enriched["current_bill_amount"] = current_amt or _safe_float(line.get("amount"))
        enriched["wo_qty"] = _safe_float(line.get("boq_contract_qty"))
        lines.append(enriched)
        current_total += enriched["current_bill_amount"]
        upto_total += upto_amt
    bill = dict(bill)
    bill["lines"] = lines
    bill["current_bill_total"] = _round2(current_total)
    bill["upto_date_bill_total"] = _round2(upto_total)
    bill["total_work_done"] = _round2(bill.get("taxable_amount") or bill.get("gross_amount") or current_total)
    bill["total_hold_amount"] = _round2(bill.get("retention_amount") or 0)
    bill["upto_date_deduction"] = _round2(bill.get("total_deductions") or 0)
    return bill


def get_company_bank_for_print(db) -> dict[str, str]:
    """MAXEK bank block for RA bill footer — app_settings override with template defaults."""
    defaults = {
        "account_name": "MAXEK PRIVATE LIMITED",
        "account_no": "120037548492",
        "ifsc": "CNRB0002968",
        "bank_branch": "Canara Bank, Pattoor Branch, Thiruvananthapuram",
    }
    if not _table_exists(db, "app_settings"):
        return defaults
    keys = {
        "billing_bank_account_name": "account_name",
        "billing_bank_account_no": "account_no",
        "billing_bank_ifsc": "ifsc",
        "billing_bank_branch": "bank_branch",
    }
    result = dict(defaults)
    for setting_key, field in keys.items():
        row = db.execute(
            "SELECT setting_value FROM app_settings WHERE setting_key=?",
            (setting_key,),
        ).fetchone()
        if row and row[0]:
            result[field] = str(row[0])
    return result
