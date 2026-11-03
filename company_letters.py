"""MAXEK ERP - Administration -> Company Letters.

Prepared letters (offer letters and general administration letters) kept in their
own table, ``company_letters``. The older Office -> Letter Preparation module and its
``office_letters`` table are left untouched.

Access (enforced in the routes, see ``app.company_letter_access``):
  * the ERP's existing role model - Administrator, workflow roles (Maker prepares,
    Approver issues), department tab grants, guest / base-HR exclusions;
  * the ERP's existing tenant scoping - ``customer_id`` and ``company_id`` on the
    letter and on the staff record used for autofill.

Reference numbers use the ERP's existing document numbering service
(``document_numbering_service``): one counter per financial year (April-March).
A suggestion is made only when the counter, or letters already recorded in the
ERP, establish a sequence; the ERP never assumes a starting number.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import date, datetime
from html import escape
from html.parser import HTMLParser

import document_numbering_service as numbering

DOC_TYPE = "company_letter_no"
PAGE_SIZE = 20
PAGE_SIZES = (10, 20, 50)

# Offer Letter / General Administration Letter first; the older Office letter types
# are offered too so the two modules speak the same vocabulary.
LETTER_TYPES = (
    "Offer Letter",
    "General Administration Letter",
    "Official Letter",
    "Covering Letter",
    "Demand Letter",
    "NOC",
    "Experience Letter",
    "Appointment Letter",
    "Termination Letter",
    "Other",
)
DEFAULT_SALUTATION = "Dear Sir,"
DEFAULT_CLOSING = "Yours faithfully,"
DEFAULT_SIGNATORY_TITLE = "Authorized Signatory"
STATUS_DRAFT = "Draft"
STATUS_ISSUED = "Issued"

# NOTE: there is deliberately no pre-written offer-letter text. The ERP holds no approved
# offer-letter template, so the body is always entered or chosen by the user.


# ───────────────────────────── schema ─────────────────────────────


def ensure_company_letters_schema(db) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS company_letters(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reference_no TEXT NOT NULL,
            letter_date TEXT NOT NULL,
            letter_type TEXT NOT NULL,
            recipient_name TEXT NOT NULL,
            recipient_org TEXT,
            recipient_address TEXT,
            subject TEXT NOT NULL,
            salutation TEXT,
            body_html TEXT NOT NULL,
            closing TEXT,
            signatory_name TEXT NOT NULL,
            signatory_designation TEXT,
            employee_id INTEGER,
            status TEXT NOT NULL DEFAULT 'Draft',
            issued_by TEXT,
            issued_at TEXT,
            customer_id INTEGER,
            company_id INTEGER,
            branch_id INTEGER,
            created_by TEXT,
            created_at TEXT,
            modified_by TEXT,
            modified_at TEXT
        )
        """
    )
    existing = {r[1] for r in db.execute("PRAGMA table_info(company_letters)").fetchall()}
    for col, ctype in (
        ("status", "TEXT NOT NULL DEFAULT 'Draft'"), ("issued_by", "TEXT"), ("issued_at", "TEXT"),
        ("customer_id", "INTEGER"), ("company_id", "INTEGER"), ("branch_id", "INTEGER"),
    ):
        if col not in existing:
            db.execute(f"ALTER TABLE company_letters ADD COLUMN {col} {ctype}")
    # Unique per tenant (NULL tenant = the single-tenant / legacy scope), case/space-insensitive.
    db.execute("DROP INDEX IF EXISTS ux_company_letters_reference")
    db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_company_letters_ref_tenant "
        "ON company_letters(COALESCE(customer_id, 0), LOWER(TRIM(reference_no)))"
    )
    db.execute("CREATE INDEX IF NOT EXISTS ix_company_letters_date ON company_letters(letter_date)")
    numbering.ensure_document_numbering_schema(db)


# ───────────────────────────── scope (tenant / company) ─────────────────────────────


