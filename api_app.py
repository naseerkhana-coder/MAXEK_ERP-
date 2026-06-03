"""
MAXEK ERP API (FastAPI) — mobile app backend.
"""

from __future__ import annotations

import base64
import hmac
import hashlib
import os
import time
from datetime import datetime
from typing import Any, Literal

import pandas as pd
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from modules.branding import ERP_API_TITLE
from modules.database import (
    DATE_FMT,
    calculate_hours,
    parse_flexible_time,
    delete_attendance_record,
    generate_id,
    get_attendance_record,
    get_conn,
    get_employee,
    init_db,
    kpi_stats,
    list_payroll_by_workflow,
    load_client_names,
    load_employee_options,
    load_lookup,
    load_project_names,
    update_attendance_record,
    update_payroll_workflow,
)
from modules.payroll_engine import ATTENDANCE_STATUSES, infer_attendance_category

API_TOKEN_SECRET = os.getenv("MAXEK_API_TOKEN_SECRET", "dev-secret-change-me")
API_TOKEN_TTL_SECONDS = int(os.getenv("MAXEK_API_TOKEN_TTL_SECONDS", "86400"))


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def _sign(payload: str) -> str:
    mac = hmac.new(API_TOKEN_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).digest()
    return _b64url_encode(mac)


def issue_token(user_id: str, role: str, username: str) -> str:
    now = int(time.time())
    payload = f"{user_id}|{username}|{role}|{now}"
    sig = _sign(payload)
    return _b64url_encode(payload.encode("utf-8")) + "." + sig


def verify_token(token: str) -> dict[str, str]:
    try:
        payload_b64, sig = token.split(".", 1)
        payload = _b64url_decode(payload_b64).decode("utf-8")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=401, detail="Invalid token format") from exc

    if not hmac.compare_digest(_sign(payload), sig):
        raise HTTPException(status_code=401, detail="Invalid token signature")

    try:
        user_id, username, role, issued_at_str = payload.split("|", 3)
        issued_at = int(issued_at_str)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=401, detail="Invalid token payload") from exc

    if int(time.time()) - issued_at > API_TOKEN_TTL_SECONDS:
        raise HTTPException(status_code=401, detail="Token expired")

    return {"user_id": user_id, "username": username, "role": role}


def require_auth(authorization: str | None = Header(default=None)) -> dict[str, str]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    return verify_token(token)


def _ensure_material_requests_table() -> None:
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS material_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT UNIQUE,
            project_name TEXT,
            item_name TEXT,
            quantity REAL,
            unit TEXT,
            required_date TEXT,
            remarks TEXT,
            status TEXT DEFAULT 'Pending',
            created_by TEXT,
            created_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    token: str
    user_id: str
    full_name: str
    role: str


class AttendanceCreateRequest(BaseModel):
    employee_id: str = Field(min_length=1)
    attendance_date: str = Field(description=f"Date in {DATE_FMT} format")
    project_name: str = ""
    in_time: str = ""
    out_time: str = ""
    break_hours: float = 0.0
    status: str = "Present"
    remarks: str = ""


class AttendanceUpdateRequest(BaseModel):
    attendance_date: str = Field(description=f"Date in {DATE_FMT} format")
    project_name: str = ""
    in_time: str = ""
    out_time: str = ""
    break_hours: float = 0.0
    status: str = "Present"
    remarks: str = ""


def _parse_attendance_date(date_str: str):
    try:
        return datetime.strptime(str(date_str).strip()[:10], DATE_FMT).date()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid date. Use {DATE_FMT}") from exc


