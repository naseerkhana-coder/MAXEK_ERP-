#!/usr/bin/env bash
# MAXEK ERP — Full VPS backup (application code + database + uploads + config)
#
# Backs up everything under the app directory except venv, __pycache__, and .git.
# Writes a single timestamped tar.gz to /var/backups/maxek-erp/
#
# Usage (on VPS):
#   chmod +x deploy/vps_backup_full.sh
#   sudo bash deploy/vps_backup_full.sh
#   sudo bash deploy/vps_backup_full.sh /var/www/maxek-erp-flask
#
# Options (environment):
#   STOP_SERVICE=0     — do not stop maxek-erp (faster; DB may be mid-write)
#   INCLUDE_ENV=0      — omit .env from archive (default: include; file is sensitive)
#   KEEP=7             — keep this many full backups, prune older ones
#   BACKUP_ROOT=...    — default /var/backups/maxek-erp
#
# Domain: erp.maxekindia.com
# App path: /var/www/maxek-erp-flask
set -euo pipefail

APP_DIR="${1:-/var/www/maxek-erp-flask}"
BACKUP_ROOT="${BACKUP_ROOT:-/var/backups/maxek-erp}"
STOP_SERVICE="${STOP_SERVICE:-1}"
INCLUDE_ENV="${INCLUDE_ENV:-1}"
KEEP="${KEEP:-7}"
STAMP="$(date +%Y%m%d_%H%M%S)"
APP_NAME="$(basename "$APP_DIR")"
ARCHIVE="${BACKUP_ROOT}/maxek-erp-full_${STAMP}.tar.gz"
MANIFEST="${BACKUP_ROOT}/maxek-erp-full_${STAMP}.txt"

echo "=============================================="
echo " MAXEK ERP — Full VPS Backup"
echo " Timestamp:  ${STAMP}"
echo " App dir:    ${APP_DIR}"
echo " Archive:    ${ARCHIVE}"
echo "=============================================="

if [ ! -d "$APP_DIR" ]; then
  echo "ERROR: Application directory not found: $APP_DIR"
  exit 1
fi

mkdir -p "$BACKUP_ROOT"

RESTART_AFTER=0
if [ "$STOP_SERVICE" = "1" ] && systemctl is-active --quiet maxek-erp 2>/dev/null; then
  echo "Stopping maxek-erp for consistent database backup..."
  systemctl stop maxek-erp
  RESTART_AFTER=1
elif [ "$STOP_SERVICE" != "1" ]; then
  echo "WARN: STOP_SERVICE=0 — database may be inconsistent in archive."
fi

cleanup() {
  if [ "$RESTART_AFTER" -eq 1 ]; then
    echo "Restarting maxek-erp..."
    systemctl start maxek-erp || true
  fi
}
trap cleanup EXIT

TAR_EXCLUDES=(
  --exclude="${APP_NAME}/venv"
  --exclude="${APP_NAME}/.venv"
  --exclude="${APP_NAME}/__pycache__"
  --exclude="${APP_NAME}/*/__pycache__"
  --exclude="${APP_NAME}/*.pyc"
  --exclude="${APP_NAME}/.git"
  --exclude="${APP_NAME}/backups"
  --exclude="${APP_NAME}/.github_backup_repo"
)

if [ "$INCLUDE_ENV" != "1" ]; then
  TAR_EXCLUDES+=(--exclude="${APP_NAME}/.env")
  echo "NOTE: .env excluded (INCLUDE_ENV=0)"
else
  echo "NOTE: .env will be included — archive contains secrets; store securely."
fi

echo "Creating archive (this may take several minutes)..."
tar -czf "$ARCHIVE" \
  -C "$(dirname "$APP_DIR")" \
  "${TAR_EXCLUDES[@]}" \
  "$APP_NAME"

# systemd unit (outside app tree)
SYSTEMD_COPY=""
if [ -f /etc/systemd/system/maxek-erp.service ]; then
  SYSTEMD_COPY="${BACKUP_ROOT}/maxek-erp.service.${STAMP}"
  cp -a /etc/systemd/system/maxek-erp.service "$SYSTEMD_COPY"
fi

{
  echo "MAXEK ERP — Full VPS Backup Manifest"
  echo "===================================="
  echo "Timestamp:   ${STAMP}"
  echo "Hostname:    $(hostname)"
  echo "Domain:      erp.maxekindia.com"
  echo "App path:    ${APP_DIR}"
  echo "Archive:     ${ARCHIVE}"
  echo "Created:     $(date -Iseconds)"
  echo ""
  echo "Included:"
  echo "  - Application code (app.py, *service.py, templates, static, deploy, ...)"
  echo "  - database/maxek.db (critical)"
  echo "  - database/maxek_payroll.db (if present)"
  echo "  - database/backups/ (in-app scheduled DB backups)"
  echo "  - static/uploads/, static/photos/"
  echo "  - reports/"
  if [ "$INCLUDE_ENV" = "1" ]; then
    echo "  - .env (SENSITIVE — secrets, API keys)"
  fi
  echo ""
  echo "Excluded:"
  echo "  - venv/, .venv/, __pycache__/, *.pyc, .git/"
  echo "  - ${APP_DIR}/backups/ (pre-update local backups; redundant)"
  echo ""
  if [ -n "$SYSTEMD_COPY" ]; then
    echo "Systemd unit copy: ${SYSTEMD_COPY}"
  fi
  echo ""
  echo "Archive size: $(du -h "$ARCHIVE" | awk '{print $1}')"
  echo ""
  echo "Restore (full app tree):"
  echo "  sudo systemctl stop maxek-erp"
  echo "  sudo tar -xzf ${ARCHIVE} -C $(dirname "$APP_DIR")"
  echo "  sudo chown -R www-data:www-data ${APP_DIR}"
  echo "  sudo systemctl start maxek-erp"
  echo ""
  echo "Restore database only:"
  echo "  sudo systemctl stop maxek-erp"
  echo "  sudo tar -xzf ${ARCHIVE} -C /tmp ${APP_NAME}/database/maxek.db"
  echo "  sudo cp /tmp/${APP_NAME}/database/maxek.db ${APP_DIR}/database/maxek.db"
  echo "  sudo chown www-data:www-data ${APP_DIR}/database/maxek.db"
  echo "  sudo systemctl start maxek-erp"
} > "$MANIFEST"

# Retention: keep newest KEEP full archives
mapfile -t OLD_ARCHIVES < <(find "$BACKUP_ROOT" -maxdepth 1 -type f -name 'maxek-erp-full_*.tar.gz' | sort)
COUNT="${#OLD_ARCHIVES[@]}"
if (( COUNT > KEEP )); then
  REMOVE=$((COUNT - KEEP))
  for ((i = 0; i < REMOVE; i++)); do
    BASE="${OLD_ARCHIVES[$i]%.tar.gz}"
    STAMP_OLD="${BASE##maxek-erp-full_}"
    rm -f "${OLD_ARCHIVES[$i]}" "${BASE}.txt" "${BACKUP_ROOT}/maxek-erp.service.${STAMP_OLD}"
    echo "Pruned old backup: ${OLD_ARCHIVES[$i]}"
  done
fi

echo ""
echo "=============================================="
echo " FULL BACKUP COMPLETE"
echo " Archive:  ${ARCHIVE}"
echo " Manifest: ${MANIFEST}"
echo "=============================================="
ls -lah "$ARCHIVE" "$MANIFEST"
if [ -n "$SYSTEMD_COPY" ]; then
  ls -lah "$SYSTEMD_COPY"
fi
