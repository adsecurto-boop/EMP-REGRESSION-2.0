"""Dashboard (Layer 4) collection and validation -- **interfaces only**.

No implementation exists here, and none may be added in this sprint: browser
automation is explicitly out of scope. What this module provides is the *contract* a
future dashboard collector must satisfy, so that every consumer -- the correlation
engine, feature plugins, the report -- can be written against Layer 4 today and work
unchanged when a collector arrives.

**The framework has never observed the EmpMonitor dashboard.** Every page, element,
and assertion in ``docs/design/Dashboard_Page_Specifications.md`` is therefore
`Hypothesis`. This module deliberately encodes no page names, no selectors, and no
expected values: it would be trivially easy to invent a plausible dashboard and
impossible for a later reader to tell the invention from observation.

Until an implementation exists, Layer 4 correlations return ``INDETERMINATE`` and
Layer 4 verdicts are ``NOT_OBSERVED``. That is the honest state, and the framework
reports it rather than quietly omitting the layer.
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Sequence

from framework.shared.interfaces import Collector, Validator
from framework.shared.logger import get_logger
from framework.shared.models import (
    Evidence,
    EvidenceLayer,
    Finding,
    ValidationContext,
    Verdict,
)

__all__ = [
    "EV_DASHBOARD_UI",
    "EV_DASHBOARD_SETTINGS",
    "DashboardObservation",
    "DashboardSnapshotCollector",
    "DashboardValidator",
    "UnavailableDashboardCollector",
]

_LOGGER = get_logger(__name__)

EV_DASHBOARD_UI = "EV-006"
EV_DASHBOARD_SETTINGS = "EV-008"


@dataclass(frozen=True, slots=True)
class DashboardObservation:
    """What a dashboard collector reports about one page.

    The shape a future implementation must produce. It is deliberately generic --
    ``values`` is an open mapping rather than named fields -- because naming the fields
    now would mean inventing the dashboard's data model before seeing it.

    Args:
        page: Page identifier, matching a page in the navigation specification.
        reached: Whether the page was reached at all.
        observed_at: When the observation was taken. Dashboard values are
            time-sensitive: a stale reading cannot support a claim about current state.
        values: Observed values, keyed by the specification's field names.
        timestamps: Timestamps displayed on the page, for freshness correlation.
        visible_features: Features the page showed as available.
        errors: Anything that prevented a complete observation.
    """

    page: str
    reached: bool = False
    observed_at: datetime | None = None
    values: Mapping[str, Any] = field(default_factory=dict)
    timestamps: Mapping[str, datetime] = field(default_factory=dict)
    visible_features: Sequence[str] = field(default_factory=tuple)
    errors: Sequence[str] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-native representation.

        Returns:
            A serialisable mapping.
        """
        return {
            "page": self.page,
            "reached": self.reached,
            "observed_at": self.observed_at.isoformat() if self.observed_at else None,
            "values": dict(self.values),
            "timestamps": {
                key: value.isoformat() for key, value in self.timestamps.items()
            },
            "visible_features": list(self.visible_features),
            "errors": list(self.errors),
        }


class DashboardSnapshotCollector(Collector):
    """Contract for a Layer 4 collector.

    An implementation must:

    * be **read-only** -- navigate and read, never create, modify, or delete
      organisation data. The framework observes the product; a collector that
      changed dashboard state would invalidate every other layer's evidence;
    * **never enter credentials itself.** Authentication is out of bounds for
      automated components; a session must be supplied to it;
    * report a page it could not reach as ``reached=False`` with the reason, never
      as an empty-but-successful observation.
    """

    @property
    def layer(self) -> EvidenceLayer:
        """The evidence layer this collector serves."""
        return EvidenceLayer.DASHBOARD

    @property
    def evidence_ids(self) -> Sequence[str]:
        """Evidence Catalog identifiers a dashboard collector may produce."""
        return (EV_DASHBOARD_UI, EV_DASHBOARD_SETTINGS)

    @property
    @abstractmethod
    def pages(self) -> Sequence[str]:
        """Page identifiers this collector can observe.

        Declared so a feature plugin can check, before running, whether the pages its
        profile depends on are reachable at all.
        """

    @abstractmethod
    def observe(self, page: str, context: ValidationContext) -> DashboardObservation:
        """Observe one dashboard page.

        Args:
            page: Page identifier from :attr:`pages`.
            context: Run context.

        Returns:
            The observation. A page that could not be reached is reported with
            ``reached=False``, not raised.
        """


