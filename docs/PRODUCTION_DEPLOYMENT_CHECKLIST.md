# MAXEK ERP — Production Deployment Checklist

Use this checklist when promoting Phase 1 from internal UAT to production. Cross-reference [UAT_ACCEPTANCE_CRITERIA.md](./UAT_ACCEPTANCE_CRITERIA.md) for sign-off criteria.

---

## 1. Database backup

| Step | Action |
|------|--------|
| Locate DB | Default path: `database/maxek_payroll.db` (see `modules/database.py` `DB_PATH`) |
| Stop writes | Ask users to log out or stop Streamlit during backup |
| Copy file | PowerShell: `Copy-Item -Path "database\maxek_payroll.db" -Destination "backups\maxek_payroll_YYYYMMDD.db"` |
| Verify | Open backup copy or run `sqlite3 backups\... ".tables"` |
| Schedule | Repeat before each deploy and weekly in production |

---

## 2. SMTP configuration

Set environment variables before starting Streamlit (systemd `Environment=`, `.env`, or host panel):

| Variable | Required | Notes |
|----------|----------|-------|
| `SMTP_HOST` | Yes | Mail server hostname |
| `SMTP_PORT` | No | Default `587` |
| `SMTP_USER` | Yes | Auth username |
| `SMTP_PASSWORD` | Yes* | Or `SMTP_PASS` |
| `SMTP_FROM` | No | Defaults to `SMTP_USER` |
| `SMTP_TLS` | No | Default `1` (STARTTLS) |

Populate `users.email` for accounts that receive workflow or reset mail.

**Test (from project root):**

```bash
python scripts/test_smtp.py --to ops@yourcompany.com
python scripts/test_smtp.py --to ops@yourcompany.com --scenario password_reset
python scripts/test_smtp.py --to ops@yourcompany.com --scenario approval
python scripts/test_smtp.py --to ops@yourcompany.com --scenario payment_released
python scripts/test_smtp.py --to ops@yourcompany.com --scenario notification
```

See [DEPLOY.md](../DEPLOY.md) and `modules/email_config.py`.

---

## 3. User creation

| Step | Action |
|------|--------|
| Super Admin | Create at least one **Super Admin** (Settings → Users) |
| Roles | HR, Accounts Manager, Project Manager, Store Keeper per org chart |
| Email | Set **Email** on each user who should receive SMTP notifications or password reset |
| Password | Use strong passwords; bcrypt hashing is automatic (`modules/password_security.py`) |

---

## 4. Role assignment

| Step | Action |
|------|--------|
| Review | Settings → Users: role matches job function |
| Navigation | Confirm sidebar access via `modules/navigation.py` / `allowed_pages_for_role` |
| Workflow | Accounts roles can Check/Approve; MD/Admin for release per `modules/roles.py` |

---

## 5. Security verification

| Check | Expected |
|-------|----------|
| Password storage | bcrypt hashes only; no plaintext in `users.password` |
| Default password | **Do not** leave `admin` / `1234` in production — change immediately after deploy |
| Session timeout | `session_timeout_minutes` in `app_settings` (default 480); idle logout in `web_app.py` |
| HTTPS | Terminate TLS at reverse proxy if exposed to internet |
| Uploads | Restrict write access to `uploads/` |

---

## 6. UAT sign-off

| Step | Action |
|------|--------|
| Criteria | Complete [UAT_ACCEPTANCE_CRITERIA.md](./UAT_ACCEPTANCE_CRITERIA.md) checklist |
| Report | Record results in [UAT_READINESS_REPORT.md](./UAT_READINESS_REPORT.md) |
| Gate | Confirm 4/4 Phase 1 gate blockers PASS |
| Sign-off table | Business owner, HR, Accounts, IT — dates in readiness report |

---

## 7. Post-deploy smoke tests

| # | Test | Pass? |
|---|------|-------|
| 1 | Login with production admin (not default password) | □ |
| 2 | Multi-project attendance save (same worker, two sites, one day) | □ |
| 3 | GRN receipt → material issue → stock balance | □ |
| 4 | Subcontractor bill PDF (payroll + measurement sections) | □ |
| 5 | Reports → Petty Cash Report → Download Excel | □ |
| 6 | Workflow transition → in-app notification | □ |
| 7 | SMTP test email received (`test_smtp.py`) | □ |
| 8 | Forgot password (login expander) with test user email | □ |

---

## Quick reference

- Deploy steps: [DEPLOY.md](../DEPLOY.md)
- UAT readiness: [UAT_READINESS_REPORT.md](./UAT_READINESS_REPORT.md)
- Test cases: [UAT_TEST_CASES.md](./UAT_TEST_CASES.md)
