"""Monitors -- passive observers of system and product state.

**Empty by design in Phase 1.** Monitor implementations are Phase 3 work
(``docs/roadmap/implementation_plan.md``); the module files in this package are
scaffolds awaiting that phase.

A monitor implements :class:`framework.shared.interfaces.Monitor` and may depend
on :mod:`framework.shared` only -- never on :mod:`framework.core` or ``plugins``
(``docs/ADS/architecture.md`` §3). That is why the ``Monitor`` interface lives in
``shared``.

Monitors are passive: a monitor reports an observed anomaly through the event bus
and must not raise for a condition it exists to observe
(``docs/ADS/error_handling_standard.md`` §5).

Planned members, each registered in ``docs/Evidence_Catalog.md``:

===============================  =====  ====================================
``folder_monitor.py``            L2     File system artifacts (EV-010)
``log_monitor.py``               L2     Agent log content (EV-004)
``runtime_monitor.py``           L2     Processes, services, resources (EV-005, EV-011)
``scheduler_monitor.py``         L2     Scheduled task state (EV-009)
``sqlite_monitor.py``            L2     Local database contents (EV-003)
===============================  =====  ====================================

The Layer 3 collector is specified in
``docs/design/Synchronization_Monitor.md`` and is not yet built; its observation
strategy is an open decision (§6 there).
"""

from __future__ import annotations

__all__: list[str] = []
