"""Company Master — country-based registration, branches, directors, documents (Phase A)."""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Any

COMPANY_COUNTRIES = (
    "India",
    "Saudi Arabia",
    "UAE",
    "Qatar",
    "Oman",
    "Bahrain",
    "Kuwait",
    "Other",
)
GCC_CONFIGURABLE_COUNTRIES = ("Qatar", "Oman", "Bahrain", "Kuwait", "Other")
COMPANY_STATUSES = ("Active", "Inactive")
DIRECTOR_TYPES = ("Director", "Partner", "Proprietor", "Shareholder", "Authorized Signatory")
COMPANY_DOC_TYPES = (
    "Trade License",
    "Commercial Registration",
    "VAT Certificate",
    "GST Certificate",
    "PAN Card",
    "TAN Certificate",
    "MSME Certificate",
    "ZATCA Certificate",
    "Emirates ID Copy",
    "MOA/AOA",
    "Bank Guarantee",
    "Insurance",
    "Other",
)
EXPIRY_ALERT_DAYS = (90, 60, 30, 7)
MAX_COMPANY_UPLOAD_BYTES = 10 * 1024 * 1024
COMPANY_ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx", ".xls", ".xlsx"}

INDIA_FIELD_DEFS = [
    ("pan", "PAN", "text", 1),
    ("tan", "TAN", "text", 0),
    ("cin", "CIN / Company Registration", "text", 0),
    ("msme_reg_no", "MSME Registration No.", "text", 0),
    ("msme_category", "MSME Category", "select", 0),
    ("iec_code", "IEC Code (Import/Export)", "text", 0),
    ("pf_establishment_id", "PF Establishment ID", "text", 0),
    ("esi_establishment_id", "ESI Establishment ID", "text", 0),
]

SAUDI_FIELD_DEFS = [
    ("cr_number", "Commercial Registration (CR)", "text", 1),
    ("cr_issue_date", "CR Issue Date", "date", 0),
    ("cr_expiry_date", "CR Expiry Date", "date", 0),
    ("vat_number", "VAT Number", "text", 1),
    ("zatca_fatoora_id", "ZATCA Fatoora ID", "text", 0),
    ("gosi_number", "GOSI Number", "text", 0),
    ("municipality_license", "Municipality License", "text", 0),
]

UAE_FIELD_DEFS = [
    ("trade_license_no", "Trade License No.", "text", 1),
    ("trade_license_authority", "License Authority", "text", 0),
    ("trade_license_expiry", "Trade License Expiry", "date", 0),
    ("vat_trn", "VAT TRN", "text", 1),
    ("chamber_membership_no", "Chamber Membership No.", "text", 0),
]

INDIA_DIRECTOR_FIELDS = [
    ("pan", "PAN", "text", 0),
    ("aadhaar", "Aadhaar", "text", 0),
]
SAUDI_DIRECTOR_FIELDS = [
    ("iqama", "Iqama No.", "text", 0),
    ("passport", "Passport No.", "text", 0),
]
UAE_DIRECTOR_FIELDS = [
    ("emirates_id", "Emirates ID", "text", 0),
    ("passport", "Passport No.", "text", 0),
]

DEFAULT_GCC_FIELD_CONFIG = [
    ("commercial_reg_no", "Commercial Registration No.", "text", 1),
    ("tax_registration_no", "Tax / VAT Registration", "text", 0),
    ("license_authority", "License Authority", "text", 0),
    ("license_expiry", "License Expiry", "date", 0),
]


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


def _next_company_code(db) -> str:
    year = datetime.now().strftime("%Y")
    base = f"CO-{year}-"
    if not _table_exists(db, "companies"):
        return f"{base}0001"
    row = db.execute(
        "SELECT company_code FROM companies WHERE company_code LIKE ? ORDER BY id DESC LIMIT 1",
        (f"{base}%",),
    ).fetchone()
    seq = 1
    if row and row[0]:
        m = re.search(r"-(\d+)$", str(row[0]))
        if m:
            seq = int(m.group(1)) + 1
    return f"{base}{seq:04d}"


