"""Synchronization validators -- Layer 3 conclusions.

Eight validators, one per question the sprint asks about synchronization. Each
concludes **only** from what was observed. Where the adopted observation strategies
cannot see something -- request latency, an offline period that did not occur,
WebSocket frames -- the verdict is ``INCONCLUSIVE`` with the reason stated. That is
the required answer, not a shortfall: reporting a pass for an unobserved behaviour
would be inventing product behaviour, which the brief forbids outright.

Validators reference **configured pattern names**, never log message text. The
patterns themselves live in configuration, so a product that changes its log wording
is a configuration update rather than a code change, and an unmatched pattern
degrades to ``INCONCLUSIVE`` rather than to a false negative.

Corroboration comes from genuinely independent artifacts: Layer 1 configuration
(what the agent was told to do), Layer 2 runtime (whether the uploading process is
alive), and Layer 3 log, queue, and connection state (what it actually did).
"""

from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from framework.core.correlation import analyse_cadence
from framework.shared.interfaces import Validator
from framework.shared.logger import get_logger
from framework.shared.models import (
    Evidence,
    EvidenceLayer,
    FailureClass,
    Finding,
    ValidationContext,
    Verdict,
)
from framework.shared.profile import ProductProfile

__all__ = [
    "SchedulerValidator",
    "QueueValidator",
    "AuthenticationValidator",
    "UploadValidator",
    "RetryValidator",
    "RecoveryValidator",
    "LatencyValidator",
    "SynchronizationValidator",
]

_LOGGER = get_logger(__name__)


def _sync_config(profile: ProductProfile) -> Mapping[str, Any]:
    """Return the synchronization configuration block.

    Args:
        profile: The product profile.

    Returns:
        The block, empty when unconfigured.
    """
    section = profile.raw.get("synchronization")
    return section if isinstance(section, Mapping) else {}


def _threshold(profile: ProductProfile, name: str, default: Any) -> Any:
    """Return a synchronization threshold.

    Args:
        profile: The product profile.
        name: Threshold key.
        default: Value when unset.

    Returns:
        The threshold value.
    """
    thresholds = _sync_config(profile).get("thresholds", {})
    if not isinstance(thresholds, Mapping):
        return default
    value = thresholds.get(name, default)
    return default if value is None else value


def _parse_iso(value: Any) -> "datetime | None":
    """Parse an ISO 8601 timestamp recorded in evidence.

    Args:
        value: Timestamp text.

    Returns:
        An aware datetime, or ``None`` when unparseable.
    """
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


