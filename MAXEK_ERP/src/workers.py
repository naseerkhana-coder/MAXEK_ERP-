import os
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .settings import WORKER_PHOTOS, get_connection


class WorkerTab(ttk.Frame):
    def __init__(self, parent: ttk.Notebook) -> None:
        super().__init__(parent)
        self.photo_path = None
        self._build_ui()

    def _build_ui(self) -> None:
        labels = [
            "Sub Contractor Code",
            "Worker Name",
            "Age",
            "Trade",
            "Joining Date (YYYY-MM-DD)",
            "Salary Rate",
            "Working Hours",
            "Overtime Rate",
        ]

        self.entries = []
        for index, label in enumerate(labels):
            ttk.Label(self, text=label).grid(row=index, column=0, padx=16, pady=8, sticky="w")
            entry = ttk.Entry(self, width=42)
            entry.grid(row=index, column=1, padx=8)
            self.entries.append(entry)

        ttk.Button(self, text="Upload Photo", command=self.upload_photo).grid(row=1, column=3, padx=8)
        ttk.Button(self, text="Save Worker", command=self.save_worker).grid(row=10, column=1, pady=16, sticky="w")

    def upload_photo(self) -> None:
        file_path = filedialog.askopenfilename(filetypes=[("Image Files", "*.png *.jpg *.jpeg")])
        if not file_path:
            return

        dest_file = WORKER_PHOTOS / os.path.basename(file_path)
        try:
            shutil.copy(file_path, dest_file)
            self.photo_path = str(dest_file)
            messagebox.showinfo("Photo Uploaded", f"Photo saved to {dest_file}")
        except Exception as exc:
            messagebox.showerror("Upload Error", f"Unable to save photo: {exc}")

    def _generate_worker_id(self, sub_code: str) -> str:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM workers WHERE sub_code=?", (sub_code,))
        count = cursor.fetchone()[0] + 101
        conn.close()
        return f"{sub_code}{count}"

    def save_worker(self) -> None:
        sub_code = self.entries[0].get().strip().upper()
        worker_name = self.entries[1].get().strip()
        age_text = self.entries[2].get().strip()
        trade = self.entries[3].get().strip()
        joining_date = self.entries[4].get().strip()
        salary_text = self.entries[5].get().strip()
        working_hr_text = self.entries[6].get().strip()
        overtime_rate_text = self.entries[7].get().strip()

        if not sub_code or not worker_name:
            messagebox.showerror("Required", "Sub contractor code and worker name are required.")
            return

        try:
            age = int(age_text)
            salary = float(salary_text)
            working_hr = float(working_hr_text)
            overtime_rate = float(overtime_rate_text)
        except ValueError:
            messagebox.showerror("Validation", "Age, salary, hours, and overtime rate must be numeric.")
            return

        worker_id = self._generate_worker_id(sub_code)
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM subcontractors WHERE sub_code=?", (sub_code,))
        if not cursor.fetchone():
            messagebox.showerror("Validation", "Sub contractor code does not exist.")
            conn.close()
            return

        try:
            cursor.execute(
                "INSERT INTO workers (worker_id, sub_code, worker_name, age, trade, joining_date, salary, working_hr, overtime_rate, photo) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (worker_id, sub_code, worker_name, age, trade, joining_date, salary, working_hr, overtime_rate, self.photo_path),
            )
            conn.commit()
            messagebox.showinfo("Saved", f"Worker saved with ID {worker_id}")
            for entry in self.entries:
                entry.delete(0, tk.END)
            self.photo_path = None
        except Exception as exc:
            messagebox.showerror("Error", f"Unable to save worker: {exc}")
        finally:
            conn.close()
