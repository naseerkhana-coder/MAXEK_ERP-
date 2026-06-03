"""Deploy all MAXEK ERP fixes to VPS (subcontractor, BOQ/DPR, attendance, steel, approvals)."""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]

# Core entry + every module (avoids missing-file errors like modules.roles on VPS).
_EXTRA_FILES = (
    "web_app.py",
    "database/migrate.py",
)
_MODULE_FILES = tuple(
    f"modules/{p.name}" for p in sorted((ROOT / "modules").glob("*.py"))
)
FILES = tuple(
    (rel, rel)
    for rel in (
        *_MODULE_FILES,
        *_EXTRA_FILES,
        "styles/theme.css",
        "scripts/repair_project_boq_links.py",
        "assets/dpr_steel/chair.png",
        "assets/dpr_steel/ring.png",
        "assets/dpr_steel/starter.png",
    )
)


def _sftp_makedirs(sftp, remote_dir: str) -> None:
    parts = remote_dir.replace("\\", "/").strip("/").split("/")
    path = ""
    for part in parts:
        path = f"{path}/{part}" if path else f"/{part}"
        try:
            sftp.mkdir(path)
        except OSError:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy all pending MAXEK ERP updates to VPS")
    parser.add_argument("--host", default="72.61.224.204")
    parser.add_argument("--user", default="root")
    parser.add_argument("--remote-dir", default="/var/www/maxek-erp")
    parser.add_argument("--password", default=os.environ.get("MAXEK_SSH_PASSWORD", ""))
    parser.add_argument("--skip-repair", action="store_true", help="Skip BOQ link repair script")
    args = parser.parse_args()

    password = args.password
    if not password:
        if not sys.stdin.isatty():
            raise SystemExit("Set MAXEK_SSH_PASSWORD or pass --password.")
        password = getpass.getpass(f"SSH password for {args.user}@{args.host}: ")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {args.user}@{args.host}...")
    client.connect(args.host, username=args.user, password=password, timeout=60)
    sftp = client.open_sftp()

    for local_rel, remote_rel in FILES:
        local_path = ROOT / local_rel
        if not local_path.is_file():
            print(f"SKIP (missing): {local_rel}")
            continue
        remote_path = f"{args.remote_dir}/{remote_rel}".replace("\\", "/")
        _sftp_makedirs(sftp, os.path.dirname(remote_path))
        print(f"Upload {local_rel}")
        sftp.put(str(local_path), remote_path)

    sftp.close()

    remote_py = f"{args.remote_dir}/.venv/bin/python"
    repair = ""
    if not args.skip_repair:
        repair = f" && {remote_py} scripts/repair_project_boq_links.py"

    cmd = (
        f"cd {args.remote_dir} && {remote_py} -c \"from modules.database import init_db; init_db()\""
        f"{repair} && systemctl restart maxek-erp && systemctl is-active maxek-erp"
    )
    print("Running init_db, optional repair, restart...")
    _, stdout, stderr = client.exec_command(cmd, timeout=120)
    out = (stdout.read() or b"").decode(errors="replace").strip()
    err = (stderr.read() or b"").decode(errors="replace").strip()
    if out:
        print(out)
    if err:
        print(err, file=sys.stderr)

    client.close()
    print("Done. Hard-refresh the browser (Ctrl+F5).")


if __name__ == "__main__":
    main()
