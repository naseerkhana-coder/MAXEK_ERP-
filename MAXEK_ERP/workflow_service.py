"""MAXEK ERP – Standard 3-Step Approval Workflow (Maker → Checker → Approver)."""

from datetime import datetime

WORKFLOW_STAGES = ("maker", "checker", "approver")

# Internal workflow_status keys
STATUS_PENDING_CHECKER = "pending_checker"
STATUS_PENDING_APPROVAL = "pending_approval"
STATUS_APPROVED = "approved"
STATUS_REJECTED_CHECKER = "rejected_by_checker"
STATUS_REJECTED_APPROVER = "rejected_by_approver"

# Stored on transaction records (approval_status column)
RECORD_PENDING_CHECKER = "Pending Checker"
RECORD_PENDING_APPROVAL = "Pending Approval"
RECORD_APPROVED = "Approved"
RECORD_REJECTED_CHECKER = "Rejected by Checker"
RECORD_REJECTED_APPROVER = "Rejected by Approver"

VALID_RECORD_STATUSES = {
    RECORD_PENDING_CHECKER,
    RECORD_PENDING_APPROVAL,
    RECORD_APPROVED,
    RECORD_REJECTED_CHECKER,
    RECORD_REJECTED_APPROVER,
}

WORKFLOW_STATUS = {
    STATUS_PENDING_CHECKER: RECORD_PENDING_CHECKER,
    STATUS_PENDING_APPROVAL: RECORD_PENDING_APPROVAL,
    STATUS_APPROVED: RECORD_APPROVED,
    STATUS_REJECTED_CHECKER: RECORD_REJECTED_CHECKER,
    STATUS_REJECTED_APPROVER: RECORD_REJECTED_APPROVER,
}

MAKER_EDITABLE = {
    RECORD_REJECTED_CHECKER,
    RECORD_REJECTED_APPROVER,
}

DEFAULT_MODULES = [
    {
        "module_id": "petty_cash",
        "module_name": "Petty Cash",
        "workflow_role_mapping": "Site Engineer → Accounts Manager → Managing Director",
        "maker": "Site Engineer",
        "checker": "Accounts Manager",
        "approver": "Managing Director",
    },
    {
        "module_id": "material_request",
        "module_name": "Store / Material Request",
        "workflow_role_mapping": "Store Keeper → Store Manager → Managing Director",
        "maker": "Store Keeper",
        "checker": "Store Manager",
        "approver": "Managing Director",
    },
    {
        "module_id": "purchase_request",
        "module_name": "Purchase Request",
        "workflow_role_mapping": "Project Engineer → Purchase Manager → Managing Director",
        "maker": "Project Engineer",
        "checker": "Purchase Manager",
        "approver": "Managing Director",
    },
    {
        "module_id": "payroll",
        "module_name": "Payroll",
        "workflow_role_mapping": "HR Staff → Accounts Manager → Managing Director",
        "maker": "HR Staff",
        "checker": "Accounts Manager",
        "approver": "Managing Director",
    },
    {
        "module_id": "daily_timesheet",
        "module_name": "Daily Timesheet",
        "workflow_role_mapping": "Supervisor → Project Manager → Managing Director",
        "maker": "Supervisor",
        "checker": "Project Manager",
        "approver": "Managing Director",
    },
    {
        "module_id": "project_expenses",
        "module_name": "Project Expenses",
        "workflow_role_mapping": "Project Staff → Accounts Manager → Managing Director",
        "maker": "Project Staff",
        "checker": "Accounts Manager",
        "approver": "Managing Director",
    },
    {
        "module_id": "head_office_expenses",
        "module_name": "Head Office Expenses",
        "workflow_role_mapping": "Accounts Staff → Accounts Manager → Managing Director",
        "maker": "Accounts Staff",
        "checker": "Accounts Manager",
        "approver": "Managing Director",
    },
    {
        "module_id": "subcontract",
        "module_name": "Subcontract",
        "workflow_role_mapping": "Project Staff → Project Manager → Managing Director",
        "maker": "Project Staff",
        "checker": "Project Manager",
        "approver": "Managing Director",
    },
    {
        "module_id": "boq",
        "module_name": "BOQ Management",
        "workflow_role_mapping": "Project Engineer → Project Manager → Managing Director",
        "maker": "Project Engineer",
        "checker": "Project Manager",
        "approver": "Managing Director",
    },
    {
        "module_id": "dpr",
        "module_name": "DPR Entry",
        "workflow_role_mapping": "Site Engineer → Project Manager → Managing Director",
        "maker": "Site Engineer",
        "checker": "Project Manager",
        "approver": "Managing Director",
    },
    {
        "module_id": "manager_tool",
        "module_name": "Manager Action Items",
        "workflow_role_mapping": "Project Manager → Department Head → Managing Director",
        "maker": "Project Manager",
        "checker": "Department Head",
        "approver": "Managing Director",
    },
    {
        "module_id": "account_receipt",
        "module_name": "Accounts Receipts",
        "workflow_role_mapping": "Accounts Staff → Accounts Manager → Managing Director",
        "maker": "Accounts Staff",
        "checker": "Accounts Manager",
        "approver": "Managing Director",
    },
    {
        "module_id": "account_payment",
        "module_name": "Accounts Payments",
        "workflow_role_mapping": "Accounts Staff → Accounts Manager → Managing Director",
        "maker": "Accounts Staff",
        "checker": "Accounts Manager",
        "approver": "Managing Director",
    },
    {
        "module_id": "account_gst",
        "module_name": "GST Entries",
        "workflow_role_mapping": "Accounts Staff → Accounts Manager → Managing Director",
        "maker": "Accounts Staff",
        "checker": "Accounts Manager",
        "approver": "Managing Director",
    },
    {
        "module_id": "account_tds",
        "module_name": "TDS Entries",
        "workflow_role_mapping": "Accounts Staff → Accounts Manager → Managing Director",
        "maker": "Accounts Staff",
        "checker": "Accounts Manager",
        "approver": "Managing Director",
    },
    {
        "module_id": "leave_request",
        "module_name": "Leave Request",
        "workflow_role_mapping": "Project Staff → Department Head → Managing Director",
        "maker": "Project Staff",
        "checker": "Department Head",
        "approver": "Managing Director",
    },
    {
        "module_id": "store_issue",
        "module_name": "Store Issue",
        "workflow_role_mapping": "Store Keeper → Store Manager → Managing Director",
        "maker": "Store Keeper",
        "checker": "Store Manager",
        "approver": "Managing Director",
    },
    {
        "module_id": "store_receipt",
        "module_name": "Store Receipt",
        "workflow_role_mapping": "Store Keeper → Store Manager → Managing Director",
        "maker": "Store Keeper",
        "checker": "Store Manager",
        "approver": "Managing Director",
    },
]

ALLOWED_RECORD_TABLES = {
    "petty_cash",
    "material_requests",
    "purchase_requests",
    "payroll_records",
    "daily_timesheets",
    "project_expenses",
    "head_office_expenses",
    "subcontract_requests",
    "boq_items",
    "boq_master",
    "dpr_entries",
    "manager_tasks",
    "account_transactions",
    "leave_requests",
    "salary",
    "attendance",
    "store_issues",
    "store_receipts",
}


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_designation_by_id(db, designation_id):
    if not designation_id:
        return None
    row = db.execute(
        "SELECT * FROM designations WHERE id=?", (designation_id,)
    ).fetchone()
    return dict(row) if row else None


