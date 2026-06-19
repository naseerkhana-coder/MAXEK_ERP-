"""Sub-contractor billing — employee-wise detail bill and payment abstract."""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from typing import Any

from accounts_service import _safe_float

MODULE_ID = "subcontractor_billing"
RECORD_TABLE = "subcontractor_bills"
BILL_STATUSES = ("Draft", "Final", "Paid")


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


def ensure_subcontractor_billing_schema(db) -> None:
    db.execute("""
        CREATE TABLE IF NOT EXISTS subcontractor_bills(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_number TEXT UNIQUE NOT NULL,
            invoice_no TEXT,
            subcontractor_id INTEGER NOT NULL,
            project_id INTEGER,
            period_from TEXT,
            period_to TEXT,
            bill_date TEXT,
            payment_cycle TEXT DEFAULT '15 Days Cycle',
            report_status TEXT DEFAULT 'Final Report',
            old_mess_amount REAL DEFAULT 0,
            mess_deduction REAL DEFAULT 0,
            advance_deduction REAL DEFAULT 0,
            tds_percent REAL DEFAULT 1,
            tds_amount REAL DEFAULT 0,
            gross_amount REAL DEFAULT 0,
            net_payment REAL DEFAULT 0,
            declaration_text TEXT,
            prepared_by TEXT,
            approved_by TEXT,
            bill_status TEXT DEFAULT 'Draft',
            approval_status TEXT DEFAULT 'Pending Checker',
            created_by TEXT,
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(subcontractor_id) REFERENCES subcontractors(id),
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    """)
    for col, ctype in (
        ("bill_number", "TEXT"), ("invoice_no", "TEXT"), ("subcontractor_id", "INTEGER"),
        ("project_id", "INTEGER"), ("period_from", "TEXT"), ("period_to", "TEXT"),
        ("bill_date", "TEXT"), ("payment_cycle", "TEXT"), ("report_status", "TEXT"),
        ("old_mess_amount", "REAL DEFAULT 0"), ("mess_deduction", "REAL DEFAULT 0"),
        ("advance_deduction", "REAL DEFAULT 0"), ("tds_percent", "REAL DEFAULT 1"),
        ("tds_amount", "REAL DEFAULT 0"), ("gross_amount", "REAL DEFAULT 0"),
        ("net_payment", "REAL DEFAULT 0"), ("declaration_text", "TEXT"),
        ("prepared_by", "TEXT"), ("approved_by", "TEXT"),
        ("bill_status", "TEXT DEFAULT 'Draft'"), ("approval_status", "TEXT DEFAULT 'Pending Checker'"),
        ("created_by", "TEXT"), ("created_at", "TEXT"), ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "subcontractor_bills", col, ctype)

    db.execute("""
        CREATE TABLE IF NOT EXISTS subcontractor_bill_lines(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_id INTEGER NOT NULL,
            line_no INTEGER DEFAULT 1,
            worker_id INTEGER,
            worker_code TEXT,
            worker_name TEXT,
            designation TEXT,
            days_worked REAL DEFAULT 0,
            salary_amount REAL DEFAULT 0,
            ot_hours REAL DEFAULT 0,
            ot_amount REAL DEFAULT 0,
            total_amount REAL DEFAULT 0,
            remarks TEXT,
            FOREIGN KEY(bill_id) REFERENCES subcontractor_bills(id) ON DELETE CASCADE,
            FOREIGN KEY(worker_id) REFERENCES workers(id)
        )
    """)
    for col, ctype in (
        ("bill_id", "INTEGER"), ("line_no", "INTEGER DEFAULT 1"), ("worker_id", "INTEGER"),
        ("worker_code", "TEXT"), ("worker_name", "TEXT"), ("designation", "TEXT"),
        ("days_worked", "REAL DEFAULT 0"), ("salary_amount", "REAL DEFAULT 0"),
        ("ot_hours", "REAL DEFAULT 0"), ("ot_amount", "REAL DEFAULT 0"),
        ("total_amount", "REAL DEFAULT 0"), ("remarks", "TEXT"),
    ):
        _ensure_column(db, "subcontractor_bill_lines", col, ctype)


