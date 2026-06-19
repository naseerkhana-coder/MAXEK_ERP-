"""Office Administration, Document Control & Fleet Management — Phase 1 MVP."""

from __future__ import annotations

import re
from datetime import datetime, date
from typing import Any

from accounts_service import _safe_float, calc_gst_line

# --- Document Control enums ---
INWARD_MODES = ("Hand Delivery", "Courier", "Email", "Post", "Other")
OUTWARD_MODES = ("Hand Delivery", "Courier", "Email", "Post", "Other")
DOCUMENT_TYPES = ("Letter", "Invoice", "Quotation", "Agreement", "Legal", "Report", "Other")
LETTER_TYPES = (
    "Official Letter",
    "Covering Letter",
    "Demand Letter",
    "NOC",
    "Experience Letter",
    "Appointment Letter",
    "Termination Letter",
    "Other",
)
AGREEMENT_TYPES = ("Service", "Lease", "MOU", "NDA", "Subcontract", "Vendor", "Client", "Other")
LEGAL_DOC_TYPES = ("Court Order", "Affidavit", "License", "Registration", "Compliance", "Other")

# --- Fleet enums ---
VEHICLE_TYPES = ("Car", "SUV", "Truck", "Tipper", "JCB", "Mixer", "Bus", "Bike", "Other")
FUEL_TYPES = ("Diesel", "Petrol", "CNG", "Electric", "Hybrid")
VEHICLE_STATUSES = ("Active", "Idle", "Under Repair", "Sold", "Scrapped")
VEHICLE_DOC_TYPES = (
    "RC",
    "Insurance",
    "Fitness",
    "Pollution",
    "Road Tax",
    "Permit",
    "Driver License",
    "Other",
)
DIESEL_MOVEMENT_PURCHASE = "PURCHASE_IN"
DIESEL_MOVEMENT_ISSUE = "ISSUE_OUT"
EXPIRY_ALERT_DAYS = (90, 60, 30, 7)
OFFICE_ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx", ".xls", ".xlsx"}
MAX_OFFICE_UPLOAD_BYTES = 10 * 1024 * 1024


def _table_exists(db, table: str) -> bool:
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _column_exists(db, table: str, column: str) -> bool:
    if not _table_exists(db, table):
        return False
    cols = [row[1] for row in db.execute(f"PRAGMA table_info({table})").fetchall()]
    return column in cols


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


def _next_doc_number(db, prefix: str, table: str, column: str) -> str:
    today = datetime.now().strftime("%Y%m%d")
    base = f"{prefix}-{today}-"
    row = db.execute(
        f"SELECT {column} FROM {table} WHERE {column} LIKE ? ORDER BY id DESC LIMIT 1",
        (f"{base}%",),
    ).fetchone()
    seq = 1
    if row and row[0]:
        m = re.search(r"-(\d+)$", str(row[0]))
        if m:
            seq = int(m.group(1)) + 1
    return f"{base}{seq:03d}"