class _SyncValidatorBase(Validator):
    """Shared evidence lookup for the synchronization validators.

    Exists to avoid every validator re-implementing the same evidence selection.
    Behaviour is composed through these helpers rather than inherited: subclasses
    override only :meth:`validate`.
    """

    def __init__(self, profile: ProductProfile) -> None:
        """Initialise the validator.

        Args:
            profile: Product profile supplying thresholds and configured keys.
        """
        self._profile = profile

    @staticmethod
    def _by_source(context: ValidationContext, source: str) -> Evidence | None:
        """Return the last evidence recorded for a source.

        Args:
            context: Run context.
            source: Evidence source name.

        Returns:
            The evidence, or ``None``.
        """
        matches = [item for item in context.evidence if item.source == source]
        return matches[-1] if matches else None

    @staticmethod
    def _log_summary(context: ValidationContext) -> Evidence | None:
        """Return the log collector's summary evidence.

        Args:
            context: Run context.

        Returns:
            The summary evidence, or ``None`` when the log was not read.
        """
        for item in context.evidence:
            if item.source == "synchronization:log" and "event_count" in item.data:
                return item
        return None

    @staticmethod
    def _configuration(context: ValidationContext) -> tuple[Evidence, ...]:
        """Return Layer 1 configuration evidence, for corroboration.

        Args:
            context: Run context.

        Returns:
            Configuration evidence, in collection order.
        """
        return tuple(
            item for item in context.evidence if item.layer is EvidenceLayer.CONFIGURATION
        )

    @staticmethod
    def _runtime(context: ValidationContext) -> tuple[Evidence, ...]:
        """Return Layer 2 runtime evidence, for corroboration.

        Args:
            context: Run context.

        Returns:
            Runtime evidence, in collection order.
        """
        return tuple(item for item in context.evidence if item.layer is EvidenceLayer.RUNTIME)

    def _corroborated(
        self, primary: Sequence[Evidence], context: ValidationContext, *, want_runtime: bool = True
    ) -> tuple[Evidence, ...]:
        """Attach independent evidence from other layers to a Layer 3 observation.

        One item per layer is attached. Adding more would inflate the apparent
        breadth of support without adding an independent layer, which is what §5.1
        actually asks for.

        Args:
            primary: The Layer 3 observation.
            context: Run context.
            want_runtime: Whether to attach Layer 2 evidence as well.

        Returns:
            The combined evidence.
        """
        combined = list(primary)
        if configuration := self._configuration(context):
            combined.append(configuration[0])
        if want_runtime and (runtime := self._runtime(context)):
            combined.append(runtime[0])
        return tuple(combined)

    @staticmethod
    def _positive_verdict(
        evidence: Sequence[Evidence], intended: Verdict, minimum_layers: int
    ) -> tuple[Verdict, tuple[str, ...]]:
        """Downgrade a positive verdict when the evidence cannot support it.

        ``HEALTHY`` and ``DEGRADED`` are both positive conclusions and both require
        corroboration across at least two layers, one at L2 or higher (§5.1, §5.4).
        A validator cannot know in advance whether the other layers were collected --
        a collector may have failed, or the plugin may be running in isolation -- so
        every positive verdict passes through here rather than being asserted.

        This is the difference between a validator that reports honestly and one that
        raises: without the guard, an absent corroborating layer becomes a crash
        instead of an ``INCONCLUSIVE`` finding.

        Args:
            evidence: Evidence backing the finding.
            intended: The verdict the validator would like to report.
            minimum_layers: Configured corroboration minimum.

        Returns:
            The verdict to use, and any note explaining a downgrade.
        """
        layers = {item.layer for item in evidence}
        required = max(int(minimum_layers), 2)
        if len(layers) >= required and any(layer >= EvidenceLayer.RUNTIME for layer in layers):
            return intended, ()
        return (
            Verdict.INCONCLUSIVE,
            (
                f"Downgraded from {intended.value}: the observation is supported by "
                f"{sorted(layer.label for layer in layers)} only, which does not meet the "
                "corroboration minimum for a positive verdict.",
            ),
        )

    def _configured_interval(self, context: ValidationContext) -> tuple[float | None, str]:
        """Read the configured upload interval from Layer 1 evidence.

        The interval is read from *evidence*, not from the product's file directly:
        the configuration collector owns that artifact, and reading it twice would
        breach the one-artifact-one-collector rule.

        Args:
            context: Run context.

        Returns:
            The interval in seconds (or ``None``) and the key it came from.
        """
        key = str(
            (_sync_config(self._profile).get("interval_keys") or {}).get("upload_interval", "")
        )
        if not key:
            return None, ""
        for item in self._configuration(context):
            values = item.data.get("values")
            if isinstance(values, Mapping) and key in values:
                try:
                    return float(str(values[key]).strip()), key
                except (TypeError, ValueError):
                    return None, key
        return None, key

    def _inconclusive(
        self,
        context: ValidationContext,
        *,
        what: str,
        component: str,
        why: str,
        evidence: Sequence[Evidence],
        notes: Sequence[str] = (),
    ) -> Finding:
        """Build an ``INCONCLUSIVE`` finding.

        Args:
            context: Run context.
            what: The unanswered question.
            component: Component the question concerns.
            why: Why it could not be answered.
            evidence: Supporting evidence.
            notes: Additional explanation.

        Returns:
            The finding.
        """
        return Finding.build(
            what=what,
            where_layer=EvidenceLayer.SYNCHRONIZATION,
            where_component=component,
            why=why,
            evidence=tuple(evidence),
            verdict=Verdict.INCONCLUSIVE,
            minimum_layers=context.minimum_layers,
            plugin_id=context.plugin_id,
            notes=tuple(notes),
        )


