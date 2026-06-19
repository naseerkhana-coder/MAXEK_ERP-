#!/usr/bin/env python3
"""Production-safe migration: schema + workflow sync, no demo user overwrite."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

os.environ["MAXEK_SKIP_DEMO_SEED"] = "1"

from app import app, init_db, get_db, ensure_payroll_tables
from workflow_service import migrate_workflow_statuses, sync_workflow_designations, seed_workflow_master
from company_master_service import ensure_company_master_schema
from client_billing_service import ensure_client_billing_schema
from project_photos_service import ensure_project_photos_schema
from employee_timesheet_service import ensure_employee_timesheet_schema
from attendance_service import ensure_staff_monthly_attendance_schema
from bbs_service import ensure_bbs_schema
from subcontractor_billing_service import ensure_subcontractor_billing_schema
from corporate_dms_service import ensure_corporate_dms_schema
from qc_service import ensure_qc_schema
from precast_service import ensure_precast_schema
from helpdesk_service import ensure_helpdesk_schema
from subcontract_payment_service import ensure_subcontract_payment_schema
from store_service import ensure_store_schema
from treasury_service import ensure_treasury_schema
from budget_service import ensure_budget_schema


def main():
    os.makedirs(os.path.join(ROOT, "database"), exist_ok=True)
    with app.app_context():
        init_db()
        db = get_db()
        ensure_payroll_tables(db)
        ensure_company_master_schema(db)
        ensure_client_billing_schema(db)
        ensure_project_photos_schema(db)
        ensure_employee_timesheet_schema(db)
        ensure_staff_monthly_attendance_schema(db)
        ensure_bbs_schema(db)
        ensure_subcontractor_billing_schema(db)
        ensure_subcontract_payment_schema(db)
        ensure_store_schema(db)
        ensure_treasury_schema(db)
        ensure_budget_schema(db)
        ensure_corporate_dms_schema(db)
        ensure_qc_schema(db)
        ensure_precast_schema(db)
        ensure_helpdesk_schema(db)
        seed_workflow_master(db)
        migrate_workflow_statuses(db)
        sync_workflow_designations(db)
        # Plant Phase 3 tables (QC, costing rates, maintenance, crusher) via ensure_plant_schema in init_db
        # QC Master (qc_tests) via ensure_qc_schema
        # Precast yards (precast_yards) via ensure_precast_schema
        # Help desk topics (help_topics) via ensure_helpdesk_schema
        db.commit()
    db_path = os.path.join(ROOT, "database", "maxek.db")
    print("Production migration complete.")
    print(f"Database: {db_path}")
    print("Demo users NOT re-seeded (MAXEK_SKIP_DEMO_SEED=1).")


if __name__ == "__main__":
    main()