def _next_bill_number(db) -> str:
    year = datetime.now().strftime("%Y")
    row = db.execute(
        "SELECT bill_number FROM subcontractor_bills WHERE bill_number LIKE ? ORDER BY id DESC LIMIT 1",
        (f"SUB-{year}-%",),
    ).fetchone()
    seq = 1
    if row and row[0]:
        m = re.search(r"-(\d+)$", str(row[0]))
        if m:
            seq = int(m.group(1)) + 1
    return f"SUB-{year}-{seq:04d}"


def _next_invoice_no(db, subcontractor_code: str = "SUB") -> str:
    prefix = f"MAX/SUB/{subcontractor_code}/"
    row = db.execute(
        "SELECT invoice_no FROM subcontractor_bills WHERE invoice_no LIKE ? ORDER BY id DESC LIMIT 1",
        (f"{prefix}%",),
    ).fetchone()
    seq = 1
    if row and row[0]:
        m = re.search(r"/(\d+)$", str(row[0]))
        if m:
            seq = int(m.group(1)) + 1
    return f"{prefix}{seq:03d}"


def _parse_lines_from_form(form) -> list[dict[str, Any]]:
    worker_ids = form.getlist("line_worker_id[]")
    codes = form.getlist("line_worker_code[]")
    names = form.getlist("line_worker_name[]")
    designations = form.getlist("line_designation[]")
    days_list = form.getlist("line_days[]")
    salaries = form.getlist("line_salary[]")
    ot_hrs = form.getlist("line_ot_hours[]")
    ot_amounts = form.getlist("line_ot_amount[]")
    remarks = form.getlist("line_remarks[]")

    lines: list[dict[str, Any]] = []
    count = max(len(names), len(codes), 1)
    for idx in range(count):
        name = (names[idx] if idx < len(names) else "").strip()
        if not name:
            continue
        salary = _safe_float(salaries[idx] if idx < len(salaries) else 0)
        ot_amt = _safe_float(ot_amounts[idx] if idx < len(ot_amounts) else 0)
        try:
            worker_id = int(worker_ids[idx]) if idx < len(worker_ids) and worker_ids[idx] else None
        except ValueError:
            worker_id = None
        lines.append({
            "worker_id": worker_id,
            "worker_code": codes[idx] if idx < len(codes) else "",
            "worker_name": name,
            "designation": designations[idx] if idx < len(designations) else "",
            "days_worked": _safe_float(days_list[idx] if idx < len(days_list) else 0),
            "salary_amount": salary,
            "ot_hours": _safe_float(ot_hrs[idx] if idx < len(ot_hrs) else 0),
            "ot_amount": ot_amt,
            "total_amount": _round2(salary + ot_amt),
            "remarks": remarks[idx] if idx < len(remarks) else "",
        })
    return lines


def compute_designation_summary(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"designation": "", "days_worked": 0.0, "ot_hours": 0.0, "total_amount": 0.0}
    )
    for line in lines:
        des = (line.get("designation") or "Other").strip().upper()
        grouped[des]["designation"] = des
        grouped[des]["days_worked"] += _safe_float(line.get("days_worked"))
        grouped[des]["ot_hours"] += _safe_float(line.get("ot_hours"))
        grouped[des]["total_amount"] += _safe_float(line.get("total_amount"))
    summary = []
    for item in grouped.values():
        days = item["days_worked"]
        total = _round2(item["total_amount"])
        rate = _round2(total / days) if days else 0
        summary.append({
            "designation": item["designation"],
            "mandays": _round2(days),
            "ot_hours": _round2(item["ot_hours"]),
            "calculated_rate": rate,
            "total_amount": total,
        })
    summary.sort(key=lambda x: x["designation"])
    return summary


def calculate_bill_totals(
    lines: list[dict[str, Any]],
    old_mess: float,
    mess: float,
    advance: float,
    tds_percent: float,
) -> dict[str, float]:
    line_total = _round2(sum(_safe_float(l.get("total_amount")) for l in lines))
    gross = _round2(line_total + old_mess)
    tds = _round2(gross * tds_percent / 100)
    net = _round2(gross - tds - mess - advance)
    return {
        "gross_amount": gross,
        "line_total": line_total,
        "tds_amount": tds,
        "net_payment": net,
    }