def _parse_date(value: str | None) -> date | None:
    if not value or not str(value).strip():
        return None
    try:
        return datetime.strptime(str(value).strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _days_until(expiry_str: str | None, today: date | None = None) -> int | None:
    exp = _parse_date(expiry_str)
    if not exp:
        return None
    ref = today or date.today()
    return (exp - ref).days


def _expiry_bucket(days_left: int | None) -> str | None:
    if days_left is None:
        return None
    if days_left < 0:
        return "overdue"
    for threshold in EXPIRY_ALERT_DAYS:
        if days_left <= threshold:
            return str(threshold)
    return None


def ensure_office_fleet_schema(db) -> None:
    """Idempotent office & fleet schema (Phase 1 MVP + Phase 2 stubs)."""
    db.execute("""
        CREATE TABLE IF NOT EXISTS office_inward(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            register_number TEXT UNIQUE NOT NULL,
            received_date TEXT,
            sender_name TEXT,
            sender_address TEXT,
            document_type TEXT,
            subject TEXT,
            reference_no TEXT,
            mode TEXT,
            received_by TEXT,
            department TEXT,
            project_id INTEGER,
            remarks TEXT,
            attachment TEXT,
            created_by TEXT,
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    """)
    for col, ctype in (
        ("register_number", "TEXT"), ("received_date", "TEXT"), ("sender_name", "TEXT"),
        ("sender_address", "TEXT"), ("document_type", "TEXT"), ("subject", "TEXT"),
        ("reference_no", "TEXT"), ("mode", "TEXT"), ("received_by", "TEXT"),
        ("department", "TEXT"), ("project_id", "INTEGER"), ("remarks", "TEXT"),
        ("attachment", "TEXT"), ("created_by", "TEXT"), ("created_at", "TEXT"),
        ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "office_inward", col, ctype)

    db.execute("""
        CREATE TABLE IF NOT EXISTS office_outward(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            register_number TEXT UNIQUE NOT NULL,
            dispatch_date TEXT,
            recipient_name TEXT,
            recipient_address TEXT,
            document_type TEXT,
            subject TEXT,
            reference_no TEXT,
            mode TEXT,
            dispatched_by TEXT,
            department TEXT,
            project_id INTEGER,
            remarks TEXT,
            attachment TEXT NOT NULL DEFAULT '',
            created_by TEXT,
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    """)
    for col, ctype in (
        ("register_number", "TEXT"), ("dispatch_date", "TEXT"), ("recipient_name", "TEXT"),
        ("recipient_address", "TEXT"), ("document_type", "TEXT"), ("subject", "TEXT"),
        ("reference_no", "TEXT"), ("mode", "TEXT"), ("dispatched_by", "TEXT"),
        ("department", "TEXT"), ("project_id", "INTEGER"), ("remarks", "TEXT"),
        ("attachment", "TEXT"), ("created_by", "TEXT"), ("created_at", "TEXT"),
        ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "office_outward", col, ctype)

    db.execute("""
        CREATE TABLE IF NOT EXISTS office_letters(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            letter_number TEXT UNIQUE NOT NULL,
            letter_type TEXT,
            letter_date TEXT,
            to_name TEXT,
            to_address TEXT,
            subject TEXT,
            body TEXT,
            reference_no TEXT,
            department TEXT,
            project_id INTEGER,
            signed_by TEXT,
            remarks TEXT,
            created_by TEXT,
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    """)
    for col, ctype in (
        ("letter_number", "TEXT"), ("letter_type", "TEXT"), ("letter_date", "TEXT"),
        ("to_name", "TEXT"), ("to_address", "TEXT"), ("subject", "TEXT"), ("body", "TEXT"),
        ("reference_no", "TEXT"), ("department", "TEXT"), ("project_id", "INTEGER"),
        ("signed_by", "TEXT"), ("remarks", "TEXT"), ("created_by", "TEXT"),
        ("created_at", "TEXT"), ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "office_letters", col, ctype)

    db.execute("""
        CREATE TABLE IF NOT EXISTS office_quotations(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quotation_number TEXT UNIQUE NOT NULL,
            quotation_date TEXT,
            client_name TEXT,
            client_address TEXT,
            client_gstin TEXT,
            client_contact TEXT,
            project_id INTEGER,
            subject TEXT,
            terms TEXT,
            validity_days INTEGER DEFAULT 30,
            tax_type TEXT DEFAULT 'CGST_SGST',
            subtotal REAL DEFAULT 0,
            total_cgst REAL DEFAULT 0,
            total_sgst REAL DEFAULT 0,
            total_igst REAL DEFAULT 0,
            grand_total REAL DEFAULT 0,
            remarks TEXT,
            created_by TEXT,
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    """)
    for col, ctype in (
        ("quotation_number", "TEXT"), ("quotation_date", "TEXT"), ("client_name", "TEXT"),
        ("client_address", "TEXT"), ("client_gstin", "TEXT"), ("client_contact", "TEXT"),
        ("project_id", "INTEGER"), ("subject", "TEXT"), ("terms", "TEXT"),
        ("validity_days", "INTEGER DEFAULT 30"), ("tax_type", "TEXT DEFAULT 'CGST_SGST'"),
        ("subtotal", "REAL DEFAULT 0"), ("total_cgst", "REAL DEFAULT 0"),
        ("total_sgst", "REAL DEFAULT 0"), ("total_igst", "REAL DEFAULT 0"),
        ("grand_total", "REAL DEFAULT 0"), ("remarks", "TEXT"), ("created_by", "TEXT"),
        ("created_at", "TEXT"), ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "office_quotations", col, ctype)

    db.execute("""
        CREATE TABLE IF NOT EXISTS office_quotation_lines(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quotation_id INTEGER NOT NULL,
            line_no INTEGER DEFAULT 1,
            description TEXT,
            quantity REAL DEFAULT 1,
            unit TEXT,
            rate REAL DEFAULT 0,
            gst_percent REAL DEFAULT 18,
            tax_type TEXT DEFAULT 'CGST_SGST',
            taxable_value REAL DEFAULT 0,
            cgst REAL DEFAULT 0,
            sgst REAL DEFAULT 0,
            igst REAL DEFAULT 0,
            line_total REAL DEFAULT 0,
            FOREIGN KEY(quotation_id) REFERENCES office_quotations(id)
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS office_agreements(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agreement_number TEXT UNIQUE NOT NULL,
            title TEXT,
            party_name TEXT,
            agreement_type TEXT,
            start_date TEXT,
            end_date TEXT,
            value REAL DEFAULT 0,
            project_id INTEGER,
            remarks TEXT,
            attachment TEXT,
            created_by TEXT,
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    """)
    for col, ctype in (
        ("agreement_number", "TEXT"), ("title", "TEXT"), ("party_name", "TEXT"),
        ("agreement_type", "TEXT"), ("start_date", "TEXT"), ("end_date", "TEXT"),
        ("value", "REAL DEFAULT 0"), ("project_id", "INTEGER"), ("remarks", "TEXT"),
        ("attachment", "TEXT"), ("created_by", "TEXT"), ("created_at", "TEXT"),
        ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "office_agreements", col, ctype)

    db.execute("""
        CREATE TABLE IF NOT EXISTS office_legal_documents(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_number TEXT UNIQUE NOT NULL,
            title TEXT,
            doc_type TEXT,
            authority TEXT,
            issue_date TEXT,
            expiry_date TEXT,
            alert_flag INTEGER DEFAULT 0,
            remarks TEXT,
            attachment TEXT,
            is_active INTEGER DEFAULT 1,
            created_by TEXT,
            created_at TEXT,
            modified_at TEXT
        )
    """)
    for col, ctype in (
        ("doc_number", "TEXT"), ("title", "TEXT"), ("doc_type", "TEXT"),
        ("authority", "TEXT"), ("issue_date", "TEXT"), ("expiry_date", "TEXT"),
        ("alert_flag", "INTEGER DEFAULT 0"), ("remarks", "TEXT"), ("attachment", "TEXT"),
        ("is_active", "INTEGER DEFAULT 1"), ("created_by", "TEXT"),
        ("created_at", "TEXT"), ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "office_legal_documents", col, ctype)

    db.execute("""
        CREATE TABLE IF NOT EXISTS fleet_vehicles(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            registration_number TEXT UNIQUE NOT NULL,
            vehicle_type TEXT,
            make TEXT,
            model TEXT,
            year INTEGER,
            fuel_type TEXT,
            capacity TEXT,
            purchase_date TEXT,
            purchase_cost REAL DEFAULT 0,
            current_status TEXT DEFAULT 'Active',
            assigned_driver TEXT,
            department TEXT,
            project_id INTEGER,
            odometer_km REAL DEFAULT 0,
            remarks TEXT,
            created_by TEXT,
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    """)
    for col, ctype in (
        ("registration_number", "TEXT"), ("vehicle_type", "TEXT"), ("make", "TEXT"),
        ("model", "TEXT"), ("year", "INTEGER"), ("fuel_type", "TEXT"), ("capacity", "TEXT"),
        ("purchase_date", "TEXT"), ("purchase_cost", "REAL DEFAULT 0"),
        ("current_status", "TEXT DEFAULT 'Active'"), ("assigned_driver", "TEXT"),
        ("department", "TEXT"), ("project_id", "INTEGER"), ("odometer_km", "REAL DEFAULT 0"),
        ("remarks", "TEXT"), ("created_by", "TEXT"), ("created_at", "TEXT"),
        ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "fleet_vehicles", col, ctype)

    db.execute("""
        CREATE TABLE IF NOT EXISTS fleet_vehicle_documents(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER NOT NULL,
            doc_type TEXT,
            doc_number TEXT,
            issue_date TEXT,
            expiry_date TEXT,
            issuer TEXT,
            attachment TEXT,
            remarks TEXT,
            created_by TEXT,
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(vehicle_id) REFERENCES fleet_vehicles(id)
        )
    """)
    for col, ctype in (
        ("vehicle_id", "INTEGER"), ("doc_type", "TEXT"), ("doc_number", "TEXT"),
        ("issue_date", "TEXT"), ("expiry_date", "TEXT"), ("issuer", "TEXT"),
        ("attachment", "TEXT"), ("remarks", "TEXT"), ("created_by", "TEXT"),
        ("created_at", "TEXT"), ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "fleet_vehicle_documents", col, ctype)

    db.execute("""
        CREATE TABLE IF NOT EXISTS fleet_running_log(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER NOT NULL,
            log_date TEXT,
            driver_name TEXT,
            start_km REAL DEFAULT 0,
            end_km REAL DEFAULT 0,
            total_km REAL DEFAULT 0,
            purpose TEXT,
            project_id INTEGER,
            fuel_liters REAL DEFAULT 0,
            remarks TEXT,
            created_by TEXT,
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(vehicle_id) REFERENCES fleet_vehicles(id),
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    """)
    for col, ctype in (
        ("vehicle_id", "INTEGER"), ("log_date", "TEXT"), ("driver_name", "TEXT"),
        ("start_km", "REAL DEFAULT 0"), ("end_km", "REAL DEFAULT 0"),
        ("total_km", "REAL DEFAULT 0"), ("purpose", "TEXT"), ("project_id", "INTEGER"),
        ("fuel_liters", "REAL DEFAULT 0"), ("remarks", "TEXT"), ("created_by", "TEXT"),
        ("created_at", "TEXT"), ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "fleet_running_log", col, ctype)

    db.execute("""
        CREATE TABLE IF NOT EXISTS diesel_purchases(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            purchase_number TEXT UNIQUE NOT NULL,
            purchase_date TEXT,
            supplier TEXT,
            quantity_liters REAL DEFAULT 0,
            rate_per_liter REAL DEFAULT 0,
            total_amount REAL DEFAULT 0,
            invoice_ref TEXT,
            remarks TEXT,
            created_by TEXT,
            created_at TEXT
        )
    """)
    for col, ctype in (
        ("purchase_number", "TEXT"), ("purchase_date", "TEXT"), ("supplier", "TEXT"),
        ("quantity_liters", "REAL DEFAULT 0"), ("rate_per_liter", "REAL DEFAULT 0"),
        ("total_amount", "REAL DEFAULT 0"), ("invoice_ref", "TEXT"), ("remarks", "TEXT"),
        ("created_by", "TEXT"), ("created_at", "TEXT"),
    ):
        _ensure_column(db, "diesel_purchases", col, ctype)

    db.execute("""
        CREATE TABLE IF NOT EXISTS diesel_issues(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_number TEXT UNIQUE NOT NULL,
            issue_date TEXT,
            vehicle_id INTEGER,
            quantity_liters REAL DEFAULT 0,
            odometer_km REAL DEFAULT 0,
            issued_to TEXT,
            project_id INTEGER,
            remarks TEXT,
            created_by TEXT,
            created_at TEXT,
            FOREIGN KEY(vehicle_id) REFERENCES fleet_vehicles(id),
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    """)
    for col, ctype in (
        ("issue_number", "TEXT"), ("issue_date", "TEXT"), ("vehicle_id", "INTEGER"),
        ("quantity_liters", "REAL DEFAULT 0"), ("odometer_km", "REAL DEFAULT 0"),
        ("issued_to", "TEXT"), ("project_id", "INTEGER"), ("remarks", "TEXT"),
        ("created_by", "TEXT"), ("created_at", "TEXT"),
    ):
        _ensure_column(db, "diesel_issues", col, ctype)

    db.execute("""
        CREATE TABLE IF NOT EXISTS diesel_ledger(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            movement_date TEXT,
            movement_type TEXT NOT NULL,
            quantity_liters REAL NOT NULL,
            reference_table TEXT,
            reference_id INTEGER,
            remarks TEXT,
            created_by TEXT,
            created_at TEXT
        )
    """)
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_diesel_ledger_ref ON diesel_ledger(reference_table, reference_id)"
    )

    # Phase 2 stubs — schema only, no UI yet
    db.execute("""
        CREATE TABLE IF NOT EXISTS fleet_service_history(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER,
            service_date TEXT,
            service_type TEXT,
            odometer_km REAL,
            cost REAL DEFAULT 0,
            vendor TEXT,
            remarks TEXT,
            created_at TEXT,
            FOREIGN KEY(vehicle_id) REFERENCES fleet_vehicles(id)
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS fleet_breakdowns(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER,
            breakdown_date TEXT,
            description TEXT,
            status TEXT DEFAULT 'Open',
            remarks TEXT,
            created_at TEXT,
            FOREIGN KEY(vehicle_id) REFERENCES fleet_vehicles(id)
        )
    """)

    db.commit()


