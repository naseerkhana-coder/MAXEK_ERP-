"""Correspondence / letter management — database layer."""

from __future__ import annotations

import json
from datetime import datetime

import pandas as pd

from modules.database import (
    DATE_FMT,
    generate_id,
    get_conn,
    load_project_names,
    next_document_number,
)

RECEIVED_THROUGH = ["Email", "Courier", "Hand Delivery", "Registered Post", "WhatsApp"]
SENT_THROUGH = ["Email", "Courier", "Hand Delivery", "Registered Post"]
PRIORITIES = ["Low", "Medium", "High", "Urgent"]
INWARD_STATUSES = ["Received", "Under Review", "Reply Pending", "Reply Sent", "Closed"]
OUTWARD_STATUSES = ["Draft", "Pending Approval", "Approved", "Sent", "Acknowledged", "Closed"]
DRAFT_STATUSES = ["Draft", "Pending Dept", "Pending GM", "Pending MD", "Approved", "Rejected"]
LETTER_TEMPLATES = [
    "Company Letter",
    "Client Letter",
    "Consultant Letter",
    "Government Letter",
    "Subcontractor Letter",
    "Vendor Letter",
    "Employee Letter",
]
AUTHORITY_TYPES = [
    "Municipality",
    "Panchayat",
    "Electricity Board",
    "Water Authority",
    "Labour Department",
    "Fire & Safety",
    "Pollution Control Board",
    "Other",
]
DEPARTMENTS = ["Admin", "Accounts", "Projects", "HR", "Store", "Management", "Site"]


def _ts():
    return datetime.now().strftime("%d/%m/%Y %H:%M")