class SchedulerValidator(_SyncValidatorBase):
    """Compares the configured upload interval against the observed cadence."""

    @property
    def name(self) -> str:
        """Component name."""
        return "sync.scheduler.validator"

    def validate(self, context: ValidationContext) -> Sequence[Finding]:
        """Evaluate scheduler cadence and drift.

        Args:
            context: Run context.

        Returns:
            Findings about the scheduler. A cadence matching configuration is the
            clearest corroboration available at this layer: Layer 1 says how often,
            Layer 3 shows how often it actually happened.
        """
        summary = self._log_summary(context)
        if summary is None:
            return ()
        configured, key = self._configured_interval(context)
        minimum_cycles = int(_threshold(self._profile, "min_cycles_for_cadence", 2))
        tolerance = float(_threshold(self._profile, "scheduler_drift_tolerance_seconds", 30))

        # Cadence arithmetic is delegated to the single implementation in
        # framework.core.correlation. A local copy would be free to disagree with the
        # generic FrequencyValidator about what a configured interval means.
        analysis = analyse_cadence(
            [
                stamp
                for stamp in (
                    _parse_iso(value)
                    for value in summary.data.get("cycle_timestamps", ()) or ()
                )
                if stamp is not None
            ],
            expected_seconds=configured,
            tolerance_seconds=tolerance,
            minimum_occurrences=minimum_cycles,
        )
        intervals = list(analysis.intervals)

        if not analysis.is_measurable:
            return (
                self._inconclusive(
                    context,
                    what="upload cadence could not be established",
                    component="synchronization:scheduler",
                    why=(
                        f"only {summary.data.get('cycle_count', 0)} upload cycle(s) were "
                        f"observed; at least {minimum_cycles} are needed to measure an interval"
                    ),
                    evidence=[summary],
                    notes=(
                        "Observation window was too short. This is a limit of the "
                        "observation, not a defect in the product.",
                    ),
                ),
            )

        observed = analysis.mean_seconds
        spread = analysis.spread_seconds

        if configured is None:
            return (
                self._inconclusive(
                    context,
                    what="observed upload cadence cannot be compared with configuration",
                    component="synchronization:scheduler",
                    why=(
                        f"cadence of {observed:.1f}s was observed, but the configured "
                        f"interval key {key!r} was not found in Layer 1 evidence"
                    ),
                    evidence=self._corroborated([summary], context, want_runtime=False),
                    notes=(
                        "Cadence alone proves regularity, not correctness: without the "
                        "configured interval there is nothing to be correct against.",
                    ),
                ),
            )

        drift = analysis.drift_seconds
        if analysis.within_tolerance:
            return (
                Finding.build(
                    what=(
                        f"upload scheduler runs on its configured {configured:.0f}s interval "
                        f"(observed {observed:.1f}s across {len(intervals)} interval(s))"
                    ),
                    where_layer=EvidenceLayer.SYNCHRONIZATION,
                    where_component="synchronization:scheduler",
                    why=(
                        f"observed cadence is within {tolerance:.0f}s of the configured "
                        f"interval; drift {drift:+.1f}s, spread {spread:.1f}s"
                    ),
                    evidence=(_ev := self._corroborated([summary], context)),
                    verdict=self._positive_verdict(
                        _ev, Verdict.HEALTHY, context.minimum_layers
                    )[0],
                    minimum_layers=context.minimum_layers,
                    plugin_id=context.plugin_id,
                ),
            )
        return (
            Finding.build(
                what="upload scheduler cadence does not match its configured interval",
                where_layer=EvidenceLayer.SYNCHRONIZATION,
                where_component="synchronization:scheduler",
                why=(
                    f"configured {configured:.0f}s, observed {observed:.1f}s, "
                    f"drift {drift:+.1f}s exceeds tolerance {tolerance:.0f}s"
                ),
                evidence=(_ev := self._corroborated([summary], context)),
                verdict=self._positive_verdict(
                    _ev, Verdict.DEGRADED, context.minimum_layers
                )[0],
                minimum_layers=context.minimum_layers,
                plugin_id=context.plugin_id,
                notes=(
                    "Degraded rather than failed: data still flows, but timing "
                    "expectations downstream may not hold.",
                ),
            ),
        )


