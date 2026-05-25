"""
Reset MAXEK ERP to empty production-ready state.

Removes all transactional/test data by recreating the SQLite database
and clearing uploaded files. Keeps schema, master lists, and default admin login.

Run from project root:
    python scripts/reset_production_data.py
"""

import os
import shutil
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from modules.database import BASE_DIR as DB_BASE, DB_PATH, init_db  # noqa: E402

UPLOAD_ROOT = os.path.join(DB_BASE, "uploads")
PHOTOS_ROOT = os.path.join(DB_BASE, "photos")


def _clear_folder(folder):
    if not os.path.isdir(folder):
        return 0
    removed = 0
    for name in os.listdir(folder):
        path = os.path.join(folder, name)
        try:
            if os.path.isfile(path):
                os.remove(path)
                removed += 1
            elif os.path.isdir(path):
                for root, dirs, files in os.walk(path, topdown=False):
                    for file_name in files:
                        try:
                            os.remove(os.path.join(root, file_name))
                            removed += 1
                        except OSError:
                            pass
                    for dir_name in dirs:
                        try:
                            os.rmdir(os.path.join(root, dir_name))
                        except OSError:
                            pass
                try:
                    os.rmdir(path)
                except OSError:
                    pass
        except OSError:
            pass
    return removed


def main():
    if os.path.isfile(DB_PATH):
        os.remove(DB_PATH)
        print(f"Removed database: {DB_PATH}")
    else:
        print("No database file found (already clean).")

    upload_count = 0
    if os.path.isdir(UPLOAD_ROOT):
        for sub in os.listdir(UPLOAD_ROOT):
            upload_count += _clear_folder(os.path.join(UPLOAD_ROOT, sub))
    upload_count += _clear_folder(PHOTOS_ROOT)

    init_db()
    print(f"Cleared {upload_count} upload item(s).")
    print("Fresh database created with masters and default admin login.")
    print("  Username: admin")
    print("  Password: 1234")
    print("Change the admin password in Settings -> Users after first login.")


if __name__ == "__main__":
    main()
