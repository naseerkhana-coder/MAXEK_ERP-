"""Deploy DPR steel shape measurements to VPS."""

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
    ("modules/dpr_steel_shapes.py", "modules/dpr_steel_shapes.py"),
    ("modules/dpr_measurements.py", "modules/dpr_measurements.py"),
    ("assets/dpr_steel/chair.png", "assets/dpr_steel/chair.png"),
    ("assets/dpr_steel/ring.png", "assets/dpr_steel/ring.png"),
    ("assets/dpr_steel/starter.png", "assets/dpr_steel/starter.png"),
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
    try:
        sftp.mkdir(f"{args.remote_dir}/assets/dpr_steel")
    except OSError:
        pass
    for local_rel, remote_rel in FILES:
        print(f"Upload {ROOT / local_rel}")
        remote_path = f"{args.remote_dir}/{remote_rel}".replace("\\", "/")
        remote_parent = remote_path.rsplit("/", 1)[0]
        try:
            sftp.mkdir(remote_parent)
        except OSError:
            pass
        sftp.put(str(ROOT / local_rel), remote_path)
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
