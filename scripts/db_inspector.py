"""SQLite Database Inspector CLI Tool.

Dynamically discovers active EmpMonitor database matching local_db*.db.
Inspects database tables, columns, row counts, and pending queues read-only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from framework.shared.utils import sqlite_utils
from scripts.profile_inspector import discover_ojup_profile

def find_active_database() -> Path | None:
    """Find the newest active local_db*.db in discovered profile."""
    prof_info = discover_ojup_profile()
    empm_dir = prof_info.get("empm_dir")
    
    search_dirs = []
    if empm_dir:
        search_dirs.append(Path(empm_dir))
    
    # Also search candidate locations
    import os
    appdata_screen = Path(os.path.expandvars("%APPDATA%\\screen"))
    if appdata_screen.exists():
        search_dirs.append(appdata_screen)

    db_candidates = []
    for d in search_dirs:
        if d.is_dir():
            try:
                for match in d.glob("**/local_db*.db"):
                    if match.is_file():
                        db_candidates.append(match)
                for match in d.glob("**/*.db"):
                    if match.is_file():
                        db_candidates.append(match)
            except OSError:
                pass

    if not db_candidates:
        return None

    # Sort by modification time descending
    db_candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return db_candidates[0]

def inspect_database(db_path: Path) -> dict[str, Any]:
    """Inspect SQLite schema, row counts, and tables read-only."""
    if not db_path.is_file():
        return {
            "status": "ABSENT",
            "path": str(db_path),
            "error": "Database file not found",
        }

    if not sqlite_utils.database_is_readable(db_path):
        return {
            "status": "INACCESSIBLE",
            "path": str(db_path),
            "error": "Database exists but cannot be opened read-only",
        }

    try:
        with sqlite_utils.open_readonly(db_path) as conn:
            tables = sqlite_utils.list_tables(conn)
            table_details = {}
            pending_tables = []
            sent_tables = []
            
            for t in tables:
                cols = sqlite_utils.table_columns(conn, t)
                rc = sqlite_utils.row_count(conn, t)
                
                # Check for timestamp fields
                timestamp_cols = [c for c in cols if any(ts in c.lower() for ts in ["time", "date", "created", "timestamp"])]
                
                table_details[t] = {
                    "columns": cols,
                    "row_count": rc,
                    "timestamp_columns": timestamp_cols,
                }
                
                if t.startswith("pending_"):
                    pending_tables.append(t)
                elif t.startswith("sent_"):
                    sent_tables.append(t)

            return {
                "status": "SUCCESS",
                "path": str(db_path),
                "total_tables": len(tables),
                "tables": table_details,
                "pending_queues": pending_tables,
                "sent_queues": sent_tables,
            }
    except Exception as exc:
        return {
            "status": "INVALID",
            "path": str(db_path),
            "error": str(exc),
        }

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="EmpMonitor SQLite Database Inspector")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    parser.add_argument("--db", type=str, help="Optional path to database file")
    args = parser.parse_args(argv)

    db_path = Path(args.db) if args.db else find_active_database()
    
    if not db_path:
        out = {
            "status": "ABSENT",
            "message": "No active EmpMonitor local_db*.db found.",
        }
        if args.json:
            print(json.dumps(out, indent=2))
        else:
            print("No active EmpMonitor local_db*.db found.")
        return 0

    inspection = inspect_database(db_path)

    if args.json:
        print(json.dumps(inspection, indent=2))
    else:
        print("=== EMPMONITOR SQLITE DATABASE INSPECTION ===")
        print(f"Path:           {inspection.get('path')}")
        print(f"Status:         {inspection.get('status')}")
        print(f"Total Tables:   {inspection.get('total_tables', 0)}")
        print(f"Pending Queues: {', '.join(inspection.get('pending_queues', [])) or 'None'}")
        print("\nTable Summary:")
        for t, d in inspection.get("tables", {}).items():
            print(f"  - {t:<25} ({d.get('row_count', 0)} rows, cols: {len(d.get('columns', []))})")
        print("\nJSON Output:")
        print(json.dumps(inspection, indent=2))

    return 0

if __name__ == "__main__":
    sys.exit(main())