def _count_table(db, table: str) -> int:
    if not _table_exists(db, table):
        return 0
    row = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    return int(row[0]) if row else 0


def _empty_expiry_alerts() -> dict[str, Any]:
    buckets: dict[str, list[dict]] = {str(d): [] for d in EXPIRY_ALERT_DAYS}
    return {
        "expiring": buckets,
        "expiring_overdue": [],
        "total_alerts": 0,
        "alert_days": EXPIRY_ALERT_DAYS,
    }


def _empty_office_dashboard_stats() -> dict[str, Any]:
    alerts = _empty_expiry_alerts()
    return {
        "inward_count": 0,
        "outward_count": 0,
        "letters_count": 0,
        "quotations_count": 0,
        "agreements_count": 0,
        "legal_count": 0,
        "expiry_alerts": 0,
        "expiring": alerts["expiring"],
        "expiring_overdue": alerts["expiring_overdue"],
        "alert_days": EXPIRY_ALERT_DAYS,
    }


def _empty_fleet_dashboard_stats() -> dict[str, Any]:
    alerts = _empty_expiry_alerts()
    return {
        "active_vehicles": 0,
        "total_vehicles": 0,
        "running_logs": 0,
        "diesel_stock_liters": 0.0,
        "diesel_purchases": 0,
        "diesel_issues": 0,
        "expiry_alerts": 0,
        "expiring": alerts["expiring"],
        "expiring_overdue": alerts["expiring_overdue"],
        "alert_days": EXPIRY_ALERT_DAYS,
    }


def collect_expiry_alerts(db) -> dict[str, Any]:
    """Legal docs + vehicle documents with expiry buckets."""
    try:
        today = date.today()
        buckets: dict[str, list[dict]] = {str(d): [] for d in EXPIRY_ALERT_DAYS}
        overdue: list[dict] = []

        if _table_exists(db, "office_legal_documents"):
            rows = db.execute(
                "SELECT id, doc_number, title, doc_type, expiry_date, 'legal' AS source "
                "FROM office_legal_documents WHERE is_active=1 AND expiry_date IS NOT NULL AND expiry_date != ''"
            ).fetchall()
            for row in rows:
                item = dict(row)
                days = _days_until(item.get("expiry_date"), today)
                bucket = _expiry_bucket(days)
                if bucket == "overdue":
                    item["days_left"] = days
                    overdue.append(item)
                elif bucket:
                    item["days_left"] = days
                    buckets[bucket].append(item)

        if _table_exists(db, "fleet_vehicle_documents") and _table_exists(db, "fleet_vehicles"):
            rows = db.execute(
                "SELECT d.id, d.doc_type, d.doc_number, d.expiry_date, v.registration_number, "
                "'vehicle_doc' AS source "
                "FROM fleet_vehicle_documents d "
                "JOIN fleet_vehicles v ON d.vehicle_id = v.id "
                "WHERE d.expiry_date IS NOT NULL AND d.expiry_date != ''"
            ).fetchall()
            for row in rows:
                item = dict(row)
                item["title"] = f"{item.get('doc_type')} — {item.get('registration_number')}"
                days = _days_until(item.get("expiry_date"), today)
                bucket = _expiry_bucket(days)
                if bucket == "overdue":
                    item["days_left"] = days
                    overdue.append(item)
                elif bucket:
                    item["days_left"] = days
                    buckets[bucket].append(item)

        total_alerts = len(overdue) + sum(len(buckets[str(d)]) for d in EXPIRY_ALERT_DAYS)
        return {
            "expiring": buckets,
            "expiring_overdue": overdue,
            "total_alerts": total_alerts,
            "alert_days": EXPIRY_ALERT_DAYS,
        }
    except Exception:
        return _empty_expiry_alerts()


def office_dashboard_stats(db) -> dict[str, Any]:
    try:
        alerts = collect_expiry_alerts(db)
        return {
            "inward_count": _count_table(db, "office_inward"),
            "outward_count": _count_table(db, "office_outward"),
            "letters_count": _count_table(db, "office_letters"),
            "quotations_count": _count_table(db, "office_quotations"),
            "agreements_count": _count_table(db, "office_agreements"),
            "legal_count": _count_table(db, "office_legal_documents"),
            "expiry_alerts": alerts["total_alerts"],
            "expiring": alerts["expiring"],
            "expiring_overdue": alerts["expiring_overdue"],
            "alert_days": EXPIRY_ALERT_DAYS,
        }
    except Exception:
        return _empty_office_dashboard_stats()


