"""Master document numbering — unique auto-generated numbers per document type and fiscal year."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOC_TYPES = (
    "tender_no",
    "project_no",
    "boq_no",
    "dpr_no",
    "pr_no",
    "po_no",
    "grn_no",
    "store_issue_no",
    "bill_no",
    "payment_voucher_no",
    "receipt_voucher_no",
    "bg_no",
    "company_letter_no",
)

DOC_TYPE_LABELS: dict[str, str] = {
    "tender_no": "Tender No",
    "project_no": "Project No",
    "boq_no": "BOQ No",
    "dpr_no": "DPR No",
    "pr_no": "PR No",
    "po_no": "PO No",
    "grn_no": "GRN No",
    "store_issue_no": "Store Issue No",
    "bill_no": "Bill No",
    "payment_voucher_no": "Payment Voucher No",
    "receipt_voucher_no": "Receipt Voucher No",
    "bg_no": "BG No",
    "company_letter_no": "Company Letter No",
}

DEFAULT_PREFIXES: dict[str, str] = {
    "tender_no": "TND",
    "project_no": "PRJ",
    "boq_no": "BOQ",
    "dpr_no": "DPR",
    "pr_no": "PR",
    "po_no": "PO",
    "grn_no": "GRN",
    "store_issue_no": "SI",
    "bill_no": "BILL",
    "payment_voucher_no": "PV",
    "receipt_voucher_no": "RV",
    "bg_no": "BG",
    "company_letter_no": "MAX/LET",
}

DEFAULT_FORMAT_PATTERN = "{prefix}/{fy}/{seq:04d}"

# Types whose default layout differs from DEFAULT_FORMAT_PATTERN. ``{yy}`` is the two-digit
# year in which the financial year starts (2026-27 -> 26).
DEFAULT_PATTERNS: dict[str, str] = {
    "company_letter_no": "{prefix}/{yy}/{seq:03d}",
}


def _table_exists(db, table: str) -> bool:
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_current_fiscal_year(ref: date | None = None) -> str:
    """Indian fiscal year label, e.g. 2025-26 (April–March)."""
    ref = ref or date.today()
    if ref.month >= 4:
        start_year = ref.year
    else:
        start_year = ref.year - 1
    end_short = str(start_year + 1)[-2:]
    return f"{start_year:04d}-{end_short}"


def fiscal_year_short(fiscal_year: str) -> str:
    """Compact FY token for patterns, e.g. 2025-26 -> 2526."""
    text = (fiscal_year or "").strip()
    if "-" in text:
        parts = text.split("-", 1)
        if len(parts) == 2 and len(parts[0]) == 4:
            return parts[0][-2:] + parts[1].zfill(2)[-2:]
    return text.replace("-", "")


def ensure_document_numbering_schema(db) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS document_number_sequences(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_type TEXT NOT NULL,
            prefix TEXT NOT NULL,
            current_sequence INTEGER NOT NULL DEFAULT 0,
            fiscal_year TEXT NOT NULL,
            format_pattern TEXT NOT NULL DEFAULT '{prefix}/{fy}/{seq:04d}',
            last_generated_at TEXT,
            UNIQUE(doc_type, fiscal_year)
        )
        """
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_doc_num_seq_type "
        "ON document_number_sequences(doc_type)"
    )


def seed_default_sequences(db, fiscal_year: str | None = None) -> None:
    """Ensure default prefix/pattern rows exist for every doc type in the current FY."""
    ensure_document_numbering_schema(db)
    fy = fiscal_year or get_current_fiscal_year()
    ts = _now_ts()
    for doc_type in DOC_TYPES:
        existing = db.execute(
            "SELECT id FROM document_number_sequences WHERE doc_type=? AND fiscal_year=?",
            (doc_type, fy),
        ).fetchone()
        if existing:
            continue
        db.execute(
            """
            INSERT INTO document_number_sequences(
                doc_type, prefix, current_sequence, fiscal_year,
                format_pattern, last_generated_at
            ) VALUES(?,?,0,?,?,?)
            """,
            (
                doc_type,
                DEFAULT_PREFIXES.get(doc_type, doc_type.upper()[:3]),
                fy,
                DEFAULT_PATTERNS.get(doc_type, DEFAULT_FORMAT_PATTERN),
                ts,
            ),
        )


def _validate_doc_type(doc_type: str) -> str:
    key = (doc_type or "").strip().lower()
    if key not in DOC_TYPES:
        raise ValueError(f"Unknown document type: {doc_type}")
    return key


def _sequence_row(db, doc_type: str, fiscal_year: str) -> dict:
    row = db.execute(
        "SELECT * FROM document_number_sequences WHERE doc_type=? AND fiscal_year=?",
        (doc_type, fiscal_year),
    ).fetchone()
    if not row:
        seed_default_sequences(db, fiscal_year)
        row = db.execute(
            "SELECT * FROM document_number_sequences WHERE doc_type=? AND fiscal_year=?",
            (doc_type, fiscal_year),
        ).fetchone()
    if not row:
        raise ValueError(f"Unable to initialize sequence for {doc_type}")
    return dict(row)


