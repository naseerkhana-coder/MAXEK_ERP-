import json
import os
import sqlite3
import sys

import pytest
from flask import Flask, render_template, render_template_string, request


APP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "MAXEK_ERP")
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from payroll_service import (
    calculate_monthly_staff_pay,
    calculate_worker_period_pay,
    fetch_payroll_details,
    update_payroll_snapshot_totals,
)


@pytest.fixture
def payroll_app(tmp_path):
    db = sqlite3.connect(str(tmp_path / "payroll-details.db"))
    db.row_factory = sqlite3.Row
    db.executescript(
        """
        CREATE TABLE staff(
            id INTEGER PRIMARY KEY, employee_code TEXT, staff_name TEXT, department TEXT,
            designation TEXT, salary_type TEXT, salary_amount REAL, ot_applicable TEXT,
            ot_rate_per_hour REAL, holiday_pay_applicable TEXT, working_hours REAL,
            status TEXT, bank_account TEXT, bank_name TEXT, ifsc_code TEXT, branch_name TEXT,
            company_room_provided TEXT, company_food_provided TEXT,
            pf_applicable INTEGER, pf_rate REAL, esi_applicable INTEGER, esi_rate REAL,
            joining_date TEXT
        );
        CREATE TABLE workers(
            id INTEGER PRIMARY KEY, worker_code TEXT, worker_name TEXT, department TEXT,
            designation TEXT, salary_type TEXT, salary_amount REAL, ot_applicable TEXT,
            ot_rate_per_hour REAL, holiday_pay_applicable TEXT, working_hours REAL,
            worker_category TEXT, subcontractor_id INTEGER, project_id INTEGER, status TEXT,
            bank_account TEXT, bank_name TEXT, ifsc_code TEXT, branch_name TEXT
        );
        CREATE TABLE subcontractors(
            id INTEGER PRIMARY KEY, subcontractor_name TEXT, company_name TEXT
        );
        CREATE TABLE projects(id INTEGER PRIMARY KEY, project_name TEXT);
        CREATE TABLE attendance(
            id INTEGER PRIMARY KEY, worker_id INTEGER, worker_source TEXT,
            attendance_date TEXT, total_hours REAL, ot_hours REAL, status TEXT,
            approval_status TEXT
        );
        CREATE TABLE staff_monthly_attendance(
            id INTEGER PRIMARY KEY, staff_id INTEGER, year_month TEXT, worked_days REAL,
            half_days REAL, absent_days REAL, ot_hours REAL, approval_status TEXT
        );
        CREATE TABLE staff_salary_components(
            id INTEGER PRIMARY KEY, staff_id INTEGER, component_name TEXT, amount REAL,
            sort_order INTEGER
        );
        CREATE TABLE staff_travel_tiers(
            id INTEGER PRIMARY KEY, staff_id INTEGER, continuous_months INTEGER,
            travel_mode TEXT, allowance_amount REAL, sort_order INTEGER
        );
        CREATE TABLE employee_monthly_timesheets(
            id INTEGER PRIMARY KEY, timesheet_ref TEXT, employee_source TEXT,
            staff_id INTEGER, worker_id INTEGER, project_id INTEGER, year_month TEXT,
            working_days REAL, leave_days REAL, holiday_days REAL, overtime_hours REAL,
            total_days REAL, total_salary_paid REAL, timesheet_status TEXT,
            approval_status TEXT
        );
        CREATE TABLE payroll_runs(
            id INTEGER PRIMARY KEY, run_ref TEXT, period_start TEXT, period_end TEXT,
            month INTEGER, year INTEGER, employee_type TEXT, status TEXT,
            approval_status TEXT, draft_saved INTEGER, total_gross REAL,
            total_deductions REAL, total_net REAL, employee_count INTEGER, created_by TEXT
        );
        CREATE TABLE payroll_lines(
            id INTEGER PRIMARY KEY, payroll_run_id INTEGER, employee_type TEXT,
            staff_id INTEGER, worker_id INTEGER, employee_code TEXT, employee_name TEXT,
            department TEXT, project_id INTEGER, salary_type TEXT, base_salary REAL,
            working_days REAL, present_days REAL, leave_days REAL, ot_hours REAL,
            ot_amount REAL, holiday_pay REAL, gross_salary REAL, deductions REAL,
            advance_deduction REAL, net_salary REAL, verification_status TEXT,
            approval_status TEXT, payment_status TEXT, locked INTEGER,
            calc_snapshot TEXT, remarks TEXT
        );
        CREATE TABLE salary_payments(
            id INTEGER PRIMARY KEY, payroll_run_id INTEGER, payroll_line_id INTEGER,
            payment_date TEXT, payment_mode TEXT, bank_name TEXT, utr_ref TEXT,
            gross_amount REAL, deductions REAL, net_amount REAL, remarks TEXT,
            created_by TEXT, created_at TEXT
        );
        """
    )
    app = Flask(
        __name__,
        template_folder=os.path.join(APP_DIR, "templates"),
        static_folder=os.path.join(APP_DIR, "static"),
    )
    app.config.update(TESTING=True, SECRET_KEY="payroll-test")
    app.jinja_env.globals["url_for"] = (
        lambda endpoint, **values: f"/{endpoint}/"
        + "/".join(str(value) for value in values.values())
    )

    @app.get("/screen/<int:line_id>")
    def screen(line_id):
        detail = fetch_payroll_details(db, line_id=line_id)[0]
        return render_template_string(
            "{% from '_payroll_detail_sections.html' import payroll_detail %}"
            "{{ payroll_detail(detail) }}",
            detail=detail,
        )

    @app.get("/run/<int:run_id>")
    def run_print(run_id):
        run = dict(db.execute("SELECT * FROM payroll_runs WHERE id=?", (run_id,)).fetchone())
        return render_template(
            "payroll_run_print.html",
            run=run,
            lines=fetch_payroll_details(db, run_id=run_id),
            report_mode=request.args.get("view", "details"),
            print_date="04 Aug 2026 01:05",
            print_mode=False,
        )

    @app.get("/slip/<int:line_id>")
    def slip_print(line_id):
        line = fetch_payroll_details(db, line_id=line_id)[0]
        return render_template(
            "payroll_print_slip.html",
            line=line,
            bank={},
            payment=None,
            print_date="04 Aug 2026 01:05",
            print_mode=False,
        )

    yield app, db
    db.close()