def get_user_designation_id(db, user_id):
    row = db.execute(
        "SELECT designation_id FROM users WHERE id=?", (user_id,)
    ).fetchone()
    return row["designation_id"] if row and row["designation_id"] else None


def get_workflow_for_module(db, module_id):
    row = db.execute(
        "SELECT wm.*, "
        "dm.designation_name AS maker_designation, "
        "dc.designation_name AS checker_designation, "
        "da.designation_name AS approver_designation "
        "FROM workflow_master wm "
        "LEFT JOIN designations dm ON wm.maker_designation_id = dm.id "
        "LEFT JOIN designations dc ON wm.checker_designation_id = dc.id "
        "LEFT JOIN designations da ON wm.approver_designation_id = da.id "
        "WHERE wm.module_id=? AND wm.status='Active'",
        (module_id,),
    ).fetchone()
    return dict(row) if row else None


def user_matches_stage(db, user_id, module_id, stage, is_admin=False):
    if is_admin:
        return True
    designation_id = get_user_designation_id(db, user_id)
    if not designation_id:
        return False
    workflow = get_workflow_for_module(db, module_id)
    if not workflow:
        return False
    stage_field = f"{stage}_designation_id"
    return workflow.get(stage_field) == designation_id


def can_maker_edit(approval_status):
    status = approval_status or RECORD_PENDING_CHECKER
    return status in MAKER_EDITABLE


def get_edit_role_for_user(db, user_id, module_id, approval_status, is_admin=False):
    """Who may edit: maker (rejected), checker (pending checker), approver (pending approval)."""
    status = approval_status or RECORD_PENDING_CHECKER
    if status == RECORD_APPROVED:
        return None
    if status in MAKER_EDITABLE:
        if user_matches_stage(db, user_id, module_id, "maker", is_admin):
            return "maker"
        return None
    if status == RECORD_PENDING_CHECKER:
        if user_matches_stage(db, user_id, module_id, "checker", is_admin):
            return "checker"
        return None
    if status == RECORD_PENDING_APPROVAL:
        if user_matches_stage(db, user_id, module_id, "approver", is_admin):
            return "approver"
        return None
    return None


def can_user_edit(db, user_id, module_id, approval_status, is_admin=False):
    return get_edit_role_for_user(db, user_id, module_id, approval_status, is_admin) is not None


def _split_datetime(ts):
    if not ts or ts == "—":
        return "—", "—"
    parts = str(ts).split(" ", 1)
    return parts[0], parts[1] if len(parts) > 1 else "—"


def log_audit(db, approval_id, module_id, record_id, record_table, action, user_id, remarks=""):
    username = _username_for_id(db, user_id) if user_id else "—"
    if username == "—" and user_id:
        username = str(user_id)
    db.execute(
        "INSERT INTO approval_audit("
        "approval_request_id, module_id, record_id, record_table, action, "
        "actor_user_id, actor_username, remarks, created_at"
        ") VALUES(?,?,?,?,?,?,?,?,?)",
        (
            approval_id,
            module_id,
            record_id,
            record_table,
            action,
            user_id,
            username,
            (remarks or "").strip() or "—",
            _now(),
        ),
    )


def get_approval_request(db, module_id, record_id, record_table):
    row = db.execute(
        "SELECT * FROM approval_requests WHERE module_id=? AND record_id=? AND record_table=?",
        (module_id, record_id, record_table),
    ).fetchone()
    return dict(row) if row else None


def display_status(status, role="maker"):
    """Role-aware visible status label."""
    s = status or RECORD_PENDING_CHECKER
    if role == "maker":
        return s
    if role == "checker":
        if s == RECORD_REJECTED_CHECKER:
            return "Rejected"
        if s in (RECORD_PENDING_APPROVAL, RECORD_APPROVED):
            return "Verified"
        return s
    if role == "approver":
        if s == RECORD_REJECTED_APPROVER:
            return "Rejected"
        return s
    return s


def maker_status_message(status):
    """Maker view-only messages when record is in workflow."""
    s = status or RECORD_PENDING_CHECKER
    if s == RECORD_PENDING_CHECKER:
        return "Waiting for Verification"
    if s == RECORD_PENDING_APPROVAL:
        return "Waiting for Approval"
    if s == RECORD_APPROVED:
        return "Approved"
    return ""


def status_display(workflow_status):
    return WORKFLOW_STATUS.get(workflow_status, workflow_status.replace("_", " ").title())


def display_status_from_workflow(workflow_status, role="maker"):
    record = WORKFLOW_STATUS.get(workflow_status, workflow_status)
    return display_status(record, role)


def create_approval_request(db, module_id, record_id, record_table, created_by, user_id=None):
    """Maker SAVE — status becomes Pending Checker."""
    db.execute(
        "INSERT INTO approval_requests("
        "module_id, record_id, record_table, current_stage, workflow_status, "
        "maker_user_id, created_by, created_at"
        ") VALUES(?,?,?,?,?,?,?,?)",
        (
            module_id,
            record_id,
            record_table,
            "checker",
            STATUS_PENDING_CHECKER,
            user_id,
            created_by,
            _now(),
        ),
    )
    approval_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.execute(
        "UPDATE approval_requests SET maker_action_at=? WHERE id=?",
        (_now(), approval_id),
    )
    _notify_workflow(db, {"module_id": module_id, "record_id": record_id, "record_table": record_table, "created_by": created_by, "maker_user_id": user_id}, "submitted", user_id)
    log_audit(db, approval_id, module_id, record_id, record_table, "created", user_id, "Saved — Pending Checker")
    return approval_id


def resubmit_record(db, module_id, record_id, record_table, user_id=None):
    """Re-SAVE after rejection — back to Pending Checker."""
    req = db.execute(
        "SELECT id FROM approval_requests WHERE module_id=? AND record_id=? AND record_table=?",
        (module_id, record_id, record_table),
    ).fetchone()
    if req:
        db.execute(
            "UPDATE approval_requests SET workflow_status=?, current_stage=?, "
            "rejection_reason=NULL, checker_user_id=NULL, approver_user_id=NULL, "
            "checker_action_at=NULL, approver_action_at=NULL, checker_comment=NULL, "
            "approver_comment=NULL, maker_action_at=? WHERE id=?",
            (STATUS_PENDING_CHECKER, "checker", _now(), req["id"]),
        )
    else:
        create_approval_request(db, module_id, record_id, record_table, "", user_id)
    _sync_record_status(
        db, {"record_table": record_table, "record_id": record_id}, RECORD_PENDING_CHECKER
    )
    req_row = db.execute(
        "SELECT * FROM approval_requests WHERE module_id=? AND record_id=? AND record_table=?",
        (module_id, record_id, record_table),
    ).fetchone()
    if req_row:
        _notify_workflow(db, dict(req_row), "submitted", user_id)
        log_audit(
            db, dict(req_row)["id"], module_id, record_id, record_table,
            "resubmitted", user_id, "Re-saved — Pending Checker",
        )