def make_scope(session) -> dict:
    """Tenant scope of the logged-in user, from the same session keys the ERP uses elsewhere."""
    return {
        "customer_id": session.get("customer_id") or None,
        "company_id": session.get("company_id") or None,
        "branch_id": session.get("branch_id") or None,
    }


def _scope_sql(scope: dict | None, alias: str = "") -> tuple[str, list]:
    """Letters visible in ``scope``: same tenant, and same company when one is selected.

    Mirrors ``tenant_isolation.tenant_where_clause``: with no tenant on the session no
    tenant filter applies; with one, rows of other tenants (and untagged rows) are hidden.
    """
    scope = scope or {}
    p = f"{alias}." if alias else ""
    clauses, params = [], []
    if scope.get("customer_id"):
        clauses.append(f"{p}customer_id = ?")
        params.append(scope["customer_id"])
    if scope.get("company_id"):
        clauses.append(f"({p}company_id IS NULL OR {p}company_id = ?)")
        params.append(scope["company_id"])
    return " AND ".join(clauses), params


# ───────────────────────────── HTML sanitising ─────────────────────────────

_ALLOWED_TAGS = {
    "p", "br", "strong", "b", "em", "i", "u", "ul", "ol", "li", "blockquote",
    "h3", "h4", "div", "span", "table", "thead", "tbody", "tr", "th", "td",
}
_VOID = {"br"}
_ALIGN = re.compile(r"text-align\s*:\s*(left|right|center|justify)", re.I)
_DROP_WITH_CONTENT = {"script", "style", "iframe", "object", "embed", "noscript", "template"}


class _Sanitizer(HTMLParser):
    """Allow-list sanitiser: known tags only, no attributes except a text-align style."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.stack: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in _DROP_WITH_CONTENT:
            self.skip += 1
            return
        if self.skip or tag not in _ALLOWED_TAGS:
            return
        style = ""
        for name, value in attrs:
            if name == "style" and value:
                m = _ALIGN.search(value)
                if m:
                    style = f' style="text-align:{m.group(1).lower()}"'
            elif name == "align" and value and value.lower() in ("left", "right", "center", "justify"):
                style = f' style="text-align:{value.lower()}"'
        self.out.append(f"<{tag}{style}>")
        if tag not in _VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        if tag in _VOID and not self.skip:
            self.out.append(f"<{tag}>")

    def handle_endtag(self, tag):
        if tag in _DROP_WITH_CONTENT:
            self.skip = max(self.skip - 1, 0)
            return
        if self.skip or tag not in _ALLOWED_TAGS or tag in _VOID:
            return
        if tag in self.stack:
            while self.stack:
                top = self.stack.pop()
                self.out.append(f"</{top}>")
                if top == tag:
                    break

    def handle_data(self, data):
        if not self.skip:
            self.out.append(escape(data, quote=False))

    def close(self):
        super().close()
        while self.stack:
            self.out.append(f"</{self.stack.pop()}>")


def sanitize_letter_html(raw: str | None) -> str:
    """Return ``raw`` reduced to the small set of safe formatting tags."""
    parser = _Sanitizer()
    parser.feed(raw or "")
    parser.close()
    return "".join(parser.out).strip()


def html_to_text(html: str | None) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", html or "")).strip()




# ───────────────────────────── references ─────────────────────────────
#
# One counter per financial year (April-March), kept in ``document_number_sequences`` by
# the ERP's document numbering service. Rule on year change: a new financial year has its
# own counter row, which starts unconfigured (0); the first letter of that year therefore
# needs its number entered explicitly, and later letters continue from it automatically.


def fiscal_year_for(letter_date: str | None) -> str:
    try:
        d = datetime.strptime(str(letter_date or "")[:10], "%Y-%m-%d").date()
    except ValueError:
        d = date.today()
    return numbering.get_current_fiscal_year(d)


def _sequence(db, letter_date: str | None) -> dict:
    fy = fiscal_year_for(letter_date)
    numbering.seed_default_sequences(db, fy)
    return numbering._sequence_row(db, DOC_TYPE, fy)


def _reference_regex(row: dict) -> re.Pattern:
    sample = numbering.format_document_number(
        row["prefix"], row["fiscal_year"], 987654321, row["format_pattern"]
    )
    return re.compile("^" + re.escape(sample).replace("987654321", r"(\d+)") + "$")


def recorded_references(db, scope: dict | None = None) -> list[str]:
    """Every reference already recorded in the ERP's letter registers."""
    refs: list[str] = []
    where, params = _scope_sql(scope)
    sql = "SELECT reference_no FROM company_letters" + (f" WHERE {where}" if where else "")
    refs += [r[0] for r in db.execute(sql, params).fetchall() if r[0]]
    for table, cols in (("office_letters", ("letter_number", "reference_no")),
                        ("office_outward", ("register_number", "reference_no"))):
        have = {r[1] for r in db.execute(f"PRAGMA table_info({table})").fetchall()}
        for col in cols:
            if col in have:
                refs += [r[0] for r in db.execute(f"SELECT {col} FROM {table}").fetchall() if r[0]]
    return [str(r).strip() for r in refs]


