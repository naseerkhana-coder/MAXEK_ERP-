from pathlib import Path

import pandas as pd

from .settings import ATTENDANCE_REPORTS, EXCEL_REPORTS


def export_salary_report_excel(worker_id: str, query: str, conn, filename: str) -> Path:
    df = pd.read_sql_query(query, conn, params=(worker_id,))
    destination = EXCEL_REPORTS / filename
    df.to_excel(destination, index=False)
    return destination


def export_attendance_report_excel(conn, filename: str) -> Path:
    df = pd.read_sql_query("SELECT * FROM attendance ORDER BY date DESC", conn)
    destination = ATTENDANCE_REPORTS / filename
    df.to_excel(destination, index=False)
    return destination
