# MAXEK ERP — UAT Handoff

**Purpose:** Start hands-on UAT after server deployment.  
**Sources:** [DEPLOY.md](../DEPLOY.md), [README.md](../README.md), [UAT_READINESS_REPORT.md](./UAT_READINESS_REPORT.md), [PRODUCTION_DEPLOYMENT_CHECKLIST.md](./PRODUCTION_DEPLOYMENT_CHECKLIST.md), deploy scripts under `scripts/push_*.py`.

**Last repo commit referenced:** `949bbc9` — *Add frontend SPA, mobile shell, and decimal-hours test for deploy.*

---

## 1. Login URLs

| Surface | URL / port | Notes |
|---------|------------|--------|
| **Web ERP (primary UAT)** | **http://72.61.224.204** | Documented in `scripts/push_login_fix.py` (hard-refresh after deploy). Streamlit binds **127.0.0.1:8501** behind reverse proxy per [DEPLOY.md](../DEPLOY.md). |
| **Streamlit (direct, if exposed)** | `http://<host>:8501` | Default Streamlit port; production unit uses `--server.address 127.0.0.1` — usually **not** public. |
| **Mobile / React API** | **http://72.61.224.204:8001** | Health: `http://72.61.224.204:8001/api/health` (`mobile/README.md`, `scripts/push_mobile_api.py`). |
| **React SPA (browser)** | *Not documented as a separate production URL* | `frontend/` targets the API above (`frontend/src/auth.js`, `frontend/.env.production`). UI is primarily **Streamlit** for full ERP; React is used for **mobile APK** (`mobile/capacitor.config.json` → `frontend/dist`). |

**User must confirm:** HTTPS hostname (if any), nginx path, and whether UAT uses the same host as production.

**Template if host differs:**

| Surface | URL |
|---------|-----|
| Web ERP | `http://_______________` |
| Mobile API | `http://_______________:8001` |

---

## 2. Environment

| Known from docs | You must confirm |
|-----------------|------------------|
| VPS deploy target **72.61.224.204** (`scripts/push_*.py`, `mobile/README.md`) | Label: **UAT** vs **Production** |
| Remote app path **`/var/www/maxek-erp`** (push scripts) vs **`/opt/MAXEK_ERP`** ([DEPLOY.md](../DEPLOY.md) clone path) — **paths differ**; verify which is live | systemd units: `maxek-erp`, `maxek-api` |
| SQLite DB: `database/maxek_payroll.db` (not in git) | Whether DB was copied from dev or fresh `init_db()` |
| SMTP via `SMTP_*` env vars ([DEPLOY.md](../DEPLOY.md)) | Whether SMTP is configured on this server |

---

## 3. Test user credentials

### Default admin (seeded only when `users` table is empty)

| Field | Value | Source |
|-------|-------|--------|
| Username | `admin` | `modules/database.py` (`init_db`), [DEPLOY.md](../DEPLOY.md) |
| Password | `1234` | Stored as **bcrypt** hash via `hash_password("1234")` |
| Role | `Admin` | User id `USR101`, name `Administrator` |

**Warning:** Change immediately after first login — **Settings → Users**. Do not leave `admin` / `1234` in production ([PRODUCTION_DEPLOYMENT_CHECKLIST.md](./PRODUCTION_DEPLOYMENT_CHECKLIST.md) §5).

### Role test users

**Not seeded** beyond the single admin. Per checklist §3–4, create users for:

- Super Admin (or use changed `admin`)
- HR, Accounts Manager, Project Manager, Store Keeper
- Set **email** on users who need SMTP / forgot-password

After `python scripts/reset_production_data.py`, only `admin` / `1234` is recreated ([DEPLOY.md](../DEPLOY.md)).

---

## 4. Database migration status

### Runs automatically

- **`init_db()`** on every Streamlit start (`web_app.py` → `main()`).
- Deploy scripts also run:  
  `python -c "from modules.database import init_db; init_db()"` then `systemctl restart maxek-erp` / `maxek-api`.

### What `init_db()` does (verify after deploy)

