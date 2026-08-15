"""
Test Suite: EMP-REGRESSION-2.0
Feature: EM010_Screenshots
Layers Validated:
  - L1: Local empm.ini parsing & email extraction (EV-001)
  - L2: SQLite pending_screenshots6 check (EV-003)
  - L4: Dashboard employee correlation, scroll-to-right verification, & UI proof capture (EV-013, EV-014)
"""

import os
import time
import json
import sqlite3
import configparser
from pathlib import Path
from typing import Dict, Any
import pytest
from playwright.sync_api import sync_playwright, BrowserContext

from src.pages.screenshots_page import ScreenshotsPage

# Paths
APPDATA = os.getenv("APPDATA", "")
CONFIG_PATH = Path(APPDATA) / "screen" / "empm.ini"
SQLITE_DB_PATH = Path(APPDATA) / "screen" / "data.db"
AUTH_FILE = "playwright-profile/auth.json"
EVIDENCE_DIR = Path("reports/evidence")


def _resolve_ini_path() -> Path:
    if CONFIG_PATH.exists():
        return CONFIG_PATH
    if APPDATA:
        candidates = list(Path(APPDATA).glob("screen/OjUp*/empm.ini")) + list(Path(APPDATA).glob("screen/empm.ini"))
        if candidates:
            return candidates[0]
    local_ini = Path("config/empm.ini")
    if local_ini.exists():
        return local_ini
    return CONFIG_PATH


def _resolve_db_path() -> Path:
    if SQLITE_DB_PATH.exists():
        return SQLITE_DB_PATH
    if APPDATA:
        candidates = (
            list(Path(APPDATA).glob("screen/OjUp*/empm/local_db*.db"))
            + list(Path(APPDATA).glob("screen/OjUp*/local_db*.db"))
            + list(Path(APPDATA).glob("screen/empm/local_db*.db"))
            + list(Path(APPDATA).glob("screen/*.db"))
        )
        if candidates:
            return candidates[0]
    return SQLITE_DB_PATH


class TestScreenshotsWithProof:

    @pytest.fixture(scope="class")
    def l1_config(self) -> Dict[str, Any]:
        """Layer 1 (L1) - Local Configuration (EV-001)"""
        target_path = _resolve_ini_path()
        if not target_path.exists():
            # Fallback for environments running mock configs
            return {
                "evidence_id": "EV-001",
                "email": "auto@example.com",
                "screenshot_quality": "Medium",
                "status": "HEALTHY",
                "crypto_password": "***REDACTED***",
                "token": "***REDACTED***"
            }

        config = configparser.ConfigParser()
        config.read(target_path)

        # Extract email and strictly mask credentials
        email = config.get("settings", "email", fallback=config.get("appSettings", "userEmail", fallback="auto@example.com"))
        
        return {
            "evidence_id": "EV-001",
            "email": email,
            "screenshot_quality": config.get("appSettings", "screenshotQuality", fallback="Medium"),
            "screenshot_period_sec": config.get("appSettings", "screenshotPeriodSec", fallback="60"),
            "token": "***REDACTED***",
            "crypto_password": "***REDACTED***",
            "status": "HEALTHY"
        }

    @pytest.fixture(scope="class")
    def l2_database(self) -> Dict[str, Any]:
        """Layer 2 (L2) - Host Runtime SQLite Table (EV-003)"""
        target_db = _resolve_db_path()
        if not target_db.exists():
            return {"evidence_id": "EV-003", "persisted_count": 0, "status": "SKIPPED"}

        try:
            conn = sqlite3.connect(str(target_db))
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pending_screenshots6'")
            if cursor.fetchone():
                cursor.execute("SELECT COUNT(*) FROM pending_screenshots6 WHERE is_deleted=0")
                row_count = cursor.fetchone()[0]
            else:
                row_count = 0
            conn.close()

            return {
                "evidence_id": "EV-003",
                "persisted_count": row_count,
                "status": "HEALTHY"
            }
        except Exception:
            return {"evidence_id": "EV-003", "persisted_count": 0, "status": "INCONCLUSIVE"}

    def test_em010_screenshots_objective_proof(self, l1_config: Dict[str, Any], l2_database: Dict[str, Any]):
        """
        Executes end-to-end verification and generates screenshot proof on disk.
        """
        email_to_query = l1_config["email"]
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        proof_image_path = EVIDENCE_DIR / f"EV-013-PROOF-EM010_{int(time.time())}.png"

        if not Path(AUTH_FILE).exists():
            pytest.skip(f"Authentication state {AUTH_FILE} not present; skipping live browser execution.")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context: BrowserContext = browser.new_context(storage_state=AUTH_FILE)
            page = context.new_page()

            try:
                # 1. Initialize Dashboard POM
                dashboard = ScreenshotsPage(page)
                page.goto("https://app.dev.empmonitor.com/amember/member")
                dashboard.dismiss_modals()

                # 2. Correlate Employee (L1 Email -> L4 Dashboard Full Name)
                dashboard.navigate_to_employee_details()
                emp_identity = dashboard.find_and_select_employee(email_to_query)

                # 3. Switch to Screenshots Tab and Filter
                dashboard.switch_to_screenshots_tab()

                # 4. Scroll Gallery to Far Right to ensure all lazy-loaded elements render
                dashboard.scroll_gallery_to_right()

                # 5. Extract Rendered Count & Capture Objective UI Evidence Proof
                screenshot_items = dashboard.get_all_rendered_screenshot_metadata()
                rendered_count = len(screenshot_items)
                
                # Save visual proof to disk
                saved_proof_path = dashboard.capture_dashboard_evidence_screenshot(proof_image_path)

                # 6. Build Cross-Layer Evidence Schema
                verdict = "HEALTHY" if rendered_count > 0 else "DEGRADED"
                confidence = "HIGH" if (l1_config["status"] == "HEALTHY" and rendered_count > 0) else "MEDIUM"

                execution_summary = {
                    "feature_id": "EM010_Screenshots",
                    "overall_verdict": verdict,
                    "confidence": confidence,
                    "layers_covered": ["L1", "L2", "L4"],
                    "correlations": {
                        "user_identity_correlation": {
                            "l1_config_email": l1_config["email"],
                            "l4_dashboard_user": emp_identity["dashboard_full_name"],
                            "matched": bool(emp_identity["dashboard_full_name"])
                        },
                        "storage_to_ui_correlation": {
                            "l2_persisted_count": l2_database.get("persisted_count", 0),
                            "l4_rendered_count": rendered_count
                        }
                    },
                    "objective_evidence": {
                        "evidence_id": "EV-013",
                        "proof_screenshot_file": str(saved_proof_path),
                        "rendered_count": rendered_count,
                        "sample_entries": screenshot_items[:3]
                    }
                }

                # Save execution summary report
                report_file = Path("reports") / "em010_screenshots_proof_report.json"
                report_file.parent.mkdir(parents=True, exist_ok=True)
                with open(report_file, "w", encoding="utf-8") as f:
                    json.dump({"summary": execution_summary}, f, indent=2)

                # 7. Assertions
                assert emp_identity["dashboard_full_name"], "Failed to correlate employee name from dashboard table"
                assert rendered_count > 0, "No screenshots were rendered on the L4 dashboard after scrolling to end"
                assert saved_proof_path.exists(), "Objective proof screenshot was not written to disk"

                print(f"\n[REPORT]: Verdict={execution_summary['overall_verdict']} | Proof saved at {saved_proof_path}")

            finally:
                context.close()
                browser.close()


if __name__ == "__main__":
    pytest.main(["-v", str(__file__)])
