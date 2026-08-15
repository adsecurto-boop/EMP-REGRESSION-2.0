"""Configuration Extractor CLI Tool.

Extracts and normalizes configuration settings from `empm.ini` and `config.js`.
Strictly masks passwords, credentials, tokens, and API keys before returning output.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from framework.shared.utils import ini_utils, filesystem
from framework.shared.profile import ProductProfile
from framework.shared.config import load_configuration
from scripts.profile_inspector import discover_ojup_profile

SECRET_KEYS = {
    "password", "crypto_password", "token", "secret", "auth_key", "api_key", "credentials"
}

def mask_secrets(data: Any) -> Any:
    """Recursively mask sensitive values in dictionary structure."""
    if isinstance(data, dict):
        masked = {}
        for k, v in data.items():
            key_lower = str(k).lower()
            if any(s in key_lower for s in SECRET_KEYS):
                masked[k] = "***MASKED***"
            else:
                masked[k] = mask_secrets(v)
        return masked
    elif isinstance(data, list):
        return [mask_secrets(item) for item in data]
    return data

def parse_config_js(config_js_path: Path) -> dict[str, Any]:
    """Extract HTTPS, WebSocket, and API endpoints from configs/config.js via static parsing."""
    if not config_js_path.is_file():
        return {
            "status": "ABSENT",
            "path": str(config_js_path),
            "endpoints": [],
            "urls": [],
        }

    try:
        content = config_js_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return {
            "status": "INACCESSIBLE",
            "path": str(config_js_path),
            "error": str(exc),
        }

    # Static regex extraction for endpoints & URLs
    urls = re.findall(r'https?://[^\s\'"]+', content)
    wss = re.findall(r'wss?://[^\s\'"]+', content)
    
    # Extract object keys if any
    keys = re.findall(r'([a-zA-Z0-9_]+)\s*:\s*[\'"]([^\'"]+)[\'"]', content)
    extracted_keys = {k: v for k, v in keys}

    return {
        "status": "SUCCESS",
        "path": str(config_js_path),
        "http_endpoints": list(set(urls)),
        "websocket_endpoints": list(set(wss)),
        "parsed_keys": mask_secrets(extracted_keys),
    }

def extract_empm_ini(ini_path: Path) -> dict[str, Any]:
    """Extract sections and settings from empm.ini."""
    if not ini_path.is_file():
        return {
            "status": "ABSENT",
            "path": str(ini_path),
            "sections": {},
        }

    try:
        parsed = ini_utils.read_ini_file(ini_path)
    except Exception as exc:
        return {
            "status": "INVALID",
            "path": str(ini_path),
            "error": str(exc),
        }

    masked_sections = mask_secrets(parsed)
    
    # Extract summary highlights
    app_settings = masked_sections.get("appSettings", {})
    settings_section = masked_sections.get("settings", {})
    auth_section = masked_sections.get("auth", {})
    general_section = masked_sections.get("General", {})

    features = {}
    for k, v in settings_section.items():
        if "features\\" in k or "dlpFeatures\\" in k:
            features[k.split("\\")[-1]] = v

    return {
        "status": "SUCCESS",
        "path": str(ini_path),
        "sections": masked_sections,
        "summary": {
            "user_email": auth_section.get("email"),
            "identifier": general_section.get("identifier"),
            "data_sending_period_sec": app_settings.get("dataSendingPeriodSec"),
            "screenshot_quality": app_settings.get("screenshotQuality"),
            "screenshot_period_sec": app_settings.get("from_remote\\screenshotPeriodSec") or app_settings.get("screenshotPeriodSec"),
            "tracking_mode": settings_section.get("data\\trackingMode"),
            "features": features,
            "screen_record_enabled": settings_section.get("data\\screen_record\\is_enabled") == "1" or settings_section.get("data\\features\\screen_record") == "1",
            "screenshots_enabled": settings_section.get("data\\features\\screenshots") == "1",
            "email_monitoring_enabled": settings_section.get("data\\features\\email_monitoring") == "1",
            "keystrokes_enabled": settings_section.get("data\\features\\keystrokes") == "1",
            "activity_log_frequency": settings_section.get("data\\activity_log_update_frequency"),
        }
    }

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="EmpMonitor Configuration Extractor")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    args = parser.parse_args(argv)

    config = load_configuration()
    profile = ProductProfile(config.get("empmonitor"))
    
    # Locate empm.ini
    prof_info = discover_ojup_profile()
    ini_path = Path(prof_info["empm_ini"]) if prof_info.get("empm_ini") else Path("C:\\Program Files\\EmpMonitor\\empm.ini")
    
    # Locate config.js
    config_js_exp = next((exp for exp in profile.configuration_files() if exp.role == "agent_configuration"), None)
    config_js_path, _ = profile.locate(config_js_exp) if config_js_exp else (None, ())
    if not config_js_path:
        config_js_path = Path("C:\\Program Files\\EmpMonitor\\EmpMonitor\\gui\\configs\\config.js")

    ini_data = extract_empm_ini(ini_path)
    js_data = parse_config_js(config_js_path)

    combined = {
        "empm_ini": ini_data,
        "config_js": js_data,
    }

    if args.json:
        print(json.dumps(combined, indent=2))
    else:
        print("=== EMPMONITOR CONFIGURATION EXTRACTION ===")
        print(f"empm.ini Status:  {ini_data.get('status')} ({ini_data.get('path')})")
        print(f"config.js Status: {js_data.get('status')} ({js_data.get('path')})")
        print("\nJSON Output:")
        print(json.dumps(combined, indent=2))

    return 0

if __name__ == "__main__":
    sys.exit(main())
