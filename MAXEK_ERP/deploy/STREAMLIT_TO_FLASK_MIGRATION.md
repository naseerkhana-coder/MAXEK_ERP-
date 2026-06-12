# MAXEK ERP — Streamlit → Flask Migration Runbook

**Production today:** Streamlit at `/var/www/maxek-erp` (`web_app.py`, `modules/*.py`)  
**Target:** Flask at `/var/www/maxek-erp` (`app.py`, `templates/`, `static/`, Gunicorn)

**Package:** `deploy/dist/maxek-erp-deploy-64cdd89.zip`  
**App hash:** `64cdd89`

---

## Overview

| Item | Streamlit (current) | Flask (new) |
|------|---------------------|-------------|
| Entry | `streamlit run web_app.py` | `gunicorn wsgi:app` |
| Port | Usually 8501 | 8000 (behind Nginx) |
| UI | Streamlit widgets | Jinja2 templates + CSS/JS |
| DB | Varies (see §6) | `database/maxek.db` (SQLite) |

This is a **full application replacement**, not a file overlay. Upload the Flask package, reconfigure systemd and Nginx, then migrate or initialize the database.

---

## STEP 0 — Pre-flight (SSH)

```bash
# Confirm current stack
sudo systemctl cat maxek-erp | grep ExecStart
ls -la /var/www/maxek-erp/
head -5 /var/www/maxek-erp/web_app.py 2>/dev/null || echo "no web_app.py"

# Note Streamlit port (often 8501)
ss -tlnp | grep -E '8501|8000'
```

Expected today: `ExecStart=... streamlit run web_app.py`

---

## STEP 1 — Full backup (required)

```bash
APP=/var/www/maxek-erp
STAMP=$(date +%Y%m%d_%H%M)
BACKUP=$APP/backups/streamlit_backup_$STAMP
sudo mkdir -p "$BACKUP"

sudo systemctl stop maxek-erp

# Entire app tree (Streamlit code preserved)
sudo tar -czf "$BACKUP/streamlit_app_full.tar.gz" -C "$(dirname $APP)" "$(basename $APP)" \
  --exclude='./venv' --exclude='./.venv' --exclude='./backups'

# Any database files (discover all .db on server)
sudo find "$APP" -name "*.db" -exec cp -a {} "$BACKUP/" \;
sudo find "$APP" -name "*.sqlite*" -exec cp -a {} "$BACKUP/" \;

# Config
[ -f "$APP/.env" ] && sudo cp -a "$APP/.env" "$BACKUP/.env"
[ -f /etc/systemd/system/maxek-erp.service ] && \
  sudo cp -a /etc/systemd/system/maxek-erp.service "$BACKUP/maxek-erp.service.streamlit"
[ -f /etc/nginx/sites-enabled/maxek-erp ] && \
  sudo cp -a /etc/nginx/sites-enabled/maxek-erp "$BACKUP/nginx-maxek-erp.old"

echo "Backup: $BACKUP"
ls -lah "$BACKUP"
```

**Do not proceed until backup is confirmed.**

---

## STEP 2 — Upload Flask package (WinSCP)

**Local file:**  
`MAXEK_ERP\deploy\dist\maxek-erp-deploy-64cdd89.zip`

**Remote path:** `/var/www/maxek-erp/`

### Option A — Side-by-side (safest)

```bash
sudo mkdir -p /var/www/maxek-erp-flask
# Upload & extract zip into maxek-erp-flask first, test, then swap paths
```

### Option B — In-place (recommended after backup)

1. WinSCP: upload `maxek-erp-deploy-64cdd89.zip` to `/tmp/`
2. SSH:

```bash
APP=/var/www/maxek-erp
cd "$APP"

# Move Streamlit code aside (kept in backup + this folder)
sudo mkdir -p streamlit_legacy
sudo mv web_app.py modules streamlit_legacy/ 2>/dev/null || true
# Move any other Streamlit-only files you identify

# Extract Flask package INTO app root
sudo apt-get install -y unzip 2>/dev/null || true
sudo unzip -o /tmp/maxek-erp-deploy-64cdd89.zip -d "$APP"

# Ensure directories exist
sudo mkdir -p database reports static/photos static/uploads backups
```

**Do NOT delete** existing `.env` or any `.db` files in `database/` until §6 is evaluated.

---

## STEP 3 — Python environment

```bash
APP=/var/www/maxek-erp
cd "$APP"

# Fresh venv (Flask stack — no Streamlit)
sudo rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Verify Gunicorn + Flask import
python -c "from wsgi import app; print('WSGI OK')"
deactivate
```

---

## STEP 4 — Environment file

```bash
APP=/var/www/maxek-erp
cd "$APP"

if [ ! -f .env ]; then
  sudo cp deploy/.env.example .env
fi
sudo nano .env
```

**`.env` minimum:**

