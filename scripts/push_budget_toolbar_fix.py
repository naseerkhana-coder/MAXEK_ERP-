"""Upload budget vs actual + finance toolbar fixes to VPS."""

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
    ("modules/finance_workflow.py", "modules/finance_workflow.py"),
    ("styles/theme.css", "styles/theme.css"),
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy budget + toolbar fixes to MAXEK ERP VPS")
    parser.add_argument("--host", default="72.61.224.204")
    parser.add_argument("--user", default="root")
    parser.add_argument("--remote-dir", default="/var/www/maxek-erp")
    parser.add_argument("--password", default=os.environ.get("MAXEK_SSH_PASSWORD", ""))
    args = parser.parse_args()

    password = args.password
    if not password:
        if not sys.stdin.isatty():
            raise SystemExit("Set MAXEK_SSH_PASSWORD or pass --password for non-interactive deploy.")
        password = getpass.getpass(f"SSH password for {args.user}@{args.host}: ")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {args.user}@{args.host}...")
    client.connect(args.host, username=args.user, password=password, timeout=60)
    sftp = client.open_sftp()

    for local_rel, remote_rel in FILES:
        local_path = ROOT / local_rel
        if not local_path.is_file():
            raise SystemExit(f"Missing local file: {local_rel}")
        remote_path = f"{args.remote_dir}/{remote_rel}".replace("\\", "/")
        print(f"Upload {local_rel}")
        sftp.put(str(local_path), remote_path)

    sftp.close()

    remote_py = f"{args.remote_dir}/.venv/bin/python"
    cmd = (
        f"cd {args.remote_dir} && {remote_py} -c \"from modules.database import load_budget_vs_actual; "
        "import inspect; print(inspect.signature(load_budget_vs_actual))\" "
        "&& systemctl restart maxek-erp && systemctl is-active maxek-erp"
    )
    print("Verifying fix and restarting maxek-erp...")
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
