#!/usr/bin/env python3
"""Production-safe migration: schema + workflow sync, no demo user overwrite."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

os.environ["MAXEK_SKIP_DEMO_SEED"] = "1"

from app import app, init_db, get_db
from workflow_service import migrate_workflow_statuses, sync_workflow_designations, seed_workflow_master


def main():
    os.makedirs(os.path.join(ROOT, "database"), exist_ok=True)
    with app.app_context():
        init_db()
        db = get_db()
        seed_workflow_master(db)
        migrate_workflow_statuses(db)
        sync_workflow_designations(db)
        db.commit()
    db_path = os.path.join(ROOT, "database", "maxek.db")
    print("Production migration complete.")
    print(f"Database: {db_path}")
    print("Demo users NOT re-seeded (MAXEK_SKIP_DEMO_SEED=1).")


if __name__ == "__main__":
    main()