def save_subcontractor_bill(db, form, username: str, bill_id: int | None = None) -> int:
    subcontractor_id = int(form.get("subcontractor_id") or 0)
    if not subcontractor_id:
        raise ValueError("Sub-contractor is required.")

    sub = db.execute(
        "SELECT subcontractor_name, subcontractor_code FROM subcontractors WHERE id=?",
        (subcontractor_id,),
    ).fetchone()
    if not sub:
        raise ValueError("Sub-contractor not found.")

    lines = _parse_lines_from_form(form)
    if not lines:
        raise ValueError("Add at least one worker line.")

    old_mess = _safe_float(form.get("old_mess_amount"))
    mess = _safe_float(form.get("mess_deduction"))
    advance = _safe_float(form.get("advance_deduction"))
    tds_percent = _safe_float(form.get("tds_percent")) or 1.0
    totals = calculate_bill_totals(lines, old_mess, mess, advance, tds_percent)
    now = _now_ts()

    header = {
        "project_id": int(form["project_id"]) if form.get("project_id") else None,
        "period_from": (form.get("period_from") or "").strip(),
        "period_to": (form.get("period_to") or "").strip(),
        "bill_date": (form.get("bill_date") or _today()).strip(),
        "payment_cycle": (form.get("payment_cycle") or "15 Days Cycle").strip(),
        "report_status": (form.get("report_status") or "Final Report").strip(),
        "old_mess_amount": old_mess,
        "mess_deduction": mess,
        "advance_deduction": advance,
        "tds_percent": tds_percent,
        "tds_amount": totals["tds_amount"],
        "gross_amount": totals["gross_amount"],
        "net_payment": totals["net_payment"],
        "declaration_text": (form.get("declaration_text") or "").strip(),
        "prepared_by": (form.get("prepared_by") or "Maxek ENG").strip(),
        "approved_by": (form.get("approved_by") or "Maxek GM").strip(),
    }

    if bill_id:
        db.execute(
            """
            UPDATE subcontractor_bills SET
                subcontractor_id=?, project_id=?, period_from=?, period_to=?, bill_date=?,
                payment_cycle=?, report_status=?, old_mess_amount=?, mess_deduction=?,
                advance_deduction=?, tds_percent=?, tds_amount=?, gross_amount=?, net_payment=?,
                declaration_text=?, prepared_by=?, approved_by=?, modified_at=?
            WHERE id=?
            """,
            (
                subcontractor_id, header["project_id"], header["period_from"], header["period_to"],
                header["bill_date"], header["payment_cycle"], header["report_status"],
                header["old_mess_amount"], header["mess_deduction"], header["advance_deduction"],
                header["tds_percent"], header["tds_amount"], header["gross_amount"],
                header["net_payment"], header["declaration_text"], header["prepared_by"],
                header["approved_by"], now, bill_id,
            ),
        )
    else:
        bill_number = _next_bill_number(db)
        sub_code = (sub["subcontractor_code"] or sub["subcontractor_name"] or "SUB")[:6].upper()
        invoice_no = (form.get("invoice_no") or "").strip() or _next_invoice_no(db, sub_code)
        db.execute(
            """
            INSERT INTO subcontractor_bills(
                bill_number, invoice_no, subcontractor_id, project_id,
                period_from, period_to, bill_date, payment_cycle, report_status,
                old_mess_amount, mess_deduction, advance_deduction,
                tds_percent, tds_amount, gross_amount, net_payment,
                declaration_text, prepared_by, approved_by,
                bill_status, approval_status, created_by, created_at, modified_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                bill_number, invoice_no, subcontractor_id, header["project_id"],
                header["period_from"], header["period_to"], header["bill_date"],
                header["payment_cycle"], header["report_status"],
                header["old_mess_amount"], header["mess_deduction"], header["advance_deduction"],
                header["tds_percent"], header["tds_amount"], header["gross_amount"],
                header["net_payment"], header["declaration_text"], header["prepared_by"],
                header["approved_by"], "Draft", "Pending Checker", username, now, now,
            ),
        )
        bill_id = int(db.execute("SELECT last_insert_rowid()").fetchone()[0])

    db.execute("DELETE FROM subcontractor_bill_lines WHERE bill_id=?", (bill_id,))
    for idx, line in enumerate(lines, start=1):
        db.execute(
            """
            INSERT INTO subcontractor_bill_lines(
                bill_id, line_no, worker_id, worker_code, worker_name, designation,
                days_worked, salary_amount, ot_hours, ot_amount, total_amount, remarks
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                bill_id, idx, line.get("worker_id"), line.get("worker_code"),
                line.get("worker_name"), line.get("designation"),
                line.get("days_worked"), line.get("salary_amount"),
                line.get("ot_hours"), line.get("ot_amount"), line.get("total_amount"),
                line.get("remarks"),
            ),
        )
    return bill_id


