#!/bin/bash
# MAXEK ERP — Pull latest Flask code from GitHub on VPS
# Usage: bash deploy/vps_pull_from_github.sh [/var/www/maxek-erp-flask] [branch]
set -euo pipefail

APP_DIR="${1:-/var/www/maxek-erp-flask}"
BRANCH="${2:-feat/flask-employee-master-updates}"
REPO_URL="${MAXEK_GITHUB_REPO:-https://github.com/naseerkhana-coder/MAXEK_ERP-.git}"

echo "=============================================="
echo " MAXEK ERP — GitHub pull deploy"
echo " App dir:  ${APP_DIR}"
echo " Branch:   ${BRANCH}"
echo " Repo:     ${REPO_URL}"
echo "=============================================="

if [ ! -d "$APP_DIR" ]; then
  echo "ERROR: App directory not found: $APP_DIR"
  exit 1
fi

cd "$APP_DIR"

if [ -f deploy/vps_backup.sh ]; then
  echo "[1/6] Backup before pull..."
  bash deploy/vps_backup.sh "$APP_DIR"
else
  echo "[1/6] WARN: deploy/vps_backup.sh not found — skipping backup"
fi

echo "[2/6] Fetch from GitHub..."
if [ -d .git ]; then
  git fetch origin
  git checkout "$BRANCH"
  git pull origin "$BRANCH"
else
  echo "ERROR: ${APP_DIR} is not a git clone. Run once:"
  echo "  git clone -b ${BRANCH} ${REPO_URL} ${APP_DIR}"
  exit 1
fi

FLASK_DIR="${APP_DIR}/MAXEK_ERP"
if [ -d "$FLASK_DIR" ]; then
  echo "[3/6] Sync MAXEK_ERP/ into app root..."
  rsync -a --delete \
    --exclude='database/*.db' \
    --exclude='venv/' \
    --exclude='.env' \
    --exclude='backups/' \
    --exclude='__pycache__/' \
    "$FLASK_DIR/" "$APP_DIR/"
else
  echo "[3/6] No MAXEK_ERP/ subfolder — using repo root as app"
fi

echo "[4/6] Ensure upload folders..."
mkdir -p static/uploads/staff static/uploads/workers database reports
chown -R www-data:www-data static/uploads database reports 2>/dev/null || sudo chown -R www-data:www-data static/uploads database reports

echo "[5/6] Database migration..."
if [ -d venv ]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
fi
export MAXEK_SKIP_DEMO_SEED=1
if [ -f deploy/migrate_production.py ]; then
  python deploy/migrate_production.py
else
  python -c "from app import app, init_db; app.app_context().push(); init_db(); print('init_db OK')"
fi

echo "[6/6] Restart service..."
if systemctl is-active --quiet maxek-erp 2>/dev/null; then
  sudo systemctl restart maxek-erp
elif systemctl is-active --quiet maxek-erp-flask 2>/dev/null; then
  sudo systemctl restart maxek-erp-flask
else
  echo "WARN: service not found — restart gunicorn manually"
fi

echo "=============================================="
echo " GitHub pull deploy complete"
echo "=============================================="
