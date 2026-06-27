# MAXEK ERP — Backup Guide

Production VPS: **srv1704727** · App path: `/var/www/maxek-erp-flask/` · Domain: **erp.maxekindia.com**

Run a backup **before every deploy** or schema change.

---

## VPS — full backup (all files + database + uploads)

Use this when you need a complete snapshot off-server (tar.gz under `/var/backups/maxek-erp/`).

### One-liner (run on VPS now — no script upload required)

```bash
sudo mkdir -p /var/backups/maxek-erp && sudo systemctl stop maxek-erp 2>/dev/null; sudo tar -czf /var/backups/maxek-erp/maxek-erp-full_$(date +%Y%m%d_%H%M%S).tar.gz -C /var/www --exclude='maxek-erp-flask/venv' --exclude='maxek-erp-flask/.venv' --exclude='maxek-erp-flask/__pycache__' --exclude='maxek-erp-flask/.git' --exclude='maxek-erp-flask/backups' maxek-erp-flask; sudo systemctl start maxek-erp; ls -lh /var/backups/maxek-erp/
```

Includes: app code, `database/maxek.db`, `.env`, `static/uploads`, `static/photos`, `reports`.  
Excludes: `venv`, `__pycache__`, `.git`, in-app `backups/`.

### Script (after uploading `deploy/vps_backup_full.sh`)

```bash
cd /var/www/maxek-erp-flask
chmod +x deploy/vps_backup_full.sh
sudo bash deploy/vps_backup_full.sh
```

Options:

```bash
sudo KEEP=14 INCLUDE_ENV=1 STOP_SERVICE=1 bash deploy/vps_backup_full.sh /var/www/maxek-erp-flask
```

Output: `/var/backups/maxek-erp/maxek-erp-full_YYYYMMDD_HHMMSS.tar.gz` plus a `.txt` manifest.

### Download backup to your PC (scp)

From **PowerShell** on Windows (replace timestamp and host):

```powershell
scp root@72.61.224.204:/var/backups/maxek-erp/maxek-erp-full_YYYYMMDD_HHMMSS.tar.gz "C:\Users\rajee\Documents\maxek-vps-backups\"
```

Or with WinSCP: connect to the VPS, browse to `/var/backups/maxek-erp/`, drag the `.tar.gz` to your PC.

**Security:** archives may contain `.env` (secrets) and production data. Store locally encrypted or on a private drive only.

---

## VPS — quick DB + uploads backup (pre-deploy)

SSH into the server, then:

```bash
cd /var/www/maxek-erp-flask && chmod +x deploy/backup_vps.sh && ./deploy/backup_vps.sh
```

Database only (faster):

```bash
cd /var/www/maxek-erp-flask && KEEP=30 INCLUDE_UPLOADS=0 ./deploy/backup_vps.sh
```

Manual copy (if script not deployed yet):

```bash
cd /var/www/maxek-erp-flask
mkdir -p backups
cp database/maxek.db "backups/maxek_$(date +%Y%m%d_%H%M%S).db"
tar -czf "backups/uploads_$(date +%Y%m%d_%H%M%S).tar.gz" -C static uploads
ls -lh backups/
```

### Restore database on VPS

```bash
sudo systemctl stop maxek-erp
cp /var/www/maxek-erp-flask/backups/maxek_YYYYMMDD_HHMMSS.db /var/www/maxek-erp-flask/database/maxek.db
sudo chown www-data:www-data /var/www/maxek-erp-flask/database/maxek.db
sudo systemctl start maxek-erp
```

---

## GitHub — code backup (from your PC)

From the project folder:

```bash
cd "C:\Users\rajee\Documents\New project\MAXEK_ERP"
git status
git add -A
git commit -m "chore: backup before deploy"
git push origin main
```

Use your actual branch name if not `main`.

---

## Do NOT commit these

| Path | Reason |
|------|--------|
| `.env` | Secrets, API keys, `SECRET_KEY` |
| `database/*.db` | Production SQLite data |
| `.venv/` / `venv/` | Server/local Python environment |
| `static/uploads/**` | User uploads (GRN, DPR, staff docs, etc.) |
| `static/photos/**` | Server media |
| `backups/**` | VPS backup copies |

These are listed in `.gitignore`. If `git status` shows them, do **not** `git add` them.

---

## Recommended routine

1. **VPS:** `./deploy/backup_vps.sh`
2. **PC:** WinSCP deploy (skip `database/maxek.db`, `.env`, uploads)
3. **PC:** `git add` / `commit` / `push` for source code only
4. **VPS:** migrate + `sudo systemctl restart maxek-erp`
