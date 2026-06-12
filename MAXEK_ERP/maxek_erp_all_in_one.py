# =========================================================
# MAXEK ERP SYSTEM - ALL IN ONE SINGLE FILE
# =========================================================
# FEATURES INCLUDED
# =========================================================
# ✔ Login System
# ✔ Dashboard
# ✔ User Creation
# ✔ Client Master
# ✔ Project Master
# ✔ Sub Contractor Master
# ✔ Worker Master
# ✔ Staff Master
# ✔ Worker Photo Upload + Preview
# ✔ Auto Worker ID
# ✔ Attendance Entry
# ✔ Salary Calculation
# ✔ Between Date Reports
# ✔ Excel Export + Auto Open
# ✔ Salary Paid Option
# ✔ Sub Contractor Advance
# ✔ Good Looking Dashboard
# =========================================================

# INSTALL REQUIRED:
# pip install pillow pandas openpyxl tkcalendar

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkcalendar import DateEntry
from PIL import Image, ImageTk
import sqlite3
import pandas as pd
from datetime import datetime
import os

# =========================================================
# CREATE FOLDERS
# =========================================================

folders = [
    "database",
    "photos/workers",
    "reports"
]

for folder in folders:
    os.makedirs(folder, exist_ok=True)

# =========================================================
# DATABASE
# =========================================================

conn = sqlite3.connect(r"database/maxek_payroll.db")
cursor = conn.cursor()

