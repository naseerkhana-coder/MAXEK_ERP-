"""Upload repair scripts and run BOQ fix on VPS."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="72.61.224.204")
    parser.add_argument("--user", default="root")
    parser.add_argument("--remote-dir", default="/var/www/maxek-erp")
    parser.add_argument("--password", default=os.environ.get("MAXEK_SSH_PASSWORD", ""))
    args = parser.parse_args()
    password = args.password
    if not password:
        raise SystemExit("Set MAXEK_SSH_PASSWORD or pass --password")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(args.host, username=args.user, password=password, timeout=30)

    sftp = client.open_sftp()
    uploads = (
        ("modules/database.py", "modules/database.py"),
        ("scripts/repair_project_boq_links.py", "scripts/repair_project_boq_links.py"),
        ("scripts/inspect_boq_data.py", "scripts/inspect_boq_data.py"),
    )
    for local_rel, remote_rel in uploads:
        local_path = ROOT / local_rel
        remote_path = f"{args.remote_dir}/{remote_rel}".replace("\\", "/")
        print(f"Upload {local_path} -> {remote_path}")
        sftp.put(str(local_path), remote_path)
    sftp.close()

    py = f"{args.remote_dir}/.venv/bin/python"
    for cmd_label, cmd in [
        ("INSPECT BEFORE", f"cd {args.remote_dir} && {py} scripts/inspect_boq_data.py"),
        ("REPAIR APPLY", f"cd {args.remote_dir} && {py} scripts/repair_project_boq_links.py --fix-ids --fix-links --apply"),
        ("INSPECT AFTER", f"cd {args.remote_dir} && {py} scripts/inspect_boq_data.py"),
        ("RESTART", f"systemctl restart maxek-erp && systemctl is-active maxek-erp"),
    ]:
        print(f"\n=== {cmd_label} ===")
        _, stdout, stderr = client.exec_command(cmd)
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        if out:
            print(out)
        if err:
            print(err, file=sys.stderr)

    client.close()
    print("\nDone. Hard-refresh DPR page (Ctrl+F5).")


if __name__ == "__main__":
    main()
