#!/usr/bin/env python3
"""Initialize or migrate MAXEK ERP database (run once after VPS upload)."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from app import app, init_db


def main():
    os.makedirs(os.path.join(ROOT, "database"), exist_ok=True)
    with app.app_context():
        init_db()
    print("MAXEK ERP database initialized successfully.")
    print(f"Database path: {os.path.join(ROOT, 'database', 'maxek.db')}")


if __name__ == "__main__":
    main()