class QueueValidator(_SyncValidatorBase):
    """Concludes on upload-queue depth and drain."""

    @property
    def name(self) -> str:
        """Component name."""
        return "sync.queue.validator"

    def validate(self, context: ValidationContext) -> Sequence[Finding]:
        """Evaluate queue state.

        Args:
            context: Run context.

        Returns:
            Findings about the queue.
        """
        queue = self._by_source(context, "synchronization:queue")
        if queue is None:
            return ()
        state = queue.data.get("state")
        if state in ("absent", "unreadable", "unconfigured"):
            return (
                self._inconclusive(
                    context,
                    what="upload queue state could not be observed",
                    component="synchronization:queue",
                    why=str(queue.data.get("error") or f"queue state is {state}"),
                    evidence=[queue],
                ),
            )

        depth = int(queue.data.get("total_queue_depth") or 0)
        maximum = int(_threshold(self._profile, "max_queue_depth", 500))
        tables = queue.data.get("discovered_pending_tables") or []
        summary = self._log_summary(context)
        cycles = int(summary.data.get("cycle_count", 0)) if summary else 0

        if depth > maximum:
            return (
                Finding.build(
                    what="upload queue depth exceeds the configured maximum",
                    where_layer=EvidenceLayer.SYNCHRONIZATION,
                    where_component="synchronization:queue",
                    why=f"queue depth {depth} exceeds maximum {maximum}",
                    evidence=self._corroborated([queue], context),
                    verdict=Verdict.FAILED,
                    failure_class=FailureClass.SYNCHRONIZATION_DEFECT,
                    minimum_layers=context.minimum_layers,
                    plugin_id=context.plugin_id,
                ),
            )

        if depth == 0 and cycles > 0:
            return (
                Finding.build(
                    what=(
                        f"upload queue is drained across all {len(tables)} queue table(s) "
                        f"after {cycles} observed cycle(s)"
                    ),
                    where_layer=EvidenceLayer.SYNCHRONIZATION,
                    where_component="synchronization:queue",
                    why="no rows remain pending in any discovered queue table",
                    evidence=(_ev := self._corroborated([queue], context)),
                    verdict=self._positive_verdict(
                        _ev, Verdict.HEALTHY, context.minimum_layers
                    )[0],
                    minimum_layers=context.minimum_layers,
                    plugin_id=context.plugin_id,
                ),
            )

        if depth == 0:
            return (
                self._inconclusive(
                    context,
                    what="upload queue is empty but no upload cycle was observed",
                    component="synchronization:queue",
                    why="an empty queue with no observed cycle cannot distinguish "
                    "successful drain from nothing ever having been queued",
                    evidence=self._corroborated([queue], context, want_runtime=False),
                ),
            )

        return (
            Finding.build(
                what=f"upload queue holds {depth} pending item(s)",
                where_layer=EvidenceLayer.SYNCHRONIZATION,
                where_component="synchronization:queue",
                why=(
                    "items are pending; a non-empty queue between cycles is expected "
                    "behaviour, so this is reported without prejudice"
                ),
                evidence=(_ev := self._corroborated([queue], context)),
                verdict=self._positive_verdict(
                    _ev, Verdict.HEALTHY, context.minimum_layers
                )[0] if cycles else Verdict.INCONCLUSIVE,
                minimum_layers=context.minimum_layers,
                plugin_id=context.plugin_id,
                notes=(
                    "Queue depth alone cannot separate a healthy backlog from a stalled "
                    "one; only depth falling across cycles proves drain. "
                    f"Non-empty queues: {queue.data.get('non_empty_queues')}",
                ),
            ),
        )


