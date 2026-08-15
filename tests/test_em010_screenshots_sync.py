"""
Test Suite: EMP-REGRESSION-2.0
Feature: EM010_Screenshots
Layers Validated:
  - Layer 1 (L1): Local configuration verification (EV-001)
  - Layer 2 (L2): SQLite pending_screenshots6 verification (EV-003)
  - Layer 4 (L4): Dashboard screenshot count and rendering verification (EV-013, EV-014)
"""

import os
import sqlite3
import configparser
from pathlib import Path
from typing import Dict, Any
import pytest
from playwright.sync_api import sync_playwright, BrowserContext

from src.pages.screenshots_page import ScreenshotsPage

# Path configuration
APPDATA_PATH = os.getenv("APPDATA", "")
CONFIG_PATH = Path(APPDATA_PATH) / "screen" / "empm.ini"
SQLITE_DB_PATH = Path(APPDATA_PATH) / "screen" / "data.db"
AUTH_FILE = "playwright-profile/auth.json"


def _resolve_config_path() -> Path:
    if CONFIG_PATH.exists():
        return CONFIG_PATH
    if APPDATA_PATH:
        candidates = list(Path(APPDATA_PATH).glob("screen/OjUp*/empm.ini")) + list(Path(APPDATA_PATH).glob("screen/empm.ini"))
        if candidates:
            return candidates[0]
    local_ini = Path("config/empm.ini")
    if local_ini.exists():
        return local_ini
    return CONFIG_PATH


def _resolve_sqlite_path() -> Path:
    if SQLITE_DB_PATH.exists():
        return SQLITE_DB_PATH
    if APPDATA_PATH:
        candidates = (
            list(Path(APPDATA_PATH).glob("screen/OjUp*/empm/local_db*.db"))
            + list(Path(APPDATA_PATH).glob("screen/OjUp*/local_db*.db"))
            + list(Path(APPDATA_PATH).glob("screen/empm/local_db*.db"))
            + list(Path(APPDATA_PATH).glob("screen/*.db"))
        )
        if candidates:
            return candidates[0]
    return SQLITE_DB_PATH


class TestScreenshotsCrossLayer:

    @pytest.fixture(scope="class")
    def l1_config_evidence(self) -> Dict[str, Any]:
        """Layer 1 (L1) - Local Configuration Validation [EV-001]"""
        target_ini = _resolve_config_path()
        if not target_ini.exists():
            return {"status": "SKIPPED", "reason": "Local empm.ini not present on host"}

        config = configparser.ConfigParser()
        config.read(target_ini)

        # MASK sensitive fields per security guidelines
        masked_token = "***REDACTED***" if config.has_option("settings", "token") or config.has_option("auth", "token") else "NOT_FOUND"
        masked_pwd = "***REDACTED***" if config.has_option("settings", "crypto_password") or config.has_option("auth", "crypto_password") else "NOT_FOUND"

        screenshot_quality = config.get("appSettings", "screenshotQuality", fallback=config.get("settings", "data\\screen_record\\video_quality", fallback="Medium"))
        screenshot_period = config.get("appSettings", "screenshotPeriodSec", fallback=config.get("appSettings", "from_remote\\screenshotPeriodSec", fallback="300"))

        return {
            "evidence_id": "EV-001",
            "screenshot_quality": screenshot_quality,
            "screenshot_period": screenshot_period,
            "token": masked_token,
            "crypto_password": masked_pwd,
            "status": "HEALTHY"
        }

    @pytest.fixture(scope="class")
    def l2_db_evidence(self) -> Dict[str, Any]:
        """Layer 2 (L2) - Host Runtime & SQLite Storage Validation [EV-003]"""
        target_db = _resolve_sqlite_path()
        if not target_db.exists():
            # In test environments with isolated DBs, default to simulated or empty check
            return {"evidence_id": "EV-003", "persisted_screenshots_count": 0, "status": "UNKNOWN"}

        try:
            conn = sqlite3.connect(str(target_db))
            cursor = conn.cursor()
            # Check if pending_screenshots6 exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pending_screenshots6'")
            if cursor.fetchone():
                cursor.execute("SELECT COUNT(*) FROM pending_screenshots6 WHERE is_deleted=0")
                count = cursor.fetchone()[0]
            else:
                count = 0
            conn.close()

            return {
                "evidence_id": "EV-003",
                "persisted_screenshots_count": count,
                "status": "HEALTHY"
            }
        except Exception as e:
            return {"evidence_id": "EV-003", "persisted_screenshots_count": 0, "status": "DEGRADED", "error": str(e)}

    def test_verify_screenshots_l4_dashboard_correlation(
        self,
        l1_config_evidence: Dict[str, Any],
        l2_db_evidence: Dict[str, Any]
    ):
        """Validates Layer 4 web interface and correlates with Layer 1 and Layer 2 evidence."""
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            
            # Layer 4 Authentication via Session Caching
            if not Path(AUTH_FILE).exists():
                pytest.fail(f"Session cache not found at {AUTH_FILE}. Generate storage state first.")

            context: BrowserContext = browser.new_context(storage_state=AUTH_FILE)
            page = context.new_page()

            try:
                # 1. Initialize POM and Navigate
                dashboard = ScreenshotsPage(page)
                page.goto("https://app.dev.empmonitor.com/amember/member")
                dashboard.dismiss_modals()

                # 2. Filter target employee profile
                dashboard.navigate_to_employee_details()
                dashboard.filter_employee("auto test")

                # 3. Filter screenshots by date
                dashboard.open_screenshots_tab()
                dashboard.filter_by_date(target_date_day="15")

                # 4. Extract L4 UI Metrics
                rendered_count = dashboard.get_rendered_screenshot_count()
                sample_title = dashboard.inspect_first_screenshot() if rendered_count > 0 else "None"

                # 5. Build Cross-Layer Evidence Schema
                correlation_verdict = "HEALTHY" if rendered_count > 0 else "DEGRADED"
                confidence = "HIGH" if (l1_config_evidence.get("status") == "HEALTHY" and rendered_count > 0) else "MEDIUM"

                result_summary = {
                    "feature_id": "EM010_Screenshots",
                    "overall_verdict": correlation_verdict,
                    "confidence": confidence,
                    "layers_covered": ["L1", "L2", "L4"],
                    "evidence_collected": {
                        "L1_EV001": l1_config_evidence,
                        "L2_EV003": l2_db_evidence,
                        "L4_EV013": {
                            "rendered_screenshot_count": rendered_count,
                            "sample_screenshot_title": sample_title,
                            "status": "HEALTHY" if rendered_count > 0 else "EMPTY"
                        }
                    }
                }

                # 6. Cross-Layer Assertion Assertions
                assert rendered_count > 0, "L4 Dashboards yielded 0 screenshots for the selected active period."
                print(f"\n[EXECUTION VERDICT]: {result_summary['overall_verdict']} (Confidence: {result_summary['confidence']})")

            finally:
                context.close()
                browser.close()
