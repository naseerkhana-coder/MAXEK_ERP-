"""Extended ERP tables and data helpers for purchase, store, HR, vehicles, and masters."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from modules.database import DATE_FMT, generate_id, get_conn

# Group: (group_id, group_label | None, [(page_key, label), ...])
MenuGroup = tuple[str, str | None, list[tuple[str, str]]]


def ensure_erp_extension_tables(conn=None) -> None:
    own = conn is None
    if own:
        conn = get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS erp_units(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unit_id TEXT UNIQUE,
            unit_name TEXT UNIQUE,
            status TEXT DEFAULT 'Active'
        );
        CREATE TABLE IF NOT EXISTS erp_material_categories(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id TEXT UNIQUE,
            category_name TEXT UNIQUE,
            status TEXT DEFAULT 'Active'
        );
        CREATE TABLE IF NOT EXISTS erp_staff_categories(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id TEXT UNIQUE,
            category_name TEXT UNIQUE,
            status TEXT DEFAULT 'Active'
        );
        CREATE TABLE IF NOT EXISTS erp_vendor_ratings(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rating_id TEXT UNIQUE,
            vendor_name TEXT,
            rating REAL,
            remarks TEXT,
            rated_by TEXT,
            rated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS erp_drivers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            driver_id TEXT UNIQUE,
            driver_name TEXT,
            mobile TEXT,
            license_no TEXT,
            status TEXT DEFAULT 'Active'
        );
        CREATE TABLE IF NOT EXISTS purchase_rfqs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rfq_id TEXT UNIQUE,
            rfq_date TEXT,
            project_name TEXT,
            item_summary TEXT,
            vendors_invited TEXT,
            due_date TEXT,
            status TEXT DEFAULT 'Open',
            created_by TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS purchase_quotations(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quote_id TEXT UNIQUE,
            rfq_id TEXT,
            vendor_name TEXT,
            quoted_amount REAL,
            delivery_days INTEGER,
            remarks TEXT,
            status TEXT DEFAULT 'Received',
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS grn_entries(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grn_id TEXT UNIQUE,
            grn_no TEXT,
            grn_date TEXT,
            po_ref TEXT,
            vendor_name TEXT,
            project_name TEXT,
            material_name TEXT,
            quantity REAL,
            unit TEXT,
            remarks TEXT,
            status TEXT DEFAULT 'Received',
            created_by TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS stock_returns(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            return_id TEXT UNIQUE,
            return_date TEXT,
            project_name TEXT,
            material_code TEXT,
            material_name TEXT,
            quantity REAL,
            reason TEXT,
            created_by TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS stock_transfers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transfer_id TEXT UNIQUE,
            transfer_date TEXT,
            from_site TEXT,
            to_site TEXT,
            material_code TEXT,
            material_name TEXT,
            quantity REAL,
            remarks TEXT,
            created_by TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS stock_adjustments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            adjustment_id TEXT UNIQUE,
            adjustment_date TEXT,
            site_name TEXT,
            material_code TEXT,
            material_name TEXT,
            old_qty REAL,
            new_qty REAL,
            reason TEXT,
            created_by TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS leave_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            leave_id TEXT UNIQUE,
            employee_id TEXT,
            employee_name TEXT,
            leave_type TEXT,
            from_date TEXT,
            to_date TEXT,
            days REAL,
            reason TEXT,
            status TEXT DEFAULT 'Pending',
            approved_by TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS employee_transfers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transfer_id TEXT UNIQUE,
            employee_id TEXT,
            employee_name TEXT,
            from_project TEXT,
            to_project TEXT,
            transfer_date TEXT,
            remarks TEXT,
            created_by TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS overtime_entries(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ot_id TEXT UNIQUE,
            employee_id TEXT,
            employee_name TEXT,
            ot_date TEXT,
            ot_hours REAL,
            project_name TEXT,
            remarks TEXT,
            status TEXT DEFAULT 'Pending',
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS bank_reconciliations(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recon_id TEXT UNIQUE,
            bank_account TEXT,
            statement_date TEXT,
            book_balance REAL,
            bank_balance REAL,
            difference REAL,
            status TEXT DEFAULT 'Draft',
            remarks TEXT,
            created_by TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS cheque_register(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cheque_id TEXT UNIQUE,
            cheque_no TEXT,
            bank_name TEXT,
            payee TEXT,
            amount REAL,
            cheque_date TEXT,
            status TEXT DEFAULT 'Issued',
            remarks TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS asset_fuel_logs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            log_id TEXT UNIQUE,
            asset_id TEXT,
            asset_name TEXT,
            log_date TEXT,
            fuel_qty REAL,
            cost REAL,
            operator TEXT,
            remarks TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS asset_maintenance(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            maint_id TEXT UNIQUE,
            asset_id TEXT,
            asset_name TEXT,
            scheduled_date TEXT,
            maintenance_type TEXT,
            cost REAL,
            status TEXT DEFAULT 'Scheduled',
            remarks TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS asset_breakdowns(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            breakdown_id TEXT UNIQUE,
            asset_id TEXT,
            asset_name TEXT,
            breakdown_date TEXT,
            downtime_hours REAL,
            repair_cost REAL,
            status TEXT DEFAULT 'Open',
            remarks TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS vehicles(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id TEXT UNIQUE,
            vehicle_no TEXT,
            vehicle_type TEXT,
            make_model TEXT,
            driver_name TEXT,
            status TEXT DEFAULT 'Active'
        );
        CREATE TABLE IF NOT EXISTS vehicle_allocations(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            allocation_id TEXT UNIQUE,
            vehicle_id TEXT,
            vehicle_no TEXT,
            project_name TEXT,
            from_date TEXT,
            to_date TEXT,
            driver_name TEXT,
            remarks TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS vehicle_trips(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trip_id TEXT UNIQUE,
            vehicle_no TEXT,
            trip_date TEXT,
            from_location TEXT,
            to_location TEXT,
            start_km REAL,
            end_km REAL,
            purpose TEXT,
            driver_name TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS vehicle_fuel_logs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fuel_id TEXT UNIQUE,
            vehicle_no TEXT,
            fuel_date TEXT,
            litres REAL,
            rate REAL,
            amount REAL,
            odometer REAL,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS vehicle_services(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_id TEXT UNIQUE,
            vehicle_no TEXT,
            service_date TEXT,
            service_type TEXT,
            cost REAL,
            next_due_date TEXT,
            remarks TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS vehicle_insurance(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            insurance_id TEXT UNIQUE,
            vehicle_no TEXT,
            policy_no TEXT,
            insurer TEXT,
            from_date TEXT,
            to_date TEXT,
            premium REAL,
            status TEXT DEFAULT 'Active',
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS calendar_events(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT UNIQUE,
            event_date TEXT,
            title TEXT,
            event_type TEXT,
            project_name TEXT,
            description TEXT,
            created_by TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS controlled_documents(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id TEXT UNIQUE,
            doc_type TEXT,
            doc_title TEXT,
            project_name TEXT,
            version TEXT,
            file_path TEXT,
            status TEXT DEFAULT 'Active',
            uploaded_by TEXT,
            uploaded_at TEXT
        );
        """
    )
    if own:
        conn.commit()
        conn.close()


