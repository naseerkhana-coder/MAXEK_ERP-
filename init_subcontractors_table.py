"""
Create or upgrade the subcontractors table in the ERP database.
Run once: python init_subcontractors_table.py
"""

import os
import sqlite3

os.makedirs("database", exist_ok=True)
DB_PATH = os.path.join("database", "maxek_payroll.db")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS subcontractors (
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
        region TEXT,
        pan_card_number TEXT,
        status TEXT
    )
    """
)

cursor.execute("PRAGMA table_info(subcontractors)")
existing = {row[1] for row in cursor.fetchall()}
for column, col_type in (
    ("subcontractor_id", "TEXT"),
    ("subcontractor_name", "TEXT"),
    ("project_name", "TEXT"),
    ("contact_number", "TEXT"),
    ("region", "TEXT"),
    ("pan_card_number", "TEXT"),
    ("status", "TEXT"),
):
    if column not in existing:
        cursor.execute(f"ALTER TABLE subcontractors ADD COLUMN {column} {col_type}")

conn.commit()
conn.close()
print(f"Subcontractors table ready in {DB_PATH}")
