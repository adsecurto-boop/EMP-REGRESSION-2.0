"""EM023_EmailMonitoring -- Email Monitoring validation plugin.

Validates the EmpMonitor Email Monitoring feature across configuration (L1), runtime
(L2), persistence (L3), and dashboard (L4) layers.

Feature verification status: **Verified**.
The mechanism has been directly observed, so an expected artifact being absent
is a real defect and this plugin may report ``FAILED``.

What the profile in ``config/features.json`` expects:

* configuration: none recorded
* runtime components: EmailMonitorSvc.exe
* SQLite tables: inbound_emails, outbound_emails, mail_data, mail_attachment_data
* log patterns: request_dump, upload_succeeded
* APIs: save-email-monitoring-log
* dashboard pages: reports
* evidence: EV-003, EV-007, EV-011, EV-013, EV-017

Inherited from :class:`plugins.base.FeatureValidationPlugin`: profile loading, pipeline
composition, cross-layer correlation, evidence-sufficiency checking, summary building,
and the ``EM000_EnvironmentValidator`` dependency.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from framework.core.correlation import Correlation
from framework.shared.interfaces import Collector, Validator
from framework.shared.models import Evidence, ValidationContext
from plugins.base import FeatureValidationPlugin

__all__ = ["EmailMonitoringPlugin"]


class EmailMonitoringPlugin(FeatureValidationPlugin):
    """Validates the EmpMonitor Email Monitoring feature.

    Inherits every default from :class:`~plugins.base.FeatureValidationPlugin`.
    """

    feature_id = "EM023_EmailMonitoring"

    def collectors(self) -> Sequence[Collector]:
        """Collectors this feature needs.

        The inherited default is derived from the feature profile and reuses the
        framework's existing collectors.

        Returns:
            The collectors to run.
        """
        return super().collectors()

    def validators(self) -> Sequence[Validator]:
        """Validators this feature needs.

        Returns:
            The validators to run.
        """
        return super().validators()

    def correlate(
        self, context: ValidationContext, evidence: Sequence[Evidence]
    ) -> Sequence[Correlation]:
        """Relate this feature's observations across layers.

        Returns:
            The correlations.
        """
        return super().correlate(context, evidence)

    def feature_summary(self) -> Mapping[str, Any]:
        """Return detail specific to Email Monitoring.

        Returns:
            Feature-specific detail for the report.
        """
        profile = self.profile
        return {
            "feature_id": self.feature_id,
            "feature_name": profile.name,
            "status": profile.verification_status,
            "expected_tables": list(profile.expected_sqlite_tables),
            "expected_runtime_components": list(profile.expected_runtime_components),
            "expected_log_patterns": list(profile.expected_log_patterns),
            "expected_apis": list(profile.expected_apis),
            "expected_dashboard_pages": list(profile.expected_dashboard_pages),
            "failure_modes": list(profile.expected_failure_modes),
        }

