"""EM000 -- Environment & Agent Validator plugin.

Runs the local Windows environment pre-check through the framework's evidence
pipeline and reports whether the machine is prepared for EmpMonitor regression
testing.

The plugin is deliberately thin. It **composes** framework collectors and validators
and does not implement collection or verdict logic itself:

* collectors gather Layer 1 configuration and Layer 2 runtime evidence;
* validators turn that evidence into findings, pairing intent with reality;
* the validation engine assigns verdicts and computes confidence.

Nothing here bypasses the engine, and no observation becomes a conclusion without
passing through it (``docs/ADS/validation_standard.md``).

Scope boundaries from the sprint brief, all honoured: no dashboard automation, no
screenshot or recording validation, no report validation, and no EmpMonitor business
API calls. The plugin reads local state only.
"""

from __future__ import annotations

from typing import Any, Sequence

from framework.core.evidence import EvidenceStore
from framework.core.pipeline import EvidencePipeline
from framework.core.validation import ValidationEngine
from framework.monitors.executable_monitor import ExecutableCollector
from framework.monitors.folder_monitor import FilesystemCollector
from framework.monitors.runtime_monitor import ProcessCollector, ServiceCollector
from framework.monitors.sqlite_monitor import SqliteCollector
from framework.shared.config import ConfigurationManager
from framework.shared.interfaces import Plugin
from framework.shared.logger import get_logger
from framework.shared.models import (
    EvidenceLayer,
    ExecutionResult,
    ExecutionStatus,
    Finding,
    PluginMetadata,
    ValidationContext,
    Verdict,
    utc_now,
)
from framework.shared.profile import ProductProfile
from framework.validators.configuration import ConfigurationCollector, ConfigurationValidator
from framework.validators.environment import EnvironmentCollector, EnvironmentValidator
from framework.validators.runtime import RuntimeValidator
from plugins.EM000_EnvironmentValidator.summary import build_summary

__all__ = ["PLUGIN_ID", "EnvironmentValidatorPlugin"]

_LOGGER = get_logger(__name__)

PLUGIN_ID = "EM000_EnvironmentValidator"


