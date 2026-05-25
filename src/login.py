import tkinter as tk
from tkinter import messagebox

from .dashboard import DashboardWindow
from .settings import get_connection


class LoginApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("MAXEK Payroll ERP - Login")
        self.geometry("360x260")
        self.resizable(False, False)

        self.username_var = tk.StringVar()
        self.password_var = tk.StringVar()

        self._build_ui()

    def _build_ui(self) -> None:
        tk.Label(self, text="Username").pack(pady=(24, 6))
        tk.Entry(self, textvariable=self.username_var).pack(fill="x", padx=24)

        tk.Label(self, text="Password").pack(pady=(12, 6))
        tk.Entry(self, textvariable=self.password_var, show="*").pack(fill="x", padx=24)

        tk.Button(self, text="Login", bg="green", fg="white", width=20, command=self.login).pack(pady=20)

    def login(self) -> None:
        username = self.username_var.get().strip()
        password = self.password_var.get().strip()

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM admin WHERE username=? AND password=?", (username, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            self.withdraw()
            dashboard = DashboardWindow(self)
            dashboard.protocol("WM_DELETE_WINDOW", self.quit)
            dashboard.mainloop()
        else:
            messagebox.showerror("Login Failed", "Invalid username or password.")