def _json_load(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _json_dump(data: dict[str, Any] | None) -> str:
    return json.dumps(data or {}, ensure_ascii=False)


def country_field_defs(country: str, db=None) -> list[dict[str, Any]]:
    country = (country or "").strip()
    if country == "India":
        return [_field_def_to_dict(f) for f in INDIA_FIELD_DEFS]
    if country == "Saudi Arabia":
        return [_field_def_to_dict(f) for f in SAUDI_FIELD_DEFS]
    if country == "UAE":
        return [_field_def_to_dict(f) for f in UAE_FIELD_DEFS]
    if country in GCC_CONFIGURABLE_COUNTRIES and db is not None:
        return list_country_field_config(db, country)
    return [_field_def_to_dict(f) for f in DEFAULT_GCC_FIELD_CONFIG]


def director_field_defs(country: str) -> list[dict[str, Any]]:
    country = (country or "").strip()
    if country == "India":
        return [_field_def_to_dict(f) for f in INDIA_DIRECTOR_FIELDS]
    if country == "Saudi Arabia":
        return [_field_def_to_dict(f) for f in SAUDI_DIRECTOR_FIELDS]
    if country == "UAE":
        return [_field_def_to_dict(f) for f in UAE_DIRECTOR_FIELDS]
    return [
        {"field_key": "national_id", "field_label": "National ID", "field_type": "text", "is_required": 0},
        {"field_key": "passport", "field_label": "Passport No.", "field_type": "text", "is_required": 0},
    ]


def _field_def_to_dict(defn: tuple) -> dict[str, Any]:
    key, label, ftype, required = defn
    opts = []
    if key == "msme_category":
        opts = ["Micro", "Small", "Medium"]
    return {
        "field_key": key,
        "field_label": label,
        "field_type": ftype,
        "is_required": required,
        "options": opts,
    }


def _parse_country_fields(form, country: str, db=None) -> dict[str, str]:
    data: dict[str, str] = {}
    for field in country_field_defs(country, db):
        key = field["field_key"]
        val = (form.get(f"cf_{key}") or "").strip()
        if val:
            data[key] = val
    return data


def _parse_director_id_fields(form, country: str) -> dict[str, str]:
    data: dict[str, str] = {}
    for field in director_field_defs(country):
        key = field["field_key"]
        val = (form.get(f"dp_{key}") or "").strip()
        if val:
            data[key] = val
    return data


def ensure_company_master_schema(db) -> None:
    """Idempotent company master schema (Phase A)."""
    db.execute("""
        CREATE TABLE IF NOT EXISTS companies(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_code TEXT UNIQUE NOT NULL,
            legal_name TEXT NOT NULL,
            trade_name TEXT,
            country TEXT NOT NULL,
            status TEXT DEFAULT 'Active',
            address_line1 TEXT,
            address_line2 TEXT,
            city TEXT,
            state_region TEXT,
            postal_code TEXT,
            phone TEXT,
            email TEXT,
            website TEXT,
            country_fields_json TEXT,
            created_by TEXT,
            created_at TEXT,
            modified_at TEXT
        )
    """)
    for col, ctype in (
        ("company_code", "TEXT"), ("legal_name", "TEXT"), ("trade_name", "TEXT"),
        ("country", "TEXT"), ("status", "TEXT DEFAULT 'Active'"),
        ("address_line1", "TEXT"), ("address_line2", "TEXT"), ("city", "TEXT"),
        ("state_region", "TEXT"), ("postal_code", "TEXT"), ("phone", "TEXT"),
        ("email", "TEXT"), ("website", "TEXT"), ("country_fields_json", "TEXT"),
        ("created_by", "TEXT"), ("created_at", "TEXT"), ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "companies", col, ctype)

    db.execute("""
        CREATE TABLE IF NOT EXISTS company_branches(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            branch_code TEXT,
            branch_name TEXT NOT NULL,
            country TEXT NOT NULL,
            address_line1 TEXT,
            address_line2 TEXT,
            city TEXT,
            state_region TEXT,
            postal_code TEXT,
            phone TEXT,
            email TEXT,
            tax_registration TEXT,
            country_fields_json TEXT,
            is_head_office INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Active',
            created_by TEXT,
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(company_id) REFERENCES companies(id)
        )
    """)
    for col, ctype in (
        ("company_id", "INTEGER"), ("branch_code", "TEXT"), ("branch_name", "TEXT"),
        ("country", "TEXT"), ("address_line1", "TEXT"), ("address_line2", "TEXT"),
        ("city", "TEXT"), ("state_region", "TEXT"), ("postal_code", "TEXT"),
        ("phone", "TEXT"), ("email", "TEXT"), ("tax_registration", "TEXT"),
        ("country_fields_json", "TEXT"), ("is_head_office", "INTEGER DEFAULT 0"),
        ("status", "TEXT DEFAULT 'Active'"), ("created_by", "TEXT"),
        ("created_at", "TEXT"), ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "company_branches", col, ctype)

    db.execute("""
        CREATE TABLE IF NOT EXISTS company_gst_registrations(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            branch_id INTEGER,
            state_code TEXT,
            state_name TEXT,
            gstin TEXT NOT NULL,
            registration_date TEXT,
            status TEXT DEFAULT 'Active',
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(company_id) REFERENCES companies(id),
            FOREIGN KEY(branch_id) REFERENCES company_branches(id)
        )
    """)
    for col, ctype in (
        ("company_id", "INTEGER"), ("branch_id", "INTEGER"), ("state_code", "TEXT"),
        ("state_name", "TEXT"), ("gstin", "TEXT"), ("registration_date", "TEXT"),
        ("status", "TEXT DEFAULT 'Active'"), ("created_at", "TEXT"), ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "company_gst_registrations", col, ctype)

    db.execute("""
        CREATE TABLE IF NOT EXISTS company_directors_partners(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            person_type TEXT DEFAULT 'Director',
            full_name TEXT NOT NULL,
            designation TEXT,
            nationality TEXT,
            country TEXT,
            id_fields_json TEXT,
            address TEXT,
            phone TEXT,
            email TEXT,
            share_percentage REAL,
            is_active INTEGER DEFAULT 1,
            created_by TEXT,
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(company_id) REFERENCES companies(id)
        )
    """)
    for col, ctype in (
        ("company_id", "INTEGER"), ("person_type", "TEXT"), ("full_name", "TEXT"),
        ("designation", "TEXT"), ("nationality", "TEXT"), ("country", "TEXT"),
        ("id_fields_json", "TEXT"), ("address", "TEXT"), ("phone", "TEXT"),
        ("email", "TEXT"), ("share_percentage", "REAL"), ("is_active", "INTEGER DEFAULT 1"),
        ("created_by", "TEXT"), ("created_at", "TEXT"), ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "company_directors_partners", col, ctype)

    db.execute("""
        CREATE TABLE IF NOT EXISTS company_documents(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            branch_id INTEGER,
            director_id INTEGER,
            doc_type TEXT,
            doc_number TEXT,
            issue_date TEXT,
            expiry_date TEXT,
            alert_flag INTEGER DEFAULT 0,
            attachment TEXT,
            remarks TEXT,
            is_active INTEGER DEFAULT 1,
            created_by TEXT,
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(company_id) REFERENCES companies(id),
            FOREIGN KEY(branch_id) REFERENCES company_branches(id),
            FOREIGN KEY(director_id) REFERENCES company_directors_partners(id)
        )
    """)
    for col, ctype in (
        ("company_id", "INTEGER"), ("branch_id", "INTEGER"), ("director_id", "INTEGER"),
        ("doc_type", "TEXT"), ("doc_number", "TEXT"), ("issue_date", "TEXT"),
        ("expiry_date", "TEXT"), ("alert_flag", "INTEGER DEFAULT 0"), ("attachment", "TEXT"),
        ("remarks", "TEXT"), ("is_active", "INTEGER DEFAULT 1"), ("created_by", "TEXT"),
        ("created_at", "TEXT"), ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "company_documents", col, ctype)

    db.execute("""
        CREATE TABLE IF NOT EXISTS company_country_field_config(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            country TEXT NOT NULL,
            field_key TEXT NOT NULL,
            field_label TEXT NOT NULL,
            field_type TEXT DEFAULT 'text',
            is_required INTEGER DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            options_json TEXT,
            UNIQUE(country, field_key)
        )
    """)
    for col, ctype in (
        ("country", "TEXT"), ("field_key", "TEXT"), ("field_label", "TEXT"),
        ("field_type", "TEXT DEFAULT 'text'"), ("is_required", "INTEGER DEFAULT 0"),
        ("sort_order", "INTEGER DEFAULT 0"), ("options_json", "TEXT"),
    ):
        _ensure_column(db, "company_country_field_config", col, ctype)

    seed_country_field_config(db)


def seed_country_field_config(db) -> None:
    """Default configurable fields for GCC + Other countries."""
    for country in GCC_CONFIGURABLE_COUNTRIES:
        for idx, (key, label, ftype, required) in enumerate(DEFAULT_GCC_FIELD_CONFIG):
            existing = db.execute(
                "SELECT id FROM company_country_field_config WHERE country=? AND field_key=?",
                (country, key),
            ).fetchone()
            if existing:
                continue
            db.execute(
                "INSERT INTO company_country_field_config("
                "country, field_key, field_label, field_type, is_required, sort_order, options_json"
                ") VALUES(?,?,?,?,?,?,?)",
                (country, key, label, ftype, required, idx, "[]"),
            )


def list_country_field_config(db, country: str) -> list[dict[str, Any]]:
    if not _table_exists(db, "company_country_field_config"):
        return []
    rows = db.execute(
        "SELECT * FROM company_country_field_config WHERE country=? ORDER BY sort_order, field_label",
        (country,),
    ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        try:
            item["options"] = json.loads(item.get("options_json") or "[]")
        except json.JSONDecodeError:
            item["options"] = []
        result.append(item)
    return result


def list_companies(db, search: str = "", country: str = "") -> list[dict[str, Any]]:
    if not _table_exists(db, "companies"):
        return []
    sql = "SELECT * FROM companies WHERE 1=1"
    params: list[Any] = []
    if search:
        sql += " AND (legal_name LIKE ? OR trade_name LIKE ? OR company_code LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like, like])
    if country:
        sql += " AND country=?"
        params.append(country)
    sql += " ORDER BY legal_name, id"
    rows = db.execute(sql, params).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["country_fields"] = _json_load(item.get("country_fields_json"))
        result.append(item)
    return result


def get_company(db, company_id: int) -> dict[str, Any] | None:
    if not company_id or not _table_exists(db, "companies"):
        return None
    row = db.execute("SELECT * FROM companies WHERE id=?", (company_id,)).fetchone()
    if not row:
        return None
    item = dict(row)
    item["country_fields"] = _json_load(item.get("country_fields_json"))
    return item


def save_company(db, form, username: str, company_id: int | None = None) -> int:
    legal_name = (form.get("legal_name") or "").strip()
    if not legal_name:
        raise ValueError("Legal name is required.")
    country = (form.get("country") or "India").strip()
    if country not in COMPANY_COUNTRIES:
        raise ValueError("Select a valid country.")
    trade_name = (form.get("trade_name") or "").strip()
    status = (form.get("status") or "Active").strip()
    country_fields = _parse_country_fields(form, country, db)
    now = _now_ts()
    values = (
        legal_name,
        trade_name,
        country,
        status,
        (form.get("address_line1") or "").strip(),
        (form.get("address_line2") or "").strip(),
        (form.get("city") or "").strip(),
        (form.get("state_region") or "").strip(),
        (form.get("postal_code") or "").strip(),
        (form.get("phone") or "").strip(),
        (form.get("email") or "").strip(),
        (form.get("website") or "").strip(),
        _json_dump(country_fields),
        now,
    )
    if company_id:
        db.execute(
            "UPDATE companies SET legal_name=?, trade_name=?, country=?, status=?, "
            "address_line1=?, address_line2=?, city=?, state_region=?, postal_code=?, "
            "phone=?, email=?, website=?, country_fields_json=?, modified_at=? WHERE id=?",
            (*values, company_id),
        )
        return company_id
    code = _next_company_code(db)
    cur = db.execute(
        "INSERT INTO companies(company_code, legal_name, trade_name, country, status, "
        "address_line1, address_line2, city, state_region, postal_code, phone, email, "
        "website, country_fields_json, created_by, created_at, modified_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (code, *values, username, now),
    )
    return int(cur.lastrowid)


def delete_company(db, company_id: int) -> None:
    if not company_id:
        raise ValueError("Invalid company.")
    for table in (
        "company_documents",
        "company_gst_registrations",
        "company_directors_partners",
        "company_branches",
    ):
        if _table_exists(db, table):
            db.execute(f"DELETE FROM {table} WHERE company_id=?", (company_id,))
    db.execute("DELETE FROM companies WHERE id=?", (company_id,))


def list_branches(db, company_id: int) -> list[dict[str, Any]]:
    if not _table_exists(db, "company_branches"):
        return []
    rows = db.execute(
        "SELECT * FROM company_branches WHERE company_id=? ORDER BY is_head_office DESC, branch_name",
        (company_id,),
    ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["country_fields"] = _json_load(item.get("country_fields_json"))
        result.append(item)
    return result


def get_branch(db, branch_id: int) -> dict[str, Any] | None:
    row = db.execute("SELECT * FROM company_branches WHERE id=?", (branch_id,)).fetchone()
    if not row:
        return None
    item = dict(row)
    item["country_fields"] = _json_load(item.get("country_fields_json"))
    return item


def save_branch(db, form, username: str, branch_id: int | None = None) -> int:
    company_id = int(form.get("company_id") or 0)
    if not company_id:
        raise ValueError("Company is required.")
    branch_name = (form.get("branch_name") or "").strip()
    if not branch_name:
        raise ValueError("Branch name is required.")
    country = (form.get("branch_country") or form.get("country") or "India").strip()
    country_fields = _parse_country_fields(form, country, db)
    is_ho = 1 if form.get("is_head_office") == "on" else 0
    now = _now_ts()
    values = (
        company_id,
        (form.get("branch_code") or "").strip(),
        branch_name,
        country,
        (form.get("branch_address_line1") or form.get("address_line1") or "").strip(),
        (form.get("branch_address_line2") or form.get("address_line2") or "").strip(),
        (form.get("branch_city") or form.get("city") or "").strip(),
        (form.get("branch_state_region") or form.get("state_region") or "").strip(),
        (form.get("branch_postal_code") or form.get("postal_code") or "").strip(),
        (form.get("branch_phone") or form.get("phone") or "").strip(),
        (form.get("branch_email") or form.get("email") or "").strip(),
        (form.get("tax_registration") or "").strip(),
        _json_dump(country_fields),
        is_ho,
        (form.get("branch_status") or "Active").strip(),
        now,
    )
    if branch_id:
        db.execute(
            "UPDATE company_branches SET company_id=?, branch_code=?, branch_name=?, country=?, "
            "address_line1=?, address_line2=?, city=?, state_region=?, postal_code=?, phone=?, "
            "email=?, tax_registration=?, country_fields_json=?, is_head_office=?, status=?, "
            "modified_at=? WHERE id=?",
            (*values, branch_id),
        )
        return branch_id
    cur = db.execute(
        "INSERT INTO company_branches(company_id, branch_code, branch_name, country, "
        "address_line1, address_line2, city, state_region, postal_code, phone, email, "
        "tax_registration, country_fields_json, is_head_office, status, created_by, created_at, "
        "modified_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (*values, username, now),
    )
    return int(cur.lastrowid)


def delete_branch(db, branch_id: int) -> None:
    if _table_exists(db, "company_documents"):
        db.execute("UPDATE company_documents SET branch_id=NULL WHERE branch_id=?", (branch_id,))
    db.execute("DELETE FROM company_branches WHERE id=?", (branch_id,))


def list_gst_registrations(db, company_id: int) -> list[dict[str, Any]]:
    if not _table_exists(db, "company_gst_registrations"):
        return []
    rows = db.execute(
        "SELECT * FROM company_gst_registrations WHERE company_id=? ORDER BY state_name, gstin",
        (company_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def save_gst_registration(db, form, company_id: int, record_id: int | None = None) -> int:
    gstin = (form.get("gstin") or "").strip().upper()
    if not gstin:
        raise ValueError("GSTIN is required.")
    now = _now_ts()
    branch_id = form.get("gst_branch_id") or None
    branch_id = int(branch_id) if branch_id else None
    values = (
        company_id,
        branch_id,
        (form.get("state_code") or "").strip(),
        (form.get("state_name") or "").strip(),
        gstin,
        (form.get("registration_date") or "").strip(),
        (form.get("gst_status") or "Active").strip(),
        now,
    )
    if record_id:
        db.execute(
            "UPDATE company_gst_registrations SET company_id=?, branch_id=?, state_code=?, "
            "state_name=?, gstin=?, registration_date=?, status=?, modified_at=? WHERE id=?",
            (*values, record_id),
        )
        return record_id
    cur = db.execute(
        "INSERT INTO company_gst_registrations(company_id, branch_id, state_code, state_name, "
        "gstin, registration_date, status, created_at, modified_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (*values, now),
    )
    return int(cur.lastrowid)


def delete_gst_registration(db, record_id: int) -> None:
    db.execute("DELETE FROM company_gst_registrations WHERE id=?", (record_id,))


def list_directors(db, company_id: int) -> list[dict[str, Any]]:
    if not _table_exists(db, "company_directors_partners"):
        return []
    rows = db.execute(
        "SELECT * FROM company_directors_partners WHERE company_id=? ORDER BY full_name",
        (company_id,),
    ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["id_fields"] = _json_load(item.get("id_fields_json"))
        result.append(item)
    return result


def get_director(db, director_id: int) -> dict[str, Any] | None:
    row = db.execute(
        "SELECT * FROM company_directors_partners WHERE id=?", (director_id,)
    ).fetchone()
    if not row:
        return None
    item = dict(row)
    item["id_fields"] = _json_load(item.get("id_fields_json"))
    return item


def save_director(db, form, username: str, director_id: int | None = None) -> int:
    company_id = int(form.get("company_id") or 0)
    if not company_id:
        raise ValueError("Company is required.")
    full_name = (form.get("director_full_name") or form.get("full_name") or "").strip()
    if not full_name:
        raise ValueError("Director / partner name is required.")
    country = (form.get("director_country") or form.get("country") or "India").strip()
    id_fields = _parse_director_id_fields(form, country)
    share_raw = (form.get("share_percentage") or "").strip()
    share_pct = float(share_raw) if share_raw else None
    now = _now_ts()
    values = (
        company_id,
        (form.get("person_type") or "Director").strip(),
        full_name,
        (form.get("designation") or "").strip(),
        (form.get("nationality") or "").strip(),
        country,
        _json_dump(id_fields),
        (form.get("director_address") or form.get("address") or "").strip(),
        (form.get("director_phone") or form.get("phone") or "").strip(),
        (form.get("director_email") or form.get("email") or "").strip(),
        share_pct,
        1 if form.get("director_active") == "on" else 0,
        now,
    )
    if director_id:
        db.execute(
            "UPDATE company_directors_partners SET company_id=?, person_type=?, full_name=?, "
            "designation=?, nationality=?, country=?, id_fields_json=?, address=?, phone=?, "
            "email=?, share_percentage=?, is_active=?, modified_at=? WHERE id=?",
            (*values, director_id),
        )
        return director_id
    cur = db.execute(
        "INSERT INTO company_directors_partners(company_id, person_type, full_name, designation, "
        "nationality, country, id_fields_json, address, phone, email, share_percentage, is_active, "
        "created_by, created_at, modified_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (*values, username, now),
    )
    return int(cur.lastrowid)


def delete_director(db, director_id: int) -> None:
    if _table_exists(db, "company_documents"):
        db.execute(
            "UPDATE company_documents SET director_id=NULL WHERE director_id=?", (director_id,)
        )
    db.execute("DELETE FROM company_directors_partners WHERE id=?", (director_id,))


def list_company_documents(db, company_id: int) -> list[dict[str, Any]]:
    if not _table_exists(db, "company_documents"):
        return []
    today = date.today()
    rows = db.execute(
        "SELECT d.*, b.branch_name FROM company_documents d "
        "LEFT JOIN company_branches b ON d.branch_id = b.id "
        "WHERE d.company_id=? AND d.is_active=1 ORDER BY d.expiry_date ASC, d.id DESC",
        (company_id,),
    ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        days = _days_until(item.get("expiry_date"), today)
        item["days_left"] = days
        item["alert_bucket"] = _expiry_bucket(days)
        result.append(item)
    return result


def get_company_document(db, doc_id: int) -> dict[str, Any] | None:
    row = db.execute("SELECT * FROM company_documents WHERE id=?", (doc_id,)).fetchone()
    return dict(row) if row else None


def save_company_document(
    db,
    form,
    username: str,
    attachment: str | None,
    doc_id: int | None = None,
) -> int:
    company_id = int(form.get("company_id") or 0)
    if not company_id:
        raise ValueError("Company is required.")
    doc_type = (form.get("doc_type") or "Other").strip()
    expiry_date = (form.get("expiry_date") or "").strip()
    days = _days_until(expiry_date)
    alert_flag = 1 if _expiry_bucket(days) else 0
    branch_id = form.get("doc_branch_id") or None
    branch_id = int(branch_id) if branch_id else None
    director_id = form.get("doc_director_id") or None
    director_id = int(director_id) if director_id else None
    now = _now_ts()
    values = (
        company_id,
        branch_id,
        director_id,
        doc_type,
        (form.get("doc_number") or "").strip(),
        (form.get("issue_date") or "").strip(),
        expiry_date,
        alert_flag,
        (form.get("remarks") or "").strip(),
        now,
    )
    if doc_id:
        existing = get_company_document(db, doc_id)
        attach = attachment if attachment is not None else (existing or {}).get("attachment")
        db.execute(
            "UPDATE company_documents SET company_id=?, branch_id=?, director_id=?, doc_type=?, "
            "doc_number=?, issue_date=?, expiry_date=?, alert_flag=?, remarks=?, attachment=?, "
            "modified_at=? WHERE id=?",
            (*values, attach or "", doc_id),
        )
        return doc_id
    if not attachment:
        attachment = ""
    cur = db.execute(
        "INSERT INTO company_documents(company_id, branch_id, director_id, doc_type, doc_number, "
        "issue_date, expiry_date, alert_flag, remarks, attachment, is_active, created_by, "
        "created_at, modified_at) VALUES(?,?,?,?,?,?,?,?,?,?,1,?,?,?)",
        (*values, attachment, username, now),
    )
    return int(cur.lastrowid)


def delete_company_document(db, doc_id: int) -> None:
    db.execute("UPDATE company_documents SET is_active=0 WHERE id=?", (doc_id,))


def collect_company_expiry_alerts(db) -> dict[str, Any]:
    """Company documents with expiry buckets (90/60/30/7 + overdue)."""
    buckets: dict[str, list[dict]] = {str(d): [] for d in EXPIRY_ALERT_DAYS}
    overdue: list[dict] = []
    if not _table_exists(db, "company_documents"):
        return {
            "expiring": buckets,
            "expiring_overdue": overdue,
            "total_alerts": 0,
            "alert_days": EXPIRY_ALERT_DAYS,
        }
    today = date.today()
    rows = db.execute(
        "SELECT d.id, d.doc_type, d.doc_number, d.expiry_date, d.company_id, "
        "c.legal_name AS company_name, c.company_code "
        "FROM company_documents d "
        "JOIN companies c ON d.company_id = c.id "
        "WHERE d.is_active=1 AND d.expiry_date IS NOT NULL AND d.expiry_date != ''"
    ).fetchall()
    for row in rows:
        item = dict(row)
        item["title"] = f"{item.get('doc_type')} — {item.get('company_name')}"
        item["source"] = "company_doc"
        days = _days_until(item.get("expiry_date"), today)
        bucket = _expiry_bucket(days)
        item["days_left"] = days
        if bucket == "overdue":
            overdue.append(item)
        elif bucket:
            buckets[bucket].append(item)
    total = len(overdue) + sum(len(buckets[str(d)]) for d in EXPIRY_ALERT_DAYS)
    return {
        "expiring": buckets,
        "expiring_overdue": overdue,
        "total_alerts": total,
        "alert_days": EXPIRY_ALERT_DAYS,
    }


def sync_company_expiry_notifications(db, notify_fn) -> int:
    """Create in-app notifications for admins when company documents are expiring."""
    alerts = collect_company_expiry_alerts(db)
    if alerts["total_alerts"] == 0:
        return 0
    admin_rows = db.execute(
        "SELECT id FROM users WHERE status='Active' AND ("
        "LOWER(COALESCE(role,'')) IN ('admin','administrator') OR "
        "LOWER(COALESCE(workflow_role,''))='administrator'"
        ")"
    ).fetchall()
    admin_ids = [row[0] for row in admin_rows]
    if not admin_ids:
        return 0
    created = 0
    all_items = list(alerts["expiring_overdue"])
    for threshold in EXPIRY_ALERT_DAYS:
        all_items.extend(alerts["expiring"].get(str(threshold), []))
    seen: set[int] = set()
    for item in all_items:
        doc_id = item.get("id")
        if not doc_id or doc_id in seen:
            continue
        seen.add(doc_id)
        days = item.get("days_left")
        if days is not None and days < 0:
            msg = (
                f"Company document expired: {item.get('doc_type')} "
                f"({item.get('company_name')}) — {item.get('expiry_date')}"
            )
        else:
            msg = (
                f"Company document expiring in {days} days: {item.get('doc_type')} "
                f"({item.get('company_name')}) — {item.get('expiry_date')}"
            )
        for uid in admin_ids:
            existing = db.execute(
                "SELECT id FROM notifications WHERE user_id=? AND record_table='company_documents' "
                "AND record_id=? AND is_read=0",
                (uid, doc_id),
            ).fetchone()
            if existing:
                continue
            notify_fn(
                db,
                uid,
                msg,
                "company_doc_expiry",
                "company_master",
                doc_id,
                "company_documents",
            )
            created += 1
    return created
