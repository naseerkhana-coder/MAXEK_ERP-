"""Deploy BOQ/DPR duplicate-ID fix and repair existing project_boq_items on VPS."""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    ("modules/database.py", "modules/database.py"),
    ("modules/pages.py", "modules/pages.py"),
    ("modules/dpr.py", "modules/dpr.py"),
    ("modules/billing.py", "modules/billing.py"),
    ("scripts/repair_project_boq_links.py", "scripts/repair_project_boq_links.py"),
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy BOQ/DPR fix to VPS")
    parser.add_argument("--host", default="72.61.224.204")
    parser.add_argument("--user", default="root")
    parser.add_argument("--remote-dir", default="/var/www/maxek-erp")
    parser.add_argument("--password", default=os.environ.get("MAXEK_SSH_PASSWORD", ""))
    parser.add_argument("--skip-repair", action="store_true", help="Upload only; do not run DB repair")
    args = parser.parse_args()

    password = args.password
    if not password:
        if not sys.stdin.isatty():
            raise SystemExit("Set MAXEK_SSH_PASSWORD or pass --password.")
        password = getpass.getpass(f"SSH password for {args.user}@{args.host}: ")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(args.host, username=args.user, password=password, timeout=30)

    sftp = client.open_sftp()
    for local_rel, remote_rel in FILES:
        local_path = ROOT / local_rel
        remote_path = f"{args.remote_dir}/{remote_rel}".replace("\\", "/")
        print(f"Upload {local_path} -> {remote_path}")
        sftp.put(str(local_path), remote_path)
    sftp.close()

    remote_py = f"{args.remote_dir}/.venv/bin/python"
    repair = ""
    if not args.skip_repair:
        repair = (
            f" && cd {args.remote_dir} && {remote_py} scripts/repair_project_boq_links.py --fix-ids --apply"
        )
    post_cmds = f"systemctl restart maxek-erp{repair} && systemctl is-active maxek-erp"
    _, stdout, stderr = client.exec_command(post_cmds)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    print(out or err)
    client.close()
    print("Done. Hard-refresh DPR (Ctrl+F5) and check BOQ numbers 1 and 2 show separately.")


if __name__ == "__main__":
    main()
