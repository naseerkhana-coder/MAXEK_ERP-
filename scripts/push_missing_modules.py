"""Upload modules missing on VPS after partial deploy."""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "modules/__init__.py",
    "modules/branding.py",
    "modules/roles.py",
    "modules/correspondence.py",
    "modules/correspondence_data.py",
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="72.61.224.204")
    parser.add_argument("--user", default="root")
    parser.add_argument("--remote-dir", default="/var/www/maxek-erp")
    parser.add_argument("--password", default=os.environ.get("MAXEK_SSH_PASSWORD", ""))
    args = parser.parse_args()

    password = args.password or getpass.getpass(f"SSH password for {args.user}@{args.host}: ")
    if not password:
        raise SystemExit("Password required.")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(args.host, username=args.user, password=password, timeout=60)
    sftp = client.open_sftp()
    for rel in FILES:
        local = ROOT / rel
        remote = f"{args.remote_dir}/{rel}".replace("\\", "/")
        print(f"Upload {rel}")
        sftp.put(str(local), remote)
    sftp.close()

    verify = (
        f"cd {args.remote_dir} && {args.remote_dir}/.venv/bin/python -c "
        "'from modules.branding import ERP_DISPLAY_NAME; print(ERP_DISPLAY_NAME)'"
    )
    cmd = f"systemctl restart maxek-erp && sleep 2 && systemctl is-active maxek-erp && {verify}"
    _, stdout, stderr = client.exec_command(cmd, timeout=60)
    print(stdout.read().decode(errors="replace").strip())
    err = stderr.read().decode(errors="replace").strip()
    if err:
        print(err, file=sys.stderr)
    client.close()
    print("Done.")


if __name__ == "__main__":
    main()
