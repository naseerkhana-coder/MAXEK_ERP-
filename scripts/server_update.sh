#!/bin/bash
# Run on Linux VPS after git pull to update MAXEK ERP.
set -e
cd "$(dirname "$0")/.."
source .venv/bin/activate
pip install -r requirements.txt -q
python -c "from modules.database import init_db; init_db()"
if systemctl is-active --quiet maxek-erp 2>/dev/null; then
  sudo systemctl restart maxek-erp
  echo "Restarted maxek-erp service."
else
  echo "Code updated. Restart Streamlit manually if not using systemd."
fi
