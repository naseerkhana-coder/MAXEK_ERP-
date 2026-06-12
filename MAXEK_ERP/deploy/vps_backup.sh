#!/bin/bash
# MAXEK ERP — Full production backup BEFORE any update
# Run on VPS: bash deploy/vps_backup.sh [/var/www/maxek_erp]
set -euo pipefail

APP_DIR="${1:-/var/www/maxek_erp}"
STAMP="$(date +%Y%m%d_%H%M)"
BACKUP_ROOT="${APP_DIR}/backups"
BACKUP_DIR="${BACKUP_ROOT}/backup_${STAMP}"

echo "=============================================="
echo " MAXEK ERP — Production Backup"
echo " Timestamp: ${STAMP}"
echo " App dir:   ${APP_DIR}"
echo " Backup to: ${BACKUP_DIR}"
echo "=============================================="

if [ ! -d "$APP_DIR" ]; then
  echo "ERROR: Application directory not found: $APP_DIR"
  exit 1
fi

mkdir -p "$BACKUP_DIR"

# Stop service during DB backup for consistency (optional but safer)
if systemctl is-active --quiet maxek-erp 2>/dev/null; then
  echo "Stopping maxek-erp service for consistent backup..."
  sudo systemctl stop maxek-erp
  RESTART_AFTER=1
else
  RESTART_AFTER=0
fi

echo "[1/6] Backing up application files..."
tar -czf "${BACKUP_DIR}/app_files.tar.gz" \
  -C "$APP_DIR" \
  --exclude='./venv' \
  --exclude='./.venv' \
  --exclude='./backups' \
  --exclude='./__pycache__' \
  --exclude='./*.pyc' \
  app.py workflow_service.py wsgi.py requirements.txt templates static deploy tests 2>/dev/null || \
tar -czf "${BACKUP_DIR}/app_files.tar.gz" \
  -C "$APP_DIR" \
  --exclude='./venv' \
  --exclude='./backups' \
  app.py workflow_service.py wsgi.py requirements.txt templates static deploy 2>/dev/null || true

echo "[2/6] Backing up database..."
if [ -f "${APP_DIR}/database/maxek.db" ]; then
  cp -a "${APP_DIR}/database/maxek.db" "${BACKUP_DIR}/maxek.db"
  sqlite3 "${APP_DIR}/database/maxek.db" ".backup '${BACKUP_DIR}/maxek.db.backup'" 2>/dev/null || true
else
  echo "WARN: database/maxek.db not found — skipping DB file"
fi

echo "[3/6] Backing up configuration..."
[ -f "${APP_DIR}/.env" ] && cp -a "${APP_DIR}/.env" "${BACKUP_DIR}/.env"
[ -f /etc/systemd/system/maxek-erp.service ] && sudo cp -a /etc/systemd/system/maxek-erp.service "${BACKUP_DIR}/maxek-erp.service"

echo "[4/6] Backing up templates..."
tar -czf "${BACKUP_DIR}/templates.tar.gz" -C "$APP_DIR" templates 2>/dev/null || true

echo "[5/6] Backing up static files..."
tar -czf "${BACKUP_DIR}/static.tar.gz" -C "$APP_DIR" static 2>/dev/null || true

echo "[6/6] Writing backup manifest..."
cat > "${BACKUP_DIR}/BACKUP_MANIFEST.txt" <<EOF
MAXEK ERP Backup
================
Timestamp: ${STAMP}
Hostname: $(hostname)
App path: ${APP_DIR}
Created: $(date -Iseconds)

Contents:
- app_files.tar.gz   (application code)
- maxek.db           (SQLite database copy)
- maxek.db.backup    (SQLite hot backup if available)
- .env               (environment config, if present)
- maxek-erp.service  (systemd unit, if present)
- templates.tar.gz
- static.tar.gz

Restore DB only:
  sudo systemctl stop maxek-erp
  cp ${BACKUP_DIR}/maxek.db ${APP_DIR}/database/maxek.db
  sudo chown www-data:www-data ${APP_DIR}/database/maxek.db
  sudo systemctl start maxek-erp
EOF

if [ "$RESTART_AFTER" -eq 1 ]; then
  echo "Restarting maxek-erp service..."
  sudo systemctl start maxek-erp
fi

echo ""
echo "=============================================="
echo " BACKUP COMPLETE"
echo " Location: ${BACKUP_DIR}"
echo "=============================================="
echo "Confirm this path before running vps_update.sh"
ls -lah "$BACKUP_DIR"