def advance_approval(db, approval_id, user_id, action, comments="", is_admin=False):
    """
    Checker: VERIFY → Pending Approval | REJECT → Rejected by Checker
    Approver: APPROVE → Approved | REJECT → Rejected by Approver
    """
    req = db.execute(
        "SELECT * FROM approval_requests WHERE id=?", (approval_id,)
    ).fetchone()
    if not req:
        return False, "Approval request not found."
    req = dict(req)
    status = req["workflow_status"]
    module_id = req["module_id"]

    if status == STATUS_APPROVED:
        return False, "This request is already approved."

    if action == "reject":
        if not (comments or "").strip():
            return False, "Reject reason is mandatory."
        reason = comments.strip()
        if status == STATUS_PENDING_CHECKER:
            if not user_matches_stage(db, user_id, module_id, "checker", is_admin):
                return False, "You are not authorized as Checker for this module."
            db.execute(
                "UPDATE approval_requests SET workflow_status=?, rejection_reason=?, "
                "current_stage=?, checker_user_id=?, checker_action_at=? WHERE id=?",
                (STATUS_REJECTED_CHECKER, reason, "maker", user_id, _now(), approval_id),
            )
            _sync_record_status(db, req, RECORD_REJECTED_CHECKER)
            log_audit(db, approval_id, module_id, req["record_id"], req["record_table"], "rejected", user_id, reason)
            _notify_workflow(db, req, "rejected_checker", user_id)
            return True, "Rejected. Returned to Maker."
        if status == STATUS_PENDING_APPROVAL:
            if not user_matches_stage(db, user_id, module_id, "approver", is_admin):
                return False, "You are not authorized as Approver for this module."
            db.execute(
                "UPDATE approval_requests SET workflow_status=?, rejection_reason=?, "
                "current_stage=?, approver_user_id=?, approver_action_at=? WHERE id=?",
                (STATUS_REJECTED_APPROVER, reason, "maker", user_id, _now(), approval_id),
            )
            _sync_record_status(db, req, RECORD_REJECTED_APPROVER)
            log_audit(db, approval_id, module_id, req["record_id"], req["record_table"], "rejected", user_id, reason)
            _notify_workflow(db, req, "rejected_approver", user_id)
            return True, "Rejected. Returned to Maker."
        return False, "Cannot reject at this stage."

    if action == "verify" and status == STATUS_PENDING_CHECKER:
        if not user_matches_stage(db, user_id, module_id, "checker", is_admin):
            return False, "You are not authorized as Checker for this module."
        note = (comments or "").strip()
        db.execute(
            "UPDATE approval_requests SET workflow_status=?, current_stage=?, "
            "checker_user_id=?, checker_action_at=?, checker_comment=? WHERE id=?",
            (STATUS_PENDING_APPROVAL, "approver", user_id, _now(), note or None, approval_id),
        )
        _sync_record_status(db, req, RECORD_PENDING_APPROVAL)
        log_audit(db, approval_id, module_id, req["record_id"], req["record_table"], "verified", user_id, note or "—")
        _notify_workflow(db, req, "verified", user_id)
        return True, "Verified. Status: Pending Approval."

    if action == "approve" and status == STATUS_PENDING_APPROVAL:
        if not user_matches_stage(db, user_id, module_id, "approver", is_admin):
            return False, "You are not authorized as Approver for this module."
        note = (comments or "").strip()
        db.execute(
            "UPDATE approval_requests SET workflow_status=?, current_stage=?, "
            "approver_user_id=?, approver_action_at=?, approver_comment=? WHERE id=?",
            (STATUS_APPROVED, "completed", user_id, _now(), note or None, approval_id),
        )
        _sync_record_status(db, req, RECORD_APPROVED)
        log_audit(db, approval_id, module_id, req["record_id"], req["record_table"], "approved", user_id, note or "—")
        _notify_workflow(db, req, "approved", user_id)
        return True, "Approved. Transaction completed."

    return False, "Invalid action for current status."


def reopen_transaction(db, approval_id, user_id, reason, is_admin=False):
    if not is_admin:
        return False, "Only System Administrator can reopen approved transactions."
    if not (reason or "").strip():
        return False, "Reopen reason is mandatory."
    req = db.execute(
        "SELECT * FROM approval_requests WHERE id=?", (approval_id,)
    ).fetchone()
    if not req:
        return False, "Approval request not found."
    req = dict(req)
    if req["workflow_status"] != STATUS_APPROVED:
        return False, "Only approved transactions can be reopened."
    reason = reason.strip()
    db.execute(
        "UPDATE approval_requests SET workflow_status=?, current_stage=?, "
        "rejection_reason=NULL, checker_user_id=NULL, approver_user_id=NULL, "
        "checker_action_at=NULL, approver_action_at=NULL, checker_comment=NULL, "
        "approver_comment=NULL, maker_action_at=? WHERE id=?",
        (STATUS_PENDING_CHECKER, "checker", _now(), approval_id),
    )
    _sync_record_status(db, req, RECORD_PENDING_CHECKER)
    log_audit(db, approval_id, req["module_id"], req["record_id"], req["record_table"], "reopened", user_id, reason)
    _notify_workflow(db, req, "submitted", user_id)
    return True, "Transaction reopened. Status: Pending Checker."


def _sync_record_status(db, req, status_label):
    table = req["record_table"]
    if table not in ALLOWED_RECORD_TABLES:
        return
    try:
        db.execute(
            f"UPDATE {table} SET approval_status=? WHERE id=?",
            (status_label, req["record_id"]),
        )
    except Exception:
        pass


def get_pending_counts(db, user_id, is_admin=False):
    designation_id = get_user_designation_id(db, user_id)
    counts = {"maker": 0, "checker": 0, "approver": 0}

    if is_admin:
        counts["maker"] = db.execute(
            "SELECT COUNT(*) AS c FROM approval_requests "
            "WHERE workflow_status IN (?, ?)",
            (STATUS_REJECTED_CHECKER, STATUS_REJECTED_APPROVER),
        ).fetchone()["c"]
        counts["checker"] = db.execute(
            "SELECT COUNT(*) AS c FROM approval_requests WHERE workflow_status=?",
            (STATUS_PENDING_CHECKER,),
        ).fetchone()["c"]
        counts["approver"] = db.execute(
            "SELECT COUNT(*) AS c FROM approval_requests WHERE workflow_status=?",
            (STATUS_PENDING_APPROVAL,),
        ).fetchone()["c"]
        return counts

    if not designation_id:
        return counts

    workflows = db.execute(
        "SELECT module_id, maker_designation_id, checker_designation_id, approver_designation_id "
        "FROM workflow_master WHERE status='Active'"
    ).fetchall()

    maker_modules, checker_modules, approver_modules = [], [], []
    for wf in workflows:
        wf = dict(wf)
        if wf["maker_designation_id"] == designation_id:
            maker_modules.append(wf["module_id"])
        if wf["checker_designation_id"] == designation_id:
            checker_modules.append(wf["module_id"])
        if wf["approver_designation_id"] == designation_id:
            approver_modules.append(wf["module_id"])

    if maker_modules:
        placeholders = ",".join("?" * len(maker_modules))
        counts["maker"] = db.execute(
            f"SELECT COUNT(*) AS c FROM approval_requests "
            f"WHERE workflow_status IN (?, ?) AND module_id IN ({placeholders})",
            [STATUS_REJECTED_CHECKER, STATUS_REJECTED_APPROVER] + maker_modules,
        ).fetchone()["c"]

    if checker_modules:
        placeholders = ",".join("?" * len(checker_modules))
        counts["checker"] = db.execute(
            f"SELECT COUNT(*) AS c FROM approval_requests "
            f"WHERE workflow_status=? AND module_id IN ({placeholders})",
            [STATUS_PENDING_CHECKER] + checker_modules,
        ).fetchone()["c"]

    if approver_modules:
        placeholders = ",".join("?" * len(approver_modules))
        counts["approver"] = db.execute(
            f"SELECT COUNT(*) AS c FROM approval_requests "
            f"WHERE workflow_status=? AND module_id IN ({placeholders})",
            [STATUS_PENDING_APPROVAL] + approver_modules,
        ).fetchone()["c"]

    return counts