def _attendance_hours_for_employee(employee: dict, payload) -> tuple[float, float, float, float, float]:
    fixed_working_hours = 8.0
    applied_rate = float(employee.get("salary_amount") or 0)
    applied_ot_rate = float(employee.get("ot_rate") or 0)
    ot_allowed = (employee.get("ot_applicable") or "").lower() == "yes"
    total_hours, ot_hours = 0.0, 0.0
    in_raw = getattr(payload, "in_time", "") or ""
    out_raw = getattr(payload, "out_time", "") or ""
    break_hours = float(getattr(payload, "break_hours", 0) or 0)
    in_time = ""
    out_time = ""
    try:
        if in_raw:
            in_time = parse_flexible_time(in_raw, is_out_time=False)
        if out_raw:
            out_time = parse_flexible_time(out_raw, is_out_time=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if in_time and out_time:
        try:
            total_hours, ot_hours = calculate_hours(
                in_time, out_time, break_hours, fixed_working_hours, ot_allowed
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return total_hours, ot_hours, fixed_working_hours, applied_rate, applied_ot_rate


def _attendance_fields(employee_id: str, payload) -> dict:
    if payload.status not in ATTENDANCE_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Use: {ATTENDANCE_STATUSES}")
    employee = get_employee(employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    att_date = _parse_attendance_date(payload.attendance_date)
    total_hours, ot_hours, fixed_working_hours, applied_rate, applied_ot_rate = _attendance_hours_for_employee(
        employee, payload
    )
    attendance_category, payment_type, holiday_name = infer_attendance_category(
        employee, att_date, payload.status
    )
    return {
        "project_name": payload.project_name or "",
        "attendance_date": att_date.strftime(DATE_FMT),
        "in_time": payload.in_time or "",
        "out_time": payload.out_time or "",
        "break_hours": float(payload.break_hours or 0.0),
        "total_hours": total_hours,
        "ot_hours": ot_hours,
        "status": payload.status,
        "remarks": payload.remarks or "",
        "worked_hours": total_hours,
        "overtime": ot_hours,
        "start_time": payload.in_time or "",
        "end_time": payload.out_time or "",
        "attendance_category": attendance_category,
        "payment_type": payment_type,
        "holiday_name": holiday_name,
        "fixed_working_hours": fixed_working_hours,
        "applied_rate": applied_rate,
        "applied_ot_rate": applied_ot_rate,
    }


class PayrollActionRequest(BaseModel):
    remarks: str = ""


class MaterialRequestCreate(BaseModel):
    project_name: str = ""
    item_name: str = Field(min_length=1)
    quantity: float = Field(gt=0)
    unit: str = "Nos"
    required_date: str = ""
    remarks: str = ""


class MaterialActionRequest(BaseModel):
    status: Literal["Approved", "Rejected", "Issued"]


class DprCreateRequest(BaseModel):
    project_name: str = Field(min_length=1)
    dpr_date: str = Field(description=f"Date in {DATE_FMT}")
    progress_quantity: float = 0.0
    remarks: str = ""


class ExpenseCreateRequest(BaseModel):
    expense_date: str = Field(description=f"Date in {DATE_FMT}")
    expense_head: str = Field(min_length=1)
    project_name: str = ""
    client_name: str = ""
    paid_to: str = ""
    amount: float = Field(gt=0)
    payment_mode: str = "Cash"
    approved_by: str = ""
    remarks: str = ""


class StandardResponse(BaseModel):
    ok: bool
    message: str = ""
    data: Any | None = None


app = FastAPI(title=ERP_API_TITLE, version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db()
    _ensure_material_requests_table()


@app.get("/api/health", response_model=StandardResponse)
def health() -> StandardResponse:
    return StandardResponse(ok=True, message="ok")


@app.post("/api/login", response_model=LoginResponse)
def api_login(payload: LoginRequest) -> LoginResponse:
    conn = get_conn()
    row = conn.execute(
        "SELECT user_id, full_name, role, username FROM users WHERE username=? AND password=?",
        (payload.username.strip(), payload.password),
    ).fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    user_id, full_name, role, username = row
    token = issue_token(str(user_id or ""), str(role or "User"), str(username or payload.username))
    return LoginResponse(
        token=token,
        user_id=str(user_id or ""),
        full_name=str(full_name or ""),
        role=str(role or "User"),
    )


@app.get("/api/me", response_model=StandardResponse)
def api_me(auth: dict[str, str] = Depends(require_auth)) -> StandardResponse:
    conn = get_conn()
    row = conn.execute(
        "SELECT user_id, full_name, role, username, mobile FROM users WHERE user_id=? OR username=? LIMIT 1",
        (auth["user_id"], auth["username"]),
    ).fetchone()
    conn.close()
    if not row:
        return StandardResponse(ok=True, data=auth)
    return StandardResponse(
        ok=True,
        data={
            "user_id": row[0],
            "full_name": row[1],
            "role": row[2],
            "username": row[3],
            "mobile": row[4],
        },
    )


@app.get("/api/dashboard", response_model=StandardResponse)
def api_dashboard(auth: dict[str, str] = Depends(require_auth)) -> StandardResponse:
    _ = auth
    return StandardResponse(ok=True, data=kpi_stats())


@app.get("/api/employees", response_model=StandardResponse)
def api_employees(auth: dict[str, str] = Depends(require_auth)) -> StandardResponse:
    _ = auth
    rows = [
        {"employee_id": eid, "employee_name": name}
        for eid, name in load_employee_options()
    ]
    return StandardResponse(ok=True, data=rows)


@app.get("/api/projects", response_model=StandardResponse)
def api_projects(auth: dict[str, str] = Depends(require_auth)) -> StandardResponse:
    _ = auth
    return StandardResponse(ok=True, data=load_project_names())


@app.get("/api/attendance/statuses", response_model=StandardResponse)
def attendance_statuses(auth: dict[str, str] = Depends(require_auth)) -> StandardResponse:
    _ = auth
    return StandardResponse(ok=True, data=ATTENDANCE_STATUSES)


@app.get("/api/attendance", response_model=StandardResponse)
def get_attendance(
    employee_id: str,
    limit: int = 50,
    auth: dict[str, str] = Depends(require_auth),
) -> StandardResponse:
    _ = auth
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT id, employee_id, employee_name, attendance_date, project_name,
               in_time, out_time, break_hours, total_hours, ot_hours,
               status, remarks, attendance_category
        FROM attendance
        WHERE employee_id = ? OR worker_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        conn,
        params=(employee_id, employee_id, max(1, min(limit, 500))),
    )
    conn.close()
    return StandardResponse(ok=True, data=df.to_dict(orient="records"))


@app.get("/api/attendance/{attendance_id}", response_model=StandardResponse)
def get_attendance_by_id(
    attendance_id: int,
    auth: dict[str, str] = Depends(require_auth),
) -> StandardResponse:
    _ = auth
    record = get_attendance_record(attendance_id)
    if not record:
        raise HTTPException(status_code=404, detail="Timesheet not found")
    return StandardResponse(ok=True, data=record)


@app.post("/api/attendance", response_model=StandardResponse)
def create_attendance(
    payload: AttendanceCreateRequest,
    auth: dict[str, str] = Depends(require_auth),
) -> StandardResponse:
    _ = auth
    fields = _attendance_fields(payload.employee_id, payload)
    employee = get_employee(payload.employee_id)
    conn = get_conn()
    duplicate = conn.execute(
        "SELECT id FROM attendance WHERE employee_id=? AND attendance_date=?",
        (payload.employee_id, fields["attendance_date"]),
    ).fetchone()
    if duplicate:
        conn.close()
        raise HTTPException(status_code=409, detail="Attendance already exists for this date")

    conn.execute(
        """
        INSERT INTO attendance(
            employee_id, employee_name, employee_type, department, designation,
            project_name, sub_contractor, attendance_date, in_time, out_time,
            break_hours, total_hours, ot_hours, status, remarks,
            worker_id, worker_name, start_time, end_time, worked_hours, overtime, work_description,
            fixed_working_hours, applied_rate, applied_ot_rate, attendance_category, payment_type, holiday_name
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            payload.employee_id,
            employee.get("employee_name") or "",
            employee.get("employee_type") or "",
            employee.get("department") or "",
            employee.get("designation") or "",
            fields["project_name"],
            employee.get("company_or_subcontractor") or "",
            fields["attendance_date"],
            fields["in_time"],
            fields["out_time"],
            fields["break_hours"],
            fields["total_hours"],
            fields["ot_hours"],
            fields["status"],
            fields["remarks"],
            payload.employee_id,
            employee.get("employee_name") or "",
            fields["start_time"],
            fields["end_time"],
            fields["worked_hours"],
            fields["overtime"],
            fields["remarks"],
            fields["fixed_working_hours"],
            fields["applied_rate"],
            fields["applied_ot_rate"],
            fields["attendance_category"],
            fields["payment_type"],
            fields["holiday_name"],
        ),
    )
    conn.commit()
    conn.close()
    return StandardResponse(ok=True, message="Attendance saved")


@app.put("/api/attendance/{attendance_id}", response_model=StandardResponse)
def update_attendance(
    attendance_id: int,
    payload: AttendanceUpdateRequest,
    auth: dict[str, str] = Depends(require_auth),
) -> StandardResponse:
    _ = auth
    record = get_attendance_record(attendance_id)
    if not record:
        raise HTTPException(status_code=404, detail="Timesheet not found")
    employee_id = record.get("employee_id") or record.get("worker_id")
    if not employee_id:
        raise HTTPException(status_code=400, detail="Invalid timesheet record")
    fields = _attendance_fields(str(employee_id), payload)
    conn = get_conn()
    duplicate = conn.execute(
        """
        SELECT id FROM attendance
        WHERE (employee_id=? OR worker_id=?) AND attendance_date=? AND id != ?
        """,
        (employee_id, employee_id, fields["attendance_date"], attendance_id),
    ).fetchone()
    if duplicate:
        conn.close()
        raise HTTPException(status_code=409, detail="Another timesheet already exists for this date")
    conn.close()
    update_attendance_record(attendance_id, fields)
    return StandardResponse(ok=True, message="Timesheet updated")


@app.delete("/api/attendance/{attendance_id}", response_model=StandardResponse)
def remove_attendance(
    attendance_id: int,
    auth: dict[str, str] = Depends(require_auth),
) -> StandardResponse:
    _ = auth
    record = get_attendance_record(attendance_id)
    if not record:
        raise HTTPException(status_code=404, detail="Timesheet not found")
    delete_attendance_record(attendance_id)
    return StandardResponse(ok=True, message="Timesheet deleted")


@app.get("/api/payroll", response_model=StandardResponse)
def get_payroll(
    workflow_status: str = "Submitted to MD",
    payment_status: Literal["Pending", "Paid"] | None = None,
    auth: dict[str, str] = Depends(require_auth),
) -> StandardResponse:
    _ = auth
    df = list_payroll_by_workflow(workflow_status, payment_status=payment_status)
    return StandardResponse(ok=True, data=df.to_dict(orient="records"))


@app.post("/api/payroll/{payroll_id}/approve", response_model=StandardResponse)
def approve_payroll(
    payroll_id: str,
    body: PayrollActionRequest,
    auth: dict[str, str] = Depends(require_auth),
) -> StandardResponse:
    role = (auth.get("role") or "").strip()
    if role not in ("Admin", "MD"):
        raise HTTPException(status_code=403, detail="Only MD/Admin can approve payroll")
    update_payroll_workflow(payroll_id, "MD Approved", body.remarks)
    return StandardResponse(ok=True, message="Payroll approved")


@app.post("/api/payroll/{payroll_id}/reject", response_model=StandardResponse)
def reject_payroll(
    payroll_id: str,
    body: PayrollActionRequest,
    auth: dict[str, str] = Depends(require_auth),
) -> StandardResponse:
    role = (auth.get("role") or "").strip()
    if role not in ("Admin", "MD"):
        raise HTTPException(status_code=403, detail="Only MD/Admin can reject payroll")
    update_payroll_workflow(payroll_id, "Rejected", body.remarks)
    return StandardResponse(ok=True, message="Payroll rejected")


@app.post("/api/payroll/{payroll_id}/send-back", response_model=StandardResponse)
def send_back_payroll(
    payroll_id: str,
    body: PayrollActionRequest,
    auth: dict[str, str] = Depends(require_auth),
) -> StandardResponse:
    role = (auth.get("role") or "").strip()
    if role not in ("Admin", "MD"):
        raise HTTPException(status_code=403, detail="Only MD/Admin can send back payroll")
    update_payroll_workflow(payroll_id, "Sent Back", body.remarks)
    return StandardResponse(ok=True, message="Payroll sent back to HR")


@app.get("/api/dpr", response_model=StandardResponse)
def list_dpr(
    limit: int = 50,
    auth: dict[str, str] = Depends(require_auth),
) -> StandardResponse:
    _ = auth
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT dpr_id, dpr_date, project_name, progress_quantity, status, remarks, created_by
        FROM dpr_reports
        ORDER BY id DESC
        LIMIT ?
        """,
        conn,
        params=(max(1, min(limit, 200)),),
    )
    conn.close()
    return StandardResponse(ok=True, data=df.to_dict(orient="records"))


@app.post("/api/dpr", response_model=StandardResponse)
def create_dpr(
    payload: DprCreateRequest,
    auth: dict[str, str] = Depends(require_auth),
) -> StandardResponse:
    dpr_id = generate_id("DPR", "dpr_reports")
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO dpr_reports(
            dpr_id, dpr_date, project_name, progress_quantity, remarks,
            status, created_by, created_at
        ) VALUES(?,?,?,?,?,?,?,?)
        """,
        (
            dpr_id,
            payload.dpr_date,
            payload.project_name,
            float(payload.progress_quantity or 0),
            payload.remarks or "",
            "Submitted",
            auth.get("username") or auth.get("user_id") or "",
            now,
        ),
    )
    conn.commit()
    conn.close()
    return StandardResponse(ok=True, message="DPR created", data={"dpr_id": dpr_id})


@app.get("/api/materials", response_model=StandardResponse)
def list_materials(
    status: str | None = None,
    auth: dict[str, str] = Depends(require_auth),
) -> StandardResponse:
    _ = auth
    conn = get_conn()
    sql = """
        SELECT request_id, project_name, item_name, quantity, unit,
               required_date, remarks, status, created_by, created_at
        FROM material_requests
    """
    params: list[Any] = []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY id DESC LIMIT 100"
    df = pd.read_sql_query(sql, conn, params=params or None)
    conn.close()
    return StandardResponse(ok=True, data=df.to_dict(orient="records"))


@app.post("/api/materials", response_model=StandardResponse)
def create_material_request(
    payload: MaterialRequestCreate,
    auth: dict[str, str] = Depends(require_auth),
) -> StandardResponse:
    request_id = generate_id("MR", "material_requests")
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    req_date = payload.required_date or datetime.now().strftime(DATE_FMT)
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO material_requests(
            request_id, project_name, item_name, quantity, unit,
            required_date, remarks, status, created_by, created_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?)
        """,
        (
            request_id,
            payload.project_name or "",
            payload.item_name,
            float(payload.quantity),
            payload.unit or "Nos",
            req_date,
            payload.remarks or "",
            "Pending",
            auth.get("username") or "",
            now,
        ),
    )
    conn.commit()
    conn.close()
    return StandardResponse(ok=True, message="Material request created", data={"request_id": request_id})


@app.post("/api/materials/{request_id}/status", response_model=StandardResponse)
def update_material_status(
    request_id: str,
    body: MaterialActionRequest,
    auth: dict[str, str] = Depends(require_auth),
) -> StandardResponse:
    role = (auth.get("role") or "").strip()
    if role not in ("Admin", "MD", "Project Manager", "Site Engineer"):
        raise HTTPException(status_code=403, detail="Not allowed to update material request")
    conn = get_conn()
    cur = conn.execute(
        "UPDATE material_requests SET status = ? WHERE request_id = ?",
        (body.status, request_id),
    )
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Request not found")
    return StandardResponse(ok=True, message=f"Status updated to {body.status}")


@app.get("/api/expense-heads", response_model=StandardResponse)
def list_expense_heads(auth: dict[str, str] = Depends(require_auth)) -> StandardResponse:
    _ = auth
    return StandardResponse(ok=True, data=load_lookup("expense_heads", "head_name"))


@app.get("/api/clients", response_model=StandardResponse)
def list_clients(auth: dict[str, str] = Depends(require_auth)) -> StandardResponse:
    _ = auth
    return StandardResponse(ok=True, data=load_client_names())


@app.get("/api/expenses", response_model=StandardResponse)
def list_expenses(
    limit: int = 50,
    auth: dict[str, str] = Depends(require_auth),
) -> StandardResponse:
    _ = auth
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT expense_id, expense_date, expense_head, project_name,
               client_name, paid_to, amount, payment_mode, approved_by, remarks
        FROM expenses
        ORDER BY id DESC
        LIMIT ?
        """,
        conn,
        params=(max(1, min(limit, 200)),),
    )
    conn.close()
    return StandardResponse(ok=True, data=df.to_dict(orient="records"))


@app.post("/api/expenses", response_model=StandardResponse)
def create_expense(
    payload: ExpenseCreateRequest,
    auth: dict[str, str] = Depends(require_auth),
) -> StandardResponse:
    _parse_attendance_date(payload.expense_date)
    expense_heads = load_lookup("expense_heads", "head_name")
    if payload.expense_head not in expense_heads:
        raise HTTPException(status_code=400, detail="Invalid expense head")
    payment_modes = {"Cash", "Bank Transfer", "Cheque", "UPI"}
    if payload.payment_mode not in payment_modes:
        raise HTTPException(status_code=400, detail=f"Invalid payment mode. Use: {sorted(payment_modes)}")

    expense_id = generate_id("EXP", "expenses")
    approved_by = payload.approved_by.strip() or auth.get("username") or auth.get("user_id") or ""
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO expenses(
            expense_id, expense_date, expense_head, project_name,
            client_name, paid_to, amount, payment_mode, approved_by, bill_upload, remarks
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            expense_id,
            payload.expense_date,
            payload.expense_head,
            payload.project_name or "",
            payload.client_name or "",
            payload.paid_to or "",
            float(payload.amount),
            payload.payment_mode,
            approved_by,
            "",
            payload.remarks or "",
        ),
    )
    conn.commit()
    conn.close()
    return StandardResponse(ok=True, message="Expense saved", data={"expense_id": expense_id})
