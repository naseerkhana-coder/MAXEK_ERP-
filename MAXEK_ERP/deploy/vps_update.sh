#!/bin/bash
# MAXEK ERP — Production update (run AFTER backup + WinSCP upload)
# Does NOT overwrite database or .env from upload package
# Usage: bash deploy/vps_update.sh [/var/www/maxek_erp]
set -euo pipefail

APP_DIR="${1:-/var/www/maxek_erp}"
cd "$APP_DIR"

echo "=============================================="
echo " MAXEK ERP — Production Update"
echo " App dir: ${APP_DIR}"
echo "=============================================="

# Require recent backup
LATEST_BACKUP=$(ls -dt "${APP_DIR}/backups/backup_"* 2>/dev/null | head -1 || true)
if [ -z "$LATEST_BACKUP" ]; then
  echo "ERROR: No backup found. Run deploy/vps_backup.sh first."
  exit 1
fi
echo "Latest backup: ${LATEST_BACKUP}"
read -r -p "Proceed with update? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
  echo "Update cancelled."
  exit 0
fi

echo "[1/7] Fixing permissions..."
sudo chown -R www-data:www-data "$APP_DIR"
sudo chmod -R 755 "$APP_DIR"
sudo chmod -R 775 "${APP_DIR}/database" "${APP_DIR}/reports" \
  "${APP_DIR}/static/photos" "${APP_DIR}/static/uploads" \
  "${APP_DIR}/static/uploads/staff" "${APP_DIR}/static/uploads/workers" 2>/dev/null || true
mkdir -p "${APP_DIR}/static/uploads/staff" "${APP_DIR}/static/uploads/workers" 2>/dev/null || true

echo "[2/7] Activating virtualenv & updating dependencies..."
if [ ! -d "${APP_DIR}/venv" ]; then
  python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q

echo "[3/7] Database migration (schema only, preserves data)..."
export MAXEK_SKIP_DEMO_SEED=1
python deploy/migrate_production.py

echo "[4/7] Workflow & designation synchronization..."
echo "  (included in migrate_production.py)"

echo "[5/7] Restarting service..."
sudo systemctl daemon-reload
sudo systemctl restart maxek-erp
sleep 2

echo "[6/7] Service status..."
sudo systemctl status maxek-erp --no-pager || true

echo "[7/7] Running post-deploy tests..."
if [ -f tests/test_workflow_phase.py ]; then
  export MAXEK_SKIP_DEMO_SEED=1
  python tests/test_workflow_phase.py || echo "WARN: Some workflow tests failed — review journalctl"
else
  echo "Skip: tests/test_workflow_phase.py not found"
fi

echo ""
echo "=============================================="
echo " UPDATE COMPLETE"
echo " Backup: ${LATEST_BACKUP}"
echo " Check:  journalctl -u maxek-erp -n 50"
echo "=============================================="
