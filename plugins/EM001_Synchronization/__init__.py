"""EM001 -- Synchronization Validator.

Reverse-engineers the EmpMonitor synchronization lifecycle from passive evidence,
then validates the behaviour it found. Depends on
``EM000_EnvironmentValidator``: synchronization cannot be meaningfully assessed on a
machine whose agent is not installed and running.

Reports only what was observed. Behaviour the adopted observation strategies cannot
see -- request latency, an offline period that did not occur, WebSocket frames -- is
reported as ``INCONCLUSIVE`` or recorded as ``Hypothesis``, never asserted.
"""

from __future__ import annotations

from plugins.EM001_Synchronization.plugin import PLUGIN_ID, SynchronizationPlugin
from plugins.EM001_Synchronization.promotion import (
    PromotionRecord,
    VerificationStatus,
    build_promotions,
)
from plugins.EM001_Synchronization.timeline import (
    TimelineStage,
    build_evidence_graph,
    build_timeline,
)

__all__ = [
    "PLUGIN_ID",
    "SynchronizationPlugin",
    "PromotionRecord",
    "VerificationStatus",
    "build_promotions",
    "TimelineStage",
    "build_timeline",
    "build_evidence_graph",
]
