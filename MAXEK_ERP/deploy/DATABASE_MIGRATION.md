# MAXEK ERP — Database Migration (Streamlit → Flask)

## Flask database location

```
/var/www/maxek-erp/database/maxek.db
```

Configured in `app.py`:

```python
DB_PATH = os.path.join(BASE_DIR, "database", "maxek.db")
```

---

## Can the existing Streamlit production database be reused?

**Short answer:** Only if production already uses this same SQLite file and compatible table names. Streamlit and Flask are different apps — in most cases the Streamlit DB schema **will not match** and requires assessment before reuse.

### Step 1 — Discover Streamlit database on VPS

```bash
APP=/var/www/maxek-erp

# Find all SQLite files
find "$APP" -name "*.db" -o -name "*.sqlite" 2>/dev/null

# Search Streamlit code for DB path
grep -r "sqlite\|\.db\|database" "$APP/streamlit_legacy" "$APP/web_app.py" "$APP/modules" 2>/dev/null | head -30
```

Common Streamlit patterns:
- `data/erp.db`, `database.db`, `maxek.db` in a subfolder
- Pandas CSV files instead of SQLite
- Separate DB per module

### Step 2 — Compare schemas

If you find a candidate file (e.g. `old.db`):

```bash
echo "=== Streamlit DB tables ==="
sqlite3 /path/to/streamlit.db ".tables"

echo "=== Flask expected tables (partial) ==="
echo "users staff workers projects clients attendance petty_cash salary"
echo "designations workflow_master approval_requests approval_audit notifications"
echo "material_requests purchase_requests store_issues store_receipts ..."
```

### Reuse scenarios

| Scenario | Reuse? | Action |
|----------|--------|--------|
| **A.** No SQLite on Streamlit server (CSV/JSON only) | No | Run `migrate_production.py` → fresh `maxek.db`; import data manually later |
| **B.** Streamlit uses `database/maxek.db` with **same table names** as Flask | **Partial/Yes** | Keep file; run `python deploy/migrate_production.py` — adds missing columns/tables without dropping data |
| **C.** Streamlit uses different DB path | Maybe | Copy/rename to `database/maxek.db` after backup; then run migration |
| **D.** Completely different schema | No | Keep Streamlit DB as archive; create new `maxek.db`; plan ETL script |

### Step 3 — Safe migration procedure (when reusing a .db file)

```bash
APP=/var/www/maxek-erp
cd "$APP"
source venv/bin/activate
export MAXEK_SKIP_DEMO_SEED=1

# Backup before touching DB
cp -a database/maxek.db "backups/maxek_pre_flask_$(date +%Y%m%d_%H%M).db"

# Schema upgrade (non-destructive: CREATE IF NOT EXISTS, ALTER ADD COLUMN)
python deploy/migrate_production.py

# Verify
sqlite3 database/maxek.db "PRAGMA table_info(users);"
sqlite3 database/maxek.db "SELECT COUNT(*) FROM users;"
sqlite3 database/maxek.db "SELECT COUNT(*) FROM workflow_master;"
```

### What `migrate_production.py` does

1. `init_db()` — creates any missing tables; adds columns via `_ensure_column()`
2. `seed_workflow_master()` — inserts workflow module rows if missing
3. `migrate_workflow_statuses()` — normalizes approval status values
4. `sync_workflow_designations()` — links designations to workflow matrix
5. Skips demo user seeding when `MAXEK_SKIP_DEMO_SEED=1`

**It does NOT:**
- Drop tables
- Delete user rows
- Overwrite passwords (with `MAXEK_SKIP_DEMO_SEED=1`)

### Step 4 — If Streamlit DB cannot be reused

```bash
cd /var/www/maxek-erp
source venv/bin/activate
export MAXEK_SKIP_DEMO_SEED=0   # only for FIRST setup with demo users

# Rename old DB
mv database/maxek.db database/maxek_streamlit_archived.db 2>/dev/null || true

python deploy/migrate_production.py
# Creates fresh maxek.db with admin/admin + demo workflow users
# CHANGE ALL PASSWORDS before go-live
```

### Step 5 — User password compatibility

Flask stores passwords as plain text in current codebase (same as legacy). If Streamlit hashed passwords, users **cannot log in** until passwords are reset in User Settings or DB update.

Check format:

```bash
sqlite3 database/maxek.db "SELECT username, password FROM users LIMIT 3;"
```

---

## Tables required by Flask app (reference)

**Core masters:** users, staff, subcontractors, clients, projects, workers, designations  
**Operations:** attendance, petty_cash, salary  
**Workflow:** workflow_master, approval_requests, approval_audit, notifications  
**Transactions:** material_requests, purchase_requests, payroll_records, daily_timesheets, project_expenses, head_office_expenses, subcontract_requests, leave_requests, store_issues, store_receipts

If Streamlit DB lacks workflow tables, migration script creates them empty — existing transactional data in shared tables (e.g. `workers`, `petty_cash`) may still be usable.

---

## Recommended approach for MAXEK production

1. **Backup** all Streamlit files + every `.db` found  
2. **Deploy Flask** package (do not delete backups)  
3. **Locate** Streamlit DB with discovery commands above  
4. If `database/maxek.db` exists with ERP data → **keep it**, run `migrate_production.py`  
5. If only Streamlit-specific storage → **new** `maxek.db`, archive old data, plan import  
6. Run `python tests/test_workflow_phase.py` on VPS  
7. Verify login with a known user; use User Settings to reset passwords if needed
