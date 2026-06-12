# MAXEK ERP — VPS Deployment via WinSCP

**Version:** 1.0.0  
**Date:** 2026-06-06  
**Method:** WinSCP file upload + systemd + Gunicorn

---

## 1. Clean Project (Before Upload)

On your **Windows PC**, run:

```bat
deploy\clean_project.bat
```

Or manually delete:
- `__pycache__/` folders
- `*.pyc`, `*.tmp`, `*.bak`, `*.old`
- Do **not** upload `.venv/` or `.git/`

---

## 2. Local Verification (Completed)

Run before upload:

```bat
python tests\test_workflow_phase.py
```

All **21 tests** must pass (Maker → Checker → Approver → Reject → Reopen).

---

## 3. Deployment Package — Files to Upload

Upload these via WinSCP:

| Path | Required |
|------|----------|
| `app.py` | Yes |
| `workflow_service.py` | Yes |
| `wsgi.py` | Yes |
| `requirements.txt` | Yes |
| `templates/` | Yes (entire folder) |
| `static/` | Yes (entire folder) |
| `deploy/` | Yes (service, migrate, config) |
| `tests/test_workflow_phase.py` | Optional (verification) |
| `database/` | Empty folder OK; `maxek.db` optional |
| `reports/` | Empty folder OK |

**Do NOT upload:** `.venv/`, `__pycache__/`, `.git/`, `.env` (create on server)

See `deploy/WINSCP_UPLOAD_MANIFEST.txt` for full file list.

---

## 4. Files Changed Today (2026-06-06)

### Core application
- `app.py`
- `workflow_service.py`
- `wsgi.py` *(new — production entry)*

### Templates
- `templates/dashboard.html`
- `templates/login.html`
- `templates/forgot_password.html` *(new)*
- `templates/users.html`
- `templates/settings.html`
- `templates/attendance.html`
- `templates/salary.html`
- `templates/timesheet.html`
- `templates/reports.html`
- `templates/module_request.html`
- `templates/petty_cash.html`
- `templates/macros/erp_ui.html`
- `templates/staff.html`
- `templates/workflow_audit_report.html`
- `templates/workflow_settings.html`

### Static assets
- `static/css/maxek-dashboard.css`
- `static/css/maxek-login.css` *(new)*
- `static/js/workflow.js`

### Tests & deployment *(new)*
- `tests/test_workflow_phase.py`
- `deploy/` (service, migrate, scripts, this guide)
- `requirements.txt` *(added gunicorn)*

---

## 5. VPS Upload Path

**Recommended (production):**

```
/var/www/maxek_erp/
```

**Alternative (user home):**

```
/home/maxek_erp/app/
```

WinSCP settings:
- **Protocol:** SFTP
- **Remote directory:** `/var/www/maxek_erp/`
- **Transfer mode:** Binary
- **Preserve timestamp:** Optional

Ensure Linux ownership after upload:

```bash
sudo chown -R www-data:www-data /var/www/maxek_erp
sudo chmod -R 755 /var/www/maxek_erp
sudo chmod -R 775 /var/www/maxek_erp/database
sudo chmod -R 775 /var/www/maxek_erp/reports
sudo chmod -R 775 /var/www/maxek_erp/static/photos
sudo chmod -R 775 /var/www/maxek_erp/static/uploads
```

---

## 6. VPS First-Time Setup (SSH)

After WinSCP upload, SSH into VPS:

```bash
cd /var/www/maxek_erp
chmod +x deploy/vps_setup.sh deploy/clean_project.sh
bash deploy/vps_setup.sh /var/www/maxek_erp
```

Or step-by-step:

```bash
cd /var/www/maxek_erp
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp deploy/.env.example .env
nano .env   # set MAXEK_SECRET_KEY
python deploy/migrate_db.py
sudo cp deploy/maxek-erp.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable maxek-erp
sudo systemctl restart maxek-erp
```

---

## 7. After Upload — Service Commands

```bash
sudo systemctl restart maxek-erp
sudo systemctl status maxek-erp
journalctl -u maxek-erp -n 50
```

**Follow logs live:**

```bash
journalctl -u maxek-erp -f
```

---

## 8. Nginx Reverse Proxy (Example)

```nginx
server {
    listen 80;
    server_name erp.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static {
        alias /var/www/maxek_erp/static;
    }
}
```

```bash
sudo nginx -t && sudo systemctl reload nginx
```

---

## 9. Post-Deploy Verification

| Check | How |
|-------|-----|
| Login page loads | Open `http://your-server/login` |
| Dashboard loads | Login as `admin` / `admin` |
| Workflow counters | Dashboard → Approval Summary widgets |
| User Settings | Settings → User Settings |
| Audit Report | Reports → Workflow Audit Report |
| Maker flow | Login `maker1` / `maker123` → Petty Cash → Save |
| Checker flow | Login `checker1` / `checker123` → Approvals → Verify |
| Approver flow | Login `approver1` / `approver123` → Approvals → Approve |
| Database | `ls -la /var/www/maxek_erp/database/maxek.db` |
| Service health | `sudo systemctl status maxek-erp` |

**SSH quick test:**

```bash
cd /var/www/maxek_erp && source venv/bin/activate && python tests/test_workflow_phase.py
```

---

## 10. Production Release Checklist

- [ ] Ran `deploy/clean_project.bat` on Windows
- [ ] Local tests pass (`python tests/test_workflow_phase.py`)
- [ ] WinSCP upload complete (no `.venv`, no `__pycache__`)
- [ ] `.env` created on VPS with strong `MAXEK_SECRET_KEY`
- [ ] Default passwords changed (`admin`, `maker1`, etc.)
- [ ] `python deploy/migrate_db.py` executed successfully
- [ ] `database/` writable by `www-data`
- [ ] `reports/`, `static/photos/`, `static/uploads/` writable
- [ ] systemd service enabled and running
- [ ] Nginx/HTTPS configured (recommended: Certbot)
- [ ] Firewall allows 80/443 (not 8000 publicly)
- [ ] Login, Dashboard, Workflow, User Settings, Audit Report verified in browser
- [ ] Maker → Checker → Approver test on production
- [ ] Backup plan for `database/maxek.db` documented

---

## Demo Accounts (Change Before Production)

| User | Password | Role |
|------|----------|------|
| admin | admin | Administrator |
| maker1 | maker123 | Maker |
| checker1 | checker123 | Checker |
| approver1 | approver123 | Approver |

---

## Support Commands

```bash
# Restart after code update via WinSCP
sudo systemctl restart maxek-erp

# Re-run DB migration after schema updates
cd /var/www/maxek_erp && source venv/bin/activate && python deploy/migrate_db.py

# Check disk / permissions
ls -la /var/www/maxek_erp/database/
```
