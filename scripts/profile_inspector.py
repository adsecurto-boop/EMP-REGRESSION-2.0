"""Profile Inspector CLI & Discovery Tool.

Performs Windows environment discovery and dynamic OjUp profile discovery.
Supports human-readable and machine-readable JSON output.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from framework.shared.profile import ProductProfile, Expectation
from framework.shared.utils import windows, filesystem
from framework.shared.config import load_configuration

def discover_windows_environment() -> dict[str, Any]:
    """Collect system and installation information."""
    os_info = windows.os_information()
    timezone = windows.time_zone_name()
    user = windows.current_user()
    
    config = load_configuration()
    profile = ProductProfile(config.get("empmonitor"))
    
    install_root = profile.existing_install_root()
    data_root = profile.existing_data_root()
    
    executables = {}
    for exp in profile.executables():
        located_path, searched = profile.locate(exp)
        executables[exp.role] = {
            "name": exp.display_names,
            "located": str(located_path) if located_path else None,
            "required": exp.required,
            "verified": exp.verified,
            "searched": [str(p) for p in searched],
        }
        
    return {
        "status": "SUCCESS" if windows.is_windows() else "INCONCLUSIVE",
        "platform": os_info.get("system"),
        "os_version": os_info.get("version"),
        "build": os_info.get("build"),
        "architecture": os_info.get("architecture"),
        "hostname": os_info.get("node"),
        "logged_in_user": user,
        "time_zone": timezone,
        "install_root": str(install_root) if install_root else None,
        "data_root": str(data_root) if data_root else None,
        "executables": executables,
    }

def discover_ojup_profile(data_root_path: Path | None = None) -> dict[str, Any]:
    """Dynamically discover OjUp profile under %APPDATA%\\screen.
    
    Rule:
    1. Resolve %APPDATA%\\screen.
    2. Recursively enumerate directories.
    3. Identify directories beginning with OjUp.
    4. Check for empm.ini (ignore if absent).
    5. If multiple valid profiles exist, select profile with newest modification time on empm.ini.
    6. Return mapping of profile directories and candidate paths.
    """
    if data_root_path is None:
        screen_dir = Path(os.path.expandvars("%APPDATA%\\screen"))
        if not screen_dir.exists():
            # Fallback to local data root
            screen_dir = Path(os.path.expanduser("~/.empmonitor/screen"))
    else:
        screen_dir = data_root_path

    if not screen_dir.exists():
        return {
            "status": "ABSENT",
            "message": f"Data root directory '{screen_dir}' does not exist.",
            "profile_root": None,
            "empm_ini": None,
            "empm_dir": None,
            "database_dir": None,
            "logs_dir": None,
            "failed_screenshots": None,
            "failed_screenrecords": None,
        }

    valid_profiles = []
    
    # Check screen_dir and children for OjUp*
    search_dirs = [screen_dir]
    if screen_dir.is_dir():
        try:
            search_dirs.extend([p for p in screen_dir.iterdir() if p.is_dir()])
        except OSError:
            pass

    for candidate in search_dirs:
        if candidate.name.startswith("OjUp") or candidate == screen_dir:
            ini_file = candidate / "empm.ini"
            if not ini_file.is_file():
                ini_file = candidate / "empm" / "empm.ini"
            if ini_file.is_file():
                mtime = ini_file.stat().st_mtime
                valid_profiles.append((mtime, candidate, ini_file))

    if not valid_profiles:
        return {
            "status": "ABSENT",
            "message": f"No valid OjUp profile containing empm.ini found under '{screen_dir}'.",
            "profile_root": None,
            "empm_ini": None,
            "empm_dir": None,
            "database_dir": None,
            "logs_dir": None,
            "failed_screenshots": None,
            "failed_screenrecords": None,
        }

    # Pick newest modified empm.ini
    valid_profiles.sort(key=lambda x: x[0], reverse=True)
    _, profile_root, empm_ini = valid_profiles[0]

    empm_dir = profile_root / "empm" if (profile_root / "empm").is_dir() else profile_root
    db_dir = empm_dir
    logs_dir = empm_dir / "logs"
    failed_screenshots = empm_dir / "failed_screenshots"
    failed_screenrecords = empm_dir / "failed_screenrecords"

    return {
        "status": "SUCCESS",
        "profile_root": str(profile_root),
        "empm_ini": str(empm_ini),
        "empm_dir": str(empm_dir),
        "database_dir": str(db_dir),
        "logs_dir": str(logs_dir) if logs_dir.exists() else None,
        "failed_screenshots": str(failed_screenshots) if failed_screenshots.exists() else None,
        "failed_screenrecords": str(failed_screenrecords) if failed_screenrecords.exists() else None,
        "internal_roles": {
            "logs": str(logs_dir),
            "failed_screenshots": str(failed_screenshots),
            "failed_recordings": str(failed_screenrecords),
        }
    }

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="EmpMonitor Profile & Windows Environment Inspector.")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    args = parser.parse_args(argv)

    env_data = discover_windows_environment()
    profile_data = discover_ojup_profile()

    combined = {
        "environment": env_data,
        "profile_discovery": profile_data
    }

    if args.json:
        print(json.dumps(combined, indent=2))
    else:
        print("=== EMPMONITOR WINDOWS ENVIRONMENT & PROFILE DISCOVERY ===")
        print(f"Platform:      {env_data.get('platform')} {env_data.get('architecture')}")
        print(f"OS Build:      {env_data.get('build') or 'N/A'}")
        print(f"User / Zone:   {env_data.get('logged_in_user')} / {env_data.get('time_zone')}")
        print(f"Install Root:  {env_data.get('install_root') or 'Not Found / Non-Default'}")
        print(f"Data Root:     {env_data.get('data_root') or 'Not Found'}")
        print("\n--- OjUp Active Profile Discovery ---")
        print(f"Status:        {profile_data.get('status')}")
        print(f"Profile Root:  {profile_data.get('profile_root') or 'None'}")
        print(f"empm.ini:      {profile_data.get('empm_ini') or 'None'}")
        print(f"Logs Dir:      {profile_data.get('logs_dir') or 'Absent'}")
        print(f"Failed Shots:  {profile_data.get('failed_screenshots') or 'Absent'}")
        print(f"Failed Records:{profile_data.get('failed_screenrecords') or 'Absent'}")
        print("\nJSON Output:")
        print(json.dumps(combined, indent=2))

    return 0

if __name__ == "__main__":
    sys.exit(main())