def _insert_staff(db, code, name, salary=31000):
    db.execute(
        "INSERT INTO staff(employee_code, staff_name, department, designation, salary_type, "
        "salary_amount, ot_applicable, ot_rate_per_hour, working_hours, status, bank_account, "
        "bank_name, ifsc_code, pf_applicable, esi_applicable) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            code,
            name,
            "Engineering",
            "Site Engineer",
            "Monthly",
            salary,
            "Yes",
            200,
            8,
            "Active",
            "1234567890",
            "Test Bank",
            "TEST0001",
            1,
            1,
        ),
    )
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def _insert_run_and_line(db, staff_id, *, status="Draft", payment_status="Pending"):
    snapshot = {
        "calendar_days": 31,
        "working_days": 31,
        "present_days": 29.5,
        "absent_days": 1,
        "ot_hours": 6,
        "attendance": {
            "calendar_days": 31,
            "working_days": 31,
            "present_days": 29.5,
            "paid_days": 30.5,
            "absent_days": 1,
            "weekly_offs": 4,
            "holidays": 1,
            "paid_leave": 1,
            "unpaid_leave": 1,
            "half_days": 1,
            "normal_hours": 236,
            "overtime_hours": 6,
            "late_hours": None,
            "late_deduction": None,
            "timesheet_references": ["TS-202607-0001"],
            "source": "approved_timesheet",
        },
        "earnings": {
            "basic_salary": 20000,
            "basic_earned": 19000,
            "hra": 8000,
            "allowances": 3000,
            "overtime_amount": 1200,
            "incentives": 500,
            "arrears": 0,
            "reimbursements": 300,
            "other_earnings": 0,
            "holiday_pay": 0,
            "gross_earnings": 32000,
        },
        "deduction_breakdown": {
            "absence_deduction": 500,
            "unpaid_leave_deduction": 300,
            "late_deduction": 0,
            "advance_recovery": 1000,
            "loan_recovery": 500,
            "pf": 1200,
            "esi": 0,
            "professional_tax": 200,
            "tds": 300,
            "other_deductions": 0,
            "total_deductions": 4000,
        },
        "payroll_month": "07/2026",
        "prepared_by": "payroll.tester",
    }
    db.execute(
        "INSERT INTO payroll_runs(run_ref, period_start, period_end, month, year, employee_type, "
        "status, approval_status, draft_saved, total_gross, total_deductions, total_net, "
        "employee_count, created_by) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "PR-TEST-001",
            "2026-07-01",
            "2026-07-31",
            7,
            2026,
            "company_staff",
            status,
            "Approved" if status != "Draft" else "Draft",
            1,
            32000,
            4000,
            28000,
            1,
            "payroll.tester",
        ),
    )
    run_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    staff = db.execute("SELECT * FROM staff WHERE id=?", (staff_id,)).fetchone()
    db.execute(
        "INSERT INTO payroll_lines(payroll_run_id, employee_type, staff_id, employee_code, "
        "employee_name, department, salary_type, base_salary, working_days, present_days, "
        "leave_days, ot_hours, ot_amount, gross_salary, deductions, advance_deduction, "
        "net_salary, approval_status, payment_status, calc_snapshot) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            run_id,
            "staff",
            staff_id,
            staff["employee_code"],
            staff["staff_name"],
            staff["department"],
            "Monthly",
            31000,
            31,
            29.5,
            1,
            6,
            1200,
            32000,
            3000,
            1000,
            28000,
            "Approved" if status != "Draft" else "Draft",
            payment_status,
            json.dumps(snapshot),
        ),
    )
    line_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.commit()
    return run_id, line_id


