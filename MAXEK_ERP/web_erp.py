from flask import Flask, g, render_template, request, redirect, url_for, session, flash, send_from_directory
import sqlite3
import os
import pandas as pd
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database", "maxek_payroll.db")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")

os.makedirs(REPORTS_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = "change-this-secret"


def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    cursor = db.cursor()
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
    db.commit()

    cursor.execute("SELECT * FROM users LIMIT 1")
    if cursor.fetchone() is None:
        cursor.execute(
            "INSERT INTO users(user_id, full_name, username, password, role, mobile) VALUES(?,?,?,?,?,?)",
            ("USR101", "Administrator", "admin", "1234", "Admin", "9999999999")
        )
        db.commit()


def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


def generate_id(prefix, table_name):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cursor.fetchone()[0] + 101
    return f"{prefix}{count}"


def login_required(fn):
    from functools import wraps

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)

    return wrapper


@app.route("/")
def index():
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        user = query_db("SELECT * FROM users WHERE username=? AND password=?", (username, password), one=True)
        if user:
            session["user_id"] = user["user_id"]
            session["full_name"] = user["full_name"]
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    counts = {
        "users": query_db("SELECT COUNT(*) AS count FROM users", one=True)["count"],
        "projects": query_db("SELECT COUNT(*) AS count FROM projects", one=True)["count"],
        "clients": query_db("SELECT COUNT(*) AS count FROM clients", one=True)["count"],
        "attendance": query_db("SELECT COUNT(*) AS count FROM attendance", one=True)["count"]
    }
    return render_template("dashboard.html", counts=counts)


@app.route("/users", methods=["GET", "POST"])
@login_required
def users():
    if request.method == "POST":
        user_id = generate_id("USR", "users")
        full_name = request.form.get("full_name", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        role = request.form.get("role", "").strip()
        mobile = request.form.get("mobile", "").strip()
        if not full_name or not username or not password:
            flash("Name, username, and password are required.")
        else:
            existing = query_db("SELECT * FROM users WHERE username=?", (username,), one=True)
            if existing:
                flash("Username already exists. Please choose another.")
            else:
                db = get_db()
                db.execute(
                    "INSERT INTO users(user_id, full_name, username, password, role, mobile) VALUES(?,?,?,?,?,?)",
                    (user_id, full_name, username, password, role, mobile)
                )
                db.commit()
                flash(f"User created: {user_id}")
                return redirect(url_for("users"))
    rows = query_db("SELECT user_id, full_name, username, role, mobile FROM users ORDER BY id DESC")
    return render_template("users.html", rows=rows)


@app.route("/advances", methods=["GET", "POST"])
@login_required
def advances():
    subcontractors = query_db("SELECT sub_name FROM subcontractors ORDER BY sub_name")
    subcontractor_names = [row["sub_name"] for row in subcontractors]
    if request.method == "POST":
        sub_name = request.form.get("subcontractor_name", "").strip()
        remarks = request.form.get("remarks", "").strip()
        amount = request.form.get("amount", "").strip()
        try:
            amount_val = float(amount)
        except ValueError:
            flash("Please enter a valid numeric amount.")
            amount_val = None
        if not sub_name or amount_val is None:
            flash("Subcontractor and amount are required.")
        else:
            advance_id = generate_id("ADV", "subcontractor_advance")
            db = get_db()
            db.execute(
                "INSERT INTO subcontractor_advance(advance_id, subcontractor_name, amount, remarks) VALUES(?,?,?,?)",
                (advance_id, sub_name, amount_val, remarks)
            )
            db.commit()
            flash(f"Advance saved: {advance_id}")
            return redirect(url_for("advances"))
    rows = query_db("SELECT advance_id, subcontractor_name, amount, remarks FROM subcontractor_advance ORDER BY id DESC")
    return render_template("advances.html", rows=rows, subcontractor_names=subcontractor_names)


@app.route("/timesheet", methods=["GET", "POST"])
@login_required
def timesheet():
    workers = query_db("SELECT worker_id, worker_name FROM workers ORDER BY worker_name")
    worker_list = [(row["worker_id"], row["worker_name"]) for row in workers]
    if request.method == "POST":
        worker_id = request.form.get("worker_id", "").strip()
        project_name = request.form.get("project_name", "").strip()
        attendance_date = request.form.get("attendance_date", "").strip()
        start_time = request.form.get("start_time", "").strip()
        end_time = request.form.get("end_time", "").strip()
        break_hours = request.form.get("break_hours", "0").strip()
        work_description = request.form.get("work_description", "").strip()
        if not worker_id or not attendance_date:
            flash("Worker and Date are required.")
        else:
            try:
                start_dt = datetime.strptime(start_time, "%H:%M")
                end_dt = datetime.strptime(end_time, "%H:%M")
                worked = (end_dt - start_dt).seconds / 3600 - float(break_hours)
                overtime = max(worked - 8, 0)
                attendance_date_iso = datetime.strptime(attendance_date, "%Y-%m-%d").strftime("%Y-%m-%d")
                db = get_db()
                db.execute(
                    "INSERT INTO attendance(worker_id, project_name, date, start_time, end_time, break_time, worked_hours, overtime, work_description) VALUES(?,?,?,?,?,?,?,?,?)",
                    (worker_id, project_name, attendance_date_iso, start_time, end_time, float(break_hours), worked, overtime, work_description)
                )
                db.commit()
                flash("Time sheet saved.")
                return redirect(url_for("timesheet"))
            except Exception as exc:
                flash(str(exc))
    rows = query_db(
        "SELECT a.worker_id, w.worker_name, a.project_name, a.date AS attendance_date, a.start_time, a.end_time, a.break_time AS break_hours, a.worked_hours, a.overtime, a.work_description "
        "FROM attendance a LEFT JOIN workers w ON a.worker_id = w.worker_id ORDER BY a.id DESC LIMIT 20"
    )
    return render_template("timesheet.html", worker_list=worker_list, rows=rows)


@app.route("/reports", methods=["GET", "POST"])
@login_required
def reports():
    report_rows = None
    file_url = None
    if request.method == "POST":
        worker_id = request.form.get("worker_id", "").strip()
        from_date = request.form.get("from_date", "").strip()
        to_date = request.form.get("to_date", "").strip()
        if not worker_id or not from_date or not to_date:
            flash("Worker ID and date range are required.")
        else:
            try:
                from_iso = datetime.strptime(from_date, "%Y-%m-%d").strftime("%Y-%m-%d")
                to_iso = datetime.strptime(to_date, "%Y-%m-%d").strftime("%Y-%m-%d")
                query = "SELECT * FROM attendance WHERE worker_id=? AND date BETWEEN ? AND ?"
                df = pd.read_sql_query(query, get_db(), params=(worker_id, from_iso, to_iso))
                if df.empty:
                    flash("No attendance found for this worker and date range.")
                else:
                    filename = f"{worker_id}_report_{from_date}_to_{to_date}.xlsx"
                    file_path = os.path.join(REPORTS_DIR, filename)
                    df.to_excel(file_path, index=False)
                    file_url = url_for("download_report", filename=filename)
                    report_rows = df.to_dict(orient="records")
            except Exception as exc:
                flash(str(exc))
    return render_template("reports.html", rows=report_rows, file_url=file_url)


@app.route("/reports/download/<path:filename>")
@login_required
def download_report(filename):
    return send_from_directory(REPORTS_DIR, filename, as_attachment=True)


if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(debug=True)
