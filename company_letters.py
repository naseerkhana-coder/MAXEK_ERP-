"""MAXEK ERP - Administration -> Company Letters.

Prepared letters (offer letters and general administration letters) kept in their
own table, ``company_letters``. The older Office -> Letter Preparation module and its
``office_letters`` table are left untouched.

Reference numbers follow the company's own format (see the sample letter
``MAX/LT/26/116``): ``MAX/LT/<yy>/<nnn>``. The next number is suggested on the
form and can be overridden; uniqueness is enforced by the database and checked
before saving.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from html import escape
from html.parser import HTMLParser

REFERENCE_PREFIX = "MAX/LT"
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

OFFER_LETTER_BODY = (
    "<p>With reference to the discussions we have had with you, we are pleased to offer you "
    "the position of <strong>{designation}</strong> at MAXEK Private Limited.</p>"
    "<p>Your date of joining will be <strong>{joining_date}</strong>. Your monthly "
    "remuneration and other terms of employment will be as set out in the annexure to this letter "
    "[monthly salary to be confirmed].</p>"
    "<p>Please confirm your acceptance by signing and returning a copy of this letter.</p>"
    "<p>We look forward to welcoming you to the team.</p>"
)


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
            created_by TEXT,
            created_at TEXT,
            modified_by TEXT,
            modified_at TEXT
        )
        """
    )
    db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_company_letters_reference "
        "ON company_letters(LOWER(TRIM(reference_no)))"
    )
    db.execute("CREATE INDEX IF NOT EXISTS ix_company_letters_date ON company_letters(letter_date)")


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


def _two_digit_year(letter_date: str | None) -> str:
    try:
        return datetime.strptime(str(letter_date or "")[:10], "%Y-%m-%d").strftime("%y")
    except ValueError:
        return date.today().strftime("%y")


def suggest_reference(db, letter_date: str | None = None) -> str:
    """Next ``MAX/LT/<yy>/<nnn>`` after the highest existing number for that year."""
    yy = _two_digit_year(letter_date)
    base = f"{REFERENCE_PREFIX}/{yy}/"
    highest = 0
    for (ref,) in db.execute(
        "SELECT reference_no FROM company_letters WHERE reference_no LIKE ?", (f"{base}%",)
    ).fetchall():
        m = re.fullmatch(re.escape(base) + r"(\d+)", str(ref or "").strip())
        if m:
            highest = max(highest, int(m.group(1)))
    return f"{base}{highest + 1:03d}"


def reference_exists(db, reference_no: str, exclude_id: int | None = None) -> bool:
    sql = "SELECT 1 FROM company_letters WHERE LOWER(TRIM(reference_no)) = LOWER(TRIM(?))"
    params: list = [reference_no]
    if exclude_id:
        sql += " AND id <> ?"
        params.append(exclude_id)
    return db.execute(sql, params).fetchone() is not None


# ───────────────────────────── queries ─────────────────────────────


def list_letters(
    db,
    *,
    query: str = "",
    letter_type: str = "",
    page: int = 1,
    per_page: int = PAGE_SIZE,
) -> dict:
    where, params = [], []
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
    return {
        "rows": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "pages": pages,
        "per_page": per_page,
    }


def get_letter(db, letter_id: int) -> dict | None:
    row = db.execute("SELECT * FROM company_letters WHERE id=?", (letter_id,)).fetchone()
    return dict(row) if row else None


