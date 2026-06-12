"""MAXEK ERP — Phase finalization workflow integration tests."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, init_db, query_db, get_db
from workflow_service import (
    create_approval_request,
    advance_approval,
    reopen_transaction,
    get_approval_request,
    get_approval_summary,
    get_dashboard_counters,
    get_recent_activities,
    RECORD_PENDING_CHECKER,
    RECORD_PENDING_APPROVAL,
    RECORD_APPROVED,
    RECORD_REJECTED_CHECKER,
    RECORD_REJECTED_APPROVER,
    STATUS_PENDING_CHECKER,
    STATUS_PENDING_APPROVAL,
    STATUS_APPROVED,
    STATUS_REJECTED_CHECKER,
    STATUS_REJECTED_APPROVER,
)


def _user_id(username):
    row = query_db("SELECT id FROM users WHERE username=?", (username,), one=True)
    assert row, f"User {username} not found — run init_db()"
    return row["id"]


def _petty_cash_status(record_id):
    row = query_db("SELECT approval_status FROM petty_cash WHERE id=?", (record_id,), one=True)
    return row["approval_status"] if row else None


def _req_status(approval_id):
    row = query_db("SELECT workflow_status FROM approval_requests WHERE id=?", (approval_id,), one=True)
    return row["workflow_status"] if row else None


def _create_petty_cash(db, created_by, user_id):
    db.execute(
        "INSERT INTO petty_cash(project_id, expense_date, expense_type, amount, "
        "payment_mode, remarks, created_by, approval_status) VALUES(?,?,?,?,?,?,?,?)",
        (None, "2026-06-06", "Test", 100.0, "Cash", "Workflow test", created_by, RECORD_PENDING_CHECKER),
    )
    record_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    create_approval_request(db, "petty_cash", record_id, "petty_cash", created_by, user_id)
    db.commit()
    return record_id


def run_tests():
    passed = 0
    failed = 0

    def check(name, condition, detail=""):
        nonlocal passed, failed
        if condition:
            print(f"  PASS  {name}")
            passed += 1
        else:
            print(f"  FAIL  {name} — {detail}")
            failed += 1

    with app.app_context():
        init_db()
        db = get_db()
        maker_id = _user_id("maker1")
        checker_id = _user_id("checker1")
        approver_id = _user_id("approver1")
        admin_id = _user_id("admin")

        print("\n=== Maker Test ===")
        rid = _create_petty_cash(db, "maker1", maker_id)
        req = get_approval_request(db, "petty_cash", rid, "petty_cash")
        check("Approval request created", req is not None)
        check("Status = Pending Checker", _petty_cash_status(rid) == RECORD_PENDING_CHECKER)
        check("Workflow status pending_checker", _req_status(req["id"]) == STATUS_PENDING_CHECKER)

        print("\n=== Checker Verify Test ===")
        ok, msg = advance_approval(db, req["id"], checker_id, "verify", "Verified OK", False)
        db.commit()
        check("Verify succeeded", ok, msg)
        check("Status = Pending Approval", _petty_cash_status(rid) == RECORD_PENDING_APPROVAL, _petty_cash_status(rid))

        print("\n=== Approver Test ===")
        ok, msg = advance_approval(db, req["id"], approver_id, "approve", "Approved OK", False)
        db.commit()
        check("Approve succeeded", ok, msg)
        check("Status = Approved", _petty_cash_status(rid) == RECORD_APPROVED)

        print("\n=== Reject by Checker Test ===")
        rid2 = _create_petty_cash(db, "maker1", maker_id)
        req2 = get_approval_request(db, "petty_cash", rid2, "petty_cash")
        ok, msg = advance_approval(db, req2["id"], checker_id, "reject", "Needs correction", False)
        db.commit()
        check("Checker reject succeeded", ok, msg)
        check("Back to maker (Rejected by Checker)", _petty_cash_status(rid2) == RECORD_REJECTED_CHECKER)

        print("\n=== Reject by Approver Test ===")
        rid3 = _create_petty_cash(db, "maker1", maker_id)
        req3 = get_approval_request(db, "petty_cash", rid3, "petty_cash")
        advance_approval(db, req3["id"], checker_id, "verify", "", False)
        db.commit()
        ok, msg = advance_approval(db, req3["id"], approver_id, "reject", "Not approved", False)
        db.commit()
        check("Approver reject succeeded", ok, msg)
        check("Back to maker (Rejected by Approver)", _petty_cash_status(rid3) == RECORD_REJECTED_APPROVER)

        print("\n=== Admin Reopen Test ===")
        ok, msg = reopen_transaction(db, req["id"], admin_id, "Reopen for correction", True)
        db.commit()
        check("Reopen succeeded", ok, msg)
        check("Status back to Pending Checker", _petty_cash_status(rid) == RECORD_PENDING_CHECKER)
        audit = query_db(
            "SELECT COUNT(*) AS c FROM approval_audit WHERE approval_request_id=? AND action='reopened'",
            (req["id"],),
            one=True,
        )
        check("Audit log created for reopen", audit["c"] >= 1)

        print("\n=== Dashboard & Notifications ===")
        summary = get_approval_summary(db)
        check("Approval summary has keys", all(k in summary for k in (
            "pending_checker", "pending_approval", "approved_today", "rejected_today", "reopened_today"
        )))
        counters = get_dashboard_counters(db, admin_id, "admin", True)
        check("Dashboard counters populated", "maker" in counters and "checker" in counters)
        activities = get_recent_activities(db, limit=5)
        check("Recent activities available", len(activities) >= 1)

        print("\n=== Route Smoke Test ===")
        client = app.test_client()
        with client.session_transaction() as s:
            s["user_id"] = admin_id
            s["username"] = "admin"
            s["role"] = "Admin"
            s["workflow_role"] = "Administrator"
        for path in ["/dashboard", "/settings/users", "/settings"]:
            code = client.get(path).status_code
            check(f"GET {path} → 200", code == 200, f"got {code}")
        client.get("/logout")
        check("GET /login (logged out) → 200", client.get("/login").status_code == 200)

        print(f"\n{'='*40}\nResults: {passed} passed, {failed} failed\n")
        return failed == 0


if __name__ == "__main__":
    ok = run_tests()
    sys.exit(0 if ok else 1)
