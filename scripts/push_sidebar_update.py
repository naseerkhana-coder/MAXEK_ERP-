"""Deploy ERP sidebar / navigation redesign to VPS."""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    ("modules/__init__.py", "modules/__init__.py"),
    ("modules/branding.py", "modules/branding.py"),
    ("modules/roles.py", "modules/roles.py"),
    ("modules/navigation.py", "modules/navigation.py"),
    ("modules/sidebar.py", "modules/sidebar.py"),
    ("modules/ui.py", "modules/ui.py"),
    ("modules/erp_router.py", "modules/erp_router.py"),
    ("modules/database.py", "modules/database.py"),
    ("modules/finance_workflow.py", "modules/finance_workflow.py"),
    ("modules/correspondence.py", "modules/correspondence.py"),
    ("modules/correspondence_data.py", "modules/correspondence_data.py"),
    ("styles/theme.css", "styles/theme.css"),
    ("web_app.py", "web_app.py"),
)

def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy sidebar redesign to MAXEK ERP VPS")
    parser.add_argument("--host", default="72.61.224.204")
    parser.add_argument("--user", default="root")
    parser.add_argument("--remote-dir", default="/var/www/maxek-erp")
    parser.add_argument("--password", default=os.environ.get("MAXEK_SSH_PASSWORD", ""))
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
        print(f"Upload {local_rel}")
        sftp.put(str(local_path), remote_path)

    sftp.close()
    cmd = f"systemctl restart maxek-erp && systemctl is-active maxek-erp"
    _, stdout, stderr = client.exec_command(cmd, timeout=60)
    print((stdout.read() or b"").decode(errors="replace").strip())
    err = (stderr.read() or b"").decode(errors="replace").strip()
    if err:
        print(err, file=sys.stderr)
    client.close()
    print("Done. Hard-refresh the browser (Ctrl+F5).")


if __name__ == "__main__":
    main()
