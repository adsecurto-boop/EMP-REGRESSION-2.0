"""
Module: screenshot_frequency_validator.py
Feature: EM010_Screenshots
Evidence IDs: EV-001 (L1), EV-003 (L2), EV-011 (L3), EV-013/EV-014 (L4)
Validators: FrequencyValidator, TimestampValidator, CorrelationValidator
"""

import re
from datetime import datetime
from typing import List, Dict, Any, Tuple


class ScreenshotFrequencyValidator:
    def __init__(self, tolerance_seconds: int = 15):
        """
        :param tolerance_seconds: Allowed jitter/drift per upload cycle (e.g., ±15s).
        """
        self.tolerance = tolerance_seconds

    @staticmethod
    def parse_ui_timestamp(sc_title: str) -> datetime:
        """
        Extracts datetime from screenshot titles (e.g., '2026-08-15 18:00:31-sc0' or '-08-15 18:00:31-sc0').
        """
        match = re.search(r"(\d{4}-)?(\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})", sc_title)
        if not match:
            raise ValueError(f"Unable to parse timestamp from screenshot title: {sc_title}")
        
        raw_ts = match.group(0)
        # Prefix default year if truncated
        if not re.match(r"^\d{4}", raw_ts):
            raw_ts = f"{datetime.now().year}-{raw_ts.lstrip('-')}"
            
        return datetime.strptime(raw_ts, "%Y-%m-%d %H:%M:%S")

    def validate_cadence(
        self, 
        expected_interval_sec: int, 
        timestamps: List[datetime]
    ) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Verifies that consecutive timestamps conform to the expected upload frequency.
        """
        if len(timestamps) < 2:
            return True, []

        drift_log = []
        is_healthy = True

        for i in range(len(timestamps) - 1):
            t1, t2 = timestamps[i], timestamps[i + 1]
            actual_delta = abs((t2 - t1).total_seconds())
            drift = abs(actual_delta - expected_interval_sec)

            cycle_passed = drift <= self.tolerance
            if not cycle_passed:
                is_healthy = False

            drift_log.append({
                "from": t1.strftime("%H:%M:%S"),
                "to": t2.strftime("%H:%M:%S"),
                "actual_interval_sec": actual_delta,
                "expected_interval_sec": expected_interval_sec,
                "drift_sec": drift,
                "status": "PASS" if cycle_passed else "DRIFT_EXCEEDED"
            })

        return is_healthy, drift_log
