# MAXEK ERP — GitHub and server updates

## Database

| Item | Value |
|------|--------|
| Engine | **SQLite 3** |
| File | `database/maxek_payroll.db` (created on first run, **not** in Git) |
| App | `web_app.py` (Streamlit) |

Back up `database/maxek_payroll.db` and `uploads/` daily on the server.

---

## Push code to GitHub (first time)

### 1. Create an empty repo on GitHub

- GitHub → **New repository**
- Name: e.g. `MAXEK_ERP`
- **Do not** add README/license (already in project)
- Copy the repo URL: `https://github.com/YOUR_ORG/MAXEK_ERP.git`

### 2. On your PC (project folder)

```powershell
cd "C:\path\to\MAXEK_ERP"
git init
git add .
git commit -m "Initial commit: MAXEK ERP Streamlit app"
git branch -M main
git remote add origin https://github.com/YOUR_ORG/MAXEK_ERP.git
git push -u origin main
```

Use **GitHub Personal Access Token** as password if prompted (not your GitHub account password).

---

## After you change code (day-to-day)

```powershell
git add .
git status
git commit -m "Describe what you changed"
git push
```

---

## Update the live server from GitHub

On the **VPS** (first time):

```bash
cd /opt
git clone https://github.com/YOUR_ORG/MAXEK_ERP.git
cd MAXEK_ERP
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -c "from modules.database import init_db; init_db()"
```

**Important:** `init_db()` creates an empty database on the server. Do **not** overwrite `database/maxek_payroll.db` on the server when pulling updates.

### Each deployment (new code only)

```bash
cd /opt/MAXEK_ERP
git pull
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart maxek-erp
```

Create systemd unit `maxek-erp` running:

```bash
/opt/MAXEK_ERP/.venv/bin/streamlit run web_app.py --server.port 8501 --server.address 127.0.0.1
```

Working directory: `/opt/MAXEK_ERP`

---

## Post-push VPS steps

**Live path:** production scripts and systemd use **`/var/www/maxek-erp`** (not `/opt/MAXEK_ERP`). Confirm with `systemctl cat maxek-erp` before first deploy.

**Default branch:** GitHub `origin/HEAD` → **`master`**. Merge feature work via PR before `git pull` on the server unless you intentionally deploy a feature branch.

### A. Git pull deploy (preferred after merge to `master`)

```bash
ssh root@72.61.224.204
cd /var/www/maxek-erp
git fetch origin
git checkout master
git pull origin master
bash scripts/server_update.sh
sudo systemctl restart maxek-api   # if mobile API unit exists
sudo systemctl is-active maxek-erp maxek-api
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8501/
```

`scripts/server_update.sh` activates `.venv`, runs `pip install -r requirements.txt`, `init_db()`, and restarts `maxek-erp` when the unit is active.

### B. SFTP push deploy (feature branch / hotfix without merge)

From your PC (requires `MAXEK_SSH_PASSWORD` or `--password`):

```powershell
cd "C:\path\to\MAXEK_ERP"
$env:MAXEK_SSH_PASSWORD = "your-vps-password"
python scripts/push_all_updates.py --host 72.61.224.204 --remote-dir /var/www/maxek-erp
```

Uploads all `modules/*.py`, `web_app.py`, assets; runs `init_db`, optional BOQ repair, `systemctl restart maxek-erp`.

### C. First-time or missing systemd (Streamlit)

```bash
cat > /etc/systemd/system/maxek-erp.service <<'EOF'
[Unit]
Description=MAXEK ERP Streamlit
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/var/www/maxek-erp
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=-/var/www/maxek-erp/.env
ExecStart=/var/www/maxek-erp/.venv/bin/streamlit run web_app.py --server.port 8501 --server.address 127.0.0.1
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now maxek-erp
```

Copy `deploy/maxek-api.service` for the FastAPI mobile API on port 8001 if needed.

### D. Pre-deploy backup (production DB)

```bash
cp /var/www/maxek-erp/database/maxek_payroll.db \
   /var/www/maxek-erp/backups/maxek_payroll_$(date +%Y%m%d).db
```

### E. Post-deploy smoke (on VPS)

```bash
cd /var/www/maxek-erp && source .venv/bin/activate
python -m pytest -q --tb=no
python -c "from modules.erp_router import PAGE_HANDLERS; print(len(PAGE_HANDLERS), 'handlers OK')"
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8501/
python scripts/test_smtp.py --to ops@yourcompany.com
```

### F. Merge feature branch → `master` (GitHub CLI)

```powershell
cd "C:\path\to\MAXEK_ERP"
git checkout cursor/client-proj-integr-1580d
git push -u origin HEAD
gh pr create --base master --head cursor/client-proj-integr-1580d --title "Deploy: Phase 3 client/project integration" --body "## Summary`n- Phase 3 modules, PDFs, workflows, UAT docs`n- Local: pytest pass, init_db OK`n`n## Test plan`n- [ ] VPS git pull + server_update.sh`n- [ ] Login smoke`n- [ ] SMTP test_smtp.py"
# After review:
gh pr merge --merge
```

---

## Email (SMTP) for workflow notifications

Set these environment variables before starting Streamlit (or in systemd `Environment=`):

| Variable | Example |
|----------|---------|
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | `erp@yourcompany.com` |
| `SMTP_PASSWORD` | app password |
| `SMTP_FROM` | same as user if omitted |
| `SMTP_TLS` | `1` (default) |

Ensure `users.email` is filled for roles that receive workflow mail (Accounts, MD, etc.).

Verify after deploy:

```bash
python scripts/test_smtp.py --to accounts@yourcompany.com
python scripts/test_smtp.py --to accounts@yourcompany.com --scenario password_reset
python scripts/test_smtp.py --to accounts@yourcompany.com --scenario approval
python scripts/test_smtp.py --to accounts@yourcompany.com --scenario payment_released
python scripts/test_smtp.py --to accounts@yourcompany.com --scenario notification
```

Login **Forgot password?** (on the sign-in page) emails a temporary password when `SMTP_*` is set and the user row has `email` populated.

Session idle timeout defaults to **8 hours** (`session_timeout_minutes` in `app_settings`, seeded as `480`).

---

## Reset test data (local or server)

```bash
python scripts/reset_production_data.py
```

Removes DB and uploads; recreates schema and default admin (`admin` / `1234`).

---

## Default login (after reset)

- Username: `admin`
- Password: `1234` — change immediately in **Settings → Users**
