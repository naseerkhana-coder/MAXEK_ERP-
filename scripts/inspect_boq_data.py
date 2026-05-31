"""Print project / BOQ linkage summary."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.database import get_conn

conn = get_conn()
print("=== PROJECTS ===")
for row in conn.execute("SELECT project_id, project_name, client_name FROM projects ORDER BY project_name"):
    print(row)
print("\n=== BOQ BY PROJECT ===")
for row in conn.execute(
    """
    SELECT project_id, project_name, COUNT(*) AS cnt
    FROM project_boq_items
    GROUP BY project_id, project_name
    ORDER BY project_name
    """
):
    print(row)
print("\n=== TOTAL BOQ ===", conn.execute("SELECT COUNT(*) FROM project_boq_items").fetchone()[0])
print("\n=== SAMPLE BOQ (first 15) ===")
for row in conn.execute(
    """
    SELECT boq_item_id, project_id, project_name, boq_number
    FROM project_boq_items
    ORDER BY id DESC
    LIMIT 15
    """
):
    print(row)
conn.close()
