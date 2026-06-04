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