def _now() -> str:
    return datetime.now().strftime(f"{DATE_FMT} %H:%M")


def _insert_row(table: str, id_col: str, prefix: str, data: dict) -> str:
    ensure_erp_extension_tables()
    conn = get_conn()
    row_id = data.get(id_col) or generate_id(prefix, table, id_col, conn=conn)
    data[id_col] = row_id
    data.setdefault("created_at", _now())
    cols = ", ".join(data.keys())
    placeholders = ", ".join("?" for _ in data)
    conn.execute(f"INSERT INTO {table}({cols}) VALUES({placeholders})", tuple(data.values()))
    conn.commit()
    conn.close()
    return row_id


def _load_table(table: str, order_col: str = "id", limit: int = 200) -> pd.DataFrame:
    ensure_erp_extension_tables()
    conn = get_conn()
    df = pd.read_sql_query(
        f"SELECT * FROM {table} ORDER BY {order_col} DESC LIMIT ?",
        conn,
        params=(max(1, min(limit, 500)),),
    )
    conn.close()
    return df


def save_simple_master(table: str, id_col: str, prefix: str, name_col: str, name: str) -> None:
    _insert_row(table, id_col, prefix, {name_col: name.strip(), "status": "Active"})


def load_simple_master(table: str, name_col: str = "unit_name") -> pd.DataFrame:
    return _load_table(table)


