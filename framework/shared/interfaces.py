"""Abstract base classes every extension point inherits from.

These interfaces live in ``framework.shared`` rather than ``framework.core``
because of the dependency rule in ``docs/ADS/architecture.md`` §3: modules under
``framework/monitors`` and ``framework/validators`` may depend on ``shared`` but
must not depend on ``core``. Putting the contracts in ``shared`` lets every tier
implement them without inverting that dependency.

The separation the interfaces encode is load-bearing and must not be blurred
(``docs/FRAMEWORK_MANIFEST.md`` §4):

* A :class:`Collector` **collects** evidence and never returns a verdict.
* A :class:`Validator` **concludes**, turning evidence into findings.
* A :class:`Monitor` observes over time and must not raise for the conditions it
  exists to observe -- it reports them.

All interfaces are deliberately narrow. Behaviour is composed by injecting
collaborators (logger, configuration, event bus) rather than by deep
inheritance.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Iterable, Mapping, Sequence

from framework.shared.models import (
    Evidence,
    EvidenceLayer,
    ExecutionResult,
    Finding,
    PluginMetadata,
    ValidationContext,
)

__all__ = [
    "Component",
    "Collector",
    "Normalizer",
    "Validator",
    "Correlator",
    "Monitor",
    "Plugin",
    "Reporter",
    "Scheduler",
]


class Component(ABC):
    """Common base for every named, lifecycle-managed framework component.

    Provides identity and an optional setup/teardown pair. Subclasses inherit
    no behaviour beyond this, keeping the hierarchy shallow.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable component name, used in logs and evidence attribution."""

    def setup(self) -> None:
        """Prepare the component. Default is a no-op.

        Override for components that must acquire resources. Must be safe to
        call once per run before any other method.
        """

    def teardown(self) -> None:
        """Release resources. Default is a no-op.

        Must be safe to call even if :meth:`setup` failed, so cleanup paths do
        not need to track partial initialisation.
        """


class Collector(Component):
    """Collects evidence from one source. Never concludes.

    A collector's sole output is :class:`~framework.shared.models.Evidence`. If
    a collector returned a verdict it would be making a judgement without the
    corroboration rules the Validation Standard requires -- hence the split.
    """

    @property
    @abstractmethod
    def layer(self) -> EvidenceLayer:
        """The evidence layer this collector serves."""

    @property
    @abstractmethod
    def evidence_ids(self) -> Sequence[str]:
        """Evidence Catalog identifiers this collector can produce.

        Declared so the framework can report coverage and reject citation of
        unregistered sources (``docs/Evidence_Catalog.md`` §1).
        """

    @abstractmethod
    def collect(self, context: ValidationContext) -> Sequence[Evidence]:
        """Collect evidence.

        Args:
            context: Run context describing what is being validated.

        Returns:
            Evidence collected. An empty sequence is valid and meaningful: it
            says the source yielded nothing, which is weak evidence at most
            (Validation Standard §7 rule 4), not a failure.

        Raises:
            EvidenceError: If the source could not be read at all. Inability to
                collect is distinct from collecting an absence.
        """


class Normalizer(Component):
    """Converts raw collected evidence into a comparable canonical form.

    Sits between collection and validation in the evidence pipeline. It exists so
    that validators compare like with like: two collectors observing the same fact
    (a timestamp, a path, a version string) may render it differently, and a
    validator that had to know every collector's idiosyncrasies would defeat the
    point of having one validation contract.

    A normalizer must be **information-preserving**: it may reshape a value but
    must never discard evidence or invent detail that was not observed.
    """

    @abstractmethod
    def normalize(self, evidence: Sequence[Evidence]) -> Sequence[Evidence]:
        """Return evidence in canonical form.

        Args:
            evidence: Evidence as collected.

        Returns:
            Normalized evidence. Implementations should return input unchanged
            when they have nothing to normalize, rather than filtering it out.

        Raises:
            EvidenceError: If evidence is malformed beyond normalization.
        """


class Validator(Component):
    """Turns evidence into findings by applying the Validation Standard.

    Implementations must not collect their own evidence: they receive it, so
    that one artifact has one collector (independence rule, §4.1).
    """

    @abstractmethod
    def validate(self, context: ValidationContext) -> Sequence[Finding]:
        """Evaluate the context and produce findings.

        Args:
            context: Run context including the evidence to evaluate.

        Returns:
            Findings. Prefer :meth:`Finding.build` so confidence is computed
            rather than asserted (§8.2).

        Raises:
            ValidationError: If validation could not be carried out. A product
                defect is a ``FAILED`` finding, not an exception.
        """


class Correlator(Component):
    """Relates findings and evidence across layers before a verdict is settled.

    The final pipeline stage before a verdict. Correlation is what turns
    per-layer observations into a localised conclusion: it identifies the first
    diverging layer, detects disagreements between sources, and merges findings
    that describe the same defect seen from different layers.

    A correlator is the only component permitted to *change* a finding's verdict,
    and only by applying the ratified §7 conflict rules -- never by preferring a
    more convenient answer.
    """

    @abstractmethod
    def correlate(
        self, findings: Sequence[Finding], context: ValidationContext
    ) -> Sequence[Finding]:
        """Relate findings to one another and return the reconciled set.

        Args:
            findings: Findings produced by validators.
            context: Run context, including all available evidence.

        Returns:
            The reconciled findings. May be fewer than the input (merged) or carry
            recorded conflicts, but must never silently drop a finding.

        Raises:
            ValidationError: If correlation cannot be carried out.
        """


class Monitor(Component):
    """Observes state over a period and reports what it sees.

    Monitors are passive. Per ``docs/ADS/error_handling_standard.md`` §5 a
    monitor must not raise for a condition it exists to observe -- an anomaly is
    something to report, not an error to throw.
    """

    @property
    @abstractmethod
    def layer(self) -> EvidenceLayer:
        """The evidence layer this monitor observes."""

    @abstractmethod
    def start(self, context: ValidationContext) -> None:
        """Begin observing.

        Args:
            context: Run context.
        """

    @abstractmethod
    def sample(self) -> Sequence[Evidence]:
        """Take a point-in-time sample of observed state.

        Returns:
            Evidence for this sample; empty if nothing changed.
        """

    @abstractmethod
    def stop(self) -> Sequence[Evidence]:
        """Stop observing and return any final evidence.

        Returns:
            Evidence accumulated since the last :meth:`sample`.
        """


class Plugin(Component):
    """A feature-area validation module.

    Plugins are the only place feature-specific logic belongs
    (``docs/FRAMEWORK_MANIFEST.md`` §7). Phase 1 defines the contract only; no
    plugin implementations exist yet.
    """

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Declarative plugin metadata, including declared evidence layers."""

    @property
    def name(self) -> str:
        """Plugin name, defaulting to its identifier.

        Implemented here so plugins satisfy :class:`Component` by declaring
        metadata alone.
        """
        return self.metadata.plugin_id

    @abstractmethod
    def execute(self, context: ValidationContext) -> ExecutionResult:
        """Run the plugin's validation.

        Invoked during the ``EXECUTE`` stage. The only method a plugin must
        implement; every hook below is optional with a safe default, so a minimal
        plugin stays minimal.

        Args:
            context: Run context.

        Returns:
            The execution result, carrying findings and completion status.

        Raises:
            PluginError: For failures specific to this plugin. The engine isolates
                these so one plugin cannot fail the whole run.
        """

    def should_execute(self, context: ValidationContext) -> bool:
        """Whether this plugin applies to the current run.

        Invoked before ``PRECHECK``. Returning ``False`` moves the plugin to the
        ``SKIPPED`` stage. Skipping is recorded and reported -- it is never
        silently equivalent to success.

        Args:
            context: Run context.

        Returns:
            ``True`` by default.
        """
        return True

    def precheck(self, context: ValidationContext) -> Sequence[Finding]:
        """Check preconditions before executing.

        Invoked during the ``PRECHECK`` stage. Returning any ``BLOCKED`` finding
        prevents execution, since running a validation whose preconditions are
        unmet would produce misleading results.

        Args:
            context: Run context.

        Returns:
            Findings; empty by default.
        """
        return ()

    def validate(
        self, context: ValidationContext, result: ExecutionResult
    ) -> Sequence[Finding]:
        """Derive additional findings from the execution result.

        Invoked during the ``VALIDATE`` stage, after ``EXECUTE``. Use this for
        conclusions that need the executed result in hand; findings returned here
        are merged with those the result already carries.

        Args:
            context: Run context.
            result: The result produced by :meth:`execute`.

        Returns:
            Additional findings; empty by default.
        """
        return ()

    def postcheck(
        self, context: ValidationContext, result: ExecutionResult
    ) -> Sequence[Finding]:
        """Check invariants after validation.

        Invoked during the ``POSTCHECK`` stage. Intended for confirming the run
        left the observed system as it found it -- the framework must not alter
        what it observes.

        Args:
            context: Run context.
            result: The result after validation.

        Returns:
            Additional findings; empty by default.
        """
        return ()


