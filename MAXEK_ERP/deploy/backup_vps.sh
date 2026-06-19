#!/usr/bin/env bash
# MAXEK ERP — VPS database (and optional uploads) backup
# Usage: ./deploy/backup_vps.sh
#   KEEP=30 INCLUDE_UPLOADS=0 ./deploy/backup_vps.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${APP_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"
BACKUP_DIR="${BACKUP_DIR:-$APP_DIR/backups}"
DB_FILE="${DB_FILE:-$APP_DIR/database/maxek.db}"
UPLOADS_DIR="${UPLOADS_DIR:-$APP_DIR/static/uploads}"
KEEP="${KEEP:-14}"
INCLUDE_UPLOADS="${INCLUDE_UPLOADS:-1}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

mkdir -p "$BACKUP_DIR"

DB_BACKUP=""
UPLOADS_BACKUP=""

if [[ -f "$DB_FILE" ]]; then
  DB_BACKUP="$BACKUP_DIR/maxek_${TIMESTAMP}.db"
  cp "$DB_FILE" "$DB_BACKUP"
  echo "Database backup: $DB_BACKUP"
else
  echo "WARNING: database not found at $DB_FILE" >&2
fi

if [[ "$INCLUDE_UPLOADS" == "1" && -d "$UPLOADS_DIR" ]]; then
  UPLOADS_BACKUP="$BACKUP_DIR/uploads_${TIMESTAMP}.tar.gz"
  tar -czf "$UPLOADS_BACKUP" -C "$(dirname "$UPLOADS_DIR")" "$(basename "$UPLOADS_DIR")"
  echo "Uploads backup: $UPLOADS_BACKUP"
elif [[ "$INCLUDE_UPLOADS" == "1" ]]; then
  echo "NOTE: uploads folder not found at $UPLOADS_DIR — skipped."
fi

prune_backups() {
  local pattern="$1"
  mapfile -t files < <(find "$BACKUP_DIR" -maxdepth 1 -type f -name "$pattern" | sort)
  local count="${#files[@]}"
  if (( count > KEEP )); then
    local remove_count=$((count - KEEP))
    for ((i = 0; i < remove_count; i++)); do
      rm -f "${files[$i]}"
      echo "Pruned old backup: ${files[$i]}"
    done
  fi
}

prune_backups 'maxek_*.db'
prune_backups 'uploads_*.tar.gz'

echo ""
echo "=== Restore hints ==="
if [[ -n "$DB_BACKUP" ]]; then
  echo "  # Stop app first, then restore database:"
  echo "  sudo systemctl stop maxek-erp"
  echo "  cp \"$DB_BACKUP\" \"$DB_FILE\""
  echo "  sudo chown www-data:www-data \"$DB_FILE\""
  echo "  sudo systemctl start maxek-erp"
fi
if [[ -n "$UPLOADS_BACKUP" ]]; then
  echo "  # Restore uploads (overwrites current uploads folder):"
  echo "  tar -xzf \"$UPLOADS_BACKUP\" -C \"$(dirname "$UPLOADS_DIR")\""
fi
echo "Keeping last $KEEP backup(s) per type in $BACKUP_DIR"