def format_document_number(
    prefix: str,
    fiscal_year: str,
    sequence: int,
    pattern: str | None = None,
) -> str:
    pat = (pattern or DEFAULT_FORMAT_PATTERN).strip()
    fy = fiscal_year_short(fiscal_year)
    digits = "".join(ch for ch in (fiscal_year or "") if ch.isdigit())     # 2026-27 / CY2026 -> 2026...
    yy = digits[2:4] if len(digits) >= 4 else fy[:2]
    return pat.format(prefix=prefix, fy=fy, yy=yy, fiscal_year=fiscal_year, seq=sequence)


def peek_next_number(
    db,
    doc_type: str,
    *,
    fiscal_year: str | None = None,
) -> str:
    """Preview the next formatted number without consuming the sequence."""
    key = _validate_doc_type(doc_type)
    fy = fiscal_year or get_current_fiscal_year()
    row = _sequence_row(db, key, fy)
    next_seq = int(row["current_sequence"] or 0) + 1
    return format_document_number(
        row["prefix"],
        row["fiscal_year"],
        next_seq,
        row["format_pattern"],
    )


def get_next_number(
    db,
    doc_type: str,
    *,
    fiscal_year: str | None = None,
) -> str:
    """Atomically increment and return the next formatted document number."""
    key = _validate_doc_type(doc_type)
    fy = fiscal_year or get_current_fiscal_year()
    _sequence_row(db, key, fy)
    ts = _now_ts()
    db.execute(
        """
        UPDATE document_number_sequences
        SET current_sequence = current_sequence + 1,
            last_generated_at = ?
        WHERE doc_type = ? AND fiscal_year = ?
        """,
        (ts, key, fy),
    )
    row = db.execute(
        "SELECT * FROM document_number_sequences WHERE doc_type=? AND fiscal_year=?",
        (key, fy),
    ).fetchone()
    if not row:
        raise ValueError(f"Sequence row missing after increment for {key}")
    data = dict(row)
    return format_document_number(
        data["prefix"],
        data["fiscal_year"],
        int(data["current_sequence"]),
        data["format_pattern"],
    )


def integrate_next_number(
    db,
    doc_type: str,
    form_value: str | None = None,
    *,
    fiscal_year: str | None = None,
) -> str:
    """
    Hook for other services: use manual number when provided, otherwise allocate next.

    Example:
        bg_number = integrate_next_number(db, "bg_no", form.get("bg_number"))
    """
    manual = (form_value or "").strip()
    if manual:
        return manual
    return get_next_number(db, doc_type, fiscal_year=fiscal_year)


def list_sequences(db, fiscal_year: str | None = None) -> list[dict[str, Any]]:
    ensure_document_numbering_schema(db)
    fy = fiscal_year or get_current_fiscal_year()
    seed_default_sequences(db, fy)
    rows = db.execute(
        """
        SELECT * FROM document_number_sequences
        WHERE fiscal_year=?
        ORDER BY doc_type
        """,
        (fy,),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["label"] = DOC_TYPE_LABELS.get(item["doc_type"], item["doc_type"])
        item["next_preview"] = format_document_number(
            item["prefix"],
            item["fiscal_year"],
            int(item["current_sequence"] or 0) + 1,
            item["format_pattern"],
        )
        item["last_number"] = (
            format_document_number(
                item["prefix"],
                item["fiscal_year"],
                int(item["current_sequence"]),
                item["format_pattern"],
            )
            if int(item["current_sequence"] or 0) > 0
            else "—"
        )
        out.append(item)
    return out


def get_sequence_config(db, doc_type: str, fiscal_year: str | None = None) -> dict | None:
    key = _validate_doc_type(doc_type)
    fy = fiscal_year or get_current_fiscal_year()
    seed_default_sequences(db, fy)
    row = db.execute(
        "SELECT * FROM document_number_sequences WHERE doc_type=? AND fiscal_year=?",
        (key, fy),
    ).fetchone()
    if not row:
        return None
    item = dict(row)
    item["label"] = DOC_TYPE_LABELS.get(key, key)
    item["next_preview"] = peek_next_number(db, key, fiscal_year=fy)
    return item


def update_sequence_config(
    db,
    doc_type: str,
    *,
    prefix: str,
    format_pattern: str,
    fiscal_year: str | None = None,
) -> None:
    key = _validate_doc_type(doc_type)
    fy = fiscal_year or get_current_fiscal_year()
    prefix = (prefix or "").strip().upper()
    pattern = (format_pattern or DEFAULT_FORMAT_PATTERN).strip()
    if not prefix:
        raise ValueError("Prefix is required.")
    if "{seq" not in pattern:
        raise ValueError("Format pattern must include a {seq} placeholder (e.g. {seq:04d}).")
    seed_default_sequences(db, fy)
    db.execute(
        """
        UPDATE document_number_sequences
        SET prefix=?, format_pattern=?
        WHERE doc_type=? AND fiscal_year=?
        """,
        (prefix, pattern, key, fy),
    )
    if db.execute("SELECT changes()").fetchone()[0] == 0:
        raise ValueError("Sequence configuration not found.")
