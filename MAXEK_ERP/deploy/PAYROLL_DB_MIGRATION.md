# MAXEK ERP — Production DB: maxek_payroll.db → Flask (maxek.db)

## Quick answers

| # | Question | Answer |
|---|----------|--------|
| 1 | Does `app.py` use `maxek_payroll.db`? | **No.** Hardcoded `database/maxek.db` only. |
| 2 | Must it use `maxek.db`? | **Yes** (default). Or change `DB_PATH` in `app.py` — still requires **matching table names**. |
| 3 | How to migrate data? | **No automatic ETL shipped.** Table names differ; see mapping below. |
| 4 | Will passwords work? | **Only if** `users` table has plain-text passwords (Flask compares literally) and `status='Active'`. |
| 5 | Is `migrate_production.py` non-destructive? | **Yes** for existing rows (no DROP/DELETE). It **adds** tables/columns; does **not** rename Streamlit tables. |
| 6 | Pre-cutover verify command | See below. |

---

## Table name mapping (Streamlit production → Flask)

| Production (`maxek_payroll.db`) | Flask (`app.py`) | Status |
|--------------------------------|------------------|--------|
| `users` | `users` | Likely compatible (check columns) |
| `employees` | `staff` | **Different name** — Flask UI reads `staff` only |
| `workers` | `workers` | Likely compatible (verify columns) |
| `projects` | `projects` | Likely compatible |
| `clients` | `clients` | Likely compatible |
| `attendance` | `attendance` | Verify column names |
| `petty_cash_requests` | `petty_cash` | **Different name** |
| `purchase_orders` | `purchase_requests` | **Different name** |
| `material_requests` | `material_requests` | Likely compatible |
| `store_issues` | `store_issues` | Likely compatible |
| `store_receipts` | `store_receipts` | Likely compatible |
| `workflow_audit_log` | `approval_audit` | **Different name** + different workflow model |
| `dashboard_notifications` | `notifications` | **Different name** |

Flask also **requires** (will be created empty by migration if missing):

`designations`, `workflow_master`, `approval_requests`, `salary`, `subcontractors`, …

---

## Pre-cutover verification (run on VPS)

```bash
cd /var/www/maxek-erp
source venv/bin/activate   # after Flask package + pip install -r requirements.txt

# 1) Schema / table compatibility (DO NOT switch systemd until this is understood)
python deploy/check_db_compatibility.py database/maxek_payroll.db

# 2) Dry-run: copy production DB to Flask path (keeps original safe)
cp -a database/maxek_payroll.db database/maxek.db
export MAXEK_SKIP_DEMO_SEED=1
python deploy/migrate_production.py

# 3) Test Flask locally on port 8000 (Streamlit service still stopped)
gunicorn --bind 127.0.0.1:8000 wsgi:app &
curl -s -o /dev/null -w "login HTTP %{http_code}\n" http://127.0.0.1:8000/login
python tests/test_workflow_phase.py
kill %1

# 4) Test login with a REAL production user (plain-text password check)
sqlite3 database/maxek.db "SELECT username, status FROM users LIMIT 5;"
```

Exit code `0` from `check_db_compatibility.py` = schema largely ready.  
Exit code `2` = **expected today** — Streamlit names differ; data preserved but not all visible in Flask until ETL/rename.

---

## Safe migration path (preserve data)

```bash
APP=/var/www/maxek-erp
cd "$APP"

# Backup
cp -a database/maxek_payroll.db "backups/maxek_payroll_$(date +%Y%m%d_%H%M).db"

# Flask uses maxek.db — start from production copy
cp -a database/maxek_payroll.db database/maxek.db

export MAXEK_SKIP_DEMO_SEED=1
python deploy/migrate_production.py
```

**What this preserves:** all existing rows in all existing tables.  
**What this does NOT do:** move `employees` data into `staff`, or `petty_cash_requests` into `petty_cash`.

---

## Optional: SQL rename (only if column structures match — verify first)

**Do not run blindly.** Inspect with `PRAGMA table_info` on VPS first.

```bash
sqlite3 database/maxek.db <<'SQL'
-- Example ONLY if employees schema matches staff expectations:
-- ALTER TABLE employees RENAME TO staff;

-- Example ONLY if petty_cash_requests columns match petty_cash:
-- ALTER TABLE petty_cash_requests RENAME TO petty_cash;

-- After renames, re-run:
-- python deploy/migrate_production.py
SQL
```

A dedicated ETL script is safer than blind renames.

---

## Passwords

Flask login (`app.py`):

```python
SELECT * FROM users WHERE username=? AND password=? AND status='Active'
```

Passwords work if:

1. Stored as **plain text** (same as form input)
2. Column `status` exists and value is exactly `'Active'`
3. Optional columns (`workflow_role`, `employee_name`) missing → added by migration; login still works

If Streamlit hashed passwords (bcrypt, etc.), users **must reset passwords** after cutover.

Check on VPS:

```bash
sqlite3 database/maxek_payroll.db "SELECT username, length(password), substr(password,1,4) FROM users LIMIT 3;"
```

Plain text: length usually &lt; 30, no `$2b$` prefix.

---

## migrate_production.py — non-destructive guarantee

| Action | Yes/No |
|--------|--------|
| CREATE TABLE IF NOT EXISTS | Yes |
| ALTER TABLE ADD COLUMN (missing only) | Yes |
| INSERT workflow_master if missing | Yes |
| DELETE / DROP / TRUNCATE | **No** |
| Rename Streamlit tables | **No** |
| Overwrite users (with MAXEK_SKIP_DEMO_SEED=1) | **No** |

---

## Recommended cutover order

1. Backup `maxek_payroll.db`
2. Deploy Flask files + `pip install -r requirements.txt`
3. `cp maxek_payroll.db maxek.db` + `migrate_production.py`
4. `check_db_compatibility.py` + manual login test on `:8000`
5. **Only then** switch systemd to Gunicorn + update Nginx
6. Plan follow-up ETL for `employees`→`staff`, `petty_cash_requests`→`petty_cash`, etc.