def save_purchase_rfq(data: dict, actor: str) -> str:
    data["created_by"] = actor
    return _insert_row("purchase_rfqs", "rfq_id", "RFQ", data)


def load_purchase_rfqs() -> pd.DataFrame:
    return _load_table("purchase_rfqs")


def save_purchase_quotation(data: dict) -> str:
    return _insert_row("purchase_quotations", "quote_id", "QT", data)


def load_purchase_quotations() -> pd.DataFrame:
    return _load_table("purchase_quotations")


def save_grn(data: dict, actor: str) -> str:
    data["created_by"] = actor
    return _insert_row("grn_entries", "grn_id", "GRN", data)


def load_grn_entries() -> pd.DataFrame:
    return _load_table("grn_entries")


def save_stock_return(data: dict, actor: str) -> str:
    data["created_by"] = actor
    return _insert_row("stock_returns", "return_id", "SR", data)


def load_stock_returns() -> pd.DataFrame:
    return _load_table("stock_returns")


def save_stock_transfer(data: dict, actor: str) -> str:
    data["created_by"] = actor
    return _insert_row("stock_transfers", "transfer_id", "ST", data)


def load_stock_transfers() -> pd.DataFrame:
    return _load_table("stock_transfers")


def save_stock_adjustment(data: dict, actor: str) -> str:
    data["created_by"] = actor
    return _insert_row("stock_adjustments", "adjustment_id", "SA", data)


def load_stock_adjustments() -> pd.DataFrame:
    return _load_table("stock_adjustments")


def save_leave_request(data: dict) -> str:
    return _insert_row("leave_requests", "leave_id", "LV", data)


def load_leave_requests(status: str | None = None) -> pd.DataFrame:
    ensure_erp_extension_tables()
    conn = get_conn()
    sql = "SELECT * FROM leave_requests"
    params: list = []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY id DESC LIMIT 200"
    df = pd.read_sql_query(sql, conn, params=params or None)
    conn.close()
    return df


def update_leave_status(leave_id: str, status: str, approved_by: str) -> None:
    ensure_erp_extension_tables()
    conn = get_conn()
    conn.execute(
        "UPDATE leave_requests SET status = ?, approved_by = ? WHERE leave_id = ?",
        (status, approved_by, leave_id),
    )
    conn.commit()
    conn.close()


def save_employee_transfer(data: dict, actor: str) -> str:
    data["created_by"] = actor
    return _insert_row("employee_transfers", "transfer_id", "ET", data)


def load_employee_transfers() -> pd.DataFrame:
    return _load_table("employee_transfers")


def save_overtime_entry(data: dict) -> str:
    return _insert_row("overtime_entries", "ot_id", "OT", data)


def load_overtime_entries() -> pd.DataFrame:
    return _load_table("overtime_entries")


def save_bank_reconciliation(data: dict, actor: str) -> str:
    data["created_by"] = actor
    data["difference"] = float(data.get("bank_balance", 0)) - float(data.get("book_balance", 0))
    return _insert_row("bank_reconciliations", "recon_id", "BR", data)


def load_bank_reconciliations() -> pd.DataFrame:
    return _load_table("bank_reconciliations")


def save_cheque(data: dict) -> str:
    return _insert_row("cheque_register", "cheque_id", "CHQ", data)


def load_cheques() -> pd.DataFrame:
    return _load_table("cheque_register")


def save_asset_fuel(data: dict) -> str:
    return _insert_row("asset_fuel_logs", "log_id", "AF", data)


def load_asset_fuel_logs() -> pd.DataFrame:
    return _load_table("asset_fuel_logs")


def save_asset_maintenance(data: dict) -> str:
    return _insert_row("asset_maintenance", "maint_id", "AM", data)


def load_asset_maintenance() -> pd.DataFrame:
    return _load_table("asset_maintenance")


def save_asset_breakdown(data: dict) -> str:
    return _insert_row("asset_breakdowns", "breakdown_id", "AB", data)


def load_asset_breakdowns() -> pd.DataFrame:
    return _load_table("asset_breakdowns")


def save_vehicle(data: dict) -> str:
    return _insert_row("vehicles", "vehicle_id", "VH", data)