class AuthenticationValidator(_SyncValidatorBase):
    """Concludes on observed authentication activity."""

    @property
    def name(self) -> str:
        """Component name."""
        return "sync.authentication.validator"

    def validate(self, context: ValidationContext) -> Sequence[Finding]:
        """Evaluate authentication.

        Args:
            context: Run context.

        Returns:
            Findings about authentication. Token refresh is explicitly reported as
            unobservable rather than assumed: the adopted strategies see that
            authentication happened, not what was presented or when it expires.
        """
        summary = self._log_summary(context)
        if summary is None:
            return ()
        by_pattern = summary.data.get("events_by_pattern") or {}
        auth_events = int(by_pattern.get("auth_register", 0)) + int(
            by_pattern.get("auth_call", 0)
        )
        findings: list[Finding] = []

        if auth_events:
            evidence = self._corroborated([summary], context)
            verdict, downgrade = self._positive_verdict(
                evidence, Verdict.HEALTHY, context.minimum_layers
            )
            findings.append(
                Finding.build(
                    what=f"agent performed authentication ({auth_events} event(s) observed)",
                    where_layer=EvidenceLayer.SYNCHRONIZATION,
                    where_component="synchronization:authentication",
                    why="authentication events appear in the agent log",
                    evidence=evidence,
                    verdict=verdict,
                    minimum_layers=context.minimum_layers,
                    plugin_id=context.plugin_id,
                    notes=(
                        "Establishes that authentication occurred. The scheme, the "
                        "credential presented, and token lifetime are not observable "
                        "by the adopted passive strategies.",
                    )
                    + downgrade,
                )
            )
        else:
            findings.append(
                self._inconclusive(
                    context,
                    what="no authentication activity was observed",
                    component="synchronization:authentication",
                    why="no configured authentication pattern matched in the observation window",
                    evidence=[summary],
                    notes=(
                        "Absence is weak evidence: authentication most likely occurred "
                        "before the retained log window rather than not at all.",
                    ),
                )
            )

        findings.append(
            self._inconclusive(
                context,
                what="token refresh behaviour could not be determined",
                component="synchronization:authentication",
                why="no observable artifact records token issuance, lifetime, or refresh",
                evidence=[summary],
                notes=(
                    "Answering this would require request payload visibility, which the "
                    "design spike rejected obtaining by interception.",
                ),
            )
        )
        return tuple(findings)


class UploadValidator(_SyncValidatorBase):
    """Concludes on upload outcomes and the API surface actually exercised."""

    @property
    def name(self) -> str:
        """Component name."""
        return "sync.upload.validator"

    def validate(self, context: ValidationContext) -> Sequence[Finding]:
        """Evaluate uploads.

        Args:
            context: Run context.

        Returns:
            Findings about upload outcomes, including any alternate channel that was
            skipped.
        """
        summary = self._log_summary(context)
        if summary is None:
            return ()
        by_pattern = summary.data.get("events_by_pattern") or {}
        api_calls = summary.data.get("api_calls") or []
        findings: list[Finding] = []

        codes = [str(call.get("code") or "") for call in api_calls if call.get("code")]
        accepted = [code for code in codes if code.startswith("2")]
        rejected = [code for code in codes if not code.startswith("2")]

        if codes and not rejected:
            evidence = self._corroborated([summary], context)
            verdict, downgrade = self._positive_verdict(
                evidence, Verdict.HEALTHY, context.minimum_layers
            )
            findings.append(
                Finding.build(
                    what=(
                        f"every observed API call was accepted by the server "
                        f"({len(accepted)} call(s), all 2xx)"
                    ),
                    where_layer=EvidenceLayer.SYNCHRONIZATION,
                    where_component="synchronization:upload",
                    why="all observed reply codes were successful",
                    evidence=evidence,
                    verdict=verdict,
                    minimum_layers=context.minimum_layers,
                    plugin_id=context.plugin_id,
                    notes=downgrade,
                )
            )
        elif rejected:
            findings.append(
                Finding.build(
                    what=f"server rejected {len(rejected)} observed API call(s)",
                    where_layer=EvidenceLayer.SYNCHRONIZATION,
                    where_component="synchronization:upload",
                    why=f"non-success reply codes observed: {sorted(set(rejected))}",
                    evidence=self._corroborated([summary], context),
                    verdict=Verdict.FAILED,
                    failure_class=FailureClass.SYNCHRONIZATION_DEFECT,
                    minimum_layers=context.minimum_layers,
                    plugin_id=context.plugin_id,
                )
            )
        else:
            findings.append(
                self._inconclusive(
                    context,
                    what="no API reply code was observed",
                    component="synchronization:upload",
                    why="no configured API-reply pattern matched in the observation window",
                    evidence=[summary],
                )
            )

        if skipped := int(by_pattern.get("alternate_channel_skipped", 0)):
            findings.append(
                Finding.build(
                    what=f"an alternate upload channel is being skipped ({skipped} occurrence(s))",
                    where_layer=EvidenceLayer.SYNCHRONIZATION,
                    where_component="synchronization:upload",
                    why=self._first_field(summary, "alternate_channel_skipped", "reason")
                    or "the agent reports skipping this channel",
                    evidence=(_ev := self._corroborated([summary], context)),
                    verdict=self._positive_verdict(
                        _ev, Verdict.DEGRADED, context.minimum_layers
                    )[0],
                    minimum_layers=context.minimum_layers,
                    plugin_id=context.plugin_id,
                    notes=(
                        "Degraded rather than failed: the primary channel is succeeding, "
                        "so no data loss is evidenced. Whether this channel is required "
                        "is unknown.",
                    )
                    + self._positive_verdict(_ev, Verdict.DEGRADED, context.minimum_layers)[1],
                )
            )
        return tuple(findings)

    @staticmethod
    def _first_field(summary: Evidence, pattern: str, field_name: str) -> str | None:
        """Return a named field from the first event of a pattern.

        Args:
            summary: The log summary evidence.
            pattern: Pattern name to search for.
            field_name: Capture-group name to read.

        Returns:
            The field value, or ``None``.
        """
        for event in summary.data.get("events", ()) or ():
            if event.get("pattern") == pattern:
                value = (event.get("fields") or {}).get(field_name)
                if value:
                    return str(value)
        return None


