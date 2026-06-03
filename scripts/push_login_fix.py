"""Upload changed MAXEK ERP files to VPS, run init_db, restart maxek-erp."""

from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    ("modules/database.py", "modules/database.py"),
    ("modules/pages.py", "modules/pages.py"),
    ("modules/finance.py", "modules/finance.py"),
    ("modules/finance_workflow.py", "modules/finance_workflow.py"),
    ("modules/store.py", "modules/store.py"),
    ("modules/payroll_engine.py", "modules/payroll_engine.py"),
    ("styles/theme.css", "styles/theme.css"),
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
        import sys

        if not sys.stdin.isatty():
            raise SystemExit("Set MAXEK_SSH_PASSWORD or pass --password for non-interactive deploy.")
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
    post_cmds = (
        f"cd {args.remote_dir} && {remote_py} -c \"from modules.database import init_db; init_db()\" "
        "&& systemctl restart maxek-erp && systemctl is-active maxek-erp"
    )
    _, stdout, stderr = client.exec_command(post_cmds)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    print(out or err)
    client.close()
    print("Done. Hard-refresh http://72.61.224.204 (Ctrl+F5)")


if __name__ == "__main__":
    main()