def ensure_correspondence_tables(conn=None):
    own = conn is None
    if own:
        conn = get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS correspondence_inward(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inward_id TEXT UNIQUE,
            inward_no TEXT UNIQUE,
            date_received TEXT,
            received_through TEXT,
            from_party TEXT,
            contact_number TEXT,
            email_id TEXT,
            subject TEXT,
            project_related INTEGER DEFAULT 0,
            project_name TEXT,
            department TEXT,
            priority TEXT DEFAULT 'Medium',
            description TEXT,
            attachment TEXT,
            assigned_to TEXT,
            due_date TEXT,
            status TEXT DEFAULT 'Received',
            related_outward_no TEXT,
            source_email_uid TEXT,
            is_void INTEGER DEFAULT 0,
            created_by TEXT,
            created_at TEXT,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS correspondence_outward(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            outward_id TEXT UNIQUE,
            outward_no TEXT UNIQUE,
            date_sent TEXT,
            recipient TEXT,
            subject TEXT,
            related_inward_no TEXT,
            project_name TEXT,
            sent_by TEXT,
            sent_through TEXT,
            attachment TEXT,
            delivery_proof TEXT,
            letter_content TEXT,
            template_type TEXT,
            reference_number TEXT,
            status TEXT DEFAULT 'Draft',
            is_void INTEGER DEFAULT 0,
            created_by TEXT,
            created_at TEXT,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS correspondence_drafts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            draft_id TEXT UNIQUE,
            letter_no TEXT,
            draft_date TEXT,
            template_type TEXT,
            recipient_to TEXT,
            subject TEXT,
            reference_number TEXT,
            project_name TEXT,
            letter_content TEXT,
            attachment TEXT,
            related_inward_no TEXT,
            status TEXT DEFAULT 'Draft',
            dept_approved_by TEXT,
            dept_approved_at TEXT,
            gm_approved_by TEXT,
            gm_approved_at TEXT,
            md_approved_by TEXT,
            md_approved_at TEXT,
            rejection_reason TEXT,
            is_void INTEGER DEFAULT 0,
            created_by TEXT,
            created_at TEXT,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS correspondence_authority(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            authority_id TEXT UNIQUE,
            authority_name TEXT,
            authority_type TEXT,
            project_name TEXT,
            subject TEXT,
            submission_date TEXT,
            expected_reply_date TEXT,
            followup_date TEXT,
            approval_received INTEGER DEFAULT 0,
            approval_date TEXT,
            related_inward_no TEXT,
            related_outward_no TEXT,
            remarks TEXT,
            status TEXT DEFAULT 'Pending',
            is_void INTEGER DEFAULT 0,
            created_by TEXT,
            created_at TEXT,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS correspondence_email_inbox(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email_uid TEXT,
            received_at TEXT,
            from_address TEXT,
            subject TEXT,
            body_preview TEXT,
            attachment_paths TEXT,
            inward_no TEXT,
            processed INTEGER DEFAULT 0,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS correspondence_audit_log(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT,
            entity_id TEXT,
            action TEXT,
            actor TEXT,
            action_at TEXT,
            old_status TEXT,
            new_status TEXT,
            comments TEXT
        );
        """
    )
    if own:
        conn.commit()
        conn.close()


def log_correspondence_audit(conn, entity_type, entity_id, action, actor, old_status="", new_status="", comments=""):
    conn.execute(
        """
        INSERT INTO correspondence_audit_log(
            entity_type, entity_id, action, actor, action_at, old_status, new_status, comments
        ) VALUES(?,?,?,?,?,?,?,?)
        """,
        (entity_type, entity_id, action, actor, _ts(), old_status or "", new_status or "", comments or ""),
    )


def correspondence_dashboard_stats():
    conn = get_conn()
    today = datetime.now().strftime(DATE_FMT)
    cur = conn.cursor()

    def cnt(sql, params=()):
        cur.execute(sql, params)
        return cur.fetchone()[0]

    received_today = cnt(
        "SELECT COUNT(*) FROM correspondence_inward WHERE date_received = ? AND COALESCE(is_void,0)=0",
        (today,),
    )
    reply_sent_today = cnt(
        "SELECT COUNT(*) FROM correspondence_inward WHERE status = 'Reply Sent' AND updated_at LIKE ? AND COALESCE(is_void,0)=0",
        (f"{today}%",),
    )
    pending_reply = cnt(
        "SELECT COUNT(*) FROM correspondence_inward WHERE status IN ('Received','Under Review','Reply Pending') AND COALESCE(is_void,0)=0"
    )
    urgent = cnt(
        "SELECT COUNT(*) FROM correspondence_inward WHERE priority = 'Urgent' AND status NOT IN ('Closed','Reply Sent') AND COALESCE(is_void,0)=0"
    )
    authority_pending = cnt(
        "SELECT COUNT(*) FROM correspondence_authority WHERE COALESCE(approval_received,0)=0 AND COALESCE(is_void,0)=0"
    )
    unprocessed_email = cnt("SELECT COUNT(*) FROM correspondence_email_inbox WHERE processed = 0")

    conn.close()
    return {
        "received_today": received_today,
        "replied_today": reply_sent_today,
        "pending_reply": pending_reply,
        "urgent": urgent,
        "authority_pending": authority_pending,
        "unprocessed_email": unprocessed_email,
    }


def load_inward_letters(status=None, search=None, limit=300):
    conn = get_conn()
    sql = """
        SELECT inward_id, inward_no, date_received, received_through, from_party, subject,
               project_name, department, priority, assigned_to, due_date, status, related_outward_no
        FROM correspondence_inward
        WHERE COALESCE(is_void, 0) = 0
    """
    params = []
    if status and status != "All":
        sql += " AND status = ?"
        params.append(status)
    if search and search.strip():
        q = f"%{search.strip()}%"
        sql += " AND (inward_no LIKE ? OR subject LIKE ? OR from_party LIKE ? OR project_name LIKE ?)"
        params.extend([q, q, q, q])
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(int(limit))
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


def get_inward(inward_id):
    if not inward_id:
        return None
    conn = get_conn()
    cur = conn.execute("SELECT * FROM correspondence_inward WHERE inward_id = ?", (inward_id,))
    row = cur.fetchone()
    names = [c[0] for c in cur.description] if cur.description else []
    conn.close()
    return dict(zip(names, row)) if row else None


def get_outward(outward_id):
    if not outward_id:
        return None
    conn = get_conn()
    cur = conn.execute("SELECT * FROM correspondence_outward WHERE outward_id = ?", (outward_id,))
    row = cur.fetchone()
    names = [c[0] for c in cur.description] if cur.description else []
    conn.close()
    return dict(zip(names, row)) if row else None


def get_authority(authority_id):
    if not authority_id:
        return None
    conn = get_conn()
    cur = conn.execute("SELECT * FROM correspondence_authority WHERE authority_id = ?", (authority_id,))
    row = cur.fetchone()
    names = [c[0] for c in cur.description] if cur.description else []
    conn.close()
    return dict(zip(names, row)) if row else None


def save_inward(data, actor=""):
    conn = get_conn()
    inward_id = data.get("inward_id") or generate_id("INW", "correspondence_inward", id_column="inward_id", conn=conn)
    row = conn.execute("SELECT inward_no, status FROM correspondence_inward WHERE inward_id = ?", (inward_id,)).fetchone()
    old_status = row[1] if row else ""
    inward_no = (row[0] if row else None) or data.get("inward_no") or next_document_number("inward_letter", conn=conn)
    new_status = data.get("status", old_status or "Received")
    update_vals = (
        inward_no,
        data.get("date_received", datetime.now().strftime(DATE_FMT)),
        data.get("received_through", "Email"),
        data.get("from_party", ""),
        data.get("contact_number", ""),
        data.get("email_id", ""),
        data.get("subject", ""),
        1 if data.get("project_related") else 0,
        data.get("project_name", ""),
        data.get("department", ""),
        data.get("priority", "Medium"),
        data.get("description", ""),
        data.get("attachment", ""),
        data.get("assigned_to", ""),
        data.get("due_date", ""),
        new_status,
        data.get("related_outward_no", ""),
        data.get("source_email_uid", ""),
        _ts(),
        inward_id,
    )
    if row:
        conn.execute(
            """
            UPDATE correspondence_inward SET
                inward_no=?, date_received=?, received_through=?, from_party=?, contact_number=?,
                email_id=?, subject=?, project_related=?, project_name=?, department=?, priority=?,
                description=?, attachment=?, assigned_to=?, due_date=?, status=?, related_outward_no=?,
                source_email_uid=?, updated_at=?
            WHERE inward_id=?
            """,
            update_vals,
        )
        action = "Updated"
    else:
        conn.execute(
            """
            INSERT INTO correspondence_inward(
                inward_id, inward_no, date_received, received_through, from_party, contact_number,
                email_id, subject, project_related, project_name, department, priority, description,
                attachment, assigned_to, due_date, status, related_outward_no, source_email_uid,
                is_void, created_by, created_at, updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,?,?,?)
            """,
            (
                inward_id,
                inward_no,
                data.get("date_received", datetime.now().strftime(DATE_FMT)),
                data.get("received_through", "Email"),
                data.get("from_party", ""),
                data.get("contact_number", ""),
                data.get("email_id", ""),
                data.get("subject", ""),
                1 if data.get("project_related") else 0,
                data.get("project_name", ""),
                data.get("department", ""),
                data.get("priority", "Medium"),
                data.get("description", ""),
                data.get("attachment", ""),
                data.get("assigned_to", ""),
                data.get("due_date", ""),
                new_status,
                data.get("related_outward_no", ""),
                data.get("source_email_uid", ""),
                actor,
                _ts(),
                _ts(),
            ),
        )
        action = "Created"
    log_correspondence_audit(conn, "inward", inward_id, action, actor, old_status, new_status, "")
    conn.commit()
    conn.close()
    return inward_id, inward_no


def void_inward(inward_id, actor, reason=""):
    conn = get_conn()
    conn.execute(
        "UPDATE correspondence_inward SET is_void=1, status='Voided', updated_at=? WHERE inward_id=?",
        (_ts(), inward_id),
    )
    log_correspondence_audit(conn, "inward", inward_id, "Voided", actor, "", "Voided", reason)
    conn.commit()
    conn.close()


def load_outward_letters(status=None, search=None, limit=300):
    conn = get_conn()
    sql = """
        SELECT outward_id, outward_no, date_sent, recipient, subject, project_name,
               sent_by, sent_through, status, related_inward_no
        FROM correspondence_outward
        WHERE COALESCE(is_void, 0) = 0
    """
    params = []
    if status and status != "All":
        sql += " AND status = ?"
        params.append(status)
    if search and search.strip():
        q = f"%{search.strip()}%"
        sql += " AND (outward_no LIKE ? OR subject LIKE ? OR recipient LIKE ? OR related_inward_no LIKE ?)"
        params.extend([q, q, q, q])
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(int(limit))
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


def save_outward(data, actor=""):
    conn = get_conn()
    outward_id = data.get("outward_id") or generate_id("OUT", "correspondence_outward", id_column="outward_id", conn=conn)
    row = conn.execute("SELECT outward_no, status, related_inward_no FROM correspondence_outward WHERE outward_id = ?", (outward_id,)).fetchone()
    old_status = row[1] if row else ""
    outward_no = (row[0] if row else None) or data.get("outward_no") or next_document_number("outward_letter", conn=conn)
    new_status = data.get("status", old_status or "Draft")
    related_in = data.get("related_inward_no", "")
    vals = (
        outward_no,
        data.get("date_sent", datetime.now().strftime(DATE_FMT)),
        data.get("recipient", ""),
        data.get("subject", ""),
        related_in,
        data.get("project_name", ""),
        data.get("sent_by", actor),
        data.get("sent_through", "Email"),
        data.get("attachment", ""),
        data.get("delivery_proof", ""),
        data.get("letter_content", ""),
        data.get("template_type", ""),
        data.get("reference_number", ""),
        new_status,
        _ts(),
    )
    if row:
        conn.execute(
            """
            UPDATE correspondence_outward SET
                outward_no=?, date_sent=?, recipient=?, subject=?, related_inward_no=?,
                project_name=?, sent_by=?, sent_through=?, attachment=?, delivery_proof=?,
                letter_content=?, template_type=?, reference_number=?, status=?, updated_at=?
            WHERE outward_id=?
            """,
            vals + (outward_id,),
        )
    else:
        conn.execute(
            """
            INSERT INTO correspondence_outward(
                outward_id, outward_no, date_sent, recipient, subject, related_inward_no, project_name,
                sent_by, sent_through, attachment, delivery_proof, letter_content, template_type,
                reference_number, status, is_void, created_by, created_at, updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,?,?,?)
            """,
            (outward_id,) + vals + (actor, _ts(), _ts()),
        )
    if related_in:
        conn.execute(
            """
            UPDATE correspondence_inward SET related_outward_no=?, status='Reply Sent', updated_at=?
            WHERE inward_no=? AND COALESCE(is_void,0)=0
            """,
            (outward_no, _ts(), related_in),
        )
    log_correspondence_audit(conn, "outward", outward_id, "Saved" if row else "Created", actor, old_status, new_status, "")
    conn.commit()
    conn.close()
    return outward_id, outward_no


def load_drafts(status=None, limit=200):
    conn = get_conn()
    sql = """
        SELECT draft_id, letter_no, draft_date, template_type, recipient_to, subject,
               project_name, status, related_inward_no
        FROM correspondence_drafts WHERE COALESCE(is_void,0)=0
    """
    params = []
    if status and status != "All":
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(int(limit))
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


def get_draft(draft_id):
    conn = get_conn()
    cur = conn.execute("SELECT * FROM correspondence_drafts WHERE draft_id = ?", (draft_id,))
    row = cur.fetchone()
    names = [c[0] for c in cur.description] if cur.description else []
    conn.close()
    return dict(zip(names, row)) if row else None


def save_draft(data, actor=""):
    conn = get_conn()
    draft_id = data.get("draft_id") or generate_id("DFT", "correspondence_drafts", id_column="draft_id", conn=conn)
    cur = conn.execute("SELECT letter_no, status FROM correspondence_drafts WHERE draft_id = ?", (draft_id,))
    row = cur.fetchone()
    old_status = row[1] if row else ""
    letter_no = (row[0] if row else None) or data.get("letter_no") or f"DRF-{datetime.now().year}-{draft_id[-4:]}"
    new_status = data.get("status", old_status or "Draft")
    vals = (
        letter_no,
        data.get("draft_date", datetime.now().strftime(DATE_FMT)),
        data.get("template_type", "Company Letter"),
        data.get("recipient_to", ""),
        data.get("subject", ""),
        data.get("reference_number", ""),
        data.get("project_name", ""),
        data.get("letter_content", ""),
        data.get("attachment", ""),
        data.get("related_inward_no", ""),
        new_status,
        _ts(),
    )
    if row:
        conn.execute(
            """
            UPDATE correspondence_drafts SET
                letter_no=?, draft_date=?, template_type=?, recipient_to=?, subject=?,
                reference_number=?, project_name=?, letter_content=?, attachment=?,
                related_inward_no=?, status=?, updated_at=?
            WHERE draft_id=?
            """,
            vals + (draft_id,),
        )
    else:
        conn.execute(
            """
            INSERT INTO correspondence_drafts(
                draft_id, letter_no, draft_date, template_type, recipient_to, subject,
                reference_number, project_name, letter_content, attachment, related_inward_no,
                status, created_by, created_at, updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (draft_id,) + vals[:-1] + (actor, _ts(), _ts()),
        )
    log_correspondence_audit(conn, "draft", draft_id, "Saved", actor, old_status, new_status, data.get("comments", ""))
    conn.commit()
    conn.close()
    return draft_id, letter_no


def advance_draft_approval(draft_id, step, actor, comments=""):
    """step: dept | gm | md | reject"""
    conn = get_conn()
    d = get_draft(draft_id)
    if not d:
        conn.close()
        return False
    old = d.get("status", "")
    if step == "dept":
        new = "Pending GM"
        conn.execute(
            "UPDATE correspondence_drafts SET status=?, dept_approved_by=?, dept_approved_at=?, updated_at=? WHERE draft_id=?",
            (new, actor, _ts(), _ts(), draft_id),
        )
    elif step == "gm":
        new = "Pending MD"
        conn.execute(
            "UPDATE correspondence_drafts SET status=?, gm_approved_by=?, gm_approved_at=?, updated_at=? WHERE draft_id=?",
            (new, actor, _ts(), _ts(), draft_id),
        )
    elif step == "md":
        new = "Approved"
        conn.execute(
            "UPDATE correspondence_drafts SET status=?, md_approved_by=?, md_approved_at=?, updated_at=? WHERE draft_id=?",
            (new, actor, _ts(), _ts(), draft_id),
        )
    elif step == "reject":
        new = "Rejected"
        conn.execute(
            "UPDATE correspondence_drafts SET status=?, rejection_reason=?, updated_at=? WHERE draft_id=?",
            (new, comments, _ts(), draft_id),
        )
    else:
        conn.close()
        return False
    log_correspondence_audit(conn, "draft", draft_id, f"Approval:{step}", actor, old, new, comments)
    conn.commit()
    conn.close()
    return True


def draft_to_outward(draft_id, actor, sent_through="Email"):
    d = get_draft(draft_id)
    if not d or d.get("status") != "Approved":
        return None, None
    return save_outward(
        {
            "recipient": d.get("recipient_to", ""),
            "subject": d.get("subject", ""),
            "related_inward_no": d.get("related_inward_no", ""),
            "project_name": d.get("project_name", ""),
            "sent_through": sent_through,
            "letter_content": d.get("letter_content", ""),
            "template_type": d.get("template_type", ""),
            "reference_number": d.get("reference_number", ""),
            "attachment": d.get("attachment", ""),
            "status": "Sent",
        },
        actor,
    )


def load_reply_tracking(limit=200):
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT i.inward_no AS incoming, i.subject, i.from_party, i.status AS inward_status,
               o.outward_no AS reply, o.date_sent AS reply_date, o.status AS outward_status
        FROM correspondence_inward i
        LEFT JOIN correspondence_outward o ON i.related_outward_no = o.outward_no AND COALESCE(o.is_void,0)=0
        WHERE COALESCE(i.is_void,0)=0
        ORDER BY i.id DESC
        LIMIT ?
        """,
        conn,
        params=(int(limit),),
    )
    conn.close()
    return df


def load_authority_tracking(status=None, limit=200):
    conn = get_conn()
    sql = """
        SELECT authority_id, authority_name, authority_type, project_name, subject,
               submission_date, expected_reply_date, followup_date, approval_received,
               approval_date, status, related_inward_no, related_outward_no
        FROM correspondence_authority WHERE COALESCE(is_void,0)=0
    """
    params = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(int(limit))
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


def save_authority(data, actor=""):
    conn = get_conn()
    aid = data.get("authority_id") or generate_id("AUTH", "correspondence_authority", id_column="authority_id", conn=conn)
    conn.execute(
        """
        INSERT INTO correspondence_authority(
            authority_id, authority_name, authority_type, project_name, subject,
            submission_date, expected_reply_date, followup_date, approval_received, approval_date,
            related_inward_no, related_outward_no, remarks, status, created_by, created_at, updated_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(authority_id) DO UPDATE SET
            authority_name=excluded.authority_name, authority_type=excluded.authority_type,
            project_name=excluded.project_name, subject=excluded.subject,
            submission_date=excluded.submission_date, expected_reply_date=excluded.expected_reply_date,
            followup_date=excluded.followup_date, approval_received=excluded.approval_received,
            approval_date=excluded.approval_date, related_inward_no=excluded.related_inward_no,
            related_outward_no=excluded.related_outward_no, remarks=excluded.remarks,
            status=excluded.status, updated_at=excluded.updated_at
        """,
        (
            aid,
            data.get("authority_name", ""),
            data.get("authority_type", "Other"),
            data.get("project_name", ""),
            data.get("subject", ""),
            data.get("submission_date", ""),
            data.get("expected_reply_date", ""),
            data.get("followup_date", ""),
            1 if data.get("approval_received") else 0,
            data.get("approval_date", ""),
            data.get("related_inward_no", ""),
            data.get("related_outward_no", ""),
            data.get("remarks", ""),
            data.get("status", "Pending"),
            actor,
            _ts(),
            _ts(),
        ),
    )
    log_correspondence_audit(conn, "authority", aid, "Saved", actor, "", data.get("status", ""), "")
    conn.commit()
    conn.close()
    return aid


def authority_pending_buckets():
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT authority_id, authority_name, authority_type, subject, submission_date,
               expected_reply_date, julianday('now') - julianday(substr(submission_date,7,4)||'-'||
               substr(submission_date,4,2)||'-'||substr(submission_date,1,2)) AS pending_days
        FROM correspondence_authority
        WHERE COALESCE(approval_received,0)=0 AND COALESCE(is_void,0)=0
        ORDER BY submission_date
        """,
        conn,
    )
    conn.close()
    if df.empty:
        return {k: pd.DataFrame() for k in ("7", "15", "30", "overdue")}
    buckets = {"7": [], "15": [], "30": [], "overdue": []}
    for _, r in df.iterrows():
        days = float(r.get("pending_days") or 0)
        row = r.to_dict()
        if days > 30:
            buckets["overdue"].append(row)
        elif days > 15:
            buckets["30"].append(row)
        elif days > 7:
            buckets["15"].append(row)
        else:
            buckets["7"].append(row)
    return {k: pd.DataFrame(v) if v else pd.DataFrame() for k, v in buckets.items()}


def load_correspondence_audit(entity_type=None, entity_id=None, limit=100):
    conn = get_conn()
    sql = "SELECT entity_type, entity_id, action, actor, action_at, old_status, new_status, comments FROM correspondence_audit_log WHERE 1=1"
    params = []
    if entity_type:
        sql += " AND entity_type = ?"
        params.append(entity_type)
    if entity_id:
        sql += " AND entity_id = ?"
        params.append(entity_id)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(int(limit))
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


def load_email_inbox(processed=None, limit=100):
    conn = get_conn()
    sql = "SELECT * FROM correspondence_email_inbox WHERE 1=1"
    params = []
    if processed is not None:
        sql += " AND processed = ?"
        params.append(1 if processed else 0)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(int(limit))
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


def save_email_inbox_row(from_address, subject, body_preview="", attachment_paths=None, email_uid=None):
    conn = get_conn()
    uid = email_uid or f"manual-{datetime.now().timestamp()}"
    conn.execute(
        """
        INSERT OR IGNORE INTO correspondence_email_inbox(
            email_uid, received_at, from_address, subject, body_preview, attachment_paths, processed, created_at
        ) VALUES(?,?,?,?,?,?,0,?)
        """,
        (uid, _ts(), from_address, subject, body_preview, json.dumps(attachment_paths or []), _ts()),
    )
    conn.commit()
    conn.close()
    return uid


def create_inward_from_email(email_uid, actor, extra=None):
    conn = get_conn()
    row = conn.execute(
        "SELECT from_address, subject, body_preview FROM correspondence_email_inbox WHERE email_uid = ?",
        (email_uid,),
    ).fetchone()
    conn.close()
    if not row:
        return None, None
    extra = extra or {}
    return save_inward(
        {
            "received_through": "Email",
            "from_party": extra.get("from_party", row[0]),
            "email_id": extra.get("email_id", row[0]),
            "subject": extra.get("subject", row[1]),
            "description": extra.get("description", row[2] or ""),
            "source_email_uid": email_uid,
            "status": "Reply Pending",
            **{k: v for k, v in extra.items() if k not in ("from_party", "email_id", "subject", "description")},
        },
        actor,
    )


def mark_email_processed(email_uid, inward_no):
    conn = get_conn()
    conn.execute(
        "UPDATE correspondence_email_inbox SET processed=1, inward_no=? WHERE email_uid=?",
        (inward_no, email_uid),
    )
    conn.commit()
    conn.close()


def fetch_imap_inbox(max_messages=20):
    """Fetch from IMAP if configured in app_settings. Returns count imported."""
    conn = get_conn()
    settings = {r[0]: r[1] for r in conn.execute("SELECT setting_key, setting_value FROM app_settings").fetchall()}
    conn.close()
    if settings.get("corr_imap_enabled") != "1":
        return 0, "IMAP not enabled. Configure in Settings or add emails manually."
    host = settings.get("corr_imap_host", "imap.gmail.com")
    user = settings.get("corr_imap_user", "info@maxexinindia.com")
    password = settings.get("corr_imap_password", "")
    if not password:
        return 0, "IMAP password not set in app_settings (corr_imap_password)."
    try:
        import imaplib
        import email
        from email.header import decode_header

        mail = imaplib.IMAP4_SSL(host)
        mail.login(user, password)
        mail.select("INBOX")
        _, data = mail.search(None, "UNSEEN")
        ids = data[0].split()[-max_messages:] if data[0] else []
        imported = 0
        for num in ids:
            _, msg_data = mail.fetch(num, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1])
            subject = msg.get("Subject", "")
            if isinstance(subject, bytes):
                subject = subject.decode()
            from_addr = msg.get("From", "")
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode(errors="replace")[:2000]
                        break
            else:
                body = (msg.get_payload(decode=True) or b"").decode(errors="replace")[:2000]
            uid = f"imap-{num.decode() if isinstance(num, bytes) else num}"
            save_email_inbox_row(from_addr, subject, body, email_uid=uid)
            imported += 1
        mail.logout()
        return imported, f"Imported {imported} new email(s)."
    except Exception as exc:
        return 0, str(exc)


def load_archive(search=None, limit=300):
    conn = get_conn()
    frames = []
    archive_specs = (
        (
            "Inward",
            "correspondence_inward",
            "inward_no",
            "COALESCE(date_received, updated_at, created_at, '')",
        ),
        (
            "Outward",
            "correspondence_outward",
            "outward_no",
            "COALESCE(date_sent, created_at, '')",
        ),
    )
    for label, table, no_col, date_expr in archive_specs:
        sql = f"""
            SELECT '{label}' AS type, {no_col} AS doc_no, subject, status,
                   {date_expr} AS doc_date, attachment
            FROM {table} WHERE COALESCE(is_void,0)=0 AND status IN ('Closed','Reply Sent','Acknowledged')
        """
        if search and search.strip():
            q = f"%{search.strip()}%"
            sql += f" AND ({no_col} LIKE ? OR subject LIKE ?)"
            df = pd.read_sql_query(sql, conn, params=(q, q))
        else:
            df = pd.read_sql_query(sql, conn)
        frames.append(df)
    conn.close()
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    return out.head(int(limit))
