"""EmpMonitor feature-area validation plugins.

Each plugin validates one EmpMonitor capability and is the **only** place
feature-specific logic belongs (``docs/FRAMEWORK_MANIFEST.md`` §7). Plugins depend
on the framework; no framework module imports this package, and discovery happens at
runtime from a configured package name so that rule holds statically
(``docs/ADS/architecture.md`` §3).

Catalog:

===============================  ==================================================
``EM000_EnvironmentValidator``   Windows environment and agent pre-check. Runs before
                                 every regression run; later plugins depend on it.
``EM001_Synchronization``        Synchronization lifecycle reverse engineering and
                                 validation (Layers 1-3). Depends on EM000.
``EM001_Login``                  Login (not implemented)
``EM002_UserManagement``         User management (not implemented)
``EM003_Attendance``             Attendance (not implemented)
``EM004_LiveMonitoring``         Live monitoring (not implemented)
``EM005_Screenshots``            Screenshots (not implemented)
``EM006_ScreenRecording``        Screen recording (not implemented)
===============================  ==================================================

A plugin becomes discoverable by exposing a concrete
:class:`framework.shared.interfaces.Plugin` subclass from a module in this package.
"""

from __future__ import annotations

from plugins.EM000_EnvironmentValidator import EnvironmentValidatorPlugin
from plugins.EM001_Synchronization import SynchronizationPlugin

__all__ = ["EnvironmentValidatorPlugin", "SynchronizationPlugin"]