```env
MAXEK_SECRET_KEY=<long-random-string>
FLASK_ENV=production
MAXEK_SKIP_DEMO_SEED=1
```

If migrating production users, **keep** `MAXEK_SKIP_DEMO_SEED=1` so demo passwords are not overwritten.

Also set Flask secret in app (or extend app to read env):

```bash
# Optional: patch secret from env if you add that to app.py later
grep secret_key app.py
```

---

## STEP 5 — systemd service (replace Streamlit)

```bash
APP=/var/www/maxek-erp
sudo cp "$APP/deploy/maxek-erp.service" /etc/systemd/system/maxek-erp.service

# If your path differs, edit WorkingDirectory and paths:
# sudo nano /etc/systemd/system/maxek-erp.service

sudo systemctl daemon-reload
sudo systemctl enable maxek-erp
sudo systemctl start maxek-erp
sudo systemctl status maxek-erp --no-pager
journalctl -u maxek-erp -n 50 --no-pager
```

**New service runs:**

```
gunicorn --workers 2 --bind 127.0.0.1:8000 --timeout 120 wsgi:app
```

**Rollback to Streamlit:**

```bash
sudo cp /var/www/maxek-erp/backups/streamlit_backup_*/maxek-erp.service.streamlit \
  /etc/systemd/system/maxek-erp.service
sudo systemctl daemon-reload
sudo systemctl restart maxek-erp
```

---

## STEP 6 — Nginx (replace Streamlit proxy)

Streamlit often proxies to port **8501**. Flask uses **8000** with `/static/` served from disk.

```bash
APP=/var/www/maxek-erp
sudo cp "$APP/deploy/nginx-maxek-erp.conf" /etc/nginx/sites-available/maxek-erp

# Edit server_name to your domain
sudo nano /etc/nginx/sites-available/maxek-erp

sudo ln -sf /etc/nginx/sites-available/maxek-erp /etc/nginx/sites-enabled/maxek-erp
sudo nginx -t
sudo systemctl reload nginx
```

**Remove old Streamlit upstream** if Nginx still points to `:8501`.

Test locally on VPS:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/login
curl -s http://127.0.0.1:8000/login | grep -o 'maxek-login-v2' || echo "OLD LOGIN HTML"
```

---

## STEP 7 — Database migration

Flask expects: **`/var/www/maxek-erp/database/maxek.db`**

```bash
APP=/var/www/maxek-erp
cd "$APP"
source venv/bin/activate
export MAXEK_SKIP_DEMO_SEED=1

python deploy/migrate_production.py
```

This will:
- Create missing tables/columns (`init_db`)
- Seed workflow master rows
- Sync workflow statuses and designations
- **Not** overwrite existing users when `MAXEK_SKIP_DEMO_SEED=1`

Post-migration checks:

```bash
sqlite3 database/maxek.db ".tables"
sqlite3 database/maxek.db "SELECT username, role, workflow_role FROM users LIMIT 10;"
bash deploy/verify_ui_on_vps.sh "$APP"
python tests/test_workflow_phase.py
```

---

## STEP 8 — Permissions

```bash
APP=/var/www/maxek-erp
sudo chown -R www-data:www-data "$APP"
sudo chmod -R 755 "$APP"
sudo chmod -R 775 "$APP/database" "$APP/reports" \
  "$APP/static/photos" "$APP/static/uploads" "$APP/backups"
```

---

## STEP 9 — Browser verification

| Check | URL / action |
|-------|----------------|
| New login UI | `/login` — construction theme, `maxek-login-v2` |
| Dashboard | `/dashboard` — Approval Summary widgets |
| User Settings | `/settings/users` |
| Workflow | Maker → Checker → Approver on Petty Cash |
| Static CSS | View source → `/static/css/maxek-login.css` loads |

Hard refresh: `Ctrl+Shift+R`

---

## Rollback (full)

```bash
STAMP=<your_backup_timestamp>
APP=/var/www/maxek-erp
sudo systemctl stop maxek-erp
sudo tar -xzf "$APP/backups/streamlit_backup_$STAMP/streamlit_app_full.tar.gz" -C /var/www/
sudo cp "$APP/backups/streamlit_backup_$STAMP/maxek-erp.service.streamlit" \
  /etc/systemd/system/maxek-erp.service
sudo systemctl daemon-reload
sudo systemctl start maxek-erp
sudo systemctl reload nginx
```

---

## Package contents (56 files)

See `deploy/dist/MANIFEST_64cdd89.txt` for the full list.

Key paths after deploy:

```
/var/www/maxek-erp/
  app.py
  workflow_service.py
  wsgi.py
  requirements.txt
  templates/
  static/css/maxek-login.css
  static/css/maxek-dashboard.css
  static/js/workflow.js
  deploy/
  database/maxek.db
  tests/test_workflow_phase.py
```
