"""Staging E2E tests for material transfer, subcontract payments, BOQ bulk entry."""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

os.environ["MAXEK_SKIP_DEMO_SEED"] = "1"

from app import app, init_db, get_db  # noqa: E402
from workflow_service import get_approval_request  # noqa: E402


def _login(client, username="admin", password="admin"):
    return client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=True,
    )


def _approve_record(client, db, module_id: str, record_id: int, record_table: str):
    row = get_approval_request(db, module_id, record_id, record_table)
    if not row:
        return False, "approval request not found"
    approval_id = row["id"]
    status = row["workflow_status"]
    if status == "pending_checker":
        resp = client.post(
            "/approvals/action",
            data={
                "approval_id": approval_id,
                "action": "verify",
                "comments": "E2E verify",
                "role": "checker",
            },
            follow_redirects=True,
        )
        if resp.status_code >= 400:
            return False, f"verify HTTP {resp.status_code}"
        row = get_approval_request(db, module_id, record_id, record_table)
        if row and row["workflow_status"] == "pending_approval":
            resp = client.post(
                "/approvals/action",
                data={
                    "approval_id": approval_id,
                    "action": "approve",
                    "comments": "E2E approve",
                    "role": "approver",
                },
                follow_redirects=True,
            )
            if resp.status_code >= 400:
                return False, f"approve HTTP {resp.status_code}"
    elif status == "pending_approval":
        resp = client.post(
            "/approvals/action",
            data={
                "approval_id": approval_id,
                "action": "approve",
                "comments": "E2E approve",
                "role": "approver",
            },
            follow_redirects=True,
        )
        if resp.status_code >= 400:
            return False, f"approve HTTP {resp.status_code}"
    row = get_approval_request(db, module_id, record_id, record_table)
    if not row or row["workflow_status"] != "approved":
        return False, f"final status={row['workflow_status'] if row else None}"
    return True, "approved"


def _ensure_project(db):
    row = db.execute("SELECT id FROM projects ORDER BY id LIMIT 1").fetchone()
    if row:
        return row["id"]
    db.execute(
        "INSERT INTO projects(project_name, project_code, status) VALUES(?,?,?)",
        ("E2E Test Project", "E2E-001", "Active"),
    )
    db.commit()
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def _ensure_material(db, project_id: int):
    row = db.execute("SELECT id FROM materials ORDER BY id LIMIT 1").fetchone()
    if row:
        return row["id"]
    db.execute(
        "INSERT INTO materials(code, name, unit, is_active, created_at) VALUES(?,?,?,?,datetime('now'))",
        ("MAT-E2E", "E2E Cement", "Bag", 1),
    )
    mat_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.execute(
        "INSERT INTO stock_ledger(material_id, project_id, movement_date, movement_type, quantity, unit, reference_table, reference_id, remarks, created_at) "
        "VALUES(?,NULL,date('now'),'OPENING',?,?,?,?,?,datetime('now'))",
        (mat_id, 1000.0, "Bag", "seed", 0, "E2E seed stock"),
    )
    db.commit()
    return mat_id


