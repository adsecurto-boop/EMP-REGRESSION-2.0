"""Process & Windows Service Inspector CLI Tool.

Verifies running processes (empmonitor.exe, emp_psa_service.exe, esr.exe, UpdateMgr_Emp.exe, EmailMonitorSvc.exe)
and Windows service status (BrowserHandlingService).
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

from framework.shared.utils import windows
from framework.shared.profile import ProductProfile
from framework.shared.config import load_configuration

PROCESS_TARGETS = [
    "empmonitor.exe",
    "emp_psa_service.exe",
    "esr.exe",
    "UpdateMgr_Emp.exe",
    "EmailMonitorSvc.exe",
]

SERVICE_TARGETS = [
    "BrowserHandlingService",
]

def inspect_processes() -> dict[str, Any]:
    """Discover running target processes."""
    if not windows.is_windows():
        return {
            "status": "INCONCLUSIVE",
            "message": "Non-Windows host; cannot query Windows process list.",
            "running_processes": {},
        }

    observed = windows.list_processes()
    grouped = windows.find_processes(PROCESS_TARGETS, processes=observed)

    results = {}
    for proc_name, procs in grouped.items():
        is_running = len(procs) > 0
        details = []
        for p in procs:
            details.append({
                "pid": p.pid,
                "memory_bytes": p.memory_bytes,
                "cpu_seconds": p.cpu_seconds,
                "executable_path": p.executable_path,
                "start_time": p.start_time.isoformat() if p.start_time else None,
            })
        results[proc_name] = {
            "present": is_running,
            "instances_count": len(procs),
            "details": details,
        }

    return {
        "status": "SUCCESS",
        "running_processes": results,
    }

def inspect_services() -> dict[str, Any]:
    """Discover Windows service statuses."""
    if not windows.is_windows():
        return {
            "status": "INCONCLUSIVE",
            "message": "Non-Windows host; cannot query Windows services.",
            "services": {},
        }

    svc_results = {}
    for svc_name in SERVICE_TARGETS:
        info = windows.query_service(svc_name)
        svc_results[svc_name] = {
            "found": info.found,
            "display_name": info.display_name,
            "state": info.state,
            "is_running": info.is_running,
            "start_type": info.start_type,
            "binary_path": info.binary_path,
            "process_id": info.process_id,
        }

    return {
        "status": "SUCCESS",
        "services": svc_results,
    }

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="EmpMonitor Process & Service Inspector")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    args = parser.parse_args(argv)

    proc_data = inspect_processes()
    svc_data = inspect_services()

    combined = {
        "process_inspection": proc_data,
        "service_inspection": svc_data,
    }

    if args.json:
        print(json.dumps(combined, indent=2))
    else:
        print("=== EMPMONITOR PROCESS & SERVICE INSPECTION ===")
        print("Processes:")
        for name, data in proc_data.get("running_processes", {}).items():
            status = "RUNNING" if data.get("present") else "ABSENT"
            print(f"  - {name:<22} [{status}] (Instances: {data.get('instances_count', 0)})")
        print("Services:")
        for name, data in svc_data.get("services", {}).items():
            status = data.get("state") or ("FOUND" if data.get("found") else "ABSENT")
            print(f"  - {name:<22} [{status}] Path: {data.get('binary_path') or 'N/A'}")
        print("\nJSON Output:")
        print(json.dumps(combined, indent=2))

    return 0

if __name__ == "__main__":
    sys.exit(main())