def test_salaried_calculation_captures_attendance_allowances_ot_and_deductions(payroll_app):
    _, db = payroll_app
    staff_id = _insert_staff(db, "EMP-001", "Full Month Employee")
    for name, amount, order in (
        ("Basic Salary", 20000, 1),
        ("HRA", 8000, 2),
        ("Special Allowance", 3000, 3),
    ):
        db.execute(
            "INSERT INTO staff_salary_components(staff_id, component_name, amount, sort_order) "
            "VALUES(?,?,?,?)",
            (staff_id, name, amount, order),
        )
    attendance = (
        ("2026-07-01", "Present", 8, 2),
        ("2026-07-02", "Half Day", 4, 0),
        ("2026-07-03", "Paid Leave", 0, 0),
        ("2026-07-04", "Unpaid Leave", 0, 0),
        ("2026-07-05", "Absent", 0, 0),
    )
    for day, status, hours, ot in attendance:
        db.execute(
            "INSERT INTO attendance(worker_id, worker_source, attendance_date, total_hours, "
            "ot_hours, status, approval_status) VALUES(?,?,?,?,?,?,?)",
            (staff_id, "staff", day, hours, ot, status, "Approved"),
        )
    staff = dict(db.execute("SELECT * FROM staff WHERE id=?", (staff_id,)).fetchone())
    calc = calculate_monthly_staff_pay(db, staff, "2026-07-01", "2026-07-31", [])

    assert calc["attendance"]["present_days"] == 1.5
    assert calc["attendance"]["paid_leave"] == 1
    assert calc["attendance"]["unpaid_leave"] == 1
    assert calc["attendance"]["half_days"] == 1
    assert calc["attendance"]["overtime_hours"] == 2
    assert calc["earnings"]["hra"] > 0
    assert calc["earnings"]["allowances"] > 0
    assert calc["deduction_breakdown"]["pf"] > 0
    assert calc["deduction_breakdown"]["esi"] > 0
    assert calc["gross_salary"] - calc["deductions"] - calc["advance_deduction"] == calc["net_salary"]


def test_salaried_full_attendance_pays_complete_month(payroll_app):
    _, db = payroll_app
    staff_id = _insert_staff(db, "EMP-FULL", "Full Attendance Employee")
    db.execute(
        "INSERT INTO staff_monthly_attendance(staff_id, year_month, worked_days, half_days, "
        "absent_days, ot_hours, approval_status) VALUES(?,?,?,?,?,?,?)",
        (staff_id, "2026-07", 27, 0, 0, 0, "Approved"),
    )
    staff = dict(db.execute("SELECT * FROM staff WHERE id=?", (staff_id,)).fetchone())
    calc = calculate_monthly_staff_pay(db, staff, "2026-07-01", "2026-07-31", [])

    assert calc["calendar_days"] == 31
    assert calc["working_days"] == 27
    assert calc["paid_days"] == 31
    assert calc["gross_salary"] == 31000
    assert calc["gross_salary"] - calc["deductions"] == calc["net_salary"]