def _ensure_subcontractor(db):
    row = db.execute("SELECT id FROM subcontractors ORDER BY id LIMIT 1").fetchone()
    if row:
        return row["id"]
    db.execute(
        "INSERT INTO subcontractors(subcontractor_name, mobile, status) VALUES(?,?,?)",
        ("E2E Sub Co", "9999999999", "Active"),
    )
    db.commit()
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def run_tests(use_existing_db: bool = False):
    results: list[tuple[str, str, str]] = []
    errors: list[str] = []
    tmp_dir = None
    db_backup = None
    db_path = os.path.join(ROOT, "database", "maxek.db")

    if not use_existing_db:
        tmp_dir = tempfile.mkdtemp(prefix="maxek_e2e_")
        test_db = os.path.join(tmp_dir, "maxek.db")
        os.makedirs(os.path.dirname(test_db), exist_ok=True)
        if os.path.isfile(db_path):
            shutil.copy2(db_path, test_db)
        import app as app_module

        app_module.DB_PATH = test_db
    elif os.path.isfile(db_path):
        db_backup = db_path + ".staging_e2e.bak"
        shutil.copy2(db_path, db_backup)

    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["SECRET_KEY"] = "e2e-test-secret"

    with app.app_context():
        init_db()
        db = get_db()
        ensure_store = __import__("store_service", fromlist=["ensure_store_schema"]).ensure_store_schema
        ensure_store(db)
        from subcontract_payment_service import ensure_subcontract_payment_schema

        ensure_subcontract_payment_schema(db)
        db.commit()

        project_id = _ensure_project(db)
        material_id = _ensure_material(db, project_id)
        sub_id = _ensure_subcontractor(db)
        db.commit()

        client = app.test_client()
        login_resp = _login(client)
        if login_resp.status_code >= 400 or b"Invalid" in login_resp.data:
            results.append(("Login admin/admin", "Fail", f"HTTP {login_resp.status_code}"))
            errors.append("Login failed")
            return results, errors
        results.append(("Login admin/admin", "Pass", "Session established"))

        # Material Transfer
        try:
            today = date.today().isoformat()
            resp = client.post(
                "/material-transfer",
                data={
                    "transfer_type": "store_to_site",
                    "transfer_date": today,
                    "source_project_id": "",
                    "dest_project_id": str(project_id),
                    "remarks": "E2E staging transfer",
                    "material_id[]": str(material_id),
                    "quantity[]": "10",
                    "unit[]": "Bag",
                    "line_remarks[]": "line1",
                },
                follow_redirects=True,
            )
            transfer_id = db.execute(
                "SELECT id FROM material_transfers ORDER BY id DESC LIMIT 1"
            ).fetchone()["id"]
            row = db.execute(
                "SELECT approval_status, stock_posted FROM material_transfers WHERE id=?",
                (transfer_id,),
            ).fetchone()
            if resp.status_code >= 400:
                raise RuntimeError(f"HTTP {resp.status_code}")
            if row["approval_status"] != "Pending Checker":
                raise RuntimeError(f"status={row['approval_status']}")
            ok, msg = _approve_record(
                client, db, "material_transfer", transfer_id, "material_transfers"
            )
            if not ok:
                raise RuntimeError(msg)
            row = db.execute(
                "SELECT approval_status, stock_posted FROM material_transfers WHERE id=?",
                (transfer_id,),
            ).fetchone()
            ledger = db.execute(
                "SELECT COUNT(*) AS c FROM stock_ledger WHERE reference_table='material_transfers' AND reference_id=?",
                (transfer_id,),
            ).fetchone()["c"]
            notes = f"approved={row['approval_status']}, stock_posted={row['stock_posted']}, ledger={ledger}"
            if row["approval_status"] != "Approved":
                results.append(("Material Transfer create+approve", "Fail", notes))
            elif row["stock_posted"] != 1 or ledger < 1:
                results.append(("Material Transfer stock posting", "Fail", notes))
            else:
                results.append(("Material Transfer create+approve+stock", "Pass", notes))
        except Exception as exc:
            results.append(("Material Transfer create+approve+stock", "Fail", str(exc)))
            errors.append(f"Material Transfer: {exc}")

        # Subcontract Payments
        try:
            resp = client.post(
                "/subcontract-payments",
                data={
                    "form_action": "save_work_order",
                    "project_id": str(project_id),
                    "subcontractor_id": str(sub_id),
                    "work_description": "E2E civil works",
                    "work_order_value": "100000",
                    "certified_value": "50000",
                    "retention_percent": "5",
                    "tds_percent": "2",
                    "start_date": today,
                },
                follow_redirects=True,
            )
            wo_id = db.execute(
                "SELECT id FROM subcontract_work_orders ORDER BY id DESC LIMIT 1"
            ).fetchone()["id"]
            ok, msg = _approve_record(
                client, db, "subcontract_payments", wo_id, "subcontract_work_orders"
            )
            if not ok:
                raise RuntimeError(f"WO approval: {msg}")
            wo = db.execute(
                "SELECT retention_amount, tds_amount, balance_amount, approval_status FROM subcontract_work_orders WHERE id=?",
                (wo_id,),
            ).fetchone()
            resp = client.post(
                "/subcontract-payments",
                data={
                    "form_action": "save_payment",
                    "work_order_id": str(wo_id),
                    "payment_date": today,
                    "payment_amount": "20000",
                    "tds_deducted": "400",
                    "retention_held": "1000",
                    "net_paid": "18600",
                    "payment_mode": "NEFT",
                    "reference_no": "E2E-PAY-1",
                },
                follow_redirects=True,
            )
            pay_id = db.execute(
                "SELECT id FROM subcontract_payment_entries ORDER BY id DESC LIMIT 1"
            ).fetchone()["id"]
            ok, msg = _approve_record(
                client, db, "subcontract_payments", pay_id, "subcontract_payment_entries"
            )
            if not ok:
                raise RuntimeError(f"Payment approval: {msg}")
            wo = db.execute(
                "SELECT paid_amount, retention_amount, tds_amount, balance_amount FROM subcontract_work_orders WHERE id=?",
                (wo_id,),
            ).fetchone()
            notes = (
                f"ret={wo['retention_amount']}, tds={wo['tds_amount']}, "
                f"paid={wo['paid_amount']}, bal={wo['balance_amount']}"
            )
            if abs(wo["retention_amount"] - 2500) > 0.01:
                results.append(("Subcontract WO retention/TDS calc", "Fail", notes))
            elif abs(wo["paid_amount"] - 18600) > 0.01:
                results.append(("Subcontract payment ledger", "Fail", notes))
            else:
                results.append(("Subcontract payments ledger", "Pass", notes))
        except Exception as exc:
            results.append(("Subcontract payments ledger", "Fail", str(exc)))
            errors.append(f"Subcontract Payments: {exc}")

        # BOQ Multiple Entry
        try:
            resp = client.post(
                "/boq-multiple-entry",
                data={
                    "project_id": str(project_id),
                    "item_description[]": ["E2E BOQ Item 1", "E2E BOQ Item 2"],
                    "unit[]": ["Nos", "Nos"],
                    "quantity[]": ["10", "5"],
                    "rate[]": ["100", "200"],
                },
                follow_redirects=True,
            )
            boq = db.execute(
                "SELECT id, boq_number, total_amount, line_count, approval_status FROM boq_master ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if resp.status_code >= 400:
                raise RuntimeError(f"HTTP {resp.status_code}")
            ok, msg = _approve_record(client, db, "boq", boq["id"], "boq_master")
            if not ok:
                raise RuntimeError(msg)
            boq = db.execute(
                "SELECT approval_status, total_amount, line_count FROM boq_master WHERE id=?",
                (boq["id"],),
            ).fetchone()
            notes = f"lines={boq['line_count']}, total={boq['total_amount']}, status={boq['approval_status']}"
            if boq["approval_status"] != "Approved" or boq["line_count"] != 2:
                results.append(("BOQ bulk entry + approval", "Fail", notes))
            else:
                results.append(("BOQ bulk entry + approval", "Pass", notes))
        except Exception as exc:
            results.append(("BOQ bulk entry + approval", "Fail", str(exc)))
            errors.append(f"BOQ: {exc}")

        # Audit closure nav + route smoke tests
        try:
            smoke_routes = [
                ("/client-billing", "Client Billing register"),
                ("/project-photos", "Project Photos register"),
                ("/leave-request", "Leave Management"),
                ("/fleet", "Fleet dashboard"),
                ("/plant", "Plant dashboard"),
                ("/quality-control", "QC Master"),
                ("/settings/corporate-dms", "Corporate DMS"),
                ("/securities-guarantees", "Securities register"),
                ("/settings/company-master", "Company Master"),
                ("/project-documents", "Project Documents register"),
                ("/wbs", "WBS redirect"),
                ("/payroll/revisions", "Rate Revisions"),
                ("/timesheets", "Monthly Timesheets"),
            ]
            failed_routes = []
            for path, label in smoke_routes:
                resp = client.get(path, follow_redirects=False)
                if resp.status_code not in (200, 302):
                    failed_routes.append(f"{label} ({resp.status_code})")
            if failed_routes:
                results.append(("Audit closure route smoke", "Fail", "; ".join(failed_routes)))
            else:
                results.append(("Audit closure route smoke", "Pass", f"{len(smoke_routes)} routes OK"))
        except Exception as exc:
            results.append(("Audit closure route smoke", "Fail", str(exc)))
            errors.append(f"Audit routes: {exc}")

        # Workflow modules registered
        try:
            mods = {
                r["module_id"]
                for r in db.execute(
                    "SELECT module_id FROM workflow_master WHERE status='Active'"
                ).fetchall()
            }
            needed = {
                "material_transfer",
                "subcontract_payments",
                "boq",
                "subcontractor_billing",
                "employee_timesheet",
                "cost_planning",
            }
            missing = needed - mods
            if missing:
                results.append(("Workflow module registration", "Fail", f"missing {missing}"))
            else:
                results.append(("Workflow module registration", "Pass", "audit closure modules active"))
        except Exception as exc:
            results.append(("Workflow module registration", "Fail", str(exc)))
            errors.append(f"Workflow: {exc}")

        db.commit()

    if db_backup and os.path.isfile(db_backup):
        shutil.copy2(db_backup, db_path)
        os.remove(db_backup)
    if tmp_dir:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return results, errors


if __name__ == "__main__":
    use_existing = os.environ.get("MAXEK_E2E_USE_EXISTING_DB", "0") == "1"
    results, errors = run_tests(use_existing_db=use_existing)
    print("\n=== STAGING E2E RESULTS ===")
    print(f"{'Test Case':<45} | {'Result':<6} | Notes")
    print("-" * 90)
    for name, status, notes in results:
        print(f"{name:<45} | {status:<6} | {notes}")
    if errors:
        print("\n=== ERROR LOG ===")
        for err in errors:
            print(err)
    failed = sum(1 for _, s, _ in results if s == "Fail")
    sys.exit(1 if failed else 0)
