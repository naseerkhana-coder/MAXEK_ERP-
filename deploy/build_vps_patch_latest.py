#!/usr/bin/env python3
"""Build deploy/dist/vps-patch-latest.zip with all app.py root imports + MR/PR UI files."""
from __future__ import annotations

import re
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "deploy" / "dist"
ZIP_PATH = DIST / "vps-patch-latest.zip"
MANIFEST_PATH = DIST / "VPS-PATCH-LATEST-MANIFEST.txt"
VPS_APP = "/var/www/maxek-erp-flask"

FROM_IMPORT_RE = re.compile(r"^from ([a-z_][a-z0-9_]*) import", re.M)

# UI + deploy helpers beyond Python modules (MR/PR view/edit, store/vendor, base layout).
PATCH_UI = [
    "templates/base_maxek.html",
    "templates/dashboard.html",
    "templates/department_dashboard.html",
    "templates/department_workspace.html",
    "templates/material_request.html",
    "templates/module_request.html",
    "templates/macros/erp_ui.html",
    "templates/store_materials.html",
    "templates/store_grn.html",
    "templates/purchase_vendors.html",
    "templates/purchase_orders.html",
    "templates/subcontractors.html",
    "templates/projects.html",
    "templates/clients.html",
    "templates/staff.html",
    "templates/users.html",
    "templates/workers.html",
    "templates/login.html",
    "static/css/maxek-login.css",
    "static/js/login.js",
    "static/css/maxek-table-standards.css",
    "static/css/maxek-field-standards.css",
    "templates/boq.html",
    "templates/dpr.html",
    "templates/attendance.html",
    "static/js/attendance-form.js",
    "static/js/attendance-monthly.js",
    "static/js/data-entry.js",
    "static/css/maxek-dashboard.css",
    "static/js/master-forms.js",
    "static/js/boq-forms.js",
    "static/js/subcontractors.js",
    "static/js/maxek-ui.js",
    "deploy/migrate_production.py",
    "deploy/VPS_PATCH_maxek-erp-flask.txt",
]

REQUIRED_PY = (
    "app.py",
    "erp_framework.py",
    "super_admin_service.py",
    "store_service.py",
    "workflow_service.py",
    "erp_admin_routes.py",
    "api_routes.py",
    "tenant_isolation.py",
    "auth_jwt.py",
)


def app_direct_root_modules() -> set[str]:
    """Every top-level .py module imported directly by app.py."""
    text = (ROOT / "app.py").read_text(encoding="utf-8", errors="replace")
    files: set[str] = set()
    for mod in FROM_IMPORT_RE.findall(text):
        path = ROOT / f"{mod}.py"
        if path.is_file():
            files.add(f"{mod}.py")
    return files


def collect_files() -> list[str]:
    files = app_direct_root_modules()
    files.add("app.py")
    if (ROOT / "wsgi.py").is_file():
        files.add("wsgi.py")
    for name in REQUIRED_PY:
        if (ROOT / name).is_file():
            files.add(name)
    for rel in PATCH_UI:
        path = ROOT / rel
        if path.is_file():
            files.add(rel.replace("\\", "/"))
        else:
            print(f"WARN: patch UI file missing (skipped): {rel}")
    return sorted(files)


def build() -> None:
    DIST.mkdir(parents=True, exist_ok=True)
    files = collect_files()

    missing_required = [name for name in REQUIRED_PY if name not in files]
    if missing_required:
        raise SystemExit(f"Patch set missing required modules: {missing_required}")

    if ZIP_PATH.exists():
        ZIP_PATH.unlink()

    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in files:
            zf.write(ROOT / rel, rel)

    size = ZIP_PATH.stat().st_size
    lines = [
        "MAXEK ERP VPS patch (vps-patch-latest)",
        f"Generated: {datetime.now().isoformat()}",
        f"Production files: {len(files)}",
        f"Zip: {ZIP_PATH}",
        f"Size bytes: {size}",
        "",
        "Includes ALL app.py root imports (super_admin_service, store_service, etc.)",
        "plus MR/PR templates and store/vendor UI.",
        "",
        "LOCAL -> VPS",
        "-" * 80,
    ]
    for i, rel in enumerate(files, 1):
        local = ROOT / rel
        lines.append(f"  {i:2}. {local} -> {VPS_APP}/{rel}")

    MANIFEST_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"ZIP: {ZIP_PATH}")
    print(f"Files: {len(files)}")
    print(f"Size: {size} bytes")
    print(f"Manifest: {MANIFEST_PATH}")


if __name__ == "__main__":
    build()