def fleet_dashboard_stats(db) -> dict[str, Any]:
    try:
        alerts = collect_expiry_alerts(db)
        active_vehicles = 0
        if _table_exists(db, "fleet_vehicles") and _column_exists(db, "fleet_vehicles", "current_status"):
            row = db.execute(
                "SELECT COUNT(*) FROM fleet_vehicles WHERE current_status='Active'"
            ).fetchone()
            active_vehicles = int(row[0]) if row else 0
        diesel_stock = get_diesel_stock_balance(db)
        return {
            "active_vehicles": active_vehicles,
            "total_vehicles": _count_table(db, "fleet_vehicles"),
            "running_logs": _count_table(db, "fleet_running_log"),
            "diesel_stock_liters": diesel_stock,
            "diesel_purchases": _count_table(db, "diesel_purchases"),
            "diesel_issues": _count_table(db, "diesel_issues"),
            "expiry_alerts": alerts["total_alerts"],
            "expiring": alerts["expiring"],
            "expiring_overdue": alerts["expiring_overdue"],
            "alert_days": EXPIRY_ALERT_DAYS,
        }
    except Exception:
        return _empty_fleet_dashboard_stats()


# --- Inward Register ---
def list_inward(db, search: str = "") -> list[dict]:
    if not _table_exists(db, "office_inward"):
        return []
    sql = (
        "SELECT i.*, p.project_name FROM office_inward i "
        "LEFT JOIN projects p ON i.project_id = p.id "
    )
    params: tuple = ()
    if search.strip():
        q = f"%{search.strip()}%"
        sql += (
            "WHERE i.register_number LIKE ? OR i.sender_name LIKE ? OR i.subject LIKE ? "
            "OR i.reference_no LIKE ? "
        )
        params = (q, q, q, q)
    sql += "ORDER BY i.received_date DESC, i.id DESC LIMIT 500"
    return [dict(r) for r in db.execute(sql, params).fetchall()]


def get_inward(db, record_id: int) -> dict | None:
    if not _table_exists(db, "office_inward"):
        return None
    row = db.execute(
        "SELECT i.*, p.project_name FROM office_inward i "
        "LEFT JOIN projects p ON i.project_id = p.id WHERE i.id=?",
        (record_id,),
    ).fetchone()
    return dict(row) if row else None


def save_inward(db, form, username: str, record_id: int | None = None, attachment: str | None = None) -> int:
    received_date = (form.get("received_date") or "").strip()
    sender_name = (form.get("sender_name") or "").strip()
    subject = (form.get("subject") or "").strip()
    if not received_date:
        raise ValueError("Received date is required.")
    if not sender_name:
        raise ValueError("Sender name is required.")
    if not subject:
        raise ValueError("Subject is required.")
    project_id = form.get("project_id") or None
    now = _now_ts()
    fields = (
        received_date,
        sender_name,
        (form.get("sender_address") or "").strip(),
        (form.get("document_type") or "Other").strip(),
        subject,
        (form.get("reference_no") or "").strip(),
        (form.get("mode") or "Hand Delivery").strip(),
        (form.get("received_by") or "").strip(),
        (form.get("department") or "").strip(),
        project_id,
        (form.get("remarks") or "").strip(),
    )
    if record_id:
        existing = get_inward(db, record_id)
        if not existing:
            raise ValueError("Record not found.")
        attach = attachment if attachment else existing.get("attachment")
        db.execute(
            "UPDATE office_inward SET received_date=?, sender_name=?, sender_address=?, "
            "document_type=?, subject=?, reference_no=?, mode=?, received_by=?, department=?, "
            "project_id=?, remarks=?, attachment=?, modified_at=? WHERE id=?",
            (*fields, attach, now, record_id),
        )
        return record_id
    reg_no = _next_doc_number(db, "IN", "office_inward", "register_number")
    db.execute(
        "INSERT INTO office_inward(register_number, received_date, sender_name, sender_address, "
        "document_type, subject, reference_no, mode, received_by, department, project_id, "
        "remarks, attachment, created_by, created_at, modified_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (reg_no, *fields, attachment or "", username, now, now),
    )
    return int(db.execute("SELECT last_insert_rowid()").fetchone()[0])


def delete_inward(db, record_id: int) -> None:
    db.execute("DELETE FROM office_inward WHERE id=?", (record_id,))


# --- Outward Register ---
def list_outward(db, search: str = "") -> list[dict]:
    if not _table_exists(db, "office_outward"):
        return []
    sql = (
        "SELECT o.*, p.project_name FROM office_outward o "
        "LEFT JOIN projects p ON o.project_id = p.id "
    )
    params: tuple = ()
    if search.strip():
        q = f"%{search.strip()}%"
        sql += (
            "WHERE o.register_number LIKE ? OR o.recipient_name LIKE ? OR o.subject LIKE ? "
            "OR o.reference_no LIKE ? "
        )
        params = (q, q, q, q)
    sql += "ORDER BY o.dispatch_date DESC, o.id DESC LIMIT 500"
    return [dict(r) for r in db.execute(sql, params).fetchall()]


def get_outward(db, record_id: int) -> dict | None:
    if not _table_exists(db, "office_outward"):
        return None
    row = db.execute(
        "SELECT o.*, p.project_name FROM office_outward o "
        "LEFT JOIN projects p ON o.project_id = p.id WHERE o.id=?",
        (record_id,),
    ).fetchone()
    return dict(row) if row else None


def save_outward(db, form, username: str, record_id: int | None = None, attachment: str | None = None) -> int:
    dispatch_date = (form.get("dispatch_date") or "").strip()
    recipient_name = (form.get("recipient_name") or "").strip()
    subject = (form.get("subject") or "").strip()
    if not dispatch_date:
        raise ValueError("Dispatch date is required.")
    if not recipient_name:
        raise ValueError("Recipient name is required.")
    if not subject:
        raise ValueError("Subject is required.")
    project_id = form.get("project_id") or None
    now = _now_ts()
    fields = (
        dispatch_date,
        recipient_name,
        (form.get("recipient_address") or "").strip(),
        (form.get("document_type") or "Other").strip(),
        subject,
        (form.get("reference_no") or "").strip(),
        (form.get("mode") or "Hand Delivery").strip(),
        (form.get("dispatched_by") or "").strip(),
        (form.get("department") or "").strip(),
        project_id,
        (form.get("remarks") or "").strip(),
    )
    if record_id:
        existing = get_outward(db, record_id)
        if not existing:
            raise ValueError("Record not found.")
        attach = attachment if attachment else existing.get("attachment")
        if not attach:
            raise ValueError("Document attachment is required for outward register.")
        db.execute(
            "UPDATE office_outward SET dispatch_date=?, recipient_name=?, recipient_address=?, "
            "document_type=?, subject=?, reference_no=?, mode=?, dispatched_by=?, department=?, "
            "project_id=?, remarks=?, attachment=?, modified_at=? WHERE id=?",
            (*fields, attach, now, record_id),
        )
        return record_id
    if not attachment:
        raise ValueError("Document attachment is required for outward register.")
    reg_no = _next_doc_number(db, "OUT", "office_outward", "register_number")
    db.execute(
        "INSERT INTO office_outward(register_number, dispatch_date, recipient_name, recipient_address, "
        "document_type, subject, reference_no, mode, dispatched_by, department, project_id, "
        "remarks, attachment, created_by, created_at, modified_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (reg_no, *fields, attachment, username, now, now),
    )
    return int(db.execute("SELECT last_insert_rowid()").fetchone()[0])


def delete_outward(db, record_id: int) -> None:
    db.execute("DELETE FROM office_outward WHERE id=?", (record_id,))


# --- Letters ---
def list_letters(db, search: str = "") -> list[dict]:
    if not _table_exists(db, "office_letters"):
        return []
    sql = (
        "SELECT l.*, p.project_name FROM office_letters l "
        "LEFT JOIN projects p ON l.project_id = p.id "
    )
    params: tuple = ()
    if search.strip():
        q = f"%{search.strip()}%"
        sql += "WHERE l.letter_number LIKE ? OR l.to_name LIKE ? OR l.subject LIKE ? "
        params = (q, q, q)
    sql += "ORDER BY l.letter_date DESC, l.id DESC LIMIT 500"
    return [dict(r) for r in db.execute(sql, params).fetchall()]