1. `CREATE TABLE IF NOT EXISTS` for core schema.
2. Column migrations via `_add_column_if_missing` (e.g. `expense_invoice_lines.hsn_code`, `petty_cash_requests.staff_id`, project finance petty-cash handler fields).
3. `_migrate_attendance_multi_project`.
4. Seeds (if empty): departments, designations, payment/expense heads, allowance heads, salary/OT rules, location masters, chart of accounts, default company, dashboard settings, steel shapes.
5. Default admin if no users.
6. `session_timeout_minutes` = `480` in `app_settings`.
7. Post-commit: `ensure_correspondence_tables`, `ensure_erp_extension_tables`, `ensure_approval_workflow_schema`, `ensure_worker_payroll_schema`.

### Post-deploy verification (on server)

```bash
cd /var/www/maxek-erp   # or /opt/MAXEK_ERP — confirm actual path
source .venv/bin/activate
python -c "from modules.database import init_db; init_db()"
sudo systemctl restart maxek-erp maxek-api
sudo systemctl is-active maxek-erp maxek-api
```

- Confirm `database/maxek_payroll.db` exists and was **not** overwritten by `git pull` ([DEPLOY.md](../DEPLOY.md)).
- Backup before UAT: [PRODUCTION_DEPLOYMENT_CHECKLIST.md](./PRODUCTION_DEPLOYMENT_CHECKLIST.md) §1.

---

## 5. Version deployed

| Item | Value |
|------|--------|
| Git commit (local repo) | `949bbc9c4bcda4ce1c3847661d06a69295edb9a5` (`949bbc9`) |
| Git tags | None in repo |
| `VERSION` file | **None** |

### Check version on server

```bash
cd /var/www/maxek-erp   # adjust path
git rev-parse --short HEAD
git log -1 --oneline
```

Compare to `949bbc9` above. If deploy used SFTP-only (`push_*.py`), commit hash on server may **not** match git.

---

## 6. Known issues before testing

From [UAT_READINESS_REPORT.md](./UAT_READINESS_REPORT.md) (June 4, 2026):

| Metric | Value |
|--------|------:|
| Checklist items | 48 |
| Pass | 38 |
| **Partial** | **10** |
| Fail | 0 |
| Implementation readiness | ~79% |

### Modules **ready** for focused UAT (code)

- Attendance (6/6 Pass)
- Subcontractor billing (8/8 Pass)
- Reports (5/5 Pass) — note inventory report still Partial

### Modules **not ready** for full sign-off

- Payroll — auto advance/food/fine on generate (**Partial**)
- Inventory — project-level stock ledger (**Partial**)
- Approval workflow — not all financial modules on unified six-step UI (**Partial**)
- Security — role name gaps vs FINAL spec (**Partial**)
- Email — code ready; **SMTP ops test pending**

### Phase 1 gate blockers (automated tests)

All **4/4 PASS** at code level (`pytest`); still need operational SMTP:

1. Multi-project attendance  
2. Inventory auto-deduction  
3. Password security (bcrypt)  
4. SMTP (run `python scripts/test_smtp.py --to …` per [DEPLOY.md](../DEPLOY.md))

### Other blockers / gaps

| Issue | Detail |
|-------|--------|
| Default password | `admin` / `1234` if unchanged |
| **`api_app.py` absent from git** | Documented in `api/README.md`; `scripts/push_mobile_api.py` expects file at repo root — may exist **only on VPS**. Mobile UAT depends on API deploy. |
| Conditional go-live | SMTP ops test, change admin password, DB backup, written deferral of partials |

### Recommended UAT scope (in scope now)

- Multi-project attendance (same worker, two sites, one day)
- GRN → issue → return + stock balance
- Login security, session timeout
- Approval workflow email (after SMTP test)
- Subcontractor bill PDF (payroll + BOQ lines)
- Petty Cash Report Excel export

### Exclude or document as known gaps

- Auto advance/food/fine on payroll generate
- Project-level stock ledger (central register only)
- Uniform six-step workflow on every petty cash tab

---

## 7. UAT start checklist (numbered)

