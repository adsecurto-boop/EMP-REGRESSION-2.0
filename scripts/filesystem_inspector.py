"""Filesystem Discovery & Path Inspector CLI Tool.

Inspects paths, recursive directory tree structure, permissions, and glob patterns.
Distinguishes folder_exists, folder_absent, folder_not_configured, folder_inaccessible.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from framework.shared.utils import filesystem, windows
from scripts.profile_inspector import discover_ojup_profile

def inspect_path(target_path: Path | str) -> dict[str, Any]:
    """Report filesystem status for a target path."""
    if not target_path or str(target_path).strip() in ("", "None"):
        return {
            "status": "folder_not_configured",
            "path": str(target_path),
            "exists": False,
        }

    target = Path(target_path)
    if not target.exists():
        return {
            "status": "folder_absent",
            "path": str(target),
            "exists": False,
        }

    perms = windows.path_permissions(target)
    if not perms.get("readable"):
        return {
            "status": "folder_inaccessible",
            "path": str(target),
            "exists": True,
            "permissions": perms,
        }

    size_bytes = 0
    file_count = 0
    dir_count = 0
    if target.is_file():
        size_bytes = target.stat().st_size
        file_count = 1
    elif target.is_dir():
        try:
            for root, dirs, files in os.walk(target):
                dir_count += len(dirs)
                file_count += len(files)
                for f in files:
                    try:
                        size_bytes += Path(root, f).stat().st_size
                    except OSError:
                        pass
        except OSError:
            pass

    return {
        "status": "folder_exists",
        "path": str(target),
        "exists": True,
        "is_directory": target.is_dir(),
        "size_bytes": size_bytes,
        "file_count": file_count,
        "dir_count": dir_count,
        "permissions": perms,
    }

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="EmpMonitor Filesystem Discovery & Path Inspector")
    parser.add_argument("path", nargs="?", help="Path or glob pattern to inspect")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    args = parser.parse_args(argv)

    if not args.path:
        # Default: inspect active OjUp profile paths
        prof = discover_ojup_profile()
        paths_to_check = {
            "profile_root": prof.get("profile_root"),
            "empm_dir": prof.get("empm_dir"),
            "logs_dir": prof.get("logs_dir"),
            "failed_screenshots": prof.get("failed_screenshots"),
            "failed_screenrecords": prof.get("failed_screenrecords"),
        }
        results = {k: inspect_path(v) for k, v in paths_to_check.items()}
    else:
        results = {"target": inspect_path(args.path)}

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print("=== EMPMONITOR FILESYSTEM INSPECTION ===")
        for name, data in results.items():
            print(f"{name:<20}: [{data.get('status')}] Path: {data.get('path')}")
            if data.get("exists"):
                print(f"  Files: {data.get('file_count')}, Size: {data.get('size_bytes')} bytes")
        print("\nJSON Output:")
        print(json.dumps(results, indent=2))

    return 0

if __name__ == "__main__":
    sys.exit(main())
