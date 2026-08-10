"""EM000 -- Environment & Agent Validator.

The mandatory pre-check for every regression run. It answers one question:

    *Is this Windows machine correctly prepared to execute EmpMonitor regression
    testing?*

It answers it without touching the dashboard, calling a business API, or validating
captured screenshots or recordings -- those belong to later plugins. It observes the
local environment only.

Later plugins declare ``depends_on=("EM000_EnvironmentValidator",)``, and the gate in
:mod:`~plugins.EM000_EnvironmentValidator.gate` prevents them running when the
environment is unfit -- so a broken machine yields honestly skipped plugins rather
than a run full of misattributed failures.
"""

from __future__ import annotations

from plugins.EM000_EnvironmentValidator.gate import EnvironmentGate, register_environment_gate
from plugins.EM000_EnvironmentValidator.plugin import (
    PLUGIN_ID,
    EnvironmentValidatorPlugin,
)

__all__ = [
    "PLUGIN_ID",
    "EnvironmentValidatorPlugin",
    "EnvironmentGate",
    "register_environment_gate",
]