def get_letter(db, record_id: int) -> dict | None:
    if not _table_exists(db, "office_letters"):
        return None
    row = db.execute(
        "SELECT l.*, p.project_name FROM office_letters l "
        "LEFT JOIN projects p ON l.project_id = p.id WHERE l.id=?",
        (record_id,),
    ).fetchone()
    return dict(row) if row else None


def save_letter(db, form, username: str, record_id: int | None = None) -> int:
    letter_date = (form.get("letter_date") or "").strip()
    to_name = (form.get("to_name") or "").strip()
    subject = (form.get("subject") or "").strip()
    if not letter_date:
        raise ValueError("Letter date is required.")
    if not to_name:
        raise ValueError("Recipient name is required.")
    if not subject:
        raise ValueError("Subject is required.")
    letter_type = (form.get("letter_type") or "Official Letter").strip()
    if letter_type not in LETTER_TYPES:
        raise ValueError("Invalid letter type.")
    project_id = form.get("project_id") or None
    now = _now_ts()
    fields = (
        letter_type,
        letter_date,
        to_name,
        (form.get("to_address") or "").strip(),
        subject,
        (form.get("body") or "").strip(),
        (form.get("reference_no") or "").strip(),
        (form.get("department") or "").strip(),
        project_id,
        (form.get("signed_by") or "").strip(),
        (form.get("remarks") or "").strip(),
    )
    if record_id:
        db.execute(
            "UPDATE office_letters SET letter_type=?, letter_date=?, to_name=?, to_address=?, "
            "subject=?, body=?, reference_no=?, department=?, project_id=?, signed_by=?, "
            "remarks=?, modified_at=? WHERE id=?",
            (*fields, now, record_id),
        )
        return record_id
    letter_no = _next_doc_number(db, "LTR", "office_letters", "letter_number")
    db.execute(
        "INSERT INTO office_letters(letter_number, letter_type, letter_date, to_name, to_address, "
        "subject, body, reference_no, department, project_id, signed_by, remarks, "
        "created_by, created_at, modified_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (letter_no, *fields, username, now, now),
    )
    return int(db.execute("SELECT last_insert_rowid()").fetchone()[0])


def delete_letter(db, record_id: int) -> None:
    db.execute("DELETE FROM office_letters WHERE id=?", (record_id,))


# --- Quotations ---
def parse_quotation_lines_from_form(form) -> tuple[list[dict], str | None]:
    descriptions = form.getlist("description[]")
    quantities = form.getlist("quantity[]")
    units = form.getlist("unit[]")
    rates = form.getlist("rate[]")
    gst_list = form.getlist("gst_percent[]")
    tax_types = form.getlist("tax_type[]")
    row_count = max(len(descriptions), len(quantities))
    lines: list[dict] = []
    header_tax = (form.get("tax_type") or "CGST_SGST").strip()
    for idx in range(row_count):
        desc = (descriptions[idx] if idx < len(descriptions) else "").strip()
        qty_raw = quantities[idx] if idx < len(quantities) else ""
        if not desc and not str(qty_raw).strip():
            continue
        if not desc:
            return [], "Each line must have a description."
        qty = _safe_float(qty_raw, 1.0)
        if qty <= 0:
            return [], "Line quantity must be greater than zero."
        rate = _safe_float(rates[idx] if idx < len(rates) else 0)
        gst_percent = _safe_float(gst_list[idx] if idx < len(gst_list) else 18)
        tax_type = (tax_types[idx] if idx < len(tax_types) else header_tax).strip() or header_tax
        calc = calc_gst_line(qty, rate, gst_percent, tax_type)
        lines.append({
            "line_no": len(lines) + 1,
            "description": desc,
            "quantity": qty,
            "unit": (units[idx] if idx < len(units) else "Nos").strip(),
            "rate": rate,
            "gst_percent": gst_percent,
            "tax_type": tax_type,
            **calc,
        })
    if not lines:
        return [], "Add at least one quotation line."
    return lines, None


def _persist_quotation_lines(db, quotation_id: int, lines: list[dict]) -> None:
    db.execute("DELETE FROM office_quotation_lines WHERE quotation_id=?", (quotation_id,))
    for line in lines:
        db.execute(
            "INSERT INTO office_quotation_lines("
            "quotation_id, line_no, description, quantity, unit, rate, gst_percent, tax_type, "
            "taxable_value, cgst, sgst, igst, line_total"
            ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                quotation_id,
                line["line_no"],
                line["description"],
                line["quantity"],
                line.get("unit") or "",
                line["rate"],
                line["gst_percent"],
                line["tax_type"],
                line["taxable_value"],
                line["cgst"],
                line["sgst"],
                line["igst"],
                line["line_total"],
            ),
        )


def save_quotation(db, form, username: str, record_id: int | None = None) -> int:
    lines, err = parse_quotation_lines_from_form(form)
    if err:
        raise ValueError(err)
    client_name = (form.get("client_name") or "").strip()
    quotation_date = (form.get("quotation_date") or "").strip()
    if not client_name:
        raise ValueError("Client name is required.")
    if not quotation_date:
        raise ValueError("Quotation date is required.")
    subtotal = round(sum(l["taxable_value"] for l in lines), 2)
    total_cgst = round(sum(l["cgst"] for l in lines), 2)
    total_sgst = round(sum(l["sgst"] for l in lines), 2)
    total_igst = round(sum(l["igst"] for l in lines), 2)
    grand_total = round(sum(l["line_total"] for l in lines), 2)
    tax_type = (form.get("tax_type") or "CGST_SGST").strip()
    project_id = form.get("project_id") or None
    validity = int(_safe_float(form.get("validity_days"), 30))
    now = _now_ts()
    header = (
        quotation_date,
        client_name,
        (form.get("client_address") or "").strip(),
        (form.get("client_gstin") or "").strip(),
        (form.get("client_contact") or "").strip(),
        project_id,
        (form.get("subject") or "").strip(),
        (form.get("terms") or "").strip(),
        validity,
        tax_type,
        subtotal,
        total_cgst,
        total_sgst,
        total_igst,
        grand_total,
        (form.get("remarks") or "").strip(),
    )
    if record_id:
        db.execute(
            "UPDATE office_quotations SET quotation_date=?, client_name=?, client_address=?, "
            "client_gstin=?, client_contact=?, project_id=?, subject=?, terms=?, validity_days=?, "
            "tax_type=?, subtotal=?, total_cgst=?, total_sgst=?, total_igst=?, grand_total=?, "
            "remarks=?, modified_at=? WHERE id=?",
            (*header, now, record_id),
        )
        _persist_quotation_lines(db, record_id, lines)
        return record_id
    q_no = _next_doc_number(db, "QT", "office_quotations", "quotation_number")
    db.execute(
        "INSERT INTO office_quotations(quotation_number, quotation_date, client_name, client_address, "
        "client_gstin, client_contact, project_id, subject, terms, validity_days, tax_type, "
        "subtotal, total_cgst, total_sgst, total_igst, grand_total, remarks, "
        "created_by, created_at, modified_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (q_no, *header, username, now, now),
    )
    new_id = int(db.execute("SELECT last_insert_rowid()").fetchone()[0])
    _persist_quotation_lines(db, new_id, lines)
    return new_id


