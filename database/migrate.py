"""
Database migration — run: python database/migrate.py
Creates managers table, region columns, and seeds default managers.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.database import init_db

if __name__ == "__main__":
    init_db()
    print("Migration complete: database/maxek_payroll.db")