def load_vehicles() -> pd.DataFrame:
    return _load_table("vehicles")


def save_vehicle_allocation(data: dict) -> str:
    return _insert_row("vehicle_allocations", "allocation_id", "VA", data)


def load_vehicle_allocations() -> pd.DataFrame:
    return _load_table("vehicle_allocations")


def save_vehicle_trip(data: dict) -> str:
    return _insert_row("vehicle_trips", "trip_id", "TR", data)


def load_vehicle_trips() -> pd.DataFrame:
    return _load_table("vehicle_trips")


def save_vehicle_fuel(data: dict) -> str:
    data["amount"] = float(data.get("litres", 0)) * float(data.get("rate", 0))
    return _insert_row("vehicle_fuel_logs", "fuel_id", "VF", data)


def load_vehicle_fuel_logs() -> pd.DataFrame:
    return _load_table("vehicle_fuel_logs")


def save_vehicle_service(data: dict) -> str:
    return _insert_row("vehicle_services", "service_id", "VS", data)


def load_vehicle_services() -> pd.DataFrame:
    return _load_table("vehicle_services")


def save_vehicle_insurance(data: dict) -> str:
    return _insert_row("vehicle_insurance", "insurance_id", "VI", data)


def load_vehicle_insurance() -> pd.DataFrame:
    return _load_table("vehicle_insurance")


def save_calendar_event(data: dict, actor: str) -> str:
    data["created_by"] = actor
    return _insert_row("calendar_events", "event_id", "EV", data)


def load_calendar_events(month: str | None = None) -> pd.DataFrame:
    ensure_erp_extension_tables()
    conn = get_conn()
    sql = "SELECT * FROM calendar_events"
    params: list = []
    if month:
        sql += " WHERE event_date LIKE ?"
        params.append(f"{month}%")
    sql += " ORDER BY event_date ASC LIMIT 500"
    df = pd.read_sql_query(sql, conn, params=params or None)
    conn.close()
    return df


def save_controlled_document(data: dict, actor: str) -> str:
    data["uploaded_by"] = actor
    data["uploaded_at"] = _now()
    return _insert_row("controlled_documents", "doc_id", "DOC", data)


def load_controlled_documents(doc_type: str | None = None) -> pd.DataFrame:
    ensure_erp_extension_tables()
    conn = get_conn()
    sql = "SELECT * FROM controlled_documents"
    params: list = []
    if doc_type:
        sql += " WHERE doc_type = ?"
        params.append(doc_type)
    sql += " ORDER BY id DESC LIMIT 200"
    df = pd.read_sql_query(sql, conn, params=params or None)
    conn.close()
    return df


def save_vendor_rating(data: dict, actor: str) -> str:
    data["rated_by"] = actor
    data["rated_at"] = _now()
    return _insert_row("erp_vendor_ratings", "rating_id", "VR", data)


def load_vendor_ratings() -> pd.DataFrame:
    return _load_table("erp_vendor_ratings")


def save_driver(data: dict) -> str:
    return _insert_row("erp_drivers", "driver_id", "DR", data)


def load_drivers() -> pd.DataFrame:
    return _load_table("erp_drivers")


def load_stock_register_df() -> pd.DataFrame:
    from modules.database import load_material_master

    ensure_erp_extension_tables()
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM stock_register ORDER BY material_name", conn)
    conn.close()
    if df.empty:
        return load_material_master()
    return df


def load_site_wise_stock() -> pd.DataFrame:
    from modules.database import load_material_issues

    issues = load_material_issues(limit=500)
    if issues.empty:
        return issues
    return (
        issues.groupby(["project_name", "material_code", "material_name"], dropna=False)["quantity"]
        .sum()
        .reset_index(name="issued_qty")
    )


def load_low_stock_items(threshold: float = 10.0) -> pd.DataFrame:
    stock = load_stock_register_df()
    if stock.empty:
        return stock
    bal_col = "balance" if "balance" in stock.columns else None
    if bal_col:
        return stock[stock[bal_col].fillna(0) <= threshold]
    return stock.head(0)


def load_stock_valuation() -> pd.DataFrame:
    stock = load_stock_register_df()
    if stock.empty:
        return stock
    if "balance" in stock.columns:
        stock = stock.copy()
        stock["estimated_value"] = stock["balance"].fillna(0) * 100
    return stock