# =========================================================
# TABLES
# =========================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    full_name TEXT,
    username TEXT,
    password TEXT,
    role TEXT,
    mobile TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS clients(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT,
    client_name TEXT,
    address TEXT,
    contact_person TEXT,
    mobile TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS projects(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT,
    project_name TEXT,
    client_name TEXT,
    work_type TEXT,
    work_order_no TEXT,
    work_order_date TEXT,
    amount REAL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS subcontractors(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subcontractor_id TEXT,
    subcontractor_name TEXT,
    project_name TEXT,
    joining_date TEXT,
    contact_number TEXT,
    bank_account TEXT,
    bank_name TEXT,
    ifsc_code TEXT,
    branch_name TEXT,
    date_of_birth TEXT,
    region TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS workers(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    worker_id TEXT,
    subcontractor_name TEXT,
    worker_name TEXT,
    age TEXT,
    trade_name TEXT,
    joining_date TEXT,
    salary REAL,
    overtime_rate REAL,
    photo TEXT,
    status TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS attendance(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    worker_id TEXT,
    worker_name TEXT,
    project_name TEXT,
    attendance_date TEXT,
    start_time TEXT,
    end_time TEXT,
    break_hours REAL,
    worked_hours REAL,
    overtime REAL,
    work_description TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS payroll(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    payroll_id TEXT,
    worker_id TEXT,
    salary REAL,
    salary_status TEXT,
    paid_date TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS subcontractor_advance(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    advance_id TEXT,
    subcontractor_name TEXT,
    amount REAL,
    remarks TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS staff(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id TEXT,
    staff_name TEXT,
    department TEXT,
    designation TEXT,
    mobile TEXT,
    salary REAL
)
""")

conn.commit()

cursor.execute("PRAGMA table_info(attendance)")
attendance_columns = [row[1] for row in cursor.fetchall()]
if "work_description" not in attendance_columns:
    cursor.execute("ALTER TABLE attendance ADD COLUMN work_description TEXT")
    conn.commit()

# =========================================================
# DEFAULT LOGIN
# =========================================================

cursor.execute("SELECT * FROM users")

if cursor.fetchone() is None:
    cursor.execute("""
    INSERT INTO users(
        user_id,
        full_name,
        username,
        password,
        role,
        mobile
    )
    VALUES(
        'USR101',
        'Administrator',
        'admin',
        '1234',
        'Admin',
        '9999999999'
    )
    """)
    conn.commit()

# =========================================================
# AUTO ID GENERATION
# =========================================================

def generate_id(prefix, table_name):
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cursor.fetchone()[0] + 101
    return f"{prefix}{count}"

# =========================================================
# LOGIN WINDOW
# =========================================================

login_window = tk.Tk()
login_window.title("MAXEK ERP LOGIN")
login_window.geometry("400x330")
login_window.configure(bg="#1e1e1e")

tk.Label(
    login_window,
    text="MAXEK ERP LOGIN",
    font=("Arial", 18, "bold"),
    bg="#1e1e1e",
    fg="white"
).pack(pady=20)

tk.Label(
    login_window,
    text="Username",
    bg="#1e1e1e",
    fg="white"
).pack()

username_entry = tk.Entry(login_window, width=30)
username_entry.pack(pady=5)

tk.Label(
    login_window,
    text="Password",
    bg="#1e1e1e",
    fg="white"
).pack()

password_entry = tk.Entry(
    login_window,
    width=30,
    show="*"
)
password_entry.pack(pady=5)

# =========================================================
# MAIN ERP
# =========================================================

def open_erp():
    login_window.destroy()

    root = tk.Tk()
    root.title("MAXEK ERP SYSTEM")
    root.geometry("1600x900")
    root.configure(bg="#f0f0f0")

    dashboard = tk.Frame(
        root,
        bg="#0f3460",
        height=120
    )
    dashboard.pack(fill="x")

    tk.Label(
        dashboard,
        text="MAXEK ERP SYSTEM",
        font=("Arial", 28, "bold"),
        bg="#0f3460",
        fg="white"
    ).pack(pady=10)

    stats_frame = tk.Frame(dashboard, bg="#0f3460")
    stats_frame.pack()

    def get_count(table):
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        return cursor.fetchone()[0]

    cards = [
        ("Workers", get_count("workers")),
        ("Projects", get_count("projects")),
        ("Clients", get_count("clients")),
        ("Attendance", get_count("attendance"))
    ]

    for title, value in cards:
        card = tk.Frame(stats_frame, bg="white", width=180, height=60)
        card.pack(side="left", padx=10)
        tk.Label(card, text=title, font=("Arial", 12, "bold"), bg="white").pack()
        tk.Label(card, text=value, font=("Arial", 20, "bold"), bg="white", fg="blue").pack()

    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True)

    client_tab = ttk.Frame(notebook)
    notebook.add(client_tab, text="Clients")

    client_entries = []
    labels = [
        "Client Name",
        "Address",
        "Contact Person",
        "Mobile"
    ]

    for i, text in enumerate(labels):
        tk.Label(client_tab, text=text).grid(row=i, column=0, pady=10, padx=10, sticky="w")
        entry = tk.Entry(client_tab, width=50)
        entry.grid(row=i, column=1)
        client_entries.append(entry)

    def save_client():
        client_id = generate_id("CL", "clients")
        cursor.execute("""
        INSERT INTO clients(
            client_id,
            client_name,
            address,
            contact_person,
            mobile
        )
        VALUES(?,?,?,?,?)
        """, (
            client_id,
            client_entries[0].get(),
            client_entries[1].get(),
            client_entries[2].get(),
            client_entries[3].get()
        ))
        conn.commit()
        messagebox.showinfo("Success", f"Client Saved\nID : {client_id}")
        for entry in client_entries:
            entry.delete(0, tk.END)

    tk.Button(client_tab, text="SAVE CLIENT", bg="green", fg="white", command=save_client).grid(row=5, column=1, pady=20)

    project_tab = ttk.Frame(notebook)
    notebook.add(project_tab, text="Projects")

    project_entries = []
    project_labels = [
        "Project Name",
        "Client Name",
        "Type Of Work",
        "Work Order No",
        "Amount"
    ]

    for i, text in enumerate(project_labels):
        tk.Label(project_tab, text=text).grid(row=i, column=0, pady=10, padx=10, sticky="w")
        entry = tk.Entry(project_tab, width=50)
        entry.grid(row=i, column=1)
        project_entries.append(entry)

    tk.Label(project_tab, text="Work Order Date").grid(row=5, column=0, pady=10, padx=10, sticky="w")
    project_date = DateEntry(project_tab, date_pattern="dd-mm-yyyy")
    project_date.grid(row=5, column=1)

    def save_project():
        project_id = generate_id("PR", "projects")
        cursor.execute("""
        INSERT INTO projects(
            project_id,
            project_name,
            client_name,
            work_type,
            work_order_no,
            work_order_date,
            amount
        )
        VALUES(?,?,?,?,?,?,?)
        """, (
            project_id,
            project_entries[0].get(),
            project_entries[1].get(),
            project_entries[2].get(),
            project_entries[3].get(),
            project_date.get(),
            project_entries[4].get()
        ))
        conn.commit()
        messagebox.showinfo("Success", f"Project Saved\nID : {project_id}")
        for entry in project_entries:
            entry.delete(0, tk.END)

    tk.Button(project_tab, text="SAVE PROJECT", bg="orange", command=save_project).grid(row=6, column=1, pady=20)

    sub_tab = ttk.Frame(notebook)
    notebook.add(sub_tab, text="Sub Contractors")

    sub_entries = []
    sub_labels = [
        "Sub Contractor Name",
        "Contact Number",
        "Bank Account",
        "Bank Name",
        "IFSC Code",
        "Branch Name",
        "Date Of Birth",
        "Region"
    ]

    for i, text in enumerate(sub_labels):
        tk.Label(sub_tab, text=text).grid(row=i, column=0, pady=10, padx=10, sticky="w")
        entry = tk.Entry(sub_tab, width=50)
        entry.grid(row=i, column=1)
        sub_entries.append(entry)

    tk.Label(sub_tab, text="Joining Date").grid(row=8, column=0, pady=10, padx=10, sticky="w")
    sub_date = DateEntry(sub_tab, date_pattern="dd-mm-yyyy")
    sub_date.grid(row=8, column=1)

    def save_sub():
        sub_id = generate_id("SC", "subcontractors")
        cursor.execute("""
        INSERT INTO subcontractors(
            subcontractor_id,
            subcontractor_name,
            project_name,
            joining_date,
            contact_number,
            bank_account,
            bank_name,
            ifsc_code,
            branch_name,
            date_of_birth,
            region
        )
        VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """, (
            sub_id,
            sub_entries[0].get(),
            "",
            sub_date.get(),
            sub_entries[1].get(),
            sub_entries[2].get(),
            sub_entries[3].get(),
            sub_entries[4].get(),
            sub_entries[5].get(),
            sub_entries[6].get(),
            sub_entries[7].get()
        ))
        conn.commit()
        messagebox.showinfo("Success", f"Sub Contractor Saved\nID : {sub_id}")
        for entry in sub_entries:
            entry.delete(0, tk.END)
        sub_combo['values'] = load_subcontractors()
        sub_combo.set("")

    tk.Button(sub_tab, text="SAVE SUB CONTRACTOR", bg="blue", fg="white", command=save_sub).grid(row=9, column=1, pady=20)

    worker_tab = ttk.Frame(notebook)
    notebook.add(worker_tab, text="Workers")

    def load_subcontractors():
        cursor.execute("SELECT subcontractor_name FROM subcontractors")
        data = cursor.fetchall()
        return [x[0] for x in data]

    tk.Label(worker_tab, text="Sub Contractor").grid(row=0, column=0, pady=10, padx=10, sticky="w")
    sub_combo = ttk.Combobox(worker_tab, values=load_subcontractors(), width=47)
    sub_combo.grid(row=0, column=1)

    worker_id_label = tk.Label(worker_tab, text="AUTO ID", font=("Arial", 12, "bold"), fg="blue")
    worker_id_label.grid(row=0, column=2)

    def auto_worker_id(event):
        sub = sub_combo.get()
        if sub == "":
            return
        code = sub[:2].upper()
        cursor.execute("SELECT COUNT(*) FROM workers WHERE subcontractor_name=?", (sub,))
        count = cursor.fetchone()[0] + 101
        worker_id = f"{code}{count}"
        worker_id_label.config(text=worker_id)

    sub_combo.bind("<<ComboboxSelected>>", auto_worker_id)

    worker_labels = [
        "Worker Name",
        "Age",
        "Trade",
        "Salary",
        "OT Rate"
    ]

    worker_entries = []
    for i, text in enumerate(worker_labels):
        tk.Label(worker_tab, text=text).grid(row=i+1, column=0, pady=10, padx=10, sticky="w")
        entry = tk.Entry(worker_tab, width=50)
        entry.grid(row=i+1, column=1)
        worker_entries.append(entry)

    tk.Label(worker_tab, text="Joining Date").grid(row=6, column=0, pady=10, padx=10, sticky="w")
    worker_date = DateEntry(worker_tab, date_pattern="dd-mm-yyyy")
    worker_date.grid(row=6, column=1)

    photo_label = tk.Label(worker_tab, text="PHOTO", width=20, height=10, relief="solid")
    photo_label.grid(row=1, column=2, rowspan=5, padx=10)

    photo_path = ""

    def upload_photo():
        nonlocal photo_path
        path = filedialog.askopenfilename(filetypes=[("Image Files", "*.jpg *.png *.jpeg")])
        if path:
            photo_path = path
            img = Image.open(path)
            img = img.resize((150, 150))
            img = ImageTk.PhotoImage(img)
            photo_label.config(image=img)
            photo_label.image = img

    tk.Button(worker_tab, text="UPLOAD PHOTO", command=upload_photo).grid(row=7, column=2, pady=10)

    def save_worker():
        sub = sub_combo.get()
        if sub == "":
            messagebox.showerror("Error", "Please select a subcontractor.")
            return
        code = sub[:2].upper()
        cursor.execute("SELECT COUNT(*) FROM workers WHERE subcontractor_name=?", (sub,))
        count = cursor.fetchone()[0] + 101
        worker_id = f"{code}{count}"
        cursor.execute("""
        INSERT INTO workers(
            worker_id,
            subcontractor_name,
            worker_name,
            age,
            trade_name,
            joining_date,
            salary,
            overtime_rate,
            photo,
            status
        )
        VALUES(?,?,?,?,?,?,?,?,?,?)
        """, (
            worker_id,
            sub,
            worker_entries[0].get(),
            worker_entries[1].get(),
            worker_entries[2].get(),
            worker_date.get(),
            worker_entries[3].get(),
            worker_entries[4].get(),
            photo_path,
            "ACTIVE"
        ))
        conn.commit()
        messagebox.showinfo("Success", f"Worker Saved\nID : {worker_id}")
        for entry in worker_entries:
            entry.delete(0, tk.END)
        photo_label.config(image="", text="PHOTO")
        photo_label.image = None
        worker_id_label.config(text="AUTO ID")
        photo_path = ""
        load_workers()

    tk.Button(worker_tab, text="SAVE WORKER", bg="green", fg="white", command=save_worker).grid(row=8, column=1, pady=20)

    worker_tree = ttk.Treeview(
        worker_tab,
        columns=("ID", "Name", "Trade"),
        show="headings",
        height=8
    )
    worker_tree.heading("ID", text="Worker ID")
    worker_tree.heading("Name", text="Worker Name")
    worker_tree.heading("Trade", text="Trade")
    worker_tree.grid(row=9, column=0, columnspan=3, pady=20, padx=10, sticky="nsew")

    def load_workers():
        for item in worker_tree.get_children():
            worker_tree.delete(item)
        cursor.execute("""
        SELECT worker_id,
               worker_name,
               trade_name
        FROM workers
        """)
        data = cursor.fetchall()
        for row in data:
            worker_tree.insert("", "end", values=row)

    load_workers()

    # -----------------------------
    # Users Tab
    # -----------------------------

    user_tab = ttk.Frame(notebook)
    notebook.add(user_tab, text="Users")

    user_labels = [
        "Full Name",
        "Username",
        "Password",
        "Role",
        "Mobile"
    ]

    user_entries = []
    for i, text in enumerate(user_labels):
        tk.Label(user_tab, text=text).grid(row=i, column=0, pady=10, padx=10, sticky="w")
        if text == "Password":
            entry = tk.Entry(user_tab, width=50, show="*")
        else:
            entry = tk.Entry(user_tab, width=50)
        entry.grid(row=i, column=1)
        user_entries.append(entry)

    def save_user():
        user_id = generate_id("USR", "users")
        cursor.execute("""
        INSERT INTO users(
            user_id,
            full_name,
            username,
            password,
            role,
            mobile
        )
        VALUES(?,?,?,?,?,?)
        """, (
            user_id,
            user_entries[0].get(),
            user_entries[1].get(),
            user_entries[2].get(),
            user_entries[3].get(),
            user_entries[4].get()
        ))
        conn.commit()
        messagebox.showinfo("Success", f"User Saved\nID : {user_id}")
        for e in user_entries:
            e.delete(0, tk.END)
        load_users()

    tk.Button(user_tab, text="SAVE USER", bg="green", fg="white", command=save_user).grid(row=6, column=1, pady=20)

    user_tree = ttk.Treeview(user_tab, columns=("ID", "Name", "Username", "Role"), show="headings", height=8)
    user_tree.heading("ID", text="User ID")
    user_tree.heading("Name", text="Full Name")
    user_tree.heading("Username", text="Username")
    user_tree.heading("Role", text="Role")
    user_tree.grid(row=7, column=0, columnspan=3, pady=10, padx=10, sticky="nsew")

    def load_users():
        for item in user_tree.get_children():
            user_tree.delete(item)
        cursor.execute("SELECT user_id, full_name, username, role FROM users")
        data = cursor.fetchall()
        for row in data:
            user_tree.insert("", "end", values=row)

    load_users()

    # -----------------------------
    # Subcontractor Advance Tab
    # -----------------------------

    advance_tab = ttk.Frame(notebook)
    notebook.add(advance_tab, text="Sub Advances")

    tk.Label(advance_tab, text="Sub Contractor").grid(row=0, column=0, pady=10, padx=10, sticky="w")
    adv_sub_combo = ttk.Combobox(advance_tab, values=load_subcontractors(), width=47)
    adv_sub_combo.grid(row=0, column=1)

    tk.Label(advance_tab, text="Amount").grid(row=1, column=0, pady=10, padx=10, sticky="w")
    adv_amount = tk.Entry(advance_tab, width=40)
    adv_amount.grid(row=1, column=1)

    tk.Label(advance_tab, text="Remarks").grid(row=2, column=0, pady=10, padx=10, sticky="w")
    adv_remarks = tk.Entry(advance_tab, width=40)
    adv_remarks.grid(row=2, column=1)

    def save_advance():
        try:
            amount_val = float(adv_amount.get())
        except Exception:
            messagebox.showerror("Error", "Please enter a valid amount.")
            return
        adv_id = generate_id("ADV", "subcontractor_advance")
        cursor.execute("""
        INSERT INTO subcontractor_advance(
            advance_id,
            subcontractor_name,
            amount,
            remarks
        )
        VALUES(?,?,?,?)
        """, (
            adv_id,
            adv_sub_combo.get(),
            amount_val,
            adv_remarks.get()
        ))
        conn.commit()
        messagebox.showinfo("Success", f"Advance Saved\nID : {adv_id}")
        adv_amount.delete(0, tk.END)
        adv_remarks.delete(0, tk.END)
        adv_sub_combo.set("")
        load_advances()

    tk.Button(advance_tab, text="SAVE ADVANCE", bg="green", fg="white", command=save_advance).grid(row=3, column=1, pady=10)

    adv_tree = ttk.Treeview(advance_tab, columns=("ID", "Sub", "Amount", "Remarks"), show="headings", height=8)
    adv_tree.heading("ID", text="Advance ID")
    adv_tree.heading("Sub", text="Sub Contractor")
    adv_tree.heading("Amount", text="Amount")
    adv_tree.heading("Remarks", text="Remarks")
    adv_tree.grid(row=4, column=0, columnspan=3, pady=10, padx=10, sticky="nsew")

    def load_advances():
        for item in adv_tree.get_children():
            adv_tree.delete(item)
        cursor.execute("SELECT advance_id, subcontractor_name, amount, remarks FROM subcontractor_advance")
        for row in cursor.fetchall():
            adv_tree.insert("", "end", values=row)

    load_advances()

    timesheet_tab = ttk.Frame(notebook)
    notebook.add(
        timesheet_tab,
        text="Time Sheet"
    )

    timesheet_labels = [
        "Worker ID",
        "Worker Name",
        "Project Name",
        "Date",
        "Start Time",
        "End Time",
        "Break Hours",
        "Work Description"
    ]

    timesheet_entries = []

    for i, text in enumerate(timesheet_labels):

        tk.Label(
            timesheet_tab,
            text=text
        ).grid(row=i, column=0, pady=10)

        entry = tk.Entry(
            timesheet_tab,
            width=50
        )

        entry.grid(row=i, column=1)

        timesheet_entries.append(entry)

    def on_worker_select(event):
        selected = worker_tree.focus()
        if not selected:
            return
        values = worker_tree.item(selected, "values")
        if not values:
            return
        worker_id, worker_name = values[0], values[1]
        timesheet_entries[0].delete(0, tk.END)
        timesheet_entries[0].insert(0, worker_id)
        timesheet_entries[1].delete(0, tk.END)
        timesheet_entries[1].insert(0, worker_name)
        try:
            notebook.select(timesheet_tab)
        except Exception:
            pass

    worker_tree.bind("<<TreeviewSelect>>", on_worker_select)

    def calculate_hours(start, end, break_hr):
        fmt = "%H:%M"
        start_time = datetime.strptime(start, fmt)
        end_time = datetime.strptime(end, fmt)
        total = (end_time - start_time).seconds / 3600
        worked = total - float(break_hr)
        overtime = 0
        if worked > 8:
            overtime = worked - 8
        return worked, overtime

    def save_timesheet():

        worker_id = timesheet_entries[0].get().strip()
        worker_name = timesheet_entries[1].get().strip()
        project_name = timesheet_entries[2].get().strip()
        attendance_date_val = timesheet_entries[3].get().strip()
        start_time = timesheet_entries[4].get().strip()
        end_time = timesheet_entries[5].get().strip()
        break_hours = timesheet_entries[6].get().strip() or "0"
        work_description = timesheet_entries[7].get().strip()

        if not worker_id or not attendance_date_val:
            messagebox.showerror("Error", "Worker ID and Date are required.")
            return

        try:
            worked, overtime = calculate_hours(start_time, end_time, break_hours)
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return

        try:
            attendance_date_iso = datetime.strptime(attendance_date_val, "%d-%m-%Y").strftime("%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Error", "Date must be DD-MM-YYYY.")
            return

        cursor.execute("""
        INSERT INTO attendance(
            worker_id,
            worker_name,
            project_name,
            attendance_date,
            start_time,
            end_time,
            break_hours,
            worked_hours,
            overtime,
            work_description
        )
        VALUES(?,?,?,?,?,?,?,?,?,?)
        """, (
            worker_id,
            worker_name,
            project_name,
            attendance_date_iso,
            start_time,
            end_time,
            float(break_hours),
            worked,
            overtime,
            work_description
        ))
        conn.commit()
        messagebox.showinfo("Success", "Time Sheet Saved")

    def clear_timesheet():
        for entry in timesheet_entries:
            entry.delete(0, tk.END)

    button_frame = tk.Frame(timesheet_tab, bg="#f0f0f0")
    button_frame.grid(row=9, column=0, columnspan=2, pady=16, padx=10, sticky="w")
    tk.Button(button_frame, text="SAVE TIMESHEET", bg="green", fg="white", command=save_timesheet).pack(side="left", padx=(0, 8))
    tk.Button(button_frame, text="CLEAR TIMESHEET", bg="gray", fg="white", command=clear_timesheet).pack(side="left")

    report_tab = ttk.Frame(notebook)
    notebook.add(report_tab, text="Reports")

    tk.Label(report_tab, text="Worker ID").grid(row=0, column=0, pady=10, padx=10, sticky="w")
    report_worker = tk.Entry(report_tab, width=40)
    report_worker.grid(row=0, column=1)

    tk.Label(report_tab, text="From Date").grid(row=1, column=0, pady=10, padx=10, sticky="w")
    from_date = DateEntry(report_tab, date_pattern="dd-mm-yyyy")
    from_date.grid(row=1, column=1)

    tk.Label(report_tab, text="To Date").grid(row=2, column=0, pady=10, padx=10, sticky="w")
    to_date = DateEntry(report_tab, date_pattern="dd-mm-yyyy")
    to_date.grid(row=2, column=1)

    report_status = tk.StringVar(value="Ready to export report.")
    tk.Label(report_tab, textvariable=report_status, font=("Arial", 10, "bold"), fg="#0f3460").grid(row=3, column=0, columnspan=2, pady=(0, 10), padx=10, sticky="w")

    def export_report():
        worker_id = report_worker.get().strip()
        from_d_raw = from_date.get()
        to_d_raw = to_date.get()
        if not worker_id:
            messagebox.showerror("Error", "Worker ID is required.")
            return

        try:
            from_d = datetime.strptime(from_d_raw, "%d-%m-%Y").strftime("%Y-%m-%d")
            to_d = datetime.strptime(to_d_raw, "%d-%m-%Y").strftime("%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Error", "Please enter dates in DD-MM-YYYY format.")
            return

        query = """
        SELECT *
        FROM attendance
        WHERE worker_id=?
        AND attendance_date BETWEEN ? AND ?
        """
        df = pd.read_sql_query(
            query,
            conn,
            params=(
                worker_id,
                from_d,
                to_d
            )
        )

        if len(df) == 0:
            messagebox.showerror("Error", "No Data Found")
            return

        file_name = f"reports/{worker_id}_report.xlsx"
        df.to_excel(file_name, index=False)
        os.startfile(file_name)
        report_status.set(f"Exported report to {file_name}")
        messagebox.showinfo("Success", "Report Opened")

    def mark_salary_paid():
        payroll_id = generate_id("PAY", "payroll")
        cursor.execute("""
        INSERT INTO payroll(
            payroll_id,
            worker_id,
            salary,
            salary_status,
            paid_date
        )
        VALUES(?,?,?,?,?)
        """, (
            payroll_id,
            report_worker.get(),
            0,
            "PAID",
            datetime.now().strftime("%d-%m-%Y")
        ))
        conn.commit()
        report_status.set(f"Salary marked as PAID for {report_worker.get()}")
        messagebox.showinfo("Success", "Salary Marked As PAID")

    button_frame_report = tk.Frame(report_tab, bg="#f0f0f0")
    button_frame_report.grid(row=4, column=0, columnspan=2, pady=10, padx=10, sticky="w")
    tk.Button(button_frame_report, text="EXPORT EXCEL REPORT", bg="green", fg="white", command=export_report).pack(side="left", padx=(0, 8))
    tk.Button(button_frame_report, text="MARK SALARY PAID", bg="red", fg="white", command=mark_salary_paid).pack(side="left")

    root.mainloop()

# =========================================================
# LOGIN CHECK
# =========================================================

def login_check():
    username = username_entry.get()
    password = password_entry.get()
    cursor.execute("""
    SELECT *
    FROM users
    WHERE username=? AND password=?
    """, (
        username,
        password
    ))
    result = cursor.fetchone()
    if result:
        open_erp()
    else:
        messagebox.showerror("Error", "Invalid Login")


tk.Button(
    login_window,
    text="LOGIN",
    bg="green",
    fg="white",
    width=20,
    command=login_check
).pack(pady=20)

login_window.mainloop()
