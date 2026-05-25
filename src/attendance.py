import tkinter as tk
from tkinter import messagebox, ttk

from .settings import get_connection


class AttendanceTab(ttk.Frame):
    def __init__(self, parent: ttk.Notebook) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        labels = [
            "Worker ID",
            "Date (YYYY-MM-DD)",
            "Start Time (HH:MM)",
            "End Time (HH:MM)",
            "Break Time Hours",
            "Project Name",
        ]

        self.entries = []
        for index, label in enumerate(labels):
            ttk.Label(self, text=label).grid(row=index, column=0, padx=16, pady=10, sticky="w")
            entry = ttk.Entry(self, width=42)
            entry.grid(row=index, column=1, padx=8)
            self.entries.append(entry)

        self.entries[1].insert(0, "2026-01-01")
        self.entries[2].insert(0, "09:00")
        self.entries[3].insert(0, "18:00")
        self.entries[4].insert(0, "1.0")

        ttk.Button(self, text="Save Attendance", command=self.save_attendance).grid(row=7, column=1, pady=16, sticky="w")

    def _parse_hours(self, start_time: str, end_time: str, break_hours: str) -> tuple[float, float, float]:
        from datetime import datetime

        fmt = "%H:%M"
        try:
            start = datetime.strptime(start_time.strip(), fmt)
            end = datetime.strptime(end_time.strip(), fmt)
        except ValueError:
            raise ValueError("Start and end times must use HH:MM format.")

        if end <= start:
            raise ValueError("End time must be later than start time.")

        try:
            break_time = float(break_hours)
        except ValueError:
            raise ValueError("Break time must be numeric.")

        total_hours = (end - start).seconds / 3600.0
        worked_hours = round(total_hours - break_time, 2)
        if worked_hours < 0:
            raise ValueError("Break time cannot exceed total shift duration.")

        overtime = round(max(0.0, worked_hours - 8.0), 2)
        return worked_hours, overtime, total_hours

    def save_attendance(self) -> None:
        worker_id = self.entries[0].get().strip().upper()
        date_value = self.entries[1].get().strip()
        start_time = self.entries[2].get().strip()
        end_time = self.entries[3].get().strip()
        break_time = self.entries[4].get().strip()
        project_name = self.entries[5].get().strip()

        if not worker_id:
            messagebox.showerror("Required", "Worker ID is required.")
            return

        try:
            worked_hours, overtime, _ = self._parse_hours(start_time, end_time, break_time)
        except ValueError as exc:
            messagebox.showerror("Validation", str(exc))
            return

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM workers WHERE worker_id=?", (worker_id,))
        if cursor.fetchone() is None:
            messagebox.showerror("Validation", "Worker ID not found.")
            conn.close()
            return

        cursor.execute(
            "INSERT INTO attendance (worker_id, date, start_time, end_time, break_time, worked_hours, overtime, project_name) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (worker_id, date_value, start_time, end_time, float(break_time), worked_hours, overtime, project_name),
        )
        conn.commit()
        conn.close()

        messagebox.showinfo("Saved", f"Attendance saved. Worked: {worked_hours}h, Overtime: {overtime}h")
        for entry in self.entries:
            entry.delete(0, tk.END)
        self.entries[1].insert(0, date_value)