class Reporter(Component):
    """Renders a report from execution results.

    Phase 1 provides report *models* only; no HTML or PDF rendering exists.
    Implementations are added in a later phase.
    """

    @abstractmethod
    def render(self, results: Sequence[ExecutionResult], metadata: Mapping[str, Any]) -> Any:
        """Produce a report artifact.

        Args:
            results: Execution results to report on.
            metadata: Run metadata to embed.

        Returns:
            The rendered artifact, in whatever form the implementation targets.

        Raises:
            ReportingError: If the report could not be produced.
        """


class Scheduler(ABC):
    """Contract for scheduling units of work.

    Phase 1 defines this contract **only** -- no scheduling is implemented, per
    the sprint brief. The contract is deliberately mechanism-agnostic so
    time-based, event-based, cron, and continuous-monitoring implementations can
    all satisfy it without changing the interface. Supported kinds are
    enumerated by :class:`framework.core.scheduler.ScheduleKind`.
    """

    @abstractmethod
    def schedule(self, unit_id: str, spec: Any) -> str:
        """Register a unit of work for future execution.

        Args:
            unit_id: Identifier of the work to run.
            spec: Implementation-specific schedule specification; see
                :class:`framework.core.scheduler.ScheduleSpec`.

        Returns:
            A handle identifying the scheduled entry.

        Raises:
            SchedulerError: If the unit could not be scheduled.
        """

    @abstractmethod
    def cancel(self, handle: str) -> bool:
        """Cancel a scheduled entry.

        Args:
            handle: Handle returned by :meth:`schedule`.

        Returns:
            ``True`` if an entry was cancelled, ``False`` if it was not found.
        """

    @abstractmethod
    def due(self) -> Iterable[str]:
        """Return the handles of entries currently due to run.

        Returns:
            Handles due for execution. Implementations decide what "due" means
            for their mechanism.
        """