def load_quotation(db, record_id: int) -> dict | None:
    if not _table_exists(db, "office_quotations"):
        return None
    row = db.execute(
        "SELECT q.*, p.project_name FROM office_quotations q "
        "LEFT JOIN projects p ON q.project_id = p.id WHERE q.id=?",
        (record_id,),
    ).fetchone()
    if not row:
        return None
    data = dict(row)
    if not _table_exists(db, "office_quotation_lines"):
        data["lines"] = []
        return data
    line_rows = db.execute(
        "SELECT * FROM office_quotation_lines WHERE quotation_id=? ORDER BY line_no, id",
        (record_id,),
    ).fetchall()
    data["lines"] = [dict(l) for l in line_rows]
    return data


def list_quotations(db) -> list[dict]:
    if not _table_exists(db, "office_quotations"):
        return []
    rows = db.execute(
        "SELECT q.*, p.project_name FROM office_quotations q "
        "LEFT JOIN projects p ON q.project_id = p.id "
        "ORDER BY q.quotation_date DESC, q.id DESC LIMIT 500"
    ).fetchall()
    return [dict(r) for r in rows]


def delete_quotation(db, record_id: int) -> None:
    db.execute("DELETE FROM office_quotation_lines WHERE quotation_id=?", (record_id,))
    db.execute("DELETE FROM office_quotations WHERE id=?", (record_id,))


# --- PO Register (read-only from store) ---
def list_po_register(db, search: str = "") -> list[dict]:
    if not _table_exists(db, "purchase_orders"):
        return []
    sql = (
        "SELECT po.*, v.name AS vendor_name, v.gstin AS vendor_gstin, p.project_name "
        "FROM purchase_orders po "
        "LEFT JOIN vendors v ON po.vendor_id = v.id "
        "LEFT JOIN projects p ON po.project_id = p.id "
    )
    params: tuple = ()
    if search.strip():
        q = f"%{search.strip()}%"
        sql += "WHERE po.po_number LIKE ? OR v.name LIKE ? OR p.project_name LIKE ? "
        params = (q, q, q)
    sql += "ORDER BY po.order_date DESC, po.id DESC LIMIT 500"
    return [dict(r) for r in db.execute(sql, params).fetchall()]


# --- Agreements ---
def list_agreements(db, search: str = "") -> list[dict]:
    if not _table_exists(db, "office_agreements"):
        return []
    sql = (
        "SELECT a.*, p.project_name FROM office_agreements a "
        "LEFT JOIN projects p ON a.project_id = p.id "
    )
    params: tuple = ()
    if search.strip():
        q = f"%{search.strip()}%"
        sql += "WHERE a.agreement_number LIKE ? OR a.title LIKE ? OR a.party_name LIKE ? "
        params = (q, q, q)
    sql += "ORDER BY a.start_date DESC, a.id DESC LIMIT 500"
    return [dict(r) for r in db.execute(sql, params).fetchall()]


def get_agreement(db, record_id: int) -> dict | None:
    if not _table_exists(db, "office_agreements"):
        return None
    row = db.execute(
        "SELECT a.*, p.project_name FROM office_agreements a "
        "LEFT JOIN projects p ON a.project_id = p.id WHERE a.id=?",
        (record_id,),
    ).fetchone()
    return dict(row) if row else None


def save_agreement(db, form, username: str, record_id: int | None = None, attachment: str | None = None) -> int:
    title = (form.get("title") or "").strip()
    party_name = (form.get("party_name") or "").strip()
    if not title:
        raise ValueError("Agreement title is required.")
    if not party_name:
        raise ValueError("Party name is required.")
    project_id = form.get("project_id") or None
    now = _now_ts()
    fields = (
        title,
        party_name,
        (form.get("agreement_type") or "Other").strip(),
        (form.get("start_date") or "").strip(),
        (form.get("end_date") or "").strip(),
        _safe_float(form.get("value")),
        project_id,
        (form.get("remarks") or "").strip(),
    )
    if record_id:
        existing = get_agreement(db, record_id)
        if not existing:
            raise ValueError("Record not found.")
        attach = attachment if attachment else existing.get("attachment")
        db.execute(
            "UPDATE office_agreements SET title=?, party_name=?, agreement_type=?, start_date=?, "
            "end_date=?, value=?, project_id=?, remarks=?, attachment=?, modified_at=? WHERE id=?",
            (*fields, attach, now, record_id),
        )
        return record_id
    ag_no = _next_doc_number(db, "AGR", "office_agreements", "agreement_number")
    db.execute(
        "INSERT INTO office_agreements(agreement_number, title, party_name, agreement_type, "
        "start_date, end_date, value, project_id, remarks, attachment, created_by, created_at, modified_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (ag_no, *fields, attachment or "", username, now, now),
    )
    return int(db.execute("SELECT last_insert_rowid()").fetchone()[0])


def delete_agreement(db, record_id: int) -> None:
    db.execute("DELETE FROM office_agreements WHERE id=?", (record_id,))


# --- Legal Documents ---
def list_legal_documents(db, search: str = "") -> list[dict]:
    if not _table_exists(db, "office_legal_documents"):
        return []
    sql = "SELECT * FROM office_legal_documents WHERE is_active=1 "
    params: tuple = ()
    if search.strip():
        q = f"%{search.strip()}%"
        sql += "AND (doc_number LIKE ? OR title LIKE ? OR authority LIKE ?) "
        params = (q, q, q)
    sql += "ORDER BY expiry_date ASC, id DESC LIMIT 500"
    rows = db.execute(sql, params).fetchall()
    result = []
    today = date.today()
    for row in rows:
        item = dict(row)
        days = _days_until(item.get("expiry_date"), today)
        item["days_left"] = days
        item["alert_flag"] = 1 if _expiry_bucket(days) else 0
        result.append(item)
    return result


def get_legal_document(db, record_id: int) -> dict | None:
    if not _table_exists(db, "office_legal_documents"):
        return None
    row = db.execute("SELECT * FROM office_legal_documents WHERE id=?", (record_id,)).fetchone()
    return dict(row) if row else None


def save_legal_document(
    db, form, username: str, record_id: int | None = None, attachment: str | None = None
) -> int:
    title = (form.get("title") or "").strip()
    doc_type = (form.get("doc_type") or "Other").strip()
    expiry_date = (form.get("expiry_date") or "").strip()
    if not title:
        raise ValueError("Document title is required.")
    now = _now_ts()
    days = _days_until(expiry_date)
    alert_flag = 1 if _expiry_bucket(days) else 0
    fields = (
        title,
        doc_type,
        (form.get("authority") or "").strip(),
        (form.get("issue_date") or "").strip(),
        expiry_date,
        alert_flag,
        (form.get("remarks") or "").strip(),
    )
    if record_id:
        existing = get_legal_document(db, record_id)
        if not existing:
            raise ValueError("Record not found.")
        attach = attachment if attachment else existing.get("attachment")
        db.execute(
            "UPDATE office_legal_documents SET title=?, doc_type=?, authority=?, issue_date=?, "
            "expiry_date=?, alert_flag=?, remarks=?, attachment=?, modified_at=? WHERE id=?",
            (*fields, attach, now, record_id),
        )
        return record_id
    doc_no = _next_doc_number(db, "LEG", "office_legal_documents", "doc_number")
    db.execute(
        "INSERT INTO office_legal_documents(doc_number, title, doc_type, authority, issue_date, "
        "expiry_date, alert_flag, remarks, attachment, is_active, created_by, created_at, modified_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,1,?,?,?)",
        (doc_no, *fields, attachment or "", username, now, now),
    )
    return int(db.execute("SELECT last_insert_rowid()").fetchone()[0])