def test_approved_timesheet_drives_worker_pay_and_advance_recovery(payroll_app):
    _, db = payroll_app
    db.execute(
        "INSERT INTO workers(worker_code, worker_name, worker_category, designation, salary_type, "
        "salary_amount, ot_applicable, ot_rate_per_hour, working_hours, status) "
        "VALUES(?,?,?,?,?,?,?,?,?,?)",
        ("WRK-001", "Timesheet Worker", "Company Staff", "Technician", "Daily", 1000, "Yes", 100, 8, "Active"),
    )
    worker_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.execute(
        "INSERT INTO employee_monthly_timesheets(timesheet_ref, employee_source, worker_id, "
        "year_month, working_days, leave_days, holiday_days, overtime_hours, total_days, "
        "total_salary_paid, timesheet_status, approval_status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "TS-202607-0002",
            "worker",
            worker_id,
            "2026-07",
            20,
            2,
            1,
            5,
            20,
            2000,
            "Approved",
            "Approved",
        ),
    )
    worker = dict(db.execute("SELECT * FROM workers WHERE id=?", (worker_id,)).fetchone())
    calc = calculate_worker_period_pay(db, worker, "2026-07-01", "2026-07-31", [])

    assert calc["attendance_source"] == "approved_timesheet"
    assert calc["timesheet_references"] == ["TS-202607-0002"]
    assert calc["present_days"] == 20
    assert calc["ot_hours"] == 5
    assert calc["advance_deduction"] == 2000
    assert calc["gross_salary"] == 20500
    assert calc["net_salary"] == 18500


def test_advance_recovery_is_capped_to_preserve_payroll_equation(payroll_app):
    _, db = payroll_app
    db.execute(
        "INSERT INTO workers(worker_code, worker_name, worker_category, salary_type, "
        "salary_amount, ot_applicable, working_hours, status) VALUES(?,?,?,?,?,?,?,?)",
        ("WRK-CAP", "Advance Cap Worker", "Company Staff", "Daily", 1000, "No", 8, "Active"),
    )
    worker_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.execute(
        "INSERT INTO employee_monthly_timesheets(timesheet_ref, employee_source, worker_id, "
        "year_month, working_days, leave_days, holiday_days, overtime_hours, total_salary_paid, "
        "timesheet_status, approval_status) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (
            "TS-202607-CAP",
            "worker",
            worker_id,
            "2026-07",
            1,
            0,
            0,
            0,
            5000,
            "Approved",
            "Approved",
        ),
    )
    worker = dict(db.execute("SELECT * FROM workers WHERE id=?", (worker_id,)).fetchone())
    calc = calculate_worker_period_pay(db, worker, "2026-07-01", "2026-07-31", [])

    assert calc["gross_salary"] == 1000
    assert calc["advance_deduction"] == 1000
    assert calc["advance_balance_carried_forward"] == 4000
    assert calc["gross_salary"] - calc["advance_deduction"] == calc["net_salary"]


def test_draft_edit_reconciles_saved_snapshot_components():
    original = {
        "gross_salary": 30000,
        "deductions": 1000,
        "advance_deduction": 500,
        "net_salary": 28500,
        "earnings": {
            "basic_earned": 20000,
            "hra": 8000,
            "allowances": 2000,
            "other_earnings": 0,
            "gross_earnings": 30000,
        },
        "deduction_breakdown": {
            "pf": 1000,
            "advance_recovery": 500,
            "other_deductions": 0,
            "total_deductions": 1500,
        },
    }
    updated = json.loads(
        update_payroll_snapshot_totals(
            json.dumps(original),
            gross_salary=31000,
            deductions=1200,
            advance_deduction=800,
            net_salary=29000,
        )
    )

    assert updated["earnings"]["other_earnings"] == 1000
    assert updated["earnings"]["gross_earnings"] == 31000
    assert updated["deduction_breakdown"]["other_deductions"] == 200
    assert updated["deduction_breakdown"]["total_deductions"] == 2000
    assert updated["gross_salary"] - updated["deduction_breakdown"]["total_deductions"] == updated["net_salary"]


