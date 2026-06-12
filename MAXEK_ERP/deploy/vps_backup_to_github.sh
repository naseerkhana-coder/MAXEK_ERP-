#!/bin/bash
# MAXEK ERP — Backup VPS production data and push to a PRIVATE GitHub repo.
#
# First-time setup (on VPS):
#   1. Create a PRIVATE repo on GitHub (e.g. maxek-erp-vps-backup)
#   2. Add deploy SSH key or personal access token
#   3. Copy deploy/github_backup.env.example → deploy/github_backup.env and edit
#   4. chmod +x deploy/vps_backup_to_github.sh
#
# Run:
#   bash deploy/vps_backup_to_github.sh [/var/www/maxek_erp]
#
# Requires: git, bash, optional sqlite3
set -euo pipefail

APP_DIR="${1:-/var/www/maxek_erp}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/github_backup.env"

if [ -f "$ENV_FILE" ]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi

GITHUB_REPO="${MAXEK_GITHUB_REPO:-}"
GITHUB_BRANCH="${MAXEK_GITHUB_BRANCH:-vps-backups}"
BACKUP_WORKDIR="${MAXEK_BACKUP_WORKDIR:-${APP_DIR}/.github_backup_repo}"
INCLUDE_DB="${MAXEK_BACKUP_INCLUDE_DB:-1}"
INCLUDE_ENV="${MAXEK_BACKUP_INCLUDE_ENV:-0}"
INCLUDE_UPLOADS="${MAXEK_BACKUP_INCLUDE_UPLOADS:-1}"
GIT_USER_NAME="${MAXEK_GIT_USER_NAME:-MAXEK VPS Backup}"
GIT_USER_EMAIL="${MAXEK_GIT_USER_EMAIL:-backup@maxek.local}"

if [ -z "$GITHUB_REPO" ]; then
  echo "ERROR: Set MAXEK_GITHUB_REPO in deploy/github_backup.env"
  echo "Example: MAXEK_GITHUB_REPO=git@github.com:YOUR_USER/maxek-erp-vps-backup.git"
  exit 1
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
HOST="$(hostname -s 2>/dev/null || hostname)"
TARGET_DIR="${BACKUP_WORKDIR}/snapshots/${STAMP}"

echo "=============================================="
echo " MAXEK ERP — VPS backup → GitHub"
echo " App:      ${APP_DIR}"
echo " Repo:     ${GITHUB_REPO}"
echo " Branch:   ${GITHUB_BRANCH}"
echo " Snapshot: ${STAMP}"
echo "=============================================="

echo "[1/5] Running local VPS backup..."
bash "${SCRIPT_DIR}/vps_backup.sh" "$APP_DIR"

LATEST_LOCAL="$(ls -dt "${APP_DIR}/backups/backup_"* 2>/dev/null | head -1 || true)"
if [ -z "$LATEST_LOCAL" ]; then
  echo "ERROR: vps_backup.sh did not create a backup folder."
  exit 1
fi
echo "Local backup: ${LATEST_LOCAL}"

echo "[2/5] Preparing GitHub backup workdir..."
mkdir -p "$BACKUP_WORKDIR"
if [ ! -d "${BACKUP_WORKDIR}/.git" ]; then
  git clone --branch "$GITHUB_BRANCH" "$GITHUB_REPO" "$BACKUP_WORKDIR" 2>/dev/null || {
    mkdir -p "$BACKUP_WORKDIR"
    git -C "$BACKUP_WORKDIR" init
    git -C "$BACKUP_WORKDIR" checkout -b "$GITHUB_BRANCH" 2>/dev/null || git -C "$BACKUP_WORKDIR" checkout "$GITHUB_BRANCH"
    git -C "$BACKUP_WORKDIR" remote add origin "$GITHUB_REPO" 2>/dev/null || git -C "$BACKUP_WORKDIR" remote set-url origin "$GITHUB_REPO"
  }
fi

git -C "$BACKUP_WORKDIR" config user.name "$GIT_USER_NAME"
git -C "$BACKUP_WORKDIR" config user.email "$GIT_USER_EMAIL"

mkdir -p "$TARGET_DIR"
cp -a "${LATEST_LOCAL}/BACKUP_MANIFEST.txt" "$TARGET_DIR/" 2>/dev/null || true
cp -a "${LATEST_LOCAL}/maxek.db" "$TARGET_DIR/" 2>/dev/null || true
cp -a "${LATEST_LOCAL}/maxek.db.backup" "$TARGET_DIR/" 2>/dev/null || true
cp -a "${LATEST_LOCAL}/app_files.tar.gz" "$TARGET_DIR/" 2>/dev/null || true
cp -a "${LATEST_LOCAL}/templates.tar.gz" "$TARGET_DIR/" 2>/dev/null || true
cp -a "${LATEST_LOCAL}/static.tar.gz" "$TARGET_DIR/" 2>/dev/null || true

cat > "${TARGET_DIR}/README.txt" <<EOF
MAXEK ERP VPS snapshot
Host: ${HOST}
App:  ${APP_DIR}
Time: $(date -Iseconds)
Source backup: ${LATEST_LOCAL}
EOF

if [ "$INCLUDE_DB" != "1" ]; then
  rm -f "${TARGET_DIR}/maxek.db" "${TARGET_DIR}/maxek.db.backup"
fi

if [ "$INCLUDE_ENV" = "1" ] && [ -f "${LATEST_LOCAL}/.env" ]; then
  cp -a "${LATEST_LOCAL}/.env" "${TARGET_DIR}/.env"
  echo "WARN: .env included — repo MUST stay PRIVATE."
else
  rm -f "${TARGET_DIR}/.env"
fi

if [ "$INCLUDE_UPLOADS" = "1" ] && [ -d "${APP_DIR}/static/uploads" ]; then
  tar -czf "${TARGET_DIR}/uploads.tar.gz" -C "${APP_DIR}/static" uploads 2>/dev/null || true
fi

# Keep only the last 10 snapshots in git (adjust as needed)
find "${BACKUP_WORKDIR}/snapshots" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort | head -n -10 | xargs -r rm -rf

echo "[3/5] Committing snapshot..."
git -C "$BACKUP_WORKDIR" add -A
if git -C "$BACKUP_WORKDIR" diff --cached --quiet; then
  echo "Nothing new to commit."
else
  git -C "$BACKUP_WORKDIR" commit -m "VPS backup ${STAMP} from ${HOST}"
fi

echo "[4/5] Pushing to GitHub..."
git -C "$BACKUP_WORKDIR" push -u origin "$GITHUB_BRANCH"

echo "[5/5] Done."
echo "=============================================="
echo " GitHub backup complete"
echo " Branch:   ${GITHUB_BRANCH}"
echo " Snapshot: snapshots/${STAMP}"
echo "=============================================="