def delete_legal_document(db, record_id: int) -> None:
    db.execute("UPDATE office_legal_documents SET is_active=0 WHERE id=?", (record_id,))


# --- Fleet Vehicles ---
def list_vehicles(db, search: str = "") -> list[dict]:
    if not _table_exists(db, "fleet_vehicles"):
        return []
    sql = (
        "SELECT v.*, p.project_name FROM fleet_vehicles v "
        "LEFT JOIN projects p ON v.project_id = p.id "
    )
    params: tuple = ()
    if search.strip():
        q = f"%{search.strip()}%"
        sql += "WHERE v.registration_number LIKE ? OR v.make LIKE ? OR v.model LIKE ? "
        params = (q, q, q)
    sql += "ORDER BY v.registration_number ASC LIMIT 500"
    return [dict(r) for r in db.execute(sql, params).fetchall()]


def get_vehicle(db, record_id: int) -> dict | None:
    if not _table_exists(db, "fleet_vehicles"):
        return None
    row = db.execute(
        "SELECT v.*, p.project_name FROM fleet_vehicles v "
        "LEFT JOIN projects p ON v.project_id = p.id WHERE v.id=?",
        (record_id,),
    ).fetchone()
    return dict(row) if row else None


def save_vehicle(db, form, username: str, record_id: int | None = None) -> int:
    reg = (form.get("registration_number") or "").strip().upper()
    if not reg:
        raise ValueError("Registration number is required.")
    vehicle_type = (form.get("vehicle_type") or "Other").strip()
    status = (form.get("current_status") or "Active").strip()
    if status not in VEHICLE_STATUSES:
        raise ValueError("Invalid vehicle status.")
    project_id = form.get("project_id") or None
    now = _now_ts()
    fields = (
        reg,
        vehicle_type,
        (form.get("make") or "").strip(),
        (form.get("model") or "").strip(),
        int(_safe_float(form.get("year"), 0)) or None,
        (form.get("fuel_type") or "Diesel").strip(),
        (form.get("capacity") or "").strip(),
        (form.get("purchase_date") or "").strip(),
        _safe_float(form.get("purchase_cost")),
        status,
        (form.get("assigned_driver") or "").strip(),
        (form.get("department") or "").strip(),
        project_id,
        _safe_float(form.get("odometer_km")),
        (form.get("remarks") or "").strip(),
    )
    if record_id:
        db.execute(
            "UPDATE fleet_vehicles SET registration_number=?, vehicle_type=?, make=?, model=?, "
            "year=?, fuel_type=?, capacity=?, purchase_date=?, purchase_cost=?, current_status=?, "
            "assigned_driver=?, department=?, project_id=?, odometer_km=?, remarks=?, modified_at=? "
            "WHERE id=?",
            (*fields, now, record_id),
        )
        return record_id
    db.execute(
        "INSERT INTO fleet_vehicles(registration_number, vehicle_type, make, model, year, fuel_type, "
        "capacity, purchase_date, purchase_cost, current_status, assigned_driver, department, "
        "project_id, odometer_km, remarks, created_by, created_at, modified_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (*fields, username, now, now),
    )
    return int(db.execute("SELECT last_insert_rowid()").fetchone()[0])


def delete_vehicle(db, record_id: int) -> None:
    db.execute("DELETE FROM fleet_vehicle_documents WHERE vehicle_id=?", (record_id,))
    db.execute("DELETE FROM fleet_vehicles WHERE id=?", (record_id,))


# --- Vehicle Documents ---
def list_vehicle_documents(db, vehicle_id: int | None = None) -> list[dict]:
    if not _table_exists(db, "fleet_vehicle_documents"):
        return []
    sql = (
        "SELECT d.*, v.registration_number FROM fleet_vehicle_documents d "
        "JOIN fleet_vehicles v ON d.vehicle_id = v.id "
    )
    params: tuple = ()
    if vehicle_id:
        sql += "WHERE d.vehicle_id=? "
        params = (vehicle_id,)
    sql += "ORDER BY d.expiry_date ASC, d.id DESC LIMIT 500"
    rows = db.execute(sql, params).fetchall()
    result = []
    today = date.today()
    for row in rows:
        item = dict(row)
        item["days_left"] = _days_until(item.get("expiry_date"), today)
        result.append(item)
    return result


def get_vehicle_document(db, record_id: int) -> dict | None:
    if not _table_exists(db, "fleet_vehicle_documents"):
        return None
    row = db.execute(
        "SELECT d.*, v.registration_number FROM fleet_vehicle_documents d "
        "JOIN fleet_vehicles v ON d.vehicle_id = v.id WHERE d.id=?",
        (record_id,),
    ).fetchone()
    return dict(row) if row else None


def save_vehicle_document(
    db, form, username: str, record_id: int | None = None, attachment: str | None = None
) -> int:
    vehicle_id = form.get("vehicle_id")
    doc_type = (form.get("doc_type") or "").strip()
    if not vehicle_id:
        raise ValueError("Vehicle is required.")
    if doc_type not in VEHICLE_DOC_TYPES:
        raise ValueError("Invalid document type.")
    now = _now_ts()
    fields = (
        int(vehicle_id),
        doc_type,
        (form.get("doc_number") or "").strip(),
        (form.get("issue_date") or "").strip(),
        (form.get("expiry_date") or "").strip(),
        (form.get("issuer") or "").strip(),
        (form.get("remarks") or "").strip(),
    )
    if record_id:
        existing = get_vehicle_document(db, record_id)
        if not existing:
            raise ValueError("Record not found.")
        attach = attachment if attachment else existing.get("attachment")
        db.execute(
            "UPDATE fleet_vehicle_documents SET vehicle_id=?, doc_type=?, doc_number=?, issue_date=?, "
            "expiry_date=?, issuer=?, remarks=?, attachment=?, modified_at=? WHERE id=?",
            (*fields, attach, now, record_id),
        )
        return record_id
    db.execute(
        "INSERT INTO fleet_vehicle_documents(vehicle_id, doc_type, doc_number, issue_date, "
        "expiry_date, issuer, remarks, attachment, created_by, created_at, modified_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (*fields, attachment or "", username, now, now),
    )
    return int(db.execute("SELECT last_insert_rowid()").fetchone()[0])


def delete_vehicle_document(db, record_id: int) -> None:
    db.execute("DELETE FROM fleet_vehicle_documents WHERE id=?", (record_id,))


# --- Running Log ---
def list_running_logs(db, vehicle_id: int | None = None) -> list[dict]:
    if not _table_exists(db, "fleet_running_log"):
        return []
    sql = (
        "SELECT r.*, v.registration_number, p.project_name FROM fleet_running_log r "
        "JOIN fleet_vehicles v ON r.vehicle_id = v.id "
        "LEFT JOIN projects p ON r.project_id = p.id "
    )
    params: tuple = ()
    if vehicle_id:
        sql += "WHERE r.vehicle_id=? "
        params = (vehicle_id,)
    sql += "ORDER BY r.log_date DESC, r.id DESC LIMIT 500"
    return [dict(r) for r in db.execute(sql, params).fetchall()]


def get_running_log(db, record_id: int) -> dict | None:
    if not _table_exists(db, "fleet_running_log"):
        return None
    row = db.execute(
        "SELECT r.*, v.registration_number, p.project_name FROM fleet_running_log r "
        "JOIN fleet_vehicles v ON r.vehicle_id = v.id "
        "LEFT JOIN projects p ON r.project_id = p.id WHERE r.id=?",
        (record_id,),
    ).fetchone()
    return dict(row) if row else None