def get_subcontractor_bill(db, bill_id: int) -> dict[str, Any] | None:
    row = db.execute(
        """
        SELECT b.*, s.subcontractor_name, s.subcontractor_code, s.company_name,
               p.project_name, p.project_code
        FROM subcontractor_bills b
        JOIN subcontractors s ON b.subcontractor_id = s.id
        LEFT JOIN projects p ON b.project_id = p.id
        WHERE b.id=?
        """,
        (bill_id,),
    ).fetchone()
    if not row:
        return None
    data = dict(row)
    lines = db.execute(
        "SELECT * FROM subcontractor_bill_lines WHERE bill_id=? ORDER BY line_no, id",
        (bill_id,),
    ).fetchall()
    data["lines"] = [dict(l) for l in lines]
    data["designation_summary"] = compute_designation_summary(data["lines"])
    data["line_total"] = _round2(sum(_safe_float(l.get("total_amount")) for l in data["lines"]))
    return data


def list_subcontractor_bills(
    db, search: str = "", subcontractor_id: int | None = None
) -> list[dict[str, Any]]:
    clauses = ["1=1"]
    params: list[Any] = []
    if search:
        clauses.append(
            "(b.bill_number LIKE ? OR b.invoice_no LIKE ? OR s.subcontractor_name LIKE ?)"
        )
        like = f"%{search}%"
        params.extend([like, like, like])
    if subcontractor_id:
        clauses.append("b.subcontractor_id=?")
        params.append(subcontractor_id)
    sql = f"""
        SELECT b.*, s.subcontractor_name, s.subcontractor_code
        FROM subcontractor_bills b
        JOIN subcontractors s ON b.subcontractor_id = s.id
        WHERE {' AND '.join(clauses)}
        ORDER BY b.bill_date DESC, b.id DESC
    """
    return [dict(r) for r in db.execute(sql, params).fetchall()]


def list_subcontractors_for_billing(db) -> list[dict[str, Any]]:
    rows = db.execute(
        "SELECT id, subcontractor_name, subcontractor_code, company_name "
        "FROM subcontractors WHERE status IS NULL OR status='Active' "
        "ORDER BY subcontractor_name"
    ).fetchall()
    return [dict(r) for r in rows]


def list_workers_for_sub_bill(db, subcontractor_id: int) -> list[dict[str, Any]]:
    rows = db.execute(
        """
        SELECT id, worker_code, worker_name, designation, salary_amount
        FROM workers
        WHERE subcontractor_id=? AND (status IS NULL OR status='Active')
        ORDER BY worker_name
        """,
        (subcontractor_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def import_worker_lines_template(db, subcontractor_id: int) -> list[dict[str, Any]]:
    """Starter lines from active workers under sub — manual days/OT entry still required."""
    lines = []
    for w in list_workers_for_sub_bill(db, subcontractor_id):
        lines.append({
            "worker_id": w["id"],
            "worker_code": w.get("worker_code") or "",
            "worker_name": w.get("worker_name") or "",
            "designation": w.get("designation") or "",
            "days_worked": 0,
            "salary_amount": 0,
            "ot_hours": 0,
            "ot_amount": 0,
            "total_amount": 0,
            "remarks": "",
        })
    return lines


def delete_subcontractor_bill(db, bill_id: int) -> None:
    db.execute("DELETE FROM subcontractor_bill_lines WHERE bill_id=?", (bill_id,))
    db.execute("DELETE FROM subcontractor_bills WHERE id=?", (bill_id,))


DEFAULT_DECLARATION = (
    "I hereby declare and confirm that the worker mandays, overtime hours, and final billing "
    "metrics detailed above accurately represent the actual deployments executed at site for "
    "the specified billing period. I accept the Net Payable Amount as final settlement for this cycle."
)