class UnavailableDashboardCollector(DashboardSnapshotCollector):
    """The Layer 4 collector that exists today: one that reports its own absence.

    This is not a stub for convenience. Without it, a feature plugin needing Layer 4
    would have to special-case a missing collector, and the report would show a silent
    gap where a dashboard verdict should be. With it, the absence is *evidence*: the
    run records that Layer 4 was requested, unavailable, and why -- so an
    ``INCONCLUSIVE`` dashboard verdict is traceable rather than mysterious.

    Replace it with a real collector; nothing else needs to change.
    """

    def __init__(self, *, reason: str = "") -> None:
        """Initialise the collector.

        Args:
            reason: Why Layer 4 is unavailable. A default is supplied because the
                reason is the same in every case today.
        """
        self._reason = reason or (
            "no dashboard collector is implemented; browser automation is out of scope "
            "for the current phase"
        )

    @property
    def name(self) -> str:
        """Component name."""
        return "dashboard.unavailable"

    @property
    def pages(self) -> Sequence[str]:
        """No page can be observed."""
        return ()

    def observe(self, page: str, context: ValidationContext) -> DashboardObservation:
        """Report that the page cannot be observed.

        Args:
            page: Requested page identifier.
            context: Run context.

        Returns:
            An observation with ``reached=False`` and the reason recorded.
        """
        return DashboardObservation(page=page, reached=False, errors=(self._reason,))

    def collect(self, context: ValidationContext) -> Sequence[Evidence]:
        """Emit evidence that Layer 4 was unavailable.

        Args:
            context: Run context.

        Returns:
            A single evidence record. Emitting evidence of absence is what keeps the
            gap visible in the report instead of merely missing.
        """
        return (
            Evidence(
                evidence_id=EV_DASHBOARD_UI,
                layer=EvidenceLayer.DASHBOARD,
                source="dashboard:unavailable",
                summary="dashboard state was not observed",
                collector=self.name,
                data={"state": "unavailable", "reason": self._reason, "pages": []},
            ),
        )


class DashboardValidator(Validator):
    """Concludes about Layer 4 state.

    Concrete today only in the negative case: with no dashboard evidence it reports
    ``INCONCLUSIVE`` and says why. A future implementation extends it with real
    assertions; the reporting contract does not change.
    """

    def __init__(self, *, subject: str = "dashboard state") -> None:
        """Initialise the validator.

        Args:
            subject: What is being validated, for the finding text.
        """
        self._subject = subject

    @property
    def name(self) -> str:
        """Component name."""
        return "dashboard.validator"

    def validate(self, context: ValidationContext) -> Sequence[Finding]:
        """Evaluate Layer 4 evidence.

        Args:
            context: Run context.

        Returns:
            An ``INCONCLUSIVE`` finding whenever the dashboard was not observed. It is
            reported rather than omitted so that a run's inability to see Layer 4
            appears in the report as an open question, which is what it is.
        """
        dashboard = [
            item for item in context.evidence if item.layer is EvidenceLayer.DASHBOARD
        ]
        if not dashboard:
            return ()

        unavailable = [
            item for item in dashboard if item.data.get("state") == "unavailable"
        ]
        if unavailable:
            return (
                Finding.build(
                    what=f"{self._subject} could not be verified",
                    where_layer=EvidenceLayer.DASHBOARD,
                    where_component="dashboard",
                    why=str(unavailable[0].data.get("reason") or Finding.UNDETERMINED),
                    evidence=tuple(unavailable),
                    verdict=Verdict.INCONCLUSIVE,
                    minimum_layers=context.minimum_layers,
                    plugin_id=context.plugin_id,
                    notes=(
                        "Layer 4 is unobserved, so no end-to-end claim can be made: a "
                        "synchronization defect and a surfacing defect remain "
                        "indistinguishable until the dashboard is observed.",
                    ),
                ),
            )

        unreached = [item for item in dashboard if item.data.get("reached") is False]
        if unreached:
            return (
                Finding.build(
                    what=f"{len(unreached)} dashboard page(s) could not be reached",
                    where_layer=EvidenceLayer.DASHBOARD,
                    where_component="dashboard",
                    why="; ".join(
                        str(item.data.get("errors") or ["no reason recorded"])[:120]
                        for item in unreached[:3]
                    ),
                    evidence=tuple(unreached),
                    verdict=Verdict.INCONCLUSIVE,
                    minimum_layers=context.minimum_layers,
                    plugin_id=context.plugin_id,
                ),
            )
        return ()