@pytest.mark.parametrize("run_status", ["Draft", "Approved", "Paid"])
def test_individual_and_consolidated_views_match_saved_payroll(
    payroll_app, run_status
):
    app, db = payroll_app
    staff_id = _insert_staff(db, f"EMP-{run_status}", f"{run_status} Employee")
    run_id, line_id = _insert_run_and_line(
        db,
        staff_id,
        status=run_status,
        payment_status="Paid" if run_status == "Paid" else "Pending",
    )
    if run_status == "Paid":
        db.execute(
            "INSERT INTO salary_payments(payroll_run_id, payroll_line_id, payment_date, "
            "payment_mode, net_amount, created_by) VALUES(?,?,?,?,?,?)",
            (run_id, line_id, "2026-08-01", "Bank Transfer", 28000, "payroll.tester"),
        )
        db.commit()

    details = fetch_payroll_details(db, line_id=line_id)
    assert len(details) == 1
    detail = details[0]
    assert detail["gross_earnings"] - detail["total_deductions"] == detail["net_payable"]
    assert detail["attendance"]["timesheet_references"] == ["TS-202607-0001"]
    assert detail["balance_payable"] == (0 if run_status == "Paid" else 28000)

    client = app.test_client()
    responses = (
        client.get(f"/screen/{line_id}"),
        client.get(f"/run/{run_id}?view=summary"),
        client.get(f"/run/{run_id}?view=details"),
        client.get(f"/slip/{line_id}"),
    )
    assert all(response.status_code == 200 for response in responses)
    for response in responses:
        html = response.get_data(as_text=True)
        assert "32000.00" in html
        assert "28000.00" in html
    assert "Approved timesheet" in responses[0].get_data(as_text=True)
    assert "Full Month Details" in responses[2].get_data(as_text=True)
    assert "Salary Slip" in responses[3].get_data(as_text=True)


def test_missing_legacy_components_are_not_rendered_as_zero(payroll_app):
    app, db = payroll_app
    staff_id = _insert_staff(db, "EMP-LEGACY", "Legacy Draft")
    run_id, line_id = _insert_run_and_line(db, staff_id)
    db.execute(
        "UPDATE payroll_lines SET calc_snapshot=? WHERE id=?",
        (
            json.dumps(
                {
                    "working_days": 31,
                    "present_days": 31,
                    "gross_salary": 31000,
                    "deductions": 0,
                    "net_salary": 31000,
                }
            ),
            line_id,
        ),
    )
    db.commit()

    client = app.test_client()
    html = client.get(f"/screen/{line_id}").get_data(as_text=True)
    assert "<dt>HRA</dt><dd>—</dd>" in html
    assert "<dt>Late hours</dt><dd>—</dd>" in html


def test_multiple_employee_details_total_to_batch_summary(payroll_app):
    _, db = payroll_app
    first_staff = _insert_staff(db, "EMP-MULTI-1", "First Employee")
    run_id, first_line = _insert_run_and_line(db, first_staff)
    second_staff = _insert_staff(db, "EMP-MULTI-2", "Second Employee")
    first = dict(db.execute("SELECT * FROM payroll_lines WHERE id=?", (first_line,)).fetchone())
    columns = [
        "payroll_run_id", "employee_type", "staff_id", "employee_code", "employee_name",
        "department", "project_id", "salary_type", "base_salary", "working_days",
        "present_days", "leave_days", "ot_hours", "ot_amount", "holiday_pay",
        "gross_salary", "deductions", "advance_deduction", "net_salary",
        "verification_status", "approval_status", "payment_status", "locked",
        "calc_snapshot", "remarks",
    ]
    values = [first[column] for column in columns]
    values[2] = second_staff
    values[3] = "EMP-MULTI-2"
    values[4] = "Second Employee"
    db.execute(
        f"INSERT INTO payroll_lines({','.join(columns)}) "
        f"VALUES({','.join('?' for _ in columns)})",
        values,
    )
    db.execute(
        "UPDATE payroll_runs SET employee_count=2, total_gross=64000, "
        "total_deductions=8000, total_net=56000 WHERE id=?",
        (run_id,),
    )
    db.commit()

    run = dict(db.execute("SELECT * FROM payroll_runs WHERE id=?", (run_id,)).fetchone())
    details = fetch_payroll_details(db, run_id=run_id)
    assert len(details) == 2
    assert sum(row["gross_earnings"] for row in details) == run["total_gross"]
    assert sum(row["total_deductions"] for row in details) == run["total_deductions"]
    assert sum(row["net_payable"] for row in details) == run["total_net"]