def highest_recorded_sequence(db, row: dict, scope: dict | None = None) -> int:
    rx = _reference_regex(row)
    best = 0
    for ref in recorded_references(db, scope):
        m = rx.match(ref)
        if m:
            best = max(best, int(m.group(1)))
    return best


def suggest_reference(db, letter_date: str | None = None, scope: dict | None = None) -> dict:
    """Suggestion for the next reference, with how it was derived.

    Returns ``{"reference", "configured", "basis", "fiscal_year"}``. ``reference`` is empty,
    and ``configured`` False, when nothing establishes a sequence for the letter's financial
    year - the user must then enter the number from the real letter register.
    """
    row = _sequence(db, letter_date)
    counter = int(row["current_sequence"] or 0)
    recorded = highest_recorded_sequence(db, row, scope)
    base = max(counter, recorded)
    fy = row["fiscal_year"]
    if base <= 0:
        return {
            "reference": "", "configured": False, "fiscal_year": fy,
            "basis": (
                f"No letter number is recorded for financial year {fy} yet. Enter the next number "
                "from your letter register; later letters will continue from it."
            ),
        }
    last = numbering.format_document_number(row["prefix"], fy, base, row["format_pattern"])
    nxt = numbering.format_document_number(row["prefix"], fy, base + 1, row["format_pattern"])
    return {
        "reference": nxt, "configured": True, "fiscal_year": fy,
        "basis": f"Continues from {last} (highest number recorded for financial year {fy}). Check it against your register.",
    }


def reference_exists(db, reference_no: str, exclude_id: int | None = None, scope: dict | None = None) -> bool:
    sql = "SELECT 1 FROM company_letters WHERE LOWER(TRIM(reference_no)) = LOWER(TRIM(?))"
    params: list = [reference_no]
    cust = (scope or {}).get("customer_id")
    sql += " AND COALESCE(customer_id, 0) = ?"
    params.append(cust or 0)
    if exclude_id:
        sql += " AND id <> ?"
        params.append(exclude_id)
    return db.execute(sql, params).fetchone() is not None


def _begin_write(db) -> None:
    """Take SQLite's write lock before reading, so two saves cannot read the same state."""
    if db.in_transaction:
        db.commit()  # only schema/seed writes can be pending here; never hold a read snapshot
    db.execute("BEGIN IMMEDIATE")


