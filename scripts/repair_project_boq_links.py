"""Repair project_boq_items so project_id and project_name match the projects table."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.database import get_conn, init_db


def _next_pb_id(cur) -> str:
    cur.execute("SELECT boq_item_id FROM project_boq_items WHERE boq_item_id LIKE 'PB%'")
    max_num = 100
    for (raw,) in cur.fetchall():
        text = str(raw or "")
        if not text.startswith("PB"):
            continue
        try:
            max_num = max(max_num, int(text[2:]))
        except ValueError:
            continue
    return f"PB{max_num + 1}"


def repair_duplicate_boq_item_ids(dry_run: bool = True):
    """Assign unique boq_item_id where multiple BOQ rows share the same ID."""
    conn = get_conn()
    cur = conn.cursor()
    rows = list(
        cur.execute(
            """
            SELECT id, boq_item_id, project_id, project_name, boq_number
            FROM project_boq_items
            ORDER BY id
            """
        )
    )
    seen: dict[str, int] = {}
    reassignments: list[dict] = []

    for row_id, boq_item_id, project_id, project_name, boq_number in rows:
        key = (boq_item_id or "").strip()
        if not key:
            new_id = _next_pb_id(cur)
            reassignments.append(
                {
                    "row_id": row_id,
                    "old_id": key,
                    "new_id": new_id,
                    "project_id": project_id,
                    "boq_number": boq_number,
                    "reason": "empty_id",
                }
            )
            if not dry_run:
                cur.execute(
                    "UPDATE project_boq_items SET boq_item_id = ? WHERE id = ?",
                    (new_id, row_id),
                )
            continue

        if key not in seen:
            seen[key] = row_id
            continue

        new_id = _next_pb_id(cur)
        reassignments.append(
            {
                "row_id": row_id,
                "old_id": key,
                "new_id": new_id,
                "project_id": project_id,
                "project_name": project_name,
                "boq_number": boq_number,
                "reason": "duplicate_id",
            }
        )
        if not dry_run:
            cur.execute(
                "UPDATE project_boq_items SET boq_item_id = ? WHERE id = ?",
                (new_id, row_id),
            )
            cur.execute(
                """
                UPDATE dpr_reports
                SET boq_item_id = ?
                WHERE boq_item_id = ? AND boq_number = ?
                  AND (project_id = ? OR TRIM(COALESCE(project_name, '')) = TRIM(?))
                """,
                (new_id, key, boq_number, project_id or "", (project_name or "").strip()),
            )
            cur.execute(
                """
                UPDATE client_bill_lines
                SET boq_item_id = ?
                WHERE boq_item_id = ? AND boq_number = ?
                """,
                (new_id, key, boq_number),
            )

    print(f"Duplicate / empty BOQ IDs to fix: {len(reassignments)}")
    for item in reassignments[:30]:
        print(
            f"  row {item['row_id']}: {item['old_id']!r} -> {item['new_id']!r} "
            f"({item.get('project_name') or item.get('project_id')}, BOQ {item['boq_number']!r})"
        )
    if len(reassignments) > 30:
        print(f"  ... and {len(reassignments) - 30} more")

    if dry_run:
        print("\nDry run — no duplicate-ID fixes written. Use --fix-ids --apply.")
    else:
        conn.commit()
        print(f"\nApplied {len(reassignments)} unique BOQ ID assignments.")

    conn.close()
    return len(reassignments)


def repair_project_boq_links(dry_run: bool = True):
    conn = get_conn()
    cur = conn.cursor()

    projects: dict[str, dict[str, str]] = {}
    name_to_id: dict[str, str | None] = {}

    for pid, pname, cname in cur.execute(
        "SELECT project_id, project_name, client_name FROM projects WHERE COALESCE(project_id, '') != ''"
    ):
        pid = (pid or "").strip()
        pname = (pname or "").strip()
        cname = (cname or "").strip()
        if not pid:
            continue
        projects[pid] = {"project_name": pname, "client_name": cname}
        key = pname.casefold()
        if not key:
            continue
        if key in name_to_id and name_to_id[key] != pid:
            name_to_id[key] = None
        else:
            name_to_id[key] = pid

    fixes: list[dict] = []
    unresolved: list[dict] = []

    for boq_item_id, pid, pname, cname in cur.execute(
        """
        SELECT boq_item_id, project_id, project_name, client_name
        FROM project_boq_items
        ORDER BY id
        """
    ):
        pid = (pid or "").strip()
        pname = (pname or "").strip()
        cname = (cname or "").strip()
        new_pid, new_pname, new_cname = pid, pname, cname

        if pid and pid in projects:
            canon = projects[pid]
            new_pname = canon["project_name"]
            new_cname = canon["client_name"]
        else:
            key = pname.casefold()
            resolved = name_to_id.get(key) if key else None
            if resolved:
                new_pid = resolved
                canon = projects[resolved]
                new_pname = canon["project_name"]
                new_cname = canon["client_name"]
            elif pname:
                unresolved.append(
                    {
                        "boq_item_id": boq_item_id,
                        "project_id": pid,
                        "project_name": pname,
                        "reason": "no_matching_project",
                    }
                )

        if (new_pid, new_pname, new_cname) != (pid, pname, cname):
            fixes.append(
                {
                    "boq_item_id": boq_item_id,
                    "old": (pid, pname, cname),
                    "new": (new_pid, new_pname, new_cname),
                }
            )

    print(f"Projects in master: {len(projects)}")
    print(f"BOQ rows to update: {len(fixes)}")
    print(f"BOQ rows unresolved: {len(unresolved)}")

    for item in fixes[:50]:
        old = item["old"]
        new = item["new"]
        print(
            f"  {item['boq_item_id']}: "
            f"id {old[0]!r} -> {new[0]!r}, "
            f"name {old[1]!r} -> {new[1]!r}"
        )
    if len(fixes) > 50:
        print(f"  ... and {len(fixes) - 50} more")

    for item in unresolved[:20]:
        print(f"  UNRESOLVED {item['boq_item_id']}: {item['project_name']!r} ({item['reason']})")

    if dry_run:
        print("\nDry run only — no changes written. Re-run with --apply to fix.")
    else:
        for item in fixes:
            new_pid, new_pname, new_cname = item["new"]
            cur.execute(
                """
                UPDATE project_boq_items
                SET project_id = ?, project_name = ?, client_name = ?
                WHERE boq_item_id = ?
                """,
                (new_pid, new_pname, new_cname, item["boq_item_id"]),
            )
        conn.commit()
        print(f"\nApplied {len(fixes)} updates.")

    conn.close()
    return len(fixes), len(unresolved)


def main() -> None:
    parser = argparse.ArgumentParser(description="Repair project BOQ data")
    parser.add_argument("--apply", action="store_true", help="Write fixes to database")
    parser.add_argument("--init", action="store_true", help="Run init_db() before repair")
    parser.add_argument(
        "--fix-ids",
        action="store_true",
        help="Reassign duplicate boq_item_id values (main DPR BOQ list fix)",
    )
    parser.add_argument(
        "--fix-links",
        action="store_true",
        help="Align project_id / project_name on BOQ rows",
    )
    args = parser.parse_args()

    if args.init:
        init_db()

    dry = not args.apply
    fix_ids = args.fix_ids or not args.fix_links
    fix_links = args.fix_links or not args.fix_ids

    if fix_ids:
        repair_duplicate_boq_item_ids(dry_run=dry)
    if fix_links:
        repair_project_boq_links(dry_run=dry)


if __name__ == "__main__":
    main()
