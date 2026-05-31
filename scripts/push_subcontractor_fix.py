"""Upload subcontractor save fix (modules/pages.py) to VPS and restart maxek-erp."""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / "modules" / "pages.py"
REMOTE_REL = "modules/pages.py"


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy subcontractor INSERT fix to VPS")
    parser.add_argument("--host", default="72.61.224.204")
    parser.add_argument("--user", default="root")
    parser.add_argument("--remote-dir", default="/var/www/maxek-erp")
    parser.add_argument("--password", default=os.environ.get("MAXEK_SSH_PASSWORD", ""))
    args = parser.parse_args()

    if not LOCAL.is_file():
        raise SystemExit(f"Missing {LOCAL}")

    password = args.password
    if not password:
        if not sys.stdin.isatty():
            raise SystemExit("Set MAXEK_SSH_PASSWORD or pass --password for non-interactive deploy.")
        password = getpass.getpass(f"SSH password for {args.user}@{args.host}: ")

    remote_path = f"{args.remote_dir}/{REMOTE_REL}".replace("\\", "/")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(args.host, username=args.user, password=password, timeout=30)

    print(f"Upload {LOCAL} -> {remote_path}")
    sftp = client.open_sftp()
    sftp.put(str(LOCAL), remote_path)
    sftp.close()

    _, stdout, stderr = client.exec_command("systemctl restart maxek-erp && systemctl is-active maxek-erp")
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    print(out or err)
    client.close()
    print("Done. Hard-refresh the ERP page (Ctrl+F5) and save a sub contractor again.")


if __name__ == "__main__":
    main()
