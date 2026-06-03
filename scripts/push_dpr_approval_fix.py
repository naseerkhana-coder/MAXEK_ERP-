"""Deploy DPR approval reject/delete and entry edit flow to VPS."""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    ("modules/dpr.py", "modules/dpr.py"),
    ("modules/database.py", "modules/database.py"),
)


def main() -> None:
    parser = argparse.ArgumentParser()
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
    client.connect(args.host, username=args.user, password=password, timeout=30)
    sftp = client.open_sftp()
    for local_rel, remote_rel in FILES:
        print(f"Upload {ROOT / local_rel}")
        sftp.put(str(ROOT / local_rel), f"{args.remote_dir}/{remote_rel}".replace("\\", "/"))
    sftp.close()
    remote_py = f"{args.remote_dir}/.venv/bin/python"
    _, stdout, stderr = client.exec_command(
        f"cd {args.remote_dir} && {remote_py} -c \"from modules.database import init_db; init_db()\" "
        "&& systemctl restart maxek-erp && systemctl is-active maxek-erp"
    )
    print((stdout.read() or stderr.read()).decode().strip())
    client.close()
    print("Done. Hard-refresh DPR (Ctrl+F5).")


if __name__ == "__main__":
    main()