def last_signatory(db) -> tuple[str, str]:
    row = db.execute(
        "SELECT signatory_name, signatory_designation FROM company_letters "
        "WHERE TRIM(COALESCE(signatory_name,'')) <> '' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return (row[0], row[1] or DEFAULT_SIGNATORY_TITLE) if row else ("", DEFAULT_SIGNATORY_TITLE)


# ───────────────────────────── employees ─────────────────────────────


def _staff_columns(db) -> set[str]:
    return {r[1] for r in db.execute("PRAGMA table_info(staff)").fetchall()}


def search_employees(db, query: str = "", limit: int = 15) -> list[dict]:
    """Staff matching a name/code fragment (all statuses: letters go to past staff too)."""
    q = (query or "").strip()
    like = f"%{q}%"
    rows = db.execute(
        "SELECT id, staff_name, employee_code, designation, department, status FROM staff "
        "WHERE (? = '' OR staff_name LIKE ? OR employee_code LIKE ?) "
        "ORDER BY staff_name LIMIT ?",
        (q, like, like, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def employee_details(db, employee_id: int) -> dict | None:
    """Details of one staff member that can pre-fill a letter. Only what exists is returned."""
    row = db.execute("SELECT * FROM staff WHERE id=?", (employee_id,)).fetchone()
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
    return {
        "id": staff["id"],
        "name": name,
        "employee_code": str(staff.get("employee_code") or "").strip(),
        "designation": designation,
        "department": department,
        "joining_date": joining,
        "joining_date_display": _display_date(joining),
        "mobile": str(staff.get("mobile") or "").strip(),
        "email": str(staff.get("email") or "").strip(),
        "address": address,
        "recipient_org": ", ".join(p for p in (designation, department) if p),
        "salutation": f"Dear {name}," if name else DEFAULT_SALUTATION,
        "offer_body_html": OFFER_LETTER_BODY.format(
            designation=escape(designation or "[designation]"),
            joining_date=escape(_display_date(joining) or "[date of joining]"),
        ),
    }


def _display_date(iso: str | None) -> str:
    try:
        return datetime.strptime(str(iso or "")[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return ""


def display_date(iso: str | None) -> str:
    return _display_date(iso) or (iso or "")


# ───────────────────────────── save ─────────────────────────────


def _clean(form, key: str) -> str:
    return (form.get(key) or "").strip()


def validate_letter_form(db, form, record_id: int | None = None) -> tuple[dict, list[str]]:
    """Return ``(values, errors)``. Nothing is written."""
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
    emp = _clean(form, "employee_id")
    values["employee_id"] = int(emp) if emp.isdigit() else None
    if values["employee_id"] is not None and not db.execute(
        "SELECT 1 FROM staff WHERE id=?", (values["employee_id"],)
    ).fetchone():
        errors.append("The selected employee no longer exists.")
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
        errors.append("The letter body cannot be empty.")
    if not values["signatory_name"]:
        errors.append("Authorized signatory name is required.")
    if not values["reference_no"]:
        errors.append("Reference number is required.")
    elif len(values["reference_no"]) > 60:
        errors.append("Reference number is too long (60 characters maximum).")
    elif reference_exists(db, values["reference_no"], record_id):
        errors.append(f"Reference number {values['reference_no']} is already used by another letter.")
    return values, errors


def save_letter(db, values: dict, username: str, record_id: int | None = None) -> int:
    """Insert or update a validated letter. Raises ``ValueError`` on a reference clash."""
    import sqlite3

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cols = (
        "reference_no", "letter_date", "letter_type", "recipient_name", "recipient_org",
        "recipient_address", "subject", "salutation", "body_html", "closing",
        "signatory_name", "signatory_designation", "employee_id",
    )
    data = [values[c] for c in cols]
    try:
        if record_id:
            db.execute(
                f"UPDATE company_letters SET {', '.join(c + '=?' for c in cols)}, "
                "modified_by=?, modified_at=? WHERE id=?",
                [*data, username, now, record_id],
            )
            return record_id
        db.execute(
            f"INSERT INTO company_letters({', '.join(cols)}, created_by, created_at, modified_by, modified_at) "
            f"VALUES({','.join('?' * len(cols))},?,?,?,?)",
            [*data, username, now, username, now],
        )
    except sqlite3.IntegrityError as exc:  # a concurrent save took the same number
        raise ValueError(
            f"Reference number {values['reference_no']} is already used by another letter."
        ) from exc
    return int(db.execute("SELECT last_insert_rowid()").fetchone()[0])


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
