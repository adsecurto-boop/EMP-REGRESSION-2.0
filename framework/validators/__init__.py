"""Validators -- turn evidence into findings.

**Empty by design in Phase 1.** Validator implementations begin in Phase 2
(``docs/roadmap/implementation_plan.md``); the module files here are scaffolds
awaiting that work.

A validator implements :class:`framework.shared.interfaces.Validator` and may
depend on :mod:`framework.shared` only -- never on :mod:`framework.core` or
``plugins`` (``docs/ADS/architecture.md`` §3).

Validators conclude; they do not collect. Evidence is supplied to them so that
one artifact has exactly one collector (Validation Standard §4.1). A validator
should build findings with :meth:`framework.shared.models.Finding.build`, which
computes confidence from the evidence rather than letting it be asserted (§8.2).

A product defect is a ``FAILED`` finding, never an exception. Raising
:class:`framework.shared.exceptions.ValidationError` means the *framework* could
not reach a conclusion.

Planned members:

==============================  =====  =====================================
``configuration.py``            L1     Product configuration correctness
``environment.py``              --     Environment prerequisites (``BLOCKED`` gate)
``runtime.py``                  L2     Runtime state expectations
``evidence.py``                 --     Evidence sufficiency and corroboration
``dashboard.py``                L4     Dashboard state (EV-006, EV-008)
==============================  =====  =====================================
"""

from __future__ import annotations

__all__: list[str] = []
