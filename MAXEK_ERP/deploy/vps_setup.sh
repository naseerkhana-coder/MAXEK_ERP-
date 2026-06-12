#!/bin/bash
# MAXEK ERP — First-time VPS setup (run on server after WinSCP upload)
set -e
APP_DIR="${1:-/var/www/maxek_erp}"
cd "$APP_DIR"

echo "=== MAXEK ERP VPS Setup ==="
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

if [ ! -f .env ]; then
  cp deploy/.env.example .env
  echo "Created .env from template — edit MAXEK_SECRET_KEY before production!"
fi

mkdir -p database reports static/photos static/uploads static/uploads/staff static/uploads/workers
python deploy/migrate_db.py

echo "=== Install systemd service ==="
sudo cp deploy/maxek-erp.service /etc/systemd/system/maxek-erp.service
sudo sed -i "s|/var/www/maxek_erp|$APP_DIR|g" /etc/systemd/system/maxek-erp.service
sudo systemctl daemon-reload
sudo systemctl enable maxek-erp
sudo systemctl restart maxek-erp
sudo systemctl status maxek-erp --no-pager

echo "Setup complete. Configure Nginx to proxy to 127.0.0.1:8000"
