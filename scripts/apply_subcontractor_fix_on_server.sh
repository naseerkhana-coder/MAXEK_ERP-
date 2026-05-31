#!/bin/bash
# Run on VPS: bash scripts/apply_subcontractor_fix_on_server.sh
set -euo pipefail
ROOT="${1:-/var/www/maxek-erp}"
PAGES="$ROOT/modules/pages.py"
python3 <<PY
from pathlib import Path
p = Path(r"$PAGES")
t = p.read_text(encoding="utf-8")
needle = (
    "account_holder_name, bank_account, bank_name, ifsc_code, branch_name\n"
    "                        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
)
repl = (
    "account_holder_name, bank_account, bank_name, ifsc_code, branch_name\n"
    "                        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
)
if repl in t:
    print("Already fixed.")
elif needle not in t:
    raise SystemExit("Expected broken INSERT block not found; check pages.py manually.")
else:
    p.write_text(t.replace(needle, repl, 1), encoding="utf-8")
    print("Patched modules/pages.py (22 placeholders).")
PY
systemctl restart maxek-erp
systemctl is-active maxek-erp
echo "Restarted maxek-erp. Hard-refresh the browser (Ctrl+F5)."
