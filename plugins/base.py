"""Feature validation base plugin.

Every feature plugin inherits from :class:`FeatureValidationPlugin`. It supplies the
machinery each one would otherwise reimplement -- profile loading, pipeline
composition, correlation, summary building, promotion records -- so a feature plugin
contains only what is genuinely specific to its feature.

**Why this lives in ``plugins/`` and not ``framework/``.** It composes ``core``,
``monitors``, and ``validators`` together. The dependency rules
(``docs/ADS/architecture.md`` §3) permit exactly that combination for *plugins*, while
a framework module doing it would create a new tier and be architecture drift. Placing
it here keeps the frozen dependency direction intact.

**It is abstract, so discovery never registers it.**
:meth:`framework.core.registry.PluginRegistry.discover` skips abstract classes, so this
base and any unfinished template are inert in a real run. That matters: a template that
executed would report on a feature nobody had implemented.

A subclass supplies its feature id and the collectors it needs; it inherits the
lifecycle, and it does not decide verdicts -- the validation engine does.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any, Mapping, Sequence

from framework.core.correlation import Correlation, FeatureCorrelationEngine
from framework.core.evidence import EvidenceStore
from framework.core.pipeline import EvidencePipeline
from framework.core.validation import ValidationEngine
from framework.monitors.executable_monitor import ExecutableCollector
from framework.monitors.runtime_monitor import ProcessCollector, ServiceCollector
from framework.monitors.sqlite_monitor import SqliteCollector
from framework.monitors.sync_monitor import SyncLogCollector, SyncQueueCollector
from framework.shared.config import ConfigurationManager
from framework.shared.features import FeatureProfile, FeatureProfileRegistry
from framework.shared.interfaces import Collector, Plugin, Validator
from framework.shared.logger import get_logger
from framework.shared.models import (
    Evidence,
    EvidenceLayer,
    ExecutionResult,
    ExecutionStatus,
    Finding,
    PluginMetadata,
    SourceReliability,
    ValidationContext,
    Verdict,
    utc_now,
)
from framework.shared.profile import ProductProfile
from framework.validators.configuration import ConfigurationCollector
from framework.validators.dashboard import (
    DashboardValidator,
    UnavailableDashboardCollector,
)
from framework.validators.evidence import EvidenceSufficiencyValidator
from framework.validators.generic import CorrelationValidator

__all__ = ["FeatureValidationPlugin", "ENVIRONMENT_PLUGIN"]

_LOGGER = get_logger(__name__)

#: Every feature plugin depends on the environment pre-check: validating a feature on
#: a machine whose agent is not installed and running is meaningless.
ENVIRONMENT_PLUGIN = "EM000_EnvironmentValidator"


class FeatureValidationPlugin(Plugin):
    """Base class for every EmpMonitor feature validation plugin.

    Subclasses must provide :attr:`feature_id`. Everything else has a working default
    driven by the feature's profile, and any of it can be overridden.
    """

    #: Set by a subclass. Must match a profile in ``config/features.json``.
    feature_id: str = ""

    def __init__(
        self,
        *,
        product_profile: ProductProfile | None = None,
        feature_registry: FeatureProfileRegistry | None = None,
        evidence_store: EvidenceStore | None = None,
    ) -> None:
        """Initialise the plugin.

        Args:
            product_profile: Where product artifacts live. Loaded from configuration
                when omitted, so discovery can construct the plugin with no arguments.
            feature_registry: Feature profiles. Loaded from disk when omitted.
            evidence_store: Store used to record evidence and apply catalog
                reliability.
        """
        self._product_profile = (
            product_profile if product_profile is not None else self._load_product_profile()
        )
        self._registry = feature_registry or FeatureProfileRegistry.load()
        self._store = evidence_store
        self._correlator = FeatureCorrelationEngine()
        self._correlations: tuple[Correlation, ...] = ()
        self._summary: dict[str, Any] = {}

    # -- configuration ---------------------------------------------------------

    @staticmethod
    def _load_product_profile() -> ProductProfile:
        """Load the product profile from configuration.

        Returns:
            The profile, empty when unconfigured -- which makes :meth:`precheck` block
            rather than guess at locations.
        """
        try:
            configuration = ConfigurationManager.instance().load()
        except Exception as exc:  # noqa: BLE001 -- reported by precheck, not raised
            _LOGGER.error("Product profile could not be loaded: %s", exc)
            return ProductProfile({})
        section = configuration.get("empmonitor", {})
        return ProductProfile(section if isinstance(section, dict) else {})

    @property
    def product_profile(self) -> ProductProfile:
        """Where the product's artifacts live."""
        return self._product_profile

    @property
    def profile(self) -> FeatureProfile:
        """This feature's profile.

        Returns:
            The profile.

        Raises:
            ConfigurationError: If no profile is registered for :attr:`feature_id`.
        """
        return self._registry.get(self.feature_id)

    @property
    def correlations(self) -> tuple[Correlation, ...]:
        """Correlations produced by the most recent execution."""
        return self._correlations

    @property
    def summary(self) -> dict[str, Any]:
        """Report summary from the most recent execution."""
        return dict(self._summary)

    # -- metadata --------------------------------------------------------------

    @property
    def metadata(self) -> PluginMetadata:
        """Declarative metadata, derived from the feature profile.

        Deriving rather than restating means a plugin's declared layers can never
        contradict what its profile says it observes.

        Returns:
            The metadata.
        """
        profile = self.profile
        return PluginMetadata(
            plugin_id=self.feature_id,
            name=profile.name,
            version="0.1.0",
            description=f"Validates the EmpMonitor {profile.name} feature.",
            evidence_layers=profile.observable_layers,
            depends_on=(ENVIRONMENT_PLUGIN,),
            feature_spec_ref=f"HB-006 ({profile.name})",
            timeout_seconds=300.0,
            max_attempts=1,
        )

    # -- lifecycle -------------------------------------------------------------

    def precheck(self, context: ValidationContext) -> Sequence[Finding]:
        """Confirm the plugin can observe anything before it tries.

        Args:
            context: Run context.

        Returns:
            A ``BLOCKED`` finding when the product profile is unconfigured or the
            feature has no profile. Both are framework configuration gaps, not product
            defects, so nothing may be concluded about EmpMonitor from them.
        """
        if not self._product_profile.is_configured:
            return (
                self._blocked(
                    context, "the EmpMonitor product profile is not configured"
                ),
            )
        if self.feature_id not in self._registry:
            return (
                self._blocked(
                    context,
                    f"no feature profile is registered for {self.feature_id!r} in "
                    f"{self._registry.source}",
                ),
            )
        return ()

    def _blocked(self, context: ValidationContext, why: str) -> Finding:
        """Build a ``BLOCKED`` precondition finding.

        Args:
            context: Run context.
            why: Why the plugin cannot proceed.

        Returns:
            The finding.
        """
        evidence = Evidence(
            evidence_id="EV-012",
            layer=EvidenceLayer.RUNTIME,
            source="operating system",
            summary="feature validation is not configured",
            collector=self.feature_id or type(self).__name__,
            reliability=SourceReliability.HIGH,
            data={"state": "unconfigured"},
        )
        return Finding.build(
            what=f"{self.feature_id or type(self).__name__} cannot validate its feature",
            where_layer=EvidenceLayer.RUNTIME,
            where_component="framework configuration",
            why=why,
            evidence=[evidence],
            verdict=Verdict.BLOCKED,
            minimum_layers=context.minimum_layers,
            plugin_id=self.feature_id or None,
            notes=(
                "Blocked, not failed: a framework configuration gap supports no claim "
                "about the product.",
            ),
        )

    # -- extension points ------------------------------------------------------

    def collectors(self) -> Sequence[Collector]:
        """Collectors this feature needs.

        The default set is derived from the profile and **reuses** the framework's
        existing collectors rather than adding feature-specific ones. Override to add a
        collector; there is no need to override merely to select from these.

        Returns:
            The collectors to run, in an order that puts Layer 1 before Layer 2 before
            Layer 3, so validators see configured intent before observed behaviour.
        """
        profile = self.profile
        selected: list[Collector] = [ConfigurationCollector(self._product_profile)]
        if profile.expected_runtime_components:
            selected.append(ProcessCollector(self._product_profile))
            selected.append(ServiceCollector(self._product_profile))
            selected.append(ExecutableCollector(self._product_profile))
        if profile.expected_sqlite_tables:
            selected.append(SqliteCollector(self._product_profile))
            selected.append(SyncQueueCollector(self._product_profile))
        if profile.expected_log_patterns or profile.expected_apis:
            selected.append(SyncLogCollector(self._product_profile))
        if profile.expected_dashboard_pages:
            # Records that Layer 4 was required and unavailable, so the gap appears in
            # the report as an open question rather than as silence.
            selected.append(UnavailableDashboardCollector())
        return tuple(selected)

    def validators(self) -> Sequence[Validator]:
        """Validators this feature needs.

        The default set is generic and profile-driven. A subclass adds feature-specific
        validators; it should not need to replace these.

        Returns:
            The validators to run.
        """
        profile = self.profile
        selected: list[Validator] = [
            EvidenceSufficiencyValidator(
                required_layers=profile.observable_layers,
                required_evidence_ids=profile.expected_evidence,
                subject=f"{profile.name} validation",
            )
        ]
        if profile.expected_dashboard_pages:
            selected.append(DashboardValidator(subject=f"{profile.name} on the dashboard"))
        return tuple(selected)

    def correlate(
        self, context: ValidationContext, evidence: Sequence[Evidence]
    ) -> Sequence[Correlation]:
        """Relate this feature's observations across layers.

        The default asks the two questions every feature shares: does configuration
        explain what the runtime is doing, and does the dashboard agree with it. A
        subclass adds feature-specific correlations.

        Args:
            context: Run context.
            evidence: Evidence collected.

        Returns:
            The correlations. Layer 4 questions return ``INDETERMINATE`` until a
            dashboard collector exists, which is the honest answer rather than an
            omission.
        """
        profile = self.profile
        correlations: list[Correlation] = []

        tables = self._observed_tables(evidence)
        if profile.expected_sqlite_tables:
            missing = [
                table for table in profile.expected_sqlite_tables if table not in tables
            ]
            correlations.append(
                self._correlator.runtime_matches_configuration(
                    evidence,
                    expectation=f"{profile.name} storage tables",
                    configured=len(profile.expected_sqlite_tables),
                    observed=len(profile.expected_sqlite_tables) - len(missing),
                )
            )
        if profile.expected_dashboard_pages:
            correlations.append(
                self._correlator.dashboard_matches_runtime(
                    evidence, subject=profile.name
                )
            )
        return tuple(correlations)

    @staticmethod
    def _observed_tables(evidence: Sequence[Evidence]) -> set[str]:
        """Collect the database table names observed in this run.

        Args:
            evidence: Evidence collected.

        Returns:
            The observed table names.
        """
        tables: set[str] = set()
        for item in evidence:
            for key in ("tables", "discovered_pending_tables"):
                value = item.data.get(key)
                if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
                    tables.update(str(entry) for entry in value)
        return tables

    # -- execution -------------------------------------------------------------

    def execute(self, context: ValidationContext) -> ExecutionResult:
        """Validate the feature.

        Composes the pipeline, correlates across layers, turns correlations into
        findings, and assembles the summary. A subclass usually overrides
        :meth:`collectors`, :meth:`validators`, or :meth:`correlate` rather than this.

        Args:
            context: Run context.

        Returns:
            The execution result. Its verdict is derived by the framework from the
            findings; the plugin never asserts one.
        """
        started = utc_now()
        profile = self.profile
        engine = ValidationEngine(minimum_layers=context.minimum_layers)
        pipeline = EvidencePipeline(engine=engine)
        for collector in self.collectors():
            pipeline.add_collector(collector)
        for validator in self.validators():
            pipeline.add_validator(validator)
        result = pipeline.run(context)

        recorded = result.evidence
        if self._store is not None:
            try:
                recorded = self._store.extend(result.evidence)
            except Exception as exc:  # noqa: BLE001 -- evidence must still be reported
                _LOGGER.error("Evidence could not be recorded in the store: %s", exc)

        self._correlations = tuple(self.correlate(context, recorded))
        findings = list(result.findings)
        if self._correlations:
            findings.extend(
                CorrelationValidator(
                    subject=profile.name,
                    correlations=self._correlations,
                    component=f"feature:{self.feature_id}",
                ).validate(context)
            )

        merged = tuple(engine.merge_duplicates(findings))
        verdict = engine.aggregate(merged)
        confidence = engine.aggregate_confidence(merged)
        self._summary = self.build_summary(
            recorded, merged, verdict=verdict, confidence=confidence
        )

        for error in result.errors:
            _LOGGER.error(
                "Feature stage error in %s (%s): %s",
                error.stage,
                error.component,
                error.message,
            )
        _LOGGER.info(
            "%s: %s (%s) -- %d evidence, %d finding(s), %d correlation(s) across %s",
            self.feature_id,
            verdict.value,
            confidence.name,
            len(recorded),
            len(merged),
            len(self._correlations),
            ", ".join(layer.label for layer in result.layers_covered) or "no layers",
        )
        return ExecutionResult(
            unit_id=self.feature_id,
            status=ExecutionStatus.COMPLETED,
            findings=merged,
            started_at=started,
            finished_at=utc_now(),
            metadata={
                "summary": self._summary,
                "correlations": [item.to_dict() for item in self._correlations],
                "feature_profile": profile.to_dict(),
                "pipeline": result.to_dict(),
                "stage_errors": [
                    {
                        "stage": error.stage,
                        "component": error.component,
                        "message": error.message,
                    }
                    for error in result.errors
                ],
            },
        )

    # -- reporting -------------------------------------------------------------

    def build_summary(
        self,
        evidence: Sequence[Evidence],
        findings: Sequence[Finding],
        *,
        verdict: Verdict,
        confidence: Verdict | Any,
    ) -> dict[str, Any]:
        """Build the feature's report summary.

        Args:
            evidence: Evidence collected.
            findings: Findings produced.
            verdict: Aggregate verdict.
            confidence: Aggregate confidence.

        Returns:
            A serialisable summary. It reports the feature's *verification status*
            alongside its verdict, because a `FAILED` verdict on a `Hypothesis` feature
            means something very different from one on a `Verified` feature.
        """
        profile = self.profile
        unobservable = [
            layer.label
            for layer in profile.required_layers
            if layer not in profile.observable_layers
        ]
        return {
            "feature_id": self.feature_id,
            "feature": profile.name,
            "verification_status": profile.verification_status,
            "overall_verdict": verdict.value,
            "confidence": getattr(confidence, "name", str(confidence)),
            "absence_means": profile.absence_verdict.value,
            "layers_required": [layer.label for layer in profile.required_layers],
            "layers_observable": [layer.label for layer in profile.observable_layers],
            "layers_not_observable": unobservable,
            "correlations": self._correlator.summarise(self._correlations),
            "findings": [
                {
                    "what": finding.what,
                    "why": finding.why,
                    "verdict": finding.verdict.value,
                    "confidence": finding.confidence.name,
                    "layers": [layer.label for layer in finding.corroboration],
                    "evidence": [item.evidence_id for item in finding.evidence],
                    "notes": list(finding.notes),
                }
                for finding in findings
            ],
            "expected_failure_modes": list(profile.expected_failure_modes),
            "profile_note": profile.note,
            "counts": {
                "evidence": len(evidence),
                "findings": len(findings),
                "correlations": len(self._correlations),
                "layers_covered": sorted({item.layer.label for item in evidence}),
            },
        }

    @abstractmethod
    def feature_summary(self) -> Mapping[str, Any]:
        """Return whatever is specific to this feature.

        The one member a subclass **must** implement. It exists so that
        :class:`FeatureValidationPlugin` and every unfinished template remain abstract
        and are therefore skipped by plugin discovery -- an incomplete feature plugin
        can never run in a real regression by accident.

        Returns:
            Feature-specific detail for the report.
        """