def allocate_reference(db, letter_date: str | None, scope: dict | None = None) -> str:
    """Atomically take the next number. Call inside the transaction that inserts the letter."""
    _begin_write(db)
    row = _sequence(db, letter_date)
    recorded = highest_recorded_sequence(db, row, scope)
    if max(int(row["current_sequence"] or 0), recorded) <= 0:
        raise ValueError(
            f"No starting number is recorded for financial year {row['fiscal_year']}. "
            "Enter the reference number manually; later letters will continue from it."
        )
    for _ in range(100):
        db.execute(
            "UPDATE document_number_sequences SET current_sequence = MAX(current_sequence, ?) + 1, "
            "last_generated_at = ? WHERE doc_type = ? AND fiscal_year = ?",
            (recorded, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), DOC_TYPE, row["fiscal_year"]),
        )
        seq = db.execute(
            "SELECT current_sequence FROM document_number_sequences WHERE doc_type=? AND fiscal_year=?",
            (DOC_TYPE, row["fiscal_year"]),
        ).fetchone()[0]
        ref = numbering.format_document_number(row["prefix"], row["fiscal_year"], int(seq), row["format_pattern"])
        if not reference_exists(db, ref, scope=scope):
            return ref
    raise ValueError("Could not allocate a free reference number; please enter one manually.")


def note_manual_reference(db, reference_no: str, letter_date: str | None) -> None:
    """A hand-entered number in the ERP's format moves the counter forward (never back)."""
    row = _sequence(db, letter_date)
    m = _reference_regex(row).match((reference_no or "").strip())
    if m and int(m.group(1)) > int(row["current_sequence"] or 0):
        _begin_write(db)
        db.execute(
            "UPDATE document_number_sequences SET current_sequence = ?, last_generated_at = ? "
            "WHERE doc_type = ? AND fiscal_year = ? AND current_sequence < ?",
            (int(m.group(1)), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), DOC_TYPE,
             row["fiscal_year"], int(m.group(1))),
        )


# ───────────────────────────── queries ─────────────────────────────


