import tkinter as tk
from tkinter import messagebox, ttk

import pandas as pd

from .excel_export import export_attendance_report_excel, export_salary_report_excel
from .pdf_generator import create_payslip_pdf
from .payroll import calculate_payroll
from .settings import get_connection


class ReportTab(ttk.Frame):
    def __init__(self, parent: ttk.Notebook) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        ttk.Label(self, text="Worker ID").grid(row=0, column=0, padx=16, pady=10, sticky="w")
        self.worker_id_entry = ttk.Entry(self, width=42)
        self.worker_id_entry.grid(row=0, column=1, padx=8)

        ttk.Button(self, text="Export Salary Excel", command=self._export_salary_report).grid(row=2, column=1, pady=10, sticky="w")
        ttk.Button(self, text="Generate PDF Payslip", command=self._generate_payslip).grid(row=3, column=1, pady=10, sticky="w")
        ttk.Button(self, text="Export Attendance Report", command=self._export_attendance_report).grid(row=4, column=1, pady=10, sticky="w")

    def _export_salary_report(self) -> None:
        worker_id = self.worker_id_entry.get().strip().upper()
        if not worker_id:
            messagebox.showerror("Required", "Worker ID is required for salary export.")
            return

        conn = get_connection()
        query = """
        SELECT a.worker_id,
               w.worker_name,
               SUM(a.worked_hours) AS total_hours,
               SUM(a.overtime) AS total_overtime,
               w.salary AS salary_rate,
               w.overtime_rate
        FROM attendance a
        JOIN workers w ON a.worker_id = w.worker_id
        WHERE a.worker_id = ?
        GROUP BY a.worker_id, w.worker_name, w.salary, w.overtime_rate
        """
        filename = f"{worker_id}_salary_report.xlsx"
        try:
            destination = export_salary_report_excel(worker_id, query, conn, filename)
            messagebox.showinfo("Exported", f"Salary report saved to {destination}")
        except Exception as exc:
            messagebox.showerror("Export Error", f"Unable to export salary report: {exc}")
        finally:
            conn.close()

    def _generate_payslip(self) -> None:
        worker_id = self.worker_id_entry.get().strip().upper()
        if not worker_id:
            messagebox.showerror("Required", "Worker ID is required for PDF payslip.")
            return

        conn = get_connection()
        query = """
        SELECT w.worker_name, w.salary AS salary_rate, w.overtime_rate,
               COALESCE(SUM(a.worked_hours), 0) AS total_hours,
               COALESCE(SUM(a.overtime), 0) AS total_overtime
        FROM workers w
        LEFT JOIN attendance a ON w.worker_id = a.worker_id
        WHERE w.worker_id = ?
        GROUP BY w.worker_id
        """
        try:
            df = pd.read_sql_query(query, conn, params=(worker_id,))
            if df.empty:
                raise ValueError("Worker not found.")

            row = df.iloc[0]
            payroll = calculate_payroll(float(row["total_hours"]), float(row["total_overtime"]), float(row["salary_rate"]), float(row["overtime_rate"]))
            data = {
                "worker_id": worker_id,
                "worker_name": row["worker_name"],
                "salary_rate": float(row["salary_rate"]),
                "overtime_rate": float(row["overtime_rate"]),
                "total_hours": float(row["total_hours"]),
                "overtime_hours": float(row["total_overtime"]),
                **payroll,
            }
            destination = create_payslip_pdf(f"{worker_id}_payslip.pdf", data)
            messagebox.showinfo("Generated", f"Payslip saved to {destination}")
        except Exception as exc:
            messagebox.showerror("PDF Error", f"Unable to generate payslip: {exc}")
        finally:
            conn.close()

    def _export_attendance_report(self) -> None:
        conn = get_connection()
        filename = "attendance_report.xlsx"
        try:
            destination = export_attendance_report_excel(conn, filename)
            messagebox.showinfo("Exported", f"Attendance report saved to {destination}")
        except Exception as exc:
            messagebox.showerror("Export Error", f"Unable to export attendance report: {exc}")
        finally:
            conn.close()