1. Confirm **Web ERP URL** (default **http://72.61.224.204**) and environment name (UAT/Production).
2. Log in with production credentials — **not** default `admin`/`1234` if already changed; otherwise login once and **change password immediately**.
3. Run server `git rev-parse HEAD` (or confirm deploy artifact) vs `949bbc9`.
4. Backup `database/maxek_payroll.db` ([PRODUCTION_DEPLOYMENT_CHECKLIST.md](./PRODUCTION_DEPLOYMENT_CHECKLIST.md) §1).
5. Run `init_db` + restart services (§4 above).
6. Run SMTP tests: `python scripts/test_smtp.py --to <email>` (all scenarios in [DEPLOY.md](../DEPLOY.md)).
7. Create role users (HR, Accounts, PM, Store) with emails — §3 above.
8. Execute [UAT_TEST_CASES.md](./UAT_TEST_CASES.md) within **recommended scope** (§6).
9. Record results in [UAT_ACCEPTANCE_CRITERIA.md](./UAT_ACCEPTANCE_CRITERIA.md) and sign-off table in [UAT_READINESS_REPORT.md](./UAT_READINESS_REPORT.md).
10. Mobile-only tests: verify **http://72.61.224.204:8001/api/health** and APK against same ERP credentials (`mobile/README.md`).

---

## 8. Operational confirmations (cannot verify from git)

Complete on the **UAT server** during Internal UAT. Git/repo audit cannot confirm these.

### Default admin password changed

| Status | Record |
|--------|--------|
| [ ] Confirmed by MAXEK | |
| [ ] Not yet confirmed | |

**How to verify**

1. **Login test:** `admin` / `1234` must **fail** after change (Settings → Users → change password).
2. **Database (server):** `sqlite3 database/maxek_payroll.db "SELECT username, substr(password,1,7) FROM users WHERE username='admin';"` — expect bcrypt prefix `$2b$` or `$2a$`, not plaintext `1234`.

### SMTP test results

Requires `SMTP_*` env vars and `users.email` populated ([DEPLOY.md](../DEPLOY.md)).

| Scenario | Pass / Fail / Not run | Date | Tester |
|----------|----------------------|------|--------|
| [ ] `default` (implicit on first command) | | | |
| [ ] `password_reset` | | | |
| [ ] `approval` | | | |
| [ ] `payment_released` | | | |
| [ ] `notification` | | | |

**Commands (project root on server, with venv active):**

```bash
python scripts/test_smtp.py --to ops@yourcompany.com
python scripts/test_smtp.py --to ops@yourcompany.com --scenario password_reset
python scripts/test_smtp.py --to ops@yourcompany.com --scenario approval
python scripts/test_smtp.py --to ops@yourcompany.com --scenario payment_released
python scripts/test_smtp.py --to ops@yourcompany.com --scenario notification
```

### Database backup (before UAT)

| Status | Record |
|--------|--------|
| [ ] Backup taken | Path: `backups/maxek_payroll_YYYYMMDD.db` |
| [ ] Not yet taken | |

**Command (from [PRODUCTION_DEPLOYMENT_CHECKLIST.md](./PRODUCTION_DEPLOYMENT_CHECKLIST.md) §1):**

```powershell
# Windows (project root)
New-Item -ItemType Directory -Force -Path backups
Copy-Item -Path "database\maxek_payroll.db" -Destination "backups\maxek_payroll_$(Get-Date -Format yyyyMMdd).db"
```

```bash
# Linux server
mkdir -p backups
cp database/maxek_payroll.db "backups/maxek_payroll_$(date +%Y%m%d).db"
sqlite3 "backups/maxek_payroll_$(date +%Y%m%d).db" ".tables"
```

---

## Related docs

- [UAT_ACCEPTANCE_CRITERIA.md](./UAT_ACCEPTANCE_CRITERIA.md)
- [UAT_TEST_CASES.md](./UAT_TEST_CASES.md)
- [UAT_READINESS_REPORT.md](./UAT_READINESS_REPORT.md)
- [PRODUCTION_DEPLOYMENT_CHECKLIST.md](./PRODUCTION_DEPLOYMENT_CHECKLIST.md)
- [DEPLOY.md](../DEPLOY.md)