def save_running_log(db, form, username: str, record_id: int | None = None) -> int:
    vehicle_id = form.get("vehicle_id")
    log_date = (form.get("log_date") or "").strip()
    if not vehicle_id:
        raise ValueError("Vehicle is required.")
    if not log_date:
        raise ValueError("Log date is required.")
    start_km = _safe_float(form.get("start_km"))
    end_km = _safe_float(form.get("end_km"))
    if end_km < start_km:
        raise ValueError("End KM must be greater than or equal to start KM.")
    total_km = round(end_km - start_km, 2)
    project_id = form.get("project_id") or None
    now = _now_ts()
    fields = (
        int(vehicle_id),
        log_date,
        (form.get("driver_name") or "").strip(),
        start_km,
        end_km,
        total_km,
        (form.get("purpose") or "").strip(),
        project_id,
        _safe_float(form.get("fuel_liters")),
        (form.get("remarks") or "").strip(),
    )
    if record_id:
        db.execute(
            "UPDATE fleet_running_log SET vehicle_id=?, log_date=?, driver_name=?, start_km=?, "
            "end_km=?, total_km=?, purpose=?, project_id=?, fuel_liters=?, remarks=?, modified_at=? "
            "WHERE id=?",
            (*fields, now, record_id),
        )
        return record_id
    db.execute(
        "INSERT INTO fleet_running_log(vehicle_id, log_date, driver_name, start_km, end_km, "
        "total_km, purpose, project_id, fuel_liters, remarks, created_by, created_at, modified_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (*fields, username, now, now),
    )
    new_id = int(db.execute("SELECT last_insert_rowid()").fetchone()[0])
    if end_km > 0:
        db.execute(
            "UPDATE fleet_vehicles SET odometer_km=?, modified_at=? WHERE id=? AND odometer_km < ?",
            (end_km, now, int(vehicle_id), end_km),
        )
    return new_id


def delete_running_log(db, record_id: int) -> None:
    db.execute("DELETE FROM fleet_running_log WHERE id=?", (record_id,))


# --- Diesel ---
def get_diesel_stock_balance(db) -> float:
    if not _table_exists(db, "diesel_ledger"):
        return 0.0
    row = db.execute(
        "SELECT COALESCE(SUM(CASE WHEN movement_type=? THEN quantity_liters "
        "WHEN movement_type=? THEN -quantity_liters ELSE 0 END), 0) "
        "FROM diesel_ledger",
        (DIESEL_MOVEMENT_PURCHASE, DIESEL_MOVEMENT_ISSUE),
    ).fetchone()
    return round(float(row[0] if row else 0), 2)


def _post_diesel_ledger(
    db,
    movement_type: str,
    quantity: float,
    movement_date: str,
    reference_table: str,
    reference_id: int,
    remarks: str,
    username: str,
) -> None:
    db.execute(
        "INSERT INTO diesel_ledger(movement_date, movement_type, quantity_liters, reference_table, "
        "reference_id, remarks, created_by, created_at) VALUES(?,?,?,?,?,?,?,?)",
        (movement_date, movement_type, quantity, reference_table, reference_id, remarks, username, _now_ts()),
    )


def list_diesel_purchases(db) -> list[dict]:
    if not _table_exists(db, "diesel_purchases"):
        return []
    rows = db.execute(
        "SELECT * FROM diesel_purchases ORDER BY purchase_date DESC, id DESC LIMIT 500"
    ).fetchall()
    return [dict(r) for r in rows]


def save_diesel_purchase(db, form, username: str) -> int:
    purchase_date = (form.get("purchase_date") or "").strip()
    supplier = (form.get("supplier") or "").strip()
    qty = _safe_float(form.get("quantity_liters"))
    rate = _safe_float(form.get("rate_per_liter"))
    if not purchase_date:
        raise ValueError("Purchase date is required.")
    if not supplier:
        raise ValueError("Supplier is required.")
    if qty <= 0:
        raise ValueError("Quantity must be greater than zero.")
    total = round(qty * rate, 2)
    purchase_no = _next_doc_number(db, "DSL-P", "diesel_purchases", "purchase_number")
    now = _now_ts()
    db.execute(
        "INSERT INTO diesel_purchases(purchase_number, purchase_date, supplier, quantity_liters, "
        "rate_per_liter, total_amount, invoice_ref, remarks, created_by, created_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?)",
        (
            purchase_no,
            purchase_date,
            supplier,
            qty,
            rate,
            total,
            (form.get("invoice_ref") or "").strip(),
            (form.get("remarks") or "").strip(),
            username,
            now,
        ),
    )
    new_id = int(db.execute("SELECT last_insert_rowid()").fetchone()[0])
    _post_diesel_ledger(
        db, DIESEL_MOVEMENT_PURCHASE, qty, purchase_date,
        "diesel_purchases", new_id, f"Purchase {purchase_no}", username,
    )
    return new_id


def list_diesel_issues(db) -> list[dict]:
    if not _table_exists(db, "diesel_issues"):
        return []
    rows = db.execute(
        "SELECT i.*, v.registration_number, p.project_name FROM diesel_issues i "
        "LEFT JOIN fleet_vehicles v ON i.vehicle_id = v.id "
        "LEFT JOIN projects p ON i.project_id = p.id "
        "ORDER BY i.issue_date DESC, i.id DESC LIMIT 500"
    ).fetchall()
    return [dict(r) for r in rows]


def save_diesel_issue(db, form, username: str) -> int:
    issue_date = (form.get("issue_date") or "").strip()
    vehicle_id = form.get("vehicle_id")
    qty = _safe_float(form.get("quantity_liters"))
    if not issue_date:
        raise ValueError("Issue date is required.")
    if not vehicle_id:
        raise ValueError("Vehicle is required.")
    if qty <= 0:
        raise ValueError("Quantity must be greater than zero.")
    balance = get_diesel_stock_balance(db)
    if qty > balance:
        raise ValueError(f"Insufficient diesel stock ({balance:.2f} L available).")
    project_id = form.get("project_id") or None
    odometer = _safe_float(form.get("odometer_km"))
    issue_no = _next_doc_number(db, "DSL-I", "diesel_issues", "issue_number")
    now = _now_ts()
    db.execute(
        "INSERT INTO diesel_issues(issue_number, issue_date, vehicle_id, quantity_liters, "
        "odometer_km, issued_to, project_id, remarks, created_by, created_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?)",
        (
            issue_no,
            issue_date,
            int(vehicle_id),
            qty,
            odometer,
            (form.get("issued_to") or "").strip(),
            project_id,
            (form.get("remarks") or "").strip(),
            username,
            now,
        ),
    )
    new_id = int(db.execute("SELECT last_insert_rowid()").fetchone()[0])
    _post_diesel_ledger(
        db, DIESEL_MOVEMENT_ISSUE, qty, issue_date,
        "diesel_issues", new_id, f"Issue {issue_no}", username,
    )
    if odometer > 0:
        db.execute(
            "UPDATE fleet_vehicles SET odometer_km=?, modified_at=? WHERE id=? AND odometer_km < ?",
            (odometer, now, int(vehicle_id), odometer),
        )
    return new_id


def list_diesel_ledger(db) -> list[dict]:
    if not _table_exists(db, "diesel_ledger"):
        return []
    rows = db.execute(
        "SELECT * FROM diesel_ledger ORDER BY movement_date DESC, id DESC LIMIT 500"
    ).fetchall()
    return [dict(r) for r in rows]