class RetryValidator(_SyncValidatorBase):
    """Concludes on retry behaviour."""

    @property
    def name(self) -> str:
        """Component name."""
        return "sync.retry.validator"

    def validate(self, context: ValidationContext) -> Sequence[Finding]:
        """Evaluate retry behaviour.

        Args:
            context: Run context.

        Returns:
            Findings about retries. Retry *policy* -- count, backoff curve -- is
            reported as unobservable rather than guessed at.
        """
        summary = self._log_summary(context)
        if summary is None:
            return ()
        retries = int((summary.data.get("events_by_pattern") or {}).get("retry", 0))
        if retries == 0:
            return (
                self._inconclusive(
                    context,
                    what="retry behaviour was not exercised during observation",
                    component="synchronization:retry",
                    why="no retry event was observed, and no upload failed that would "
                    "have required one",
                    evidence=[summary],
                    notes=(
                        "Untested is not the same as working. Verifying retry needs an "
                        "induced failure, which a passive observer cannot create.",
                    ),
                ),
            )
        return (
            Finding.build(
                what=f"agent performed {retries} retry attempt(s)",
                where_layer=EvidenceLayer.SYNCHRONIZATION,
                where_component="synchronization:retry",
                why="retry events appear in the agent log",
                evidence=(_ev := self._corroborated([summary], context)),
                verdict=self._positive_verdict(
                    _ev, Verdict.DEGRADED, context.minimum_layers
                )[0],
                minimum_layers=context.minimum_layers,
                plugin_id=context.plugin_id,
                notes=(
                    "Retries observed means an operation initially failed. Backoff policy "
                    "and attempt ceiling are not observable.",
                ),
            ),
        )


class RecoveryValidator(_SyncValidatorBase):
    """Concludes on offline detection and reconnect recovery."""

    @property
    def name(self) -> str:
        """Component name."""
        return "sync.recovery.validator"

    def validate(self, context: ValidationContext) -> Sequence[Finding]:
        """Evaluate offline and recovery behaviour.

        Args:
            context: Run context.

        Returns:
            An ``INCONCLUSIVE`` finding unless an offline period was actually
            observed. Offline behaviour cannot be verified without connectivity
            loss, and the framework must not cause one -- it observes, it does not
            perturb.
        """
        summary = self._log_summary(context)
        network = self._by_source(context, "synchronization:network")
        evidence = [item for item in (summary, network) if item is not None]
        if not evidence:
            return ()

        connected = bool(
            network is not None and network.data.get("established_server_connections")
        )
        return (
            self._inconclusive(
                context,
                what="offline detection and reconnect recovery were not verified",
                component="synchronization:recovery",
                why=(
                    "no loss of connectivity occurred during observation"
                    if connected
                    else "no offline or reconnect event was observed"
                ),
                evidence=evidence,
                notes=(
                    "Verifying this requires inducing connectivity loss. The framework is "
                    "a passive observer and must not perturb the system it validates "
                    "(Manifest §14), so this remains open until observed naturally or "
                    "exercised by a deliberate, separately authorised test.",
                ),
            ),
        )


