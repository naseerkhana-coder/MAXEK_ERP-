#!/bin/bash
# MAXEK ERP — Clean project before WinSCP upload (Linux/VPS)
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
echo "Cleaning MAXEK ERP at $ROOT..."

find "$ROOT" -type d -name __pycache__ -not -path "*/.venv/*" -not -path "*/venv/*" -exec rm -rf {} + 2>/dev/null || true
find "$ROOT" -type f \( -name "*.pyc" -o -name "*.pyo" -o -name "*.tmp" -o -name "*.bak" -o -name "*.old" \) -not -path "*/.venv/*" -delete 2>/dev/null || true

echo "Clean complete."
