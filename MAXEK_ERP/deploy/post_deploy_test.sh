#!/bin/bash
# MAXEK ERP — Post-deployment HTTP & route verification (run on VPS)
APP_DIR="${1:-/var/www/maxek_erp}"
BASE_URL="${2:-http://127.0.0.1:8000}"

cd "$APP_DIR"
source venv/bin/activate 2>/dev/null || true

echo "=== Post-Deployment Verification ==="
echo "Base URL: $BASE_URL"
echo ""

pass=0
fail=0

check() {
  local name="$1"
  local code="$2"
  if [ "$code" = "200" ] || [ "$code" = "302" ]; then
    echo "  PASS  $name ($code)"
    pass=$((pass+1))
  else
    echo "  FAIL  $name ($code)"
    fail=$((fail+1))
  fi
}

# Public routes
check "Login Page" "$(curl -s -o /dev/null -w '%{http_code}' "${BASE_URL}/login")"

# Workflow engine (local Python — no auth cookie needed)
if [ -f tests/test_workflow_phase.py ]; then
  export MAXEK_SKIP_DEMO_SEED=1
  if python tests/test_workflow_phase.py; then
    echo "  PASS  Workflow Engine (21 tests)"
    pass=$((pass+1))
  else
    echo "  FAIL  Workflow Engine tests"
    fail=$((fail+1))
  fi
fi

echo ""
echo "=== Manual browser checks required ==="
echo "  - Dashboard / Approval Summary / Workflow Counters"
echo "  - User Settings (/settings/users)"
echo "  - Workflow Settings (/settings/workflow-matrix)"
echo "  - Audit Report (/reports/workflow-audit)"
echo "  - Notifications"
echo "  - Petty Cash, Material Request, Purchase Request"
echo "  - Attendance, Payroll, Store Issue, Store Receipt"
echo ""
echo "Results: $pass passed, $fail failed (automated only)"
exit $fail
