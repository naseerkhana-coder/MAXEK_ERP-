# MAXEK ERP — Backup Guide

Production VPS: **srv1704727** · App path: `/var/www/maxek-erp-flask/`

Run a backup **before every deploy** or schema change.

---

## VPS — one-liner backup (run now)

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
