import tkinter as tk
from tkinter import ttk

from .attendance import AttendanceTab
from .reports import ReportTab
from .settings import get_connection
from .subcontractor import SubcontractorTab
from .workers import WorkerTab


class DashboardWindow(tk.Toplevel):
    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master)
        self.title("MAXEK Payroll ERP")
        self.geometry("1320x760")
        self.state("zoomed")

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)

        self._create_tabs()
        self._create_footer()

    def _create_tabs(self) -> None:
        self.subcontractor_tab = SubcontractorTab(self.notebook)
        self.workers_tab = WorkerTab(self.notebook)
        self.attendance_tab = AttendanceTab(self.notebook)
        self.report_tab = ReportTab(self.notebook)

        self.notebook.add(self.subcontractor_tab, text="Sub Contractors")
        self.notebook.add(self.workers_tab, text="Workers")
        self.notebook.add(self.attendance_tab, text="Attendance")
        self.notebook.add(self.report_tab, text="Reports")

    def _create_footer(self) -> None:
        frame = ttk.Frame(self)
        frame.pack(fill="x", pady=8)

        ttk.Button(frame, text="Exit", command=self._exit_app).pack(side="right", padx=16)

    def _exit_app(self) -> None:
        self.master.destroy()
        self.destroy()
