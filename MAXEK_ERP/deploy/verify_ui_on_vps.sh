#!/bin/bash
# Verify new UI files exist on VPS (run after deploy)
# Usage: bash deploy/verify_ui_on_vps.sh [/var/www/maxek_erp]
APP_DIR="${1:-/var/www/maxek_erp}"
cd "$APP_DIR" || exit 1

pass=0
fail=0

check_file() {
  local path="$1"
  local needle="$2"
  if [ ! -f "$path" ]; then
    echo "  FAIL  MISSING: $path"
    fail=$((fail+1))
    return
  fi
  if [ -n "$needle" ] && ! grep -q "$needle" "$path" 2>/dev/null; then
    echo "  FAIL  OLD CONTENT: $path (expected: $needle)"
    fail=$((fail+1))
    return
  fi
  echo "  PASS  $path"
  pass=$((pass+1))
}

echo "=== MAXEK ERP UI Verification ==="
echo "App dir: $APP_DIR"
echo ""

check_file "templates/login.html" "maxek-login-v2"
check_file "static/css/maxek-login.css" "Login v2"
check_file "templates/forgot_password.html" "Forgot"
check_file "templates/dashboard.html" "Approval Summary"
check_file "templates/users.html" "User Settings"
check_file "app.py" "get_recent_activities"
check_file "workflow_service.py" "get_approval_summary"
check_file "static/js/workflow.js" "workflow"

echo ""
echo "Results: $pass passed, $fail failed"
if [ "$fail" -gt 0 ]; then
  echo ""
  echo "If maxek-login.css or forgot_password.html FAIL:"
  echo "  Production is on OLD package — upload deploy/dist/maxek-erp-deploy-*.zip"
  echo "  Then: sudo systemctl restart maxek-erp"
  echo "  Hard-refresh browser (Ctrl+Shift+R) or clear cache"
fi
exit $fail
