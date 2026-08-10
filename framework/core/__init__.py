"""Core engine.

Coordinates runs, executes units, and turns evidence into verdicts. May depend on
:mod:`framework.shared` and nothing else -- never on :mod:`framework.monitors`,
:mod:`framework.validators`, or ``plugins`` (``docs/ADS/architecture.md`` §3).

Internal layering, which keeps this package acyclic. A module may import only from
tiers above it:

==========  ==============================================================
Tier 1      ``dependencies``, ``hooks``, ``metrics``, ``artifacts``,
            ``event_bus``, ``evidence``, ``validation``, ``scheduler``
Tier 2      ``graph`` (dependencies), ``timeline`` (event_bus, reporting),
            ``reporting``, ``context``, ``registry`` (dependencies)
Tier 3      ``pipeline`` (hooks, validation), ``lifecycle`` (event_bus,
            hooks, metrics)
Tier 4      ``execution`` (graph, lifecycle, registry, ...)
Tier 5      ``aggregator`` (execution, timeline, artifacts, metrics)
Tier 6      ``orchestrator`` (everything)
==========  ==============================================================

Contents:

=====================================  ========================================
:mod:`~framework.core.context`         Run state and identity
:mod:`~framework.core.event_bus`       Publish/subscribe decoupling
:mod:`~framework.core.hooks`           Before/after extension points
:mod:`~framework.core.evidence`        Evidence catalog and store
:mod:`~framework.core.validation`      The verdict engine
:mod:`~framework.core.pipeline`        Collector to verdict pipeline
:mod:`~framework.core.dependencies`    Dependency resolution and ordering
:mod:`~framework.core.graph`           Execution DAG, propagation, resume
:mod:`~framework.core.lifecycle`       Per-unit lifecycle stages
:mod:`~framework.core.execution`       Sequential/parallel execution engine
:mod:`~framework.core.scheduler`       Scheduling contract and engine
:mod:`~framework.core.metrics`         Timing, resource, and counter metrics
:mod:`~framework.core.artifacts`       Artifact storage and metadata
:mod:`~framework.core.timeline`        Event-sourced execution timeline
:mod:`~framework.core.aggregator`      Result aggregation
:mod:`~framework.core.reporting`       Report models (no rendering)
:mod:`~framework.core.orchestrator`    Run lifecycle and bootstrap
=====================================  ========================================
"""

from __future__ import annotations

from framework.core.aggregator import AggregatedResult, ResultAggregator
from framework.core.artifacts import ArtifactKind, ArtifactManager, ArtifactRecord
from framework.core.context import RuntimeContext, build_environment_info
from framework.core.dependencies import (
    DependencyIssue,
    DependencyResolver,
    ResolutionResult,
)
from framework.core.event_bus import Event, EventBus, EventType, Subscription
from framework.core.evidence import (
    EvidenceCatalog,
    EvidenceStore,
    build_catalog_from_config,
)
from framework.core.execution import (
    CancellationToken,
    ExecutionEngine,
    ExecutionMode,
    ExecutionPlan,
    ExecutionReport,
)
from framework.core.graph import ExecutionGraph, GraphNode, NodeState
from framework.core.hooks import Hook, HookContext, HookOutcome, HookPoint, HookRegistry
from framework.core.lifecycle import LifecycleEngine, LifecycleOutcome, StageRecord
from framework.core.metrics import MetricsEngine, RunMetrics, Timing, UnitMetrics
from framework.core.orchestrator import BootstrapResult, Orchestrator, bootstrap
from framework.core.pipeline import EvidencePipeline, PipelineResult, StageError
from framework.core.registry import PluginFactory, PluginRegistry
from framework.core.reporting import (
    Attachment,
    FindingRecord,
    Report,
    ReportMetadata,
    ReportSection,
    ReportSummary,
    TimelineEntry,
)
from framework.core.scheduler import (
    CronExpression,
    ScheduleEntry,
    ScheduleKind,
    ScheduleSpec,
    SchedulerEngine,
)
from framework.core.timeline import ExecutionTimeline, TimelineRecord
from framework.core.validation import (
    CorrelationReport,
    LayerAssessment,
    ValidationEngine,
)

__all__ = [
    # Context
    "RuntimeContext",
    "build_environment_info",
    # Event bus
    "EventBus",
    "Event",
    "EventType",
    "Subscription",
    # Hooks
    "HookRegistry",
    "HookPoint",
    "HookContext",
    "HookOutcome",
    "Hook",
    # Evidence
    "EvidenceCatalog",
    "EvidenceStore",
    "build_catalog_from_config",
    # Validation
    "ValidationEngine",
    "CorrelationReport",
    "LayerAssessment",
    # Pipeline
    "EvidencePipeline",
    "PipelineResult",
    "StageError",
    # Dependencies and graph
    "DependencyResolver",
    "DependencyIssue",
    "ResolutionResult",
    "ExecutionGraph",
    "GraphNode",
    "NodeState",
    # Registry
    "PluginRegistry",
    "PluginFactory",
    # Lifecycle and execution
    "LifecycleEngine",
    "LifecycleOutcome",
    "StageRecord",
    "ExecutionEngine",
    "ExecutionMode",
    "ExecutionPlan",
    "ExecutionReport",
    "CancellationToken",
    # Scheduling
    "SchedulerEngine",
    "ScheduleKind",
    "ScheduleSpec",
    "ScheduleEntry",
    "CronExpression",
    # Metrics
    "MetricsEngine",
    "RunMetrics",
    "UnitMetrics",
    "Timing",
    # Artifacts
    "ArtifactManager",
    "ArtifactRecord",
    "ArtifactKind",
    # Timeline
    "ExecutionTimeline",
    "TimelineRecord",
    # Aggregation and reporting
    "ResultAggregator",
    "AggregatedResult",
    "Report",
    "ReportMetadata",
    "ReportSummary",
    "ReportSection",
    "FindingRecord",
    "TimelineEntry",
    "Attachment",
    # Orchestration
    "Orchestrator",
    "BootstrapResult",
    "bootstrap",
]
