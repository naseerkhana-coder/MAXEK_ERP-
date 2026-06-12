#!/usr/bin/env python3
"""Build maxek-erp-deploy-<hash>.zip for VPS upload."""
import hashlib
import os
import zipfile
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "deploy", "dist")
EXCLUDE_DIRS = {".venv", "venv", "__pycache__", ".git", ".cursor", "dist", "package"}
EXCLUDE_FILES = {".pyc", ".pyo", ".tmp", ".bak", ".old"}
# User-uploaded media stays on VPS — do not bundle in deploy zip
SKIP_PATH_PREFIXES = ("deploy/package", "static/photos", "static/uploads")

with open(os.path.join(ROOT, "app.py"), "rb") as f:
    short_hash = hashlib.sha256(f.read()).hexdigest()[:7].lower()

zip_name = f"maxek-erp-deploy-{short_hash}.zip"
zip_path = os.path.join(DIST, zip_name)
manifest_path = os.path.join(DIST, f"MANIFEST_{short_hash}.txt")

INCLUDE_ROOT = ["app.py", "workflow_service.py", "wsgi.py", "requirements.txt"]
INCLUDE_DIRS = ["templates", "static", "deploy", "tests"]
EXTRA_DIRS = ["database", "reports"]


def should_skip(path: str) -> bool:
    norm = path.replace("\\", "/")
    if any(norm.startswith(p) for p in SKIP_PATH_PREFIXES):
        return True
    parts = norm.split("/")
    if any(p in EXCLUDE_DIRS for p in parts):
        return True
    return any(path.endswith(ext) for ext in EXCLUDE_FILES)


os.makedirs(DIST, exist_ok=True)
entries = []

with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
    for name in INCLUDE_ROOT:
        full = os.path.join(ROOT, name)
        if os.path.isfile(full):
            zf.write(full, name)
            entries.append((name, os.path.getsize(full), os.path.getmtime(full)))

    for d in INCLUDE_DIRS:
        base = os.path.join(ROOT, d)
        for dirpath, dirnames, filenames in os.walk(base):
            rel_dir = os.path.relpath(dirpath, ROOT).replace("\\", "/")
            if rel_dir.startswith("deploy/package") or rel_dir.startswith("deploy/dist"):
                dirnames.clear()
                continue
            dirnames[:] = [
                x for x in dirnames
                if x not in EXCLUDE_DIRS
                and not (rel_dir == "deploy" and x in ("package", "dist") or x.startswith("package_"))
            ]
            for fn in filenames:
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, ROOT).replace("\\", "/")
                if should_skip(rel):
                    continue
                zf.write(full, rel)
                entries.append((rel, os.path.getsize(full), os.path.getmtime(full)))

    for d in EXTRA_DIRS:
        zf.writestr(f"{d}/.gitkeep", "")
    zf.writestr("static/photos/.gitkeep", "")
    zf.writestr("static/uploads/.gitkeep", "")

lines = [
    "MAXEK ERP Deployment Package",
    f"Generated: {datetime.now().isoformat()}",
    f"Package: {zip_name}",
    f"App hash: {short_hash}",
    "",
    f"FILE LIST ({len(entries)} files):",
    "-" * 60,
]
for rel, size, mtime in sorted(entries):
    ts = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
    lines.append(f"{rel:<52} {size:>8}  {ts}")

with open(manifest_path, "w", encoding="utf-8") as mf:
    mf.write("\n".join(lines) + "\n")

print(f"ZIP: {zip_path}")
print(f"Files: {len(entries)}")
print(f"Size: {os.path.getsize(zip_path)} bytes")