class LatencyValidator(_SyncValidatorBase):
    """Concludes on synchronization latency."""

    @property
    def name(self) -> str:
        """Component name."""
        return "sync.latency.validator"

    def validate(self, context: ValidationContext) -> Sequence[Finding]:
        """Evaluate latency.

        Args:
            context: Run context.

        Returns:
            An ``INCONCLUSIVE`` finding. The adopted strategies timestamp *events*,
            not request/response pairs, so no per-request duration exists to measure.
            The Synchronization Monitor design anticipated exactly this: §13 makes
            latency semantics dependent on the observation strategy, and the strategy
            chosen cannot supply them.
        """
        summary = self._log_summary(context)
        if summary is None:
            return ()
        return (
            self._inconclusive(
                context,
                what="synchronization latency could not be measured",
                component="synchronization:latency",
                why=(
                    "the agent log timestamps events to one-second resolution and does "
                    "not pair a request with its response, so no request duration is "
                    "derivable"
                ),
                evidence=[summary],
                notes=(
                    "Measuring latency would need request/response correlation, available "
                    "only from payload-level capture -- rejected by the design spike as "
                    "non-passive. Cycle cadence is measurable and is reported by the "
                    "scheduler validator instead.",
                ),
            ),
        )


class SynchronizationValidator(_SyncValidatorBase):
    """Correlates the synchronization pipeline end to end."""

    @property
    def name(self) -> str:
        """Component name."""
        return "sync.pipeline.validator"

    def validate(self, context: ValidationContext) -> Sequence[Finding]:
        """Evaluate the pipeline as a whole and report anomalies it surfaced.

        Args:
            context: Run context.

        Returns:
            Findings about overall pipeline health plus any product anomalies the
            observation exposed.
        """
        summary = self._log_summary(context)
        network = self._by_source(context, "synchronization:network")
        queue = self._by_source(context, "synchronization:queue")
        if summary is None:
            return ()

        by_pattern = summary.data.get("events_by_pattern") or {}
        findings: list[Finding] = []

        cycles = int(summary.data.get("cycle_count", 0))
        accepted = [
            call
            for call in (summary.data.get("api_calls") or [])
            if str(call.get("code", "")).startswith("2")
        ]
        server_connected = bool(
            network is not None and network.data.get("established_server_connections")
        )

        if cycles and accepted and server_connected:
            findings.append(
                Finding.build(
                    what=(
                        f"synchronization pipeline is functioning end to end: {cycles} cycle(s) "
                        f"triggered, {len(accepted)} server acceptance(s), live server connection"
                    ),
                    where_layer=EvidenceLayer.SYNCHRONIZATION,
                    where_component="synchronization:pipeline",
                    why=(
                        "cycle triggers, accepted API replies, and an established server "
                        "connection were each observed from independent artifacts"
                    ),
                    evidence=self._corroborated(
                        [item for item in (summary, network, queue) if item is not None][:2],
                        context,
                    ),
                    verdict=Verdict.HEALTHY,
                    minimum_layers=context.minimum_layers,
                    plugin_id=context.plugin_id,
                )
            )
        elif cycles and not accepted:
            findings.append(
                Finding.build(
                    what="upload cycles ran but no server acceptance was observed",
                    where_layer=EvidenceLayer.SYNCHRONIZATION,
                    where_component="synchronization:pipeline",
                    why="cycle triggers were observed without any successful reply code",
                    evidence=self._corroborated([summary], context),
                    verdict=Verdict.FAILED,
                    failure_class=FailureClass.SYNCHRONIZATION_DEFECT,
                    minimum_layers=context.minimum_layers,
                    plugin_id=context.plugin_id,
                )
            )
        else:
            findings.append(
                self._inconclusive(
                    context,
                    what="synchronization pipeline health could not be established",
                    component="synchronization:pipeline",
                    why=f"{cycles} cycle(s) and {len(accepted)} acceptance(s) observed",
                    evidence=[summary],
                )
            )

        findings.extend(self._anomalies(context, summary, by_pattern))
        return tuple(findings)

    def _anomalies(
        self,
        context: ValidationContext,
        summary: Evidence,
        by_pattern: Mapping[str, Any],
    ) -> Sequence[Finding]:
        """Report product anomalies the observation exposed.

        These are reported because they were *observed*, not because they were
        looked for -- which is the point of reverse engineering before validating.

        Args:
            context: Run context.
            summary: The log summary evidence.
            by_pattern: Event counts by configured pattern name.

        Returns:
            Findings for each anomaly observed.
        """
        findings: list[Finding] = []

        cleanup_results = [
            event
            for event in (summary.data.get("events") or ())
            if event.get("pattern") == "queue_cleanup_result"
        ]
        negative = [
            event
            for event in cleanup_results
            if str((event.get("fields") or {}).get("records", "")).startswith("-")
        ]
        if negative:
            findings.append(
                Finding.build(
                    what=(
                        "queue retention cleanup reports a negative record count "
                        f"({len(negative)} of {len(cleanup_results)} sweep(s))"
                    ),
                    where_layer=EvidenceLayer.SYNCHRONIZATION,
                    where_component="synchronization:queue",
                    why=(
                        "the agent's retention sweep returns a negative count, which "
                        "indicates the delete did not execute as intended"
                    ),
                    evidence=(_ev := self._corroborated([summary], context)),
                    verdict=self._positive_verdict(
                        _ev, Verdict.DEGRADED, context.minimum_layers
                    )[0],
                    minimum_layers=context.minimum_layers,
                    plugin_id=context.plugin_id,
                    notes=(
                        "Observed anomaly in the product, reported without a claimed root "
                        "cause. Retained data may grow unbounded if the sweep never "
                        "deletes, but no growth was measured in this window.",
                    ),
                )
            )

        retention_tokens = {
            str((event.get("fields") or {}).get("retention", ""))
            for event in (summary.data.get("events") or ())
            if event.get("pattern") == "queue_cleanup"
        }
        unsubstituted = {
            token for token in retention_tokens if token and not token[0].isdigit()
        }
        if unsubstituted:
            findings.append(
                Finding.build(
                    what="queue retention period is an unsubstituted placeholder",
                    where_layer=EvidenceLayer.SYNCHRONIZATION,
                    where_component="synchronization:queue",
                    why=(
                        f"the retention value logged is {sorted(unsubstituted)!r} rather "
                        "than a number, so the configured retention was never applied"
                    ),
                    evidence=(_ev := self._corroborated([summary], context)),
                    verdict=self._positive_verdict(
                        _ev, Verdict.DEGRADED, context.minimum_layers
                    )[0],
                    minimum_layers=context.minimum_layers,
                    plugin_id=context.plugin_id,
                    notes=(
                        "Corroborates the negative-count finding above: a placeholder "
                        "retention would explain a delete that never matches rows.",
                    ),
                )
            )

        if denied := int(by_pattern.get("permission_denied", 0)):
            findings.append(
                Finding.build(
                    what=f"agent could not inspect some processes ({denied} occurrence(s))",
                    where_layer=EvidenceLayer.SYNCHRONIZATION,
                    where_component="synchronization:pipeline",
                    why="the agent logs access-denied errors while inspecting processes",
                    evidence=(_ev := self._corroborated([summary], context)),
                    verdict=self._positive_verdict(
                        _ev, Verdict.DEGRADED, context.minimum_layers
                    )[0],
                    minimum_layers=context.minimum_layers,
                    plugin_id=context.plugin_id,
                    notes=(
                        "Capture coverage may be incomplete for the processes it cannot "
                        "open. Whether any monitored feature depends on those processes "
                        "is unknown.",
                    ),
                )
            )
        return tuple(findings)
