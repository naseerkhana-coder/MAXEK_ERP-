import tkinter as tk
from tkinter import messagebox, ttk

from .settings import get_connection


class SubcontractorTab(ttk.Frame):
    def __init__(self, parent: ttk.Notebook) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        labels = [
            "Sub Contractor Name",
            "Joining Date (YYYY-MM-DD)",
            "Bank Account",
            "Bank Name",
            "IFSC Code",
            "Branch Name",
            "Date of Birth (YYYY-MM-DD)",
            "Region",
            "PAN Number",
            "Contact Number",
        ]

        self.entries = []
        for index, label in enumerate(labels):
            ttk.Label(self, text=label).grid(row=index, column=0, padx=16, pady=10, sticky="w")
            entry = ttk.Entry(self, width=42)
            entry.grid(row=index, column=1, padx=8)
            self.entries.append(entry)

        ttk.Button(self, text="Save", command=self.save_subcontractor).grid(row=10, column=1, pady=16, sticky="w")

    def save_subcontractor(self) -> None:
        sub_name = self.entries[0].get().strip()
        joining_date = self.entries[1].get().strip()
        bank_account = self.entries[2].get().strip()
        bank_name = self.entries[3].get().strip()
        ifsc_code = self.entries[4].get().strip()
        branch_name = self.entries[5].get().strip()
        date_of_birth = self.entries[6].get().strip()
        region = self.entries[7].get().strip()
        pan_number = self.entries[8].get().strip()
        contact_number = self.entries[9].get().strip()

        if not sub_name:
            messagebox.showerror("Required", "Sub contractor name is required.")
            return
        if not joining_date:
            messagebox.showerror("Required", "Joining date is required.")
            return

        sub_code = sub_name[:2].upper()
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO subcontractors (sub_code, sub_name, joining_date, bank_account, bank_name, ifsc_code, branch_name, date_of_birth, region, pan_number, contact_number) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (sub_code, sub_name, joining_date, bank_account, bank_name, ifsc_code, branch_name, date_of_birth, region, pan_number, contact_number),
            )
            conn.commit()
            messagebox.showinfo("Saved", f"Sub contractor {sub_name} saved with code {sub_code}.")
            for entry in self.entries:
                entry.delete(0, tk.END)
        except Exception as exc:
            messagebox.showerror("Error", f"Unable to save subcontractor: {exc}")
        finally:
            conn.close()