def list_letters(
    db,
    *,
    scope: dict | None = None,
    query: str = "",
    letter_type: str = "",
    page: int = 1,
    per_page: int = PAGE_SIZE,
) -> dict:
    where, params = [], []
    sc, sp = _scope_sql(scope)
    if sc:
        where.append(sc)
        params += sp
    q = (query or "").strip()
    if q:
        like = f"%{q}%"
        where.append(
            "(reference_no LIKE ? OR recipient_name LIKE ? OR recipient_org LIKE ? "
            "OR subject LIKE ? OR letter_type LIKE ?)"
        )
        params += [like] * 5
    if letter_type:
        where.append("letter_type = ?")
        params.append(letter_type)
    clause = f" WHERE {' AND '.join(where)}" if where else ""
    per_page = per_page if per_page in PAGE_SIZES else PAGE_SIZE
    total = db.execute(f"SELECT COUNT(*) FROM company_letters{clause}", params).fetchone()[0]
    pages = max((total + per_page - 1) // per_page, 1)
    page = min(max(int(page or 1), 1), pages)
    rows = db.execute(
        f"SELECT * FROM company_letters{clause} ORDER BY letter_date DESC, id DESC LIMIT ? OFFSET ?",
        [*params, per_page, (page - 1) * per_page],
    ).fetchall()
    return {"rows": [dict(r) for r in rows], "total": total, "page": page, "pages": pages, "per_page": per_page}


def get_letter(db, letter_id: int, scope: dict | None = None) -> dict | None:
    """One letter, or None if it does not exist *or is outside the user's tenant/company*."""
    where, params = _scope_sql(scope)
    sql = "SELECT * FROM company_letters WHERE id=?" + (f" AND {where}" if where else "")
    row = db.execute(sql, [letter_id, *params]).fetchone()
    return dict(row) if row else None


def recent_letters(db, scope: dict | None = None, limit: int = 30) -> list[dict]:
    where, params = _scope_sql(scope)
    sql = ("SELECT id, reference_no, letter_type, subject, letter_date FROM company_letters"
           + (f" WHERE {where}" if where else "") + " ORDER BY id DESC LIMIT ?")
    return [dict(r) for r in db.execute(sql, [*params, limit]).fetchall()]


def last_signatory(db, scope: dict | None = None) -> tuple[str, str]:
    where, params = _scope_sql(scope)
    sql = ("SELECT signatory_name, signatory_designation FROM company_letters "
           "WHERE TRIM(COALESCE(signatory_name,'')) <> ''" + (f" AND {where}" if where else "")
           + " ORDER BY id DESC LIMIT 1")
    row = db.execute(sql, params).fetchone()
    return (row[0], row[1] or DEFAULT_SIGNATORY_TITLE) if row else ("", DEFAULT_SIGNATORY_TITLE)


# ───────────────────────────── employees ─────────────────────────────


def _staff_columns(db) -> set[str]:
    return {r[1] for r in db.execute("PRAGMA table_info(staff)").fetchall()}


def _staff_scope_sql(db, scope: dict | None) -> tuple[str, list]:
    """Same tenant / company / branch restriction the ERP puts on staff records
    (see ``tenant_isolation``): other tenants' staff are never offered."""
    scope = scope or {}
    cols = _staff_columns(db)
    clauses, params = [], []
    if scope.get("customer_id") and "customer_id" in cols:
        clauses.append("customer_id = ?")
        params.append(scope["customer_id"])
    if scope.get("company_id") and "company_id" in cols:
        clauses.append("(company_id IS NULL OR company_id = ?)")
        params.append(scope["company_id"])
    if scope.get("branch_id") and "branch_id" in cols:
        clauses.append("(branch_id IS NULL OR branch_id = ?)")
        params.append(scope["branch_id"])
    return " AND ".join(clauses), params


def search_employees(db, query: str = "", limit: int = 15, scope: dict | None = None) -> list[dict]:
    """Staff matching a name/code fragment within the user's scope (past staff included)."""
    q = (query or "").strip()
    like = f"%{q}%"
    sc, sp = _staff_scope_sql(db, scope)
    rows = db.execute(
        "SELECT id, staff_name, employee_code, designation, department, status FROM staff "
        "WHERE (? = '' OR staff_name LIKE ? OR employee_code LIKE ?)" + (f" AND {sc}" if sc else "")
        + " ORDER BY staff_name LIMIT ?",
        [q, like, like, *sp, limit],
    ).fetchall()
    return [dict(r) for r in rows]


def employee_details(db, employee_id: int, scope: dict | None = None) -> dict | None:
    """Facts about one in-scope staff member that can pre-fill a letter.

    Only facts are returned (name, designation, joining date, ...): never salary and never
    pre-written terms.
    """
    sc, sp = _staff_scope_sql(db, scope)
    row = db.execute("SELECT * FROM staff WHERE id=?" + (f" AND {sc}" if sc else ""), [employee_id, *sp]).fetchone()
    if not row:
        return None
    staff = dict(row)
    cols = _staff_columns(db)
    address = ""
    for col in ("address", "permanent_address", "current_address", "residential_address"):
        if col in cols and str(staff.get(col) or "").strip():
            address = str(staff[col]).strip()
            break
    designation = str(staff.get("designation") or "").strip()
    department = str(staff.get("department") or "").strip()
    joining = str(staff.get("joining_date") or "").strip()[:10]
    name = str(staff.get("staff_name") or "").strip()
    code = str(staff.get("employee_code") or "").strip()
    facts = [f"Name: {name}"]
    if code:
        facts.append(f"Employee code: {code}")
    if designation:
        facts.append(f"Designation: {designation}")
    if department:
        facts.append(f"Department: {department}")
    if _display_date(joining):
        facts.append(f"Date of joining: {_display_date(joining)}")
    return {
        "id": staff["id"],
        "name": name,
        "employee_code": code,
        "designation": designation,
        "department": department,
        "joining_date": joining,
        "joining_date_display": _display_date(joining),
        "mobile": str(staff.get("mobile") or "").strip(),
        "email": str(staff.get("email") or "").strip(),
        "address": address,
        "recipient_org": ", ".join(p for p in (designation, department) if p),
        "salutation": f"Dear {name}," if name else DEFAULT_SALUTATION,
        # Facts only, for the user to place wherever they belong; no terms are written here.
        "facts_html": "".join(f"<p>{escape(f)}</p>" for f in facts),
    }


def _display_date(iso: str | None) -> str:
    try:
        return datetime.strptime(str(iso or "")[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return ""


def display_date(iso: str | None) -> str:
    return _display_date(iso) or (iso or "")


# ───────────────────────────── save / issue ─────────────────────────────


def _clean(form, key: str) -> str:
    return (form.get(key) or "").strip()


def validate_letter_form(db, form, record_id: int | None = None, scope: dict | None = None) -> tuple[dict, list[str]]:
    """Return ``(values, errors)``. Nothing is written.

    ``values["reference_auto"]`` is True for a new letter whose number should be allocated
    at save time (blank, or still equal to the suggestion the form was opened with).
    """
    errors: list[str] = []
    values = {
        "reference_no": _clean(form, "reference_no"),
        "letter_date": _clean(form, "letter_date"),
        "letter_type": _clean(form, "letter_type"),
        "recipient_name": _clean(form, "recipient_name"),
        "recipient_org": _clean(form, "recipient_org"),
        "recipient_address": (form.get("recipient_address") or "").strip(),
        "subject": _clean(form, "subject"),
        "salutation": _clean(form, "salutation") or DEFAULT_SALUTATION,
        "body_html": sanitize_letter_html(form.get("body_html")),
        "closing": _clean(form, "closing") or DEFAULT_CLOSING,
        "signatory_name": _clean(form, "signatory_name"),
        "signatory_designation": _clean(form, "signatory_designation") or DEFAULT_SIGNATORY_TITLE,
    }
    suggested = _clean(form, "suggested_reference")
    values["reference_auto"] = (not record_id) and (
        not values["reference_no"] or (bool(suggested) and values["reference_no"] == suggested)
    )
    emp = _clean(form, "employee_id")
    values["employee_id"] = int(emp) if emp.isdigit() else None
    if values["employee_id"] is not None and employee_details(db, values["employee_id"], scope) is None:
        errors.append("The selected employee was not found in your company.")
        values["employee_id"] = None

    if not values["letter_date"]:
        errors.append("Letter date is required.")
    else:
        try:
            datetime.strptime(values["letter_date"], "%Y-%m-%d")
        except ValueError:
            errors.append("Letter date is not a valid date.")
    if values["letter_type"] not in LETTER_TYPES:
        errors.append("Choose a valid letter type.")
    if not values["recipient_name"]:
        errors.append("Recipient name is required.")
    if not values["subject"]:
        errors.append("Subject is required.")
    if not html_to_text(values["body_html"]):
        errors.append("The letter body cannot be empty: enter the content, or choose an earlier letter to copy from.")
    if not values["signatory_name"]:
        errors.append("Authorized signatory name is required.")
    if values["reference_auto"]:
        pass  # allocated atomically when saving
    elif not values["reference_no"]:
        errors.append("Reference number is required.")
    elif len(values["reference_no"]) > 60:
        errors.append("Reference number is too long (60 characters maximum).")
    elif reference_exists(db, values["reference_no"], record_id, scope):
        errors.append(f"Reference number {values['reference_no']} is already used by another letter.")
    return values, errors


def save_letter(db, values: dict, username: str, record_id: int | None = None, scope: dict | None = None) -> tuple[int, str]:
    """Insert or update a validated letter inside the caller's transaction.

    Returns ``(letter_id, reference_no)``. Raises ``ValueError`` on a reference clash or
    when a number cannot be allocated. Any edit returns a letter to Draft: it must be
    issued again after the new content has been confirmed.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cols = (
        "reference_no", "letter_date", "letter_type", "recipient_name", "recipient_org",
        "recipient_address", "subject", "salutation", "body_html", "closing",
        "signatory_name", "signatory_designation", "employee_id",
    )
    values = dict(values)
    try:
        if record_id:
            data = [values[c] for c in cols]
            db.execute(
                f"UPDATE company_letters SET {', '.join(c + '=?' for c in cols)}, status=?, issued_by=NULL, "
                "issued_at=NULL, modified_by=?, modified_at=? WHERE id=?",
                [*data, STATUS_DRAFT, username, now, record_id],
            )
            return record_id, values["reference_no"]
        if values.get("reference_auto"):
            values["reference_no"] = allocate_reference(db, values["letter_date"], scope)
        else:
            note_manual_reference(db, values["reference_no"], values["letter_date"])
        data = [values[c] for c in cols]
        scope = scope or {}
        db.execute(
            f"INSERT INTO company_letters({', '.join(cols)}, status, customer_id, company_id, branch_id, "
            "created_by, created_at, modified_by, modified_at) "
            f"VALUES({','.join('?' * len(cols))},?,?,?,?,?,?,?,?)",
            [*data, STATUS_DRAFT, scope.get("customer_id"), scope.get("company_id"), scope.get("branch_id"),
             username, now, username, now],
        )
    except sqlite3.IntegrityError as exc:  # someone else took the same number first
        raise ValueError(
            f"Reference number {values['reference_no']} is already used by another letter."
        ) from exc
    return int(db.execute("SELECT last_insert_rowid()").fetchone()[0]), values["reference_no"]


def issue_letter(db, letter_id: int, username: str, confirmed: bool, scope: dict | None = None) -> None:
    """Mark a letter Issued. The user must confirm the saved content is what is intended."""
    letter = get_letter(db, letter_id, scope)
    if not letter:
        raise ValueError("Letter not found.")
    if not confirmed:
        raise ValueError("Tick the confirmation to issue: you must confirm the letter content is the content intended for issue.")
    if not html_to_text(letter["body_html"]):
        raise ValueError("A letter with no content cannot be issued.")
    db.execute(
        "UPDATE company_letters SET status=?, issued_by=?, issued_at=? WHERE id=?",
        (STATUS_ISSUED, username, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), letter_id),
    )



# ───────────────────────────── rendering helpers ─────────────────────────────


class _BlockSplitter(HTMLParser):
    """Split sanitised HTML into its top-level blocks so each can be its own table row
    (lets the printed page break between paragraphs and keeps the layout predictable)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.blocks: list[str] = []
        self.cur: list[str] = []
        self.depth = 0

    def _flush(self, wrap: bool = False):
        text = "".join(self.cur).strip()
        self.cur = []
        if text:
            self.blocks.append(f"<p>{text}</p>" if wrap else text)

    def handle_starttag(self, tag, attrs):
        if tag == "br" and self.depth == 0:
            self.cur.append("<br>")
            return
        if self.depth == 0 and self.cur:
            self._flush(wrap=True)
        self.cur.append(self.get_starttag_text())
        if tag not in _VOID:
            self.depth += 1

    def handle_endtag(self, tag):
        if tag in _VOID:
            return
        self.cur.append(f"</{tag}>")
        self.depth = max(self.depth - 1, 0)
        if self.depth == 0:
            self._flush()

    def handle_data(self, data):
        self.cur.append(data)

    def handle_entityref(self, name):
        self.cur.append(f"&{name};")

    def handle_charref(self, name):
        self.cur.append(f"&#{name};")

    def close(self):
        super().close()
        self._flush(wrap=True)


def split_blocks(html: str | None) -> list[str]:
    splitter = _BlockSplitter()
    splitter.feed(sanitize_letter_html(html))
    splitter.close()
    return [b for b in splitter.blocks if html_to_text(b) or "<table" in b or "<br" in b]
