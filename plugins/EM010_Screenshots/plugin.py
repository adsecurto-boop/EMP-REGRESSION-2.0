"""EM010_Screenshots -- Screenshots validation plugin.

Validates the EmpMonitor Screenshots feature across configuration (L1), runtime
(L2), persistence (L3), and dashboard (L4) layers.

Feature verification status: **Partially Verified**.
Supporting artifacts have been observed but the feature's operation has not.
Absence must be reported ``INCONCLUSIVE``, not ``FAILED`` -- see
``FeatureProfile.absence_verdict``.

What the profile in ``config/features.json`` expects:

* configuration: appSettings/screenshotQuality, appSettings/from_remote\\screenshotPeriodSec
* runtime components: empmonitor.exe
* SQLite tables: pending_screenshots6
* log patterns: upload_cycle_trigger
* APIs: add-activity
* dashboard pages: screenshots
* evidence: EV-001, EV-002, EV-003, EV-007, EV-011

Inherited from :class:`plugins.base.FeatureValidationPlugin`: profile loading, pipeline
composition, cross-layer correlation, evidence-sufficiency checking, summary building,
and the ``EM000_EnvironmentValidator`` dependency.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from framework.core.correlation import Correlation
from framework.dashboard.screenshots_collector import PlaywrightScreenshotsDashboardCollector
from framework.shared.interfaces import Collector, Validator
from framework.shared.models import Evidence, ValidationContext
from framework.validators.frequency import ScreenshotCadenceValidator
from plugins.base import FeatureValidationPlugin
from plugins.EM010_Screenshots.screenshot_correlation_reducer import ScreenshotsCorrelationReducer

__all__ = ["ScreenshotsPlugin"]


class ScreenshotsPlugin(FeatureValidationPlugin):
    """Validates the EmpMonitor Screenshots feature with full L1-L4 correlation."""

    feature_id = "EM010_Screenshots"

    def collectors(self) -> Sequence[Collector]:
        """Collectors this feature needs, replacing unavailable dashboard with Playwright collector."""
        cols = list(super().collectors())
        # Replace any UnavailableDashboardCollector with Playwright collector
        filtered = [c for c in cols if "unavailable" not in getattr(c, "name", "")]
        filtered.append(PlaywrightScreenshotsDashboardCollector())
        return tuple(filtered)

    def validators(self) -> Sequence[Validator]:
        """Validators this feature needs, adding the multi-layer cadence validator."""
        vals = list(super().validators())
        vals.append(ScreenshotCadenceValidator(tolerance_seconds=15))
        return tuple(vals)

    def correlate(
        self, context: ValidationContext, evidence: Sequence[Evidence]
    ) -> Sequence[Correlation]:
        """Relate this feature's observations across layers using ScreenshotsCorrelationReducer."""
        return ScreenshotsCorrelationReducer.to_framework_correlations(evidence)

    def feature_summary(self) -> Mapping[str, Any]:
        """Return detail specific to Screenshots."""
        profile = self.profile
        return {
            "feature_id": self.feature_id,
            "feature_name": profile.name,
            "status": profile.verification_status,
            "required_configuration": list(profile.required_configuration),
            "upload_interval_key": profile.expected_upload_interval_key,
            "expected_tables": list(profile.expected_sqlite_tables),
            "expected_runtime_components": list(profile.expected_runtime_components),
            "expected_log_patterns": list(profile.expected_log_patterns),
            "expected_apis": list(profile.expected_apis),
            "expected_dashboard_pages": list(profile.expected_dashboard_pages),
            "failure_modes": list(profile.expected_failure_modes),
        }

