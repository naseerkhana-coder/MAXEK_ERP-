# MAXEK ERP — VPS Update Runbook (Production)

**Run order:** Backup → WinSCP upload → SSH update → Test → Report

---

## STEP 1 — BACKUP (SSH on VPS first)

```bash
cd /var/www/maxek_erp
chmod +x deploy/vps_backup.sh
bash deploy/vps_backup.sh /var/www/maxek_erp
```

**Confirm output shows:** `BACKUP COMPLETE` and path like:
```
/var/www/maxek_erp/backups/backup_YYYYMMDD_HHMM/
```

**Do not proceed until backup is confirmed.**

---

## STEP 2 — WinSCP upload (Windows PC)

1. Run `deploy\clean_project.bat` locally
2. Connect WinSCP to VPS → `/var/www/maxek_erp/`
3. Upload files from `deploy/UPDATE_FILES.txt` only
4. **Do NOT upload:** `database/maxek.db`, `.env`, `venv/`, `backups/`

---

## STEP 3 — VPS update (SSH)

```bash
cd /var/www/maxek_erp
chmod +x deploy/vps_update.sh deploy/post_deploy_test.sh
bash deploy/vps_update.sh /var/www/maxek_erp
```

When prompted, type `yes` to confirm backup exists.

**Manual restart (if needed):**
```bash
sudo systemctl restart maxek-erp
sudo systemctl status maxek-erp
journalctl -u maxek-erp -n 50
```

---

## STEP 4 — Post-deployment test

```bash
bash deploy/post_deploy_test.sh /var/www/maxek_erp http://127.0.0.1:8000
```

**Browser checklist:** Login, Dashboard, User Settings, Workflow Matrix, Audit Report, Notifications, all module workflows.

---

## STEP 5 — Workflow test accounts (if demo users exist on prod)

| Step | User | Action | Expected |
|------|------|--------|----------|
| Maker | maker1 | Save Petty Cash | Pending Checker |
| Checker | checker1 | Verify | Pending Approval |
| Approver | approver1 | Approve | Approved |
| Checker | checker1 | Reject | Back to Maker |
| Admin | admin | Reopen | Pending Checker |

---

## STEP 6 — Final report template

Fill after deployment:

```
1. Backup location: /var/www/maxek_erp/backups/backup_________
2. Files updated: (see deploy/UPDATE_FILES.txt)
3. Database migration: migrate_production.py — SUCCESS / FAIL
4. VPS service: systemctl status maxek-erp — active / failed
5. Application URL: https://________________
6. Errors: ________________
7. Pending issues: ________________
```

---

## Rollback

```bash
sudo systemctl stop maxek-erp
cp /var/www/maxek_erp/backups/backup_YYYYMMDD_HHMM/maxek.db /var/www/maxek_erp/database/maxek.db
cd /var/www/maxek_erp/backups/backup_YYYYMMDD_HHMM
tar -xzf app_files.tar.gz -C /var/www/maxek_erp
sudo chown -R www-data:www-data /var/www/maxek_erp
sudo systemctl start maxek-erp
```
