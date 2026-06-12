# Deploy to VPS from GitHub (recommended)

Repo: [naseerkhana-coder/MAXEK_ERP-](https://github.com/naseerkhana-coder/MAXEK_ERP-)

Flask app path on VPS: **`/var/www/maxek-erp-flask/`**

Branch with latest Flask code: **`feat/flask-employee-master-updates`**

---

## One-time VPS setup (SSH)

```bash
# If /var/www/maxek-erp-flask is NOT a git repo yet:
sudo mv /var/www/maxek-erp-flask /var/www/maxek-erp-flask.bak.$(date +%Y%m%d)
sudo git clone -b feat/flask-employee-master-updates \
  https://github.com/naseerkhana-coder/MAXEK_ERP-.git \
  /var/www/maxek-erp-flask
cd /var/www/maxek-erp-flask
# Copy MAXEK_ERP Flask files to app root (first time)
sudo rsync -a MAXEK_ERP/ /var/www/maxek-erp-flask/ \
  --exclude='database/*.db' --exclude='venv/' --exclude='backups/'
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export MAXEK_SKIP_DEMO_SEED=1
python deploy/migrate_production.py
sudo chown -R www-data:www-data /var/www/maxek-erp-flask
sudo systemctl restart maxek-erp
```

Keep your old folder backup (`maxek-erp-flask.bak.*`) until you verify the site.

---

## Every update (after you push from PC to GitHub)

### On PC — push changes

```powershell
cd "C:\Users\rajee\Documents\New project\_github_push"
# sync from your working copy:
robocopy "C:\Users\rajee\Documents\New project\MAXEK_ERP" "MAXEK_ERP" /E /XD __pycache__ .venv venv /XF *.db
git add MAXEK_ERP
git commit -m "fix: describe your change"
git push origin feat/flask-employee-master-updates
```

### On VPS — pull and restart

```bash
cd /var/www/maxek-erp-flask
bash MAXEK_ERP/deploy/vps_pull_from_github.sh /var/www/maxek-erp-flask feat/flask-employee-master-updates
```

Or if git is at repo root (after clone):

```bash
cd /var/www/maxek-erp-flask
git fetch origin
git checkout feat/flask-employee-master-updates
git pull origin feat/flask-employee-master-updates
rsync -a MAXEK_ERP/ ./ --exclude='database/*.db' --exclude='venv/' --exclude='.env' --exclude='backups/'
source venv/bin/activate
export MAXEK_SKIP_DEMO_SEED=1
python deploy/migrate_production.py
sudo systemctl restart maxek-erp
```

---

## Files in this update

- `MAXEK_ERP/app.py`
- `MAXEK_ERP/workflow_service.py`
- `MAXEK_ERP/templates/accounts_book.html`
- `MAXEK_ERP/templates/staff.html` (employee master)
- `MAXEK_ERP/templates/workers.html`
- `MAXEK_ERP/static/js/app.js`

---

## Merge to master (optional)

When ready for production default branch:

https://github.com/naseerkhana-coder/MAXEK_ERP-/compare/master...feat/flask-employee-master-updates

Then VPS can pull `master` instead of the feature branch.