class EnvironmentValidatorPlugin(Plugin):
    """Validates that the local Windows environment can host a regression run."""

    def __init__(
        self,
        *,
        profile: ProductProfile | None = None,
        evidence_store: EvidenceStore | None = None,
    ) -> None:
        """Initialise the plugin.

        Args:
            profile: Product profile. Loaded from configuration when omitted, so the
                plugin works under discovery (which constructs it with no arguments)
                while remaining injectable for testing.
            evidence_store: Store used to record evidence and apply catalog
                reliability. Injectable for the same reason.
        """
        self._profile = profile if profile is not None else self._load_profile()
        self._store = evidence_store
        self._summary: dict[str, Any] = {}

    @staticmethod
    def _load_profile() -> ProductProfile:
        """Load the product profile from configuration.

        Returns:
            The profile, empty when no ``empmonitor`` section is configured -- an
            empty profile makes :meth:`precheck` block rather than guessing.
        """
        try:
            configuration = ConfigurationManager.instance().load()
        except Exception as exc:  # noqa: BLE001 -- reported by precheck, not raised here
            _LOGGER.error("Product profile could not be loaded: %s", exc)
            return ProductProfile({})
        section = configuration.get("empmonitor", {})
        return ProductProfile(section if isinstance(section, dict) else {})

    @property
    def metadata(self) -> PluginMetadata:
        """Declarative plugin metadata.

        Declares Layer 1 and Layer 2 because the pre-check corroborates configured
        intent against runtime reality. It declares no dependencies: it is the root
        of the dependency graph, and every other plugin depends on it.
        """
        return PluginMetadata(
            plugin_id=PLUGIN_ID,
            name="Environment & Agent Validator",
            version="1.0.0",
            description=(
                "Validates the local Windows environment, EmpMonitor installation, "
                "services, processes, configuration, and storage before a regression run."
            ),
            evidence_layers=(EvidenceLayer.CONFIGURATION, EvidenceLayer.RUNTIME),
            depends_on=(),
            feature_spec_ref="HB-006 (environment pre-check)",
            timeout_seconds=300.0,
            max_attempts=1,
        )

    @property
    def summary(self) -> dict[str, Any]:
        """The report summary produced by the most recent execution."""
        return dict(self._summary)

    def precheck(self, context: ValidationContext) -> Sequence[Finding]:
        """Confirm the plugin has what it needs to validate anything.

        A missing product profile is a framework-configuration problem, not a product
        defect: without configured locations the plugin cannot know where to look, and
        reporting "nothing found" would be a false accusation against the product.

        Args:
            context: Run context.

        Returns:
            A ``BLOCKED`` finding when the profile is unusable, otherwise none.
        """
        if self._profile.is_configured:
            return ()
        from framework.shared.models import Evidence, SourceReliability  # noqa: PLC0415

        evidence = Evidence(
            evidence_id="EV-012",
            layer=EvidenceLayer.RUNTIME,
            source="operating system",
            summary="product profile is not configured",
            collector=PLUGIN_ID,
            reliability=SourceReliability.HIGH,
            data={"state": "unconfigured"},
        )
        return (
            Finding.build(
                what="EmpMonitor product profile is not configured",
                where_layer=EvidenceLayer.RUNTIME,
                where_component="framework configuration",
                why=(
                    "config/framework.json has no 'empmonitor.install_roots', so no "
                    "product location is known"
                ),
                evidence=[evidence],
                verdict=Verdict.BLOCKED,
                minimum_layers=context.minimum_layers,
                plugin_id=PLUGIN_ID,
                notes=(
                    "Blocked, not failed: this is a framework configuration gap, and no "
                    "claim about EmpMonitor may be made from it.",
                ),
            ),
        )

    def _build_pipeline(self, context: ValidationContext) -> EvidencePipeline:
        """Compose the evidence pipeline for the pre-check.

        Collector order places configuration (Layer 1) first so that when validators
        run, Layer 1 intent is already available to corroborate Layer 2 observations.

        Args:
            context: Run context, supplying the corroboration minimum.

        Returns:
            The composed pipeline.
        """
        engine = ValidationEngine(minimum_layers=context.minimum_layers)
        pipeline = EvidencePipeline(engine=engine)
        pipeline.add_collector(ConfigurationCollector(self._profile))
        pipeline.add_collector(EnvironmentCollector(self._profile))
        pipeline.add_collector(FilesystemCollector(self._profile))
        pipeline.add_collector(ExecutableCollector(self._profile))
        pipeline.add_collector(ServiceCollector(self._profile))
        pipeline.add_collector(ProcessCollector(self._profile))
        pipeline.add_collector(SqliteCollector(self._profile))
        pipeline.add_validator(ConfigurationValidator(self._profile))
        pipeline.add_validator(EnvironmentValidator(self._profile))
        pipeline.add_validator(RuntimeValidator(self._profile))
        return pipeline

    def execute(self, context: ValidationContext) -> ExecutionResult:
        """Run the environment pre-check.

        Args:
            context: Run context.

        Returns:
            The execution result carrying every finding and the report summary. The
            result's verdict is derived by the framework from those findings; the
            plugin never asserts one.
        """
        started = utc_now()
        pipeline = self._build_pipeline(context)
        result = pipeline.run(context)

        # Record evidence in the run's store so it reaches the report and so catalog
        # reliability is applied. Reliability is a property of the source, not of the
        # collector's opinion, so it must come from the catalog.
        recorded = result.evidence
        if self._store is not None:
            try:
                recorded = self._store.extend(result.evidence)
            except Exception as exc:  # noqa: BLE001 -- evidence must still be reported
                _LOGGER.error("Evidence could not be recorded in the store: %s", exc)

        findings = tuple(result.findings)
        verdict = pipeline.engine.aggregate(findings)
        confidence = pipeline.engine.aggregate_confidence(findings)
        self._summary = build_summary(
            recorded, findings, verdict=verdict, confidence=confidence
        )

        for error in result.errors:
            _LOGGER.error(
                "Pre-check stage error in %s (%s): %s",
                error.stage,
                error.component,
                error.message,
            )

        _LOGGER.info(
            "Environment pre-check: %s (%s) -- %d evidence, %d finding(s) across %s",
            verdict.value,
            confidence.name,
            len(recorded),
            len(findings),
            ", ".join(layer.label for layer in result.layers_covered) or "no layers",
        )
        return ExecutionResult(
            unit_id=PLUGIN_ID,
            status=ExecutionStatus.COMPLETED,
            findings=findings,
            started_at=started,
            finished_at=utc_now(),
            metadata={
                "summary": self._summary,
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

    def postcheck(
        self, context: ValidationContext, result: ExecutionResult
    ) -> Sequence[Finding]:
        """Confirm the pre-check produced usable evidence.

        A pre-check that concluded nothing is itself a problem: the rest of the run
        would proceed on an unverified environment. Reporting that explicitly is
        better than letting an empty result read as success.

        Args:
            context: Run context.
            result: The execution result.

        Returns:
            An ``INCONCLUSIVE`` finding when no evidence was gathered, otherwise none.
        """
        if result.findings:
            return ()
        pipeline_detail = result.metadata.get("pipeline") or {}
        if int(pipeline_detail.get("evidence_count") or 0) > 0:
            # Evidence was gathered and nothing was wrong with it: silence here is a
            # legitimate outcome, reported through the summary rather than a finding.
            return ()
        from framework.shared.models import Evidence, SourceReliability  # noqa: PLC0415

        evidence = Evidence(
            evidence_id="EV-012",
            layer=EvidenceLayer.RUNTIME,
            source="operating system",
            summary="pre-check gathered no evidence",
            collector=PLUGIN_ID,
            reliability=SourceReliability.HIGH,
            data={"state": "no evidence"},
        )
        return (
            Finding.build(
                what="environment pre-check gathered no evidence",
                where_layer=EvidenceLayer.RUNTIME,
                where_component="environment pre-check",
                why=Finding.UNDETERMINED,
                evidence=[evidence],
                verdict=Verdict.INCONCLUSIVE,
                minimum_layers=context.minimum_layers,
                plugin_id=PLUGIN_ID,
                notes=(
                    "Every collector returned nothing. Treat the environment as "
                    "unverified rather than healthy.",
                ),
            ),
        )