def get_pending_items(db, user_id, role_type, is_admin=False):
    designation_id = get_user_designation_id(db, user_id)
    status_map = {
        "maker": (
            STATUS_PENDING_CHECKER,
            STATUS_PENDING_APPROVAL,
            STATUS_APPROVED,
            STATUS_REJECTED_CHECKER,
            STATUS_REJECTED_APPROVER,
        ),
        "checker": (
            STATUS_PENDING_CHECKER,
            STATUS_PENDING_APPROVAL,
            STATUS_APPROVED,
            STATUS_REJECTED_CHECKER,
        ),
        "approver": (
            STATUS_PENDING_APPROVAL,
            STATUS_APPROVED,
            STATUS_REJECTED_APPROVER,
        ),
    }
    target_statuses = status_map.get(role_type)
    if not target_statuses:
        return []

    status_placeholders = ",".join("?" * len(target_statuses))

    if role_type == "maker":
        username_row = db.execute(
            "SELECT username FROM users WHERE id=?", (user_id,)
        ).fetchone()
        username = username_row["username"] if username_row else ""
        if is_admin:
            rows = db.execute(
                "SELECT ar.*, wm.module_name, "
                "dm.designation_name AS maker_designation, "
                "dc.designation_name AS checker_designation, "
                "da.designation_name AS approver_designation "
                "FROM approval_requests ar "
                "JOIN workflow_master wm ON ar.module_id = wm.module_id "
                "LEFT JOIN designations dm ON wm.maker_designation_id = dm.id "
                "LEFT JOIN designations dc ON wm.checker_designation_id = dc.id "
                "LEFT JOIN designations da ON wm.approver_designation_id = da.id "
                f"WHERE ar.workflow_status IN ({status_placeholders}) "
                "ORDER BY ar.created_at DESC LIMIT 50",
                list(target_statuses),
            ).fetchall()
        elif username:
            rows = db.execute(
                "SELECT ar.*, wm.module_name, "
                "dm.designation_name AS maker_designation, "
                "dc.designation_name AS checker_designation, "
                "da.designation_name AS approver_designation "
                "FROM approval_requests ar "
                "JOIN workflow_master wm ON ar.module_id = wm.module_id "
                "LEFT JOIN designations dm ON wm.maker_designation_id = dm.id "
                "LEFT JOIN designations dc ON wm.checker_designation_id = dc.id "
                "LEFT JOIN designations da ON wm.approver_designation_id = da.id "
                f"WHERE ar.workflow_status IN ({status_placeholders}) AND ar.created_by=? "
                "ORDER BY ar.created_at DESC LIMIT 50",
                list(target_statuses) + [username],
            ).fetchall()
        else:
            return []
        return [dict(r) for r in rows]

    stage_field = {
        "checker": "checker_designation_id",
        "approver": "approver_designation_id",
    }[role_type]

    if is_admin:
        module_filter = ""
        params = list(target_statuses)
    elif designation_id:
        modules = db.execute(
            f"SELECT module_id FROM workflow_master WHERE {stage_field}=? AND status='Active'",
            (designation_id,),
        ).fetchall()
        if not modules:
            return []
        module_ids = [m["module_id"] for m in modules]
        placeholders = ",".join("?" * len(module_ids))
        module_filter = f" AND ar.module_id IN ({placeholders})"
        params = list(target_statuses) + module_ids
    else:
        return []

    status_placeholders = ",".join("?" * len(target_statuses))
    rows = db.execute(
        "SELECT ar.*, wm.module_name, "
        "dm.designation_name AS maker_designation, "
        "dc.designation_name AS checker_designation, "
        "da.designation_name AS approver_designation "
        "FROM approval_requests ar "
        "JOIN workflow_master wm ON ar.module_id = wm.module_id "
        "LEFT JOIN designations dm ON wm.maker_designation_id = dm.id "
        "LEFT JOIN designations dc ON wm.checker_designation_id = dc.id "
        "LEFT JOIN designations da ON wm.approver_designation_id = da.id "
        f"WHERE ar.workflow_status IN ({status_placeholders}){module_filter} "
        "ORDER BY ar.created_at DESC",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def get_workflow_queue(db, limit=15):
    rows = db.execute(
        "SELECT ar.*, wm.module_name, "
        "dm.designation_name AS maker_designation, "
        "dc.designation_name AS checker_designation, "
        "da.designation_name AS approver_designation "
        "FROM approval_requests ar "
        "JOIN workflow_master wm ON ar.module_id = wm.module_id "
        "LEFT JOIN designations dm ON wm.maker_designation_id = dm.id "
        "LEFT JOIN designations dc ON wm.checker_designation_id = dc.id "
        "LEFT JOIN designations da ON wm.approver_designation_id = da.id "
        "WHERE ar.workflow_status NOT IN (?) "
        "ORDER BY ar.created_at DESC LIMIT ?",
        (STATUS_APPROVED, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def migrate_workflow_statuses(db):
    """Map legacy status values to simplified workflow."""
    db.execute(
        "UPDATE approval_requests SET workflow_status=? WHERE workflow_status='draft'",
        (STATUS_PENDING_CHECKER,),
    )
    db.execute(
        "UPDATE approval_requests SET workflow_status=? WHERE workflow_status='pending_approver'",
        (STATUS_PENDING_APPROVAL,),
    )
    db.execute(
        "UPDATE approval_requests SET workflow_status=? WHERE workflow_status='completed'",
        (STATUS_APPROVED,),
    )
    db.execute(
        "UPDATE approval_requests SET workflow_status=? WHERE workflow_status='rejected'",
        (STATUS_REJECTED_CHECKER,),
    )
    for table in ALLOWED_RECORD_TABLES:
        try:
            db.execute(
                f"UPDATE {table} SET approval_status=? WHERE approval_status IN ('Draft', 'draft')",
                (RECORD_PENDING_CHECKER,),
            )
            db.execute(
                f"UPDATE {table} SET approval_status=? WHERE approval_status='Pending Approver'",
                (RECORD_PENDING_APPROVAL,),
            )
            db.execute(
                f"UPDATE {table} SET approval_status=? WHERE approval_status='Completed'",
                (RECORD_APPROVED,),
            )
            db.execute(
                f"UPDATE {table} SET approval_status=? WHERE approval_status='Rejected'",
                (RECORD_REJECTED_CHECKER,),
            )
        except Exception:
            pass


def seed_designations(db):
    default_names = [
        "Site Engineer",
        "Supervisor",
        "Store Keeper",
        "Project Staff",
        "Project Engineer",
        "Purchase Manager",
        "HR Staff",
        "Accounts Staff",
        "Department Head",
        "Accounts Manager",
        "Store Manager",
        "Project Manager",
        "Managing Director",
    ]
    for name in default_names:
        existing = db.execute(
            "SELECT id FROM designations WHERE designation_name=?", (name,)
        ).fetchone()
        if not existing:
            db.execute(
                "INSERT INTO designations(designation_name, status) VALUES(?, 'Active')",
                (name,),
            )


def _find_designation_id(db, name):
    row = db.execute(
        "SELECT id FROM designations WHERE designation_name=?", (name,)
    ).fetchone()
    return row["id"] if row else None


def sync_workflow_designations(db):
    """Apply current maker/checker/approver designation routing to all modules."""
    seed_designations(db)
    mapping = {
        "petty_cash": ("Site Engineer", "Accounts Manager", "Managing Director"),
        "material_request": ("Store Keeper", "Store Manager", "Managing Director"),
        "purchase_request": ("Project Engineer", "Purchase Manager", "Managing Director"),
        "payroll": ("HR Staff", "Accounts Manager", "Managing Director"),
        "daily_timesheet": ("Supervisor", "Project Manager", "Managing Director"),
        "project_expenses": ("Project Staff", "Accounts Manager", "Managing Director"),
        "head_office_expenses": ("Accounts Staff", "Accounts Manager", "Managing Director"),
        "subcontract": ("Project Staff", "Project Manager", "Managing Director"),
        "boq": ("Project Engineer", "Project Manager", "Managing Director"),
        "dpr": ("Site Engineer", "Project Manager", "Managing Director"),
        "manager_tool": ("Project Manager", "Department Head", "Managing Director"),
        "account_receipt": ("Accounts Staff", "Accounts Manager", "Managing Director"),
        "account_payment": ("Accounts Staff", "Accounts Manager", "Managing Director"),
        "account_gst": ("Accounts Staff", "Accounts Manager", "Managing Director"),
        "account_tds": ("Accounts Staff", "Accounts Manager", "Managing Director"),
        "leave_request": ("Project Staff", "Department Head", "Managing Director"),
        "store_issue": ("Store Keeper", "Store Manager", "Managing Director"),
        "store_receipt": ("Store Keeper", "Store Manager", "Managing Director"),
    }
    for mod in DEFAULT_MODULES:
        module_id = mod["module_id"]
        maker, checker, approver = mapping[module_id]
        maker_id = _find_designation_id(db, maker)
        checker_id = _find_designation_id(db, checker)
        approver_id = _find_designation_id(db, approver)
        flow = f"{maker} → {checker} → {approver}"
        existing = db.execute(
            "SELECT id FROM workflow_master WHERE module_id=?", (module_id,)
        ).fetchone()
        if existing:
            db.execute(
                "UPDATE workflow_master SET maker_designation_id=?, checker_designation_id=?, "
                "approver_designation_id=?, workflow_role_mapping=? WHERE module_id=?",
                (maker_id, checker_id, approver_id, flow, module_id),
            )
        else:
            db.execute(
                "INSERT INTO workflow_master("
                "module_name, module_id, workflow_role_mapping, "
                "maker_designation_id, checker_designation_id, approver_designation_id, status"
                ") VALUES(?,?,?,?,?,?, 'Active')",
                (
                    mod["module_name"],
                    module_id,
                    flow,
                    maker_id,
                    checker_id,
                    approver_id,
                ),
            )


def seed_workflow_master(db):
    seed_designations(db)
    mapping = {
        "petty_cash": ("Site Engineer", "Accounts Manager", "Managing Director"),
        "material_request": ("Store Keeper", "Store Manager", "Managing Director"),
        "purchase_request": ("Project Engineer", "Purchase Manager", "Managing Director"),
        "payroll": ("HR Staff", "Accounts Manager", "Managing Director"),
        "daily_timesheet": ("Supervisor", "Project Manager", "Managing Director"),
        "project_expenses": ("Project Staff", "Accounts Manager", "Managing Director"),
        "head_office_expenses": ("Accounts Staff", "Accounts Manager", "Managing Director"),
        "subcontract": ("Project Staff", "Project Manager", "Managing Director"),
        "boq": ("Project Engineer", "Project Manager", "Managing Director"),
        "dpr": ("Site Engineer", "Project Manager", "Managing Director"),
        "manager_tool": ("Project Manager", "Department Head", "Managing Director"),
        "account_receipt": ("Accounts Staff", "Accounts Manager", "Managing Director"),
        "account_payment": ("Accounts Staff", "Accounts Manager", "Managing Director"),
        "account_gst": ("Accounts Staff", "Accounts Manager", "Managing Director"),
        "account_tds": ("Accounts Staff", "Accounts Manager", "Managing Director"),
        "leave_request": ("Project Staff", "Department Head", "Managing Director"),
        "store_issue": ("Store Keeper", "Store Manager", "Managing Director"),
        "store_receipt": ("Store Keeper", "Store Manager", "Managing Director"),
    }
    for mod in DEFAULT_MODULES:
        existing = db.execute(
            "SELECT id FROM workflow_master WHERE module_id=?", (mod["module_id"],)
        ).fetchone()
        if existing:
            continue
        maker_id = _find_designation_id(db, mapping[mod["module_id"]][0])
        checker_id = _find_designation_id(db, mapping[mod["module_id"]][1])
        approver_id = _find_designation_id(db, mapping[mod["module_id"]][2])
        db.execute(
            "INSERT INTO workflow_master("
            "module_name, module_id, workflow_role_mapping, "
            "maker_designation_id, checker_designation_id, approver_designation_id, status"
            ") VALUES(?,?,?,?,?,?, 'Active')",
            (
                mod["module_name"],
                mod["module_id"],
                mod["workflow_role_mapping"],
                maker_id,
                checker_id,
                approver_id,
            ),
        )


def _today():
    return datetime.now().strftime("%Y-%m-%d")


def _username_for_id(db, user_id):
    if not user_id:
        return "—"
    row = db.execute("SELECT username FROM users WHERE id=?", (user_id,)).fetchone()
    return row["username"] if row else "—"


def _user_ids_for_designation(db, designation_id):
    if not designation_id:
        return []
    rows = db.execute(
        "SELECT id FROM users WHERE designation_id=? AND status='Active'",
        (designation_id,),
    ).fetchall()
    ids = [r["id"] for r in rows]
    if not ids:
        admin_rows = db.execute(
            "SELECT id FROM users WHERE role='admin' AND status='Active'"
        ).fetchall()
        ids = [r["id"] for r in admin_rows]
    return ids


def _user_id_for_username(db, username):
    if not username:
        return None
    row = db.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
    return row["id"] if row else None


def create_notification(db, user_id, message, notification_type, module_id=None, record_id=None, record_table=None):
    db.execute(
        "INSERT INTO notifications(user_id, message, notification_type, module_id, record_id, record_table, is_read, created_at) "
        "VALUES(?,?,?,?,?,?,0,?)",
        (user_id, message, notification_type, module_id, record_id, record_table, _now()),
    )


def get_notifications(db, user_id, limit=20, unread_only=False):
    query = "SELECT * FROM notifications WHERE user_id=?"
    params = [user_id]
    if unread_only:
        query += " AND is_read=0"
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    return [dict(r) for r in db.execute(query, params).fetchall()]


def mark_notifications_read(db, user_id, notification_ids=None):
    if notification_ids:
        placeholders = ",".join("?" * len(notification_ids))
        db.execute(
            f"UPDATE notifications SET is_read=1 WHERE user_id=? AND id IN ({placeholders})",
            [user_id] + list(notification_ids),
        )
    else:
        db.execute("UPDATE notifications SET is_read=1 WHERE user_id=?", (user_id,))


def _notify_workflow(db, req, event, actor_user_id=None):
    module_id = req.get("module_id")
    record_id = req.get("record_id")
    record_table = req.get("record_table")
    wf = get_workflow_for_module(db, module_id) if module_id else None
    maker_uid = req.get("maker_user_id") or _user_id_for_username(db, req.get("created_by"))

    if event == "submitted" and wf:
        for uid in _user_ids_for_designation(db, wf.get("checker_designation_id")):
            create_notification(
                db, uid, "New Request", "checker_new",
                module_id, record_id, record_table,
            )
    elif event == "verified":
        if maker_uid:
            create_notification(db, maker_uid, "Verified", "maker_verified", module_id, record_id, record_table)
        if wf:
            for uid in _user_ids_for_designation(db, wf.get("approver_designation_id")):
                create_notification(
                    db, uid, "Waiting Approval", "approver_new",
                    module_id, record_id, record_table,
                )
    elif event == "approved" and maker_uid:
        create_notification(db, maker_uid, "Approved", "maker_approved", module_id, record_id, record_table)
    elif event in ("rejected_checker", "rejected_approver") and maker_uid:
        create_notification(db, maker_uid, "Rejected", "maker_rejected", module_id, record_id, record_table)


def get_approval_history(db, module_id, record_id, record_table):
    row = db.execute(
        "SELECT * FROM approval_requests WHERE module_id=? AND record_id=? AND record_table=?",
        (module_id, record_id, record_table),
    ).fetchone()
    if not row:
        return None
    row = dict(row)
    approval_id = row["id"]

    audit_rows = db.execute(
        "SELECT * FROM approval_audit WHERE approval_request_id=? ORDER BY created_at ASC, id ASC",
        (approval_id,),
    ).fetchall()

    action_labels = {
        "created": "Created",
        "resubmitted": "Created",
        "verified": "Verified",
        "approved": "Approved",
        "rejected": "Rejected",
        "reopened": "Reopened",
    }

    timeline = []
    for aud in audit_rows:
        aud = dict(aud)
        d, t = _split_datetime(aud.get("created_at"))
        timeline.append({
            "event": action_labels.get(aud.get("action"), aud.get("action", "").title()),
            "user": aud.get("actor_username") or "—",
            "date": d,
            "time": t,
            "remarks": aud.get("remarks") or "—",
        })

    if not timeline:
        created_ts = row.get("created_at") or row.get("maker_action_at") or "—"
        d, t = _split_datetime(created_ts)
        timeline.append({
            "event": "Created",
            "user": row.get("created_by") or "—",
            "date": d,
            "time": t,
            "remarks": "—",
        })
        if row.get("checker_user_id") and row.get("checker_action_at"):
            evt = "Rejected" if row.get("workflow_status") == STATUS_REJECTED_CHECKER else "Verified"
            d, t = _split_datetime(row.get("checker_action_at"))
            timeline.append({
                "event": evt,
                "user": _username_for_id(db, row["checker_user_id"]),
                "date": d,
                "time": t,
                "remarks": row.get("rejection_reason") if evt == "Rejected" else (row.get("checker_comment") or "—"),
            })
        if row.get("approver_user_id") and row.get("approver_action_at"):
            evt = "Rejected" if row.get("workflow_status") == STATUS_REJECTED_APPROVER else "Approved"
            d, t = _split_datetime(row.get("approver_action_at"))
            timeline.append({
                "event": evt,
                "user": _username_for_id(db, row["approver_user_id"]),
                "date": d,
                "time": t,
                "remarks": row.get("rejection_reason") if evt == "Rejected" else (row.get("approver_comment") or "—"),
            })

    last_reject = "—"
    for item in reversed(timeline):
        if item["event"] == "Rejected" and item["remarks"] != "—":
            last_reject = item["remarks"]
            break

    history = {
        "approval_id": approval_id,
        "timeline": timeline,
        "created_by": row.get("created_by") or "—",
        "created_date": row.get("created_at") or row.get("maker_action_at") or "—",
        "verified_by": "—",
        "verified_date": "—",
        "approved_by": "—",
        "approved_date": "—",
        "rejected_by": "—",
        "rejected_date": "—",
        "remarks": last_reject,
        "workflow_status": row.get("workflow_status"),
        "record_status": WORKFLOW_STATUS.get(row.get("workflow_status"), ""),
    }
    for item in timeline:
        if item["event"] == "Verified":
            history["verified_by"] = item["user"]
            history["verified_date"] = f"{item['date']} {item['time']}" if item["time"] != "—" else item["date"]
        elif item["event"] == "Approved":
            history["approved_by"] = item["user"]
            history["approved_date"] = f"{item['date']} {item['time']}" if item["time"] != "—" else item["date"]
        elif item["event"] == "Rejected":
            history["rejected_by"] = item["user"]
            history["rejected_date"] = f"{item['date']} {item['time']}" if item["time"] != "—" else item["date"]
    return history


def get_dashboard_counters(db, user_id, username, is_admin=False):
    today = _today()
    designation_id = get_user_designation_id(db, user_id)
    maker = {"pending_verification": 0, "pending_approval": 0, "approved": 0, "rejected": 0}
    checker = {"pending_verification": 0, "verified_today": 0, "rejected_today": 0}
    approver = {"pending_approval": 0, "approved_today": 0, "rejected_today": 0}

    if is_admin:
        maker["pending_verification"] = db.execute(
            "SELECT COUNT(*) AS c FROM approval_requests WHERE workflow_status=?",
            (STATUS_PENDING_CHECKER,),
        ).fetchone()["c"]
        maker["pending_approval"] = db.execute(
            "SELECT COUNT(*) AS c FROM approval_requests WHERE workflow_status=?",
            (STATUS_PENDING_APPROVAL,),
        ).fetchone()["c"]
        maker["approved"] = db.execute(
            "SELECT COUNT(*) AS c FROM approval_requests WHERE workflow_status=?",
            (STATUS_APPROVED,),
        ).fetchone()["c"]
        maker["rejected"] = db.execute(
            "SELECT COUNT(*) AS c FROM approval_requests WHERE workflow_status IN (?, ?)",
            (STATUS_REJECTED_CHECKER, STATUS_REJECTED_APPROVER),
        ).fetchone()["c"]
        checker["pending_verification"] = maker["pending_verification"]
        checker["verified_today"] = db.execute(
            "SELECT COUNT(*) AS c FROM approval_requests WHERE workflow_status IN (?, ?) AND checker_action_at LIKE ?",
            (STATUS_PENDING_APPROVAL, STATUS_APPROVED, f"{today}%"),
        ).fetchone()["c"]
        checker["rejected_today"] = db.execute(
            "SELECT COUNT(*) AS c FROM approval_requests WHERE workflow_status=? AND checker_action_at LIKE ?",
            (STATUS_REJECTED_CHECKER, f"{today}%"),
        ).fetchone()["c"]
        approver["pending_approval"] = maker["pending_approval"]
        approver["approved_today"] = db.execute(
            "SELECT COUNT(*) AS c FROM approval_requests WHERE workflow_status=? AND approver_action_at LIKE ?",
            (STATUS_APPROVED, f"{today}%"),
        ).fetchone()["c"]
        approver["rejected_today"] = db.execute(
            "SELECT COUNT(*) AS c FROM approval_requests WHERE workflow_status=? AND approver_action_at LIKE ?",
            (STATUS_REJECTED_APPROVER, f"{today}%"),
        ).fetchone()["c"]
        return {"maker": maker, "checker": checker, "approver": approver}

    maker["pending_verification"] = db.execute(
        "SELECT COUNT(*) AS c FROM approval_requests WHERE workflow_status=? AND created_by=?",
        (STATUS_PENDING_CHECKER, username),
    ).fetchone()["c"]
    maker["pending_approval"] = db.execute(
        "SELECT COUNT(*) AS c FROM approval_requests WHERE workflow_status=? AND created_by=?",
        (STATUS_PENDING_APPROVAL, username),
    ).fetchone()["c"]
    maker["approved"] = db.execute(
        "SELECT COUNT(*) AS c FROM approval_requests WHERE workflow_status=? AND created_by=?",
        (STATUS_APPROVED, username),
    ).fetchone()["c"]
    maker["rejected"] = db.execute(
        "SELECT COUNT(*) AS c FROM approval_requests WHERE workflow_status IN (?, ?) AND created_by=?",
        (STATUS_REJECTED_CHECKER, STATUS_REJECTED_APPROVER, username),
    ).fetchone()["c"]

    if designation_id:
        wf_rows = db.execute(
            "SELECT module_id, checker_designation_id, approver_designation_id FROM workflow_master WHERE status='Active'"
        ).fetchall()
        checker_mods = [w["module_id"] for w in wf_rows if w["checker_designation_id"] == designation_id]
        approver_mods = [w["module_id"] for w in wf_rows if w["approver_designation_id"] == designation_id]
        if checker_mods:
            ph = ",".join("?" * len(checker_mods))
            checker["pending_verification"] = db.execute(
                f"SELECT COUNT(*) AS c FROM approval_requests WHERE workflow_status=? AND module_id IN ({ph})",
                [STATUS_PENDING_CHECKER] + checker_mods,
            ).fetchone()["c"]
            checker["verified_today"] = db.execute(
                f"SELECT COUNT(*) AS c FROM approval_requests WHERE workflow_status IN (?, ?) "
                f"AND checker_action_at LIKE ? AND module_id IN ({ph})",
                [STATUS_PENDING_APPROVAL, STATUS_APPROVED, f"{today}%"] + checker_mods,
            ).fetchone()["c"]
            checker["rejected_today"] = db.execute(
                f"SELECT COUNT(*) AS c FROM approval_requests WHERE workflow_status=? "
                f"AND checker_action_at LIKE ? AND module_id IN ({ph})",
                [STATUS_REJECTED_CHECKER, f"{today}%"] + checker_mods,
            ).fetchone()["c"]
        if approver_mods:
            ph = ",".join("?" * len(approver_mods))
            approver["pending_approval"] = db.execute(
                f"SELECT COUNT(*) AS c FROM approval_requests WHERE workflow_status=? AND module_id IN ({ph})",
                [STATUS_PENDING_APPROVAL] + approver_mods,
            ).fetchone()["c"]
            approver["approved_today"] = db.execute(
                f"SELECT COUNT(*) AS c FROM approval_requests WHERE workflow_status=? "
                f"AND approver_action_at LIKE ? AND module_id IN ({ph})",
                [STATUS_APPROVED, f"{today}%"] + approver_mods,
            ).fetchone()["c"]
            approver["rejected_today"] = db.execute(
                f"SELECT COUNT(*) AS c FROM approval_requests WHERE workflow_status=? "
                f"AND approver_action_at LIKE ? AND module_id IN ({ph})",
                [STATUS_REJECTED_APPROVER, f"{today}%"] + approver_mods,
            ).fetchone()["c"]

    return {"maker": maker, "checker": checker, "approver": approver}


def get_approval_summary(db):
    """Unified dashboard approval summary."""
    today = _today()
    rejected_today = (
        db.execute(
            "SELECT COUNT(*) AS c FROM approval_requests WHERE workflow_status=? AND checker_action_at LIKE ?",
            (STATUS_REJECTED_CHECKER, f"{today}%"),
        ).fetchone()["c"]
        + db.execute(
            "SELECT COUNT(*) AS c FROM approval_requests WHERE workflow_status=? AND approver_action_at LIKE ?",
            (STATUS_REJECTED_APPROVER, f"{today}%"),
        ).fetchone()["c"]
    )
    reopened_today = 0
    try:
        reopened_today = db.execute(
            "SELECT COUNT(*) AS c FROM approval_audit WHERE action='reopened' AND created_at LIKE ?",
            (f"{today}%",),
        ).fetchone()["c"]
    except Exception:
        pass
    return {
        "pending_checker": db.execute(
            "SELECT COUNT(*) AS c FROM approval_requests WHERE workflow_status=?",
            (STATUS_PENDING_CHECKER,),
        ).fetchone()["c"],
        "pending_approval": db.execute(
            "SELECT COUNT(*) AS c FROM approval_requests WHERE workflow_status=?",
            (STATUS_PENDING_APPROVAL,),
        ).fetchone()["c"],
        "approved_today": db.execute(
            "SELECT COUNT(*) AS c FROM approval_requests WHERE workflow_status=? AND approver_action_at LIKE ?",
            (STATUS_APPROVED, f"{today}%"),
        ).fetchone()["c"],
        "rejected_today": rejected_today,
        "reopened_today": reopened_today,
    }


def get_workflow_access_for_designation(db, designation_id):
    """Modules/roles this designation can access in workflow."""
    if not designation_id:
        return "—"
    rows = db.execute(
        "SELECT module_name, maker_designation_id, checker_designation_id, approver_designation_id "
        "FROM workflow_master WHERE status='Active'"
    ).fetchall()
    access = []
    for row in rows:
        row = dict(row)
        if row["maker_designation_id"] == designation_id:
            access.append(f"Maker: {row['module_name']}")
        if row["checker_designation_id"] == designation_id:
            access.append(f"Checker: {row['module_name']}")
        if row["approver_designation_id"] == designation_id:
            access.append(f"Approver: {row['module_name']}")
    return ", ".join(access) if access else "—"


def get_workflow_access_label(db, designation_id, workflow_role=None):
    if workflow_role:
        return workflow_role
    label = get_workflow_access_for_designation(db, designation_id)
    return label if label != "—" else "No workflow role"


def get_workflow_audit_report(db, module_id=None, status_filter=None, limit=500):
    query = (
        "SELECT ar.id, ar.module_id, wm.module_name, ar.record_id, ar.record_table, "
        "ar.created_by, ar.created_at, ar.checker_action_at, ar.approver_action_at, "
        "ar.workflow_status, ar.rejection_reason, "
        "uc.username AS checker_name, ua.username AS approver_name "
        "FROM approval_requests ar "
        "JOIN workflow_master wm ON ar.module_id = wm.module_id "
        "LEFT JOIN users uc ON ar.checker_user_id = uc.id "
        "LEFT JOIN users ua ON ar.approver_user_id = ua.id "
        "WHERE 1=1"
    )
    params = []
    if module_id:
        query += " AND ar.module_id=?"
        params.append(module_id)
    if status_filter:
        query += " AND ar.workflow_status=?"
        params.append(status_filter)
    query += " ORDER BY ar.created_at DESC LIMIT ?"
    params.append(limit)
    rows = db.execute(query, params).fetchall()
    report = []
    for row in rows:
        row = dict(row)
        doc_no = f"{row['module_id'].upper()[:3]}-{row['record_id']}"
        report.append({
            "module": row.get("module_name") or row["module_id"],
            "document_number": doc_no,
            "maker": row.get("created_by") or "—",
            "checker": row.get("checker_name") or "—",
            "approver": row.get("approver_name") or "—",
            "created_date": row.get("created_at") or "—",
            "verified_date": row.get("checker_action_at") or "—",
            "approved_date": row.get("approver_action_at") or "—",
            "current_status": WORKFLOW_STATUS.get(row.get("workflow_status"), row.get("workflow_status")),
        })
    return report


def get_user_workflow_role(db, user_id):
    row = db.execute(
        "SELECT workflow_role, role FROM users WHERE id=?", (user_id,)
    ).fetchone()
    if not row:
        return None
    row = dict(row)
    wf = (row.get("workflow_role") or "").strip()
    if wf:
        return wf
    role = (row.get("role") or "").strip()
    if role.lower() in ("admin", "administrator"):
        return "Administrator"
    return None


def is_admin_role(db, user_id, session_role=None):
    if session_role and str(session_role).lower() in ("admin", "administrator"):
        return True
    wf = get_user_workflow_role(db, user_id)
    return wf == "Administrator"


def user_workflow_capabilities(db, user_id, is_admin=False):
    """Role security summary for current user."""
    if is_admin:
        return {
            "role": "administrator",
            "workflow_role": "Administrator",
            "can_create": True,
            "can_edit_rejected": True,
            "can_view_own": True,
            "can_verify": True,
            "can_reject": True,
            "can_approve": True,
            "can_view_approved": True,
            "can_reopen": True,
            "can_configure_workflow": True,
            "can_manage_users": True,
        }
    wf_role = get_user_workflow_role(db, user_id)
    caps = {
        "role": (wf_role or "user").lower(),
        "workflow_role": wf_role or "—",
        "can_create": False,
        "can_edit_rejected": False,
        "can_view_own": True,
        "can_verify": False,
        "can_reject": False,
        "can_approve": False,
        "can_view_approved": False,
        "can_reopen": False,
        "can_configure_workflow": False,
        "can_manage_users": False,
    }
    if wf_role == "Maker":
        caps["can_create"] = True
        caps["can_edit_rejected"] = True
    elif wf_role == "Checker":
        caps["can_verify"] = True
        caps["can_reject"] = True
    elif wf_role == "Approver":
        caps["can_approve"] = True
        caps["can_reject"] = True
        caps["can_view_approved"] = True
    designation_id = get_user_designation_id(db, user_id)
    if designation_id:
        wf_rows = db.execute(
            "SELECT maker_designation_id, checker_designation_id, approver_designation_id "
            "FROM workflow_master WHERE status='Active'"
        ).fetchall()
        for wf in wf_rows:
            wf = dict(wf)
            if wf["maker_designation_id"] == designation_id:
                caps["can_create"] = True
                caps["can_edit_rejected"] = True
            if wf["checker_designation_id"] == designation_id:
                caps["can_verify"] = True
                caps["can_reject"] = True
            if wf["approver_designation_id"] == designation_id:
                caps["can_approve"] = True
                caps["can_reject"] = True
                caps["can_view_approved"] = True
    return caps


def get_recent_activities(db, limit=12):
    """Recent workflow audit entries for dashboard feed."""
    try:
        rows = db.execute(
            "SELECT aa.action, aa.actor_username, aa.remarks, aa.created_at, "
            "aa.module_id, aa.record_id, wm.module_name "
            "FROM approval_audit aa "
            "LEFT JOIN workflow_master wm ON aa.module_id = wm.module_id "
            "ORDER BY aa.id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    except Exception:
        return []
    activities = []
    action_labels = {
        "created": "Created",
        "submitted": "Submitted",
        "resubmitted": "Re-submitted",
        "verified": "Verified",
        "approved": "Approved",
        "rejected": "Rejected",
        "reopened": "Reopened",
    }
    for row in rows:
        row = dict(row)
        action = row.get("action") or ""
        ts = row.get("created_at") or "—"
        time_part = "—"
        date_part = ts
        if " " in ts:
            date_part, time_part = ts.split(" ", 1)
        doc = f"{(row.get('module_id') or 'DOC').upper()[:3]}-{row.get('record_id') or '?'}"
        activities.append({
            "action": action_labels.get(action, action.title()),
            "action_key": action,
            "user": row.get("actor_username") or "—",
            "module": row.get("module_name") or row.get("module_id") or "—",
            "document": doc,
            "remarks": row.get("remarks") or "",
            "date": date_part,
            "time": time_part,
        })
    return activities


def seed_demo_users(db):
    """Demo maker / checker / approver accounts for workflow testing."""
    admin_desig = db.execute(
        "SELECT id FROM designations WHERE designation_name='Managing Director'"
    ).fetchone()
    admin_desig_id = admin_desig["id"] if admin_desig else None
    db.execute(
        "UPDATE users SET employee_name=COALESCE(employee_name, 'System Administrator'), "
        "department=COALESCE(department, 'Head Office'), workflow_role='Administrator', "
        "role='Admin', status='Active' WHERE username='admin'"
    )
    demos = [
        ("maker1", "maker123", "Rajesh Kumar", "Site Operations", "Site Engineer", "Maker", "Maker"),
        ("checker1", "checker123", "Priya Menon", "Accounts", "Accounts Manager", "Checker", "Checker"),
        ("approver1", "approver123", "Vikram Nair", "Management", "Managing Director", "Approver", "Approver"),
    ]
    for username, password, emp_name, dept, desig_name, role, wf_role in demos:
        desig = db.execute(
            "SELECT id FROM designations WHERE designation_name=?", (desig_name,)
        ).fetchone()
        desig_id = desig["id"] if desig else None
        existing = db.execute(
            "SELECT id FROM users WHERE username=?", (username,)
        ).fetchone()
        if existing:
            db.execute(
                "UPDATE users SET password=?, employee_name=?, department=?, "
                "designation_id=?, workflow_role=?, role=?, status='Active' WHERE username=?",
                (password, emp_name, dept, desig_id, wf_role, role, username),
            )
        else:
            db.execute(
                "INSERT INTO users(username, password, employee_name, department, "
                "designation_id, workflow_role, role, status) VALUES(?,?,?,?,?,?,?, 'Active')",
                (username, password, emp_name, dept, desig_id, wf_role, role),
            )


def _table_exists(db, table):
    try:
        db.execute(f"SELECT 1 FROM {table} LIMIT 1")
        return True
    except Exception:
        return False
