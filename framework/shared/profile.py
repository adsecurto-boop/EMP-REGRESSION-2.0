"""Product profile access.

A thin, typed reader over the ``empmonitor`` configuration section: the set of
product facts (install roots, executables, services, processes, configuration
files, storage layout, thresholds) that collectors need in order to know *where to
look*.

This module holds **no product facts of its own**. Every value comes from
configuration, so a different EmpMonitor version or deployment layout is a
configuration change, not a code change
(``docs/ADS/configuration_standard.md``, ``framework/shared/constants.py``).

**The ``verified`` flag is load-bearing.** Each expectation records whether its
name was directly observed on a real installation (``Verified``) or merely stated
(``Hypothesis``, per ``knowledge_base/README.md`` §6). Validators consult
:meth:`Expectation.unmet_verdict` so that an unmet *verified* expectation is a
``FAILED`` finding while an unmet *unverified* one is only ``INCONCLUSIVE``.
Absence of something whose name is a guess is not evidence of absence -- and the
Validation Standard's rule that absence is weak evidence (§7 rule 4) applies with
double force when the thing's name is itself unconfirmed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from framework.shared.logger import get_logger
from framework.shared.models import Verdict

__all__ = ["Expectation", "ProductProfile"]

_LOGGER = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Expectation:
    """One configured expectation about the product.

    Args:
        role: What this expectation is for, e.g. ``"agent"`` or ``"logs"``.
        names: Candidate names, any of which satisfies the expectation.
        relative_paths: Paths relative to a search root, tried in order.
        relative_dirs: Directories relative to a search root to search within.
        search: Which roots to search -- ``"install_root"``, ``"data_root"``, or a
            glob-bearing variant such as ``"data_root/*/empm"``.
        required: Whether the product is expected to have this at all.
        verified: Whether the name was directly observed rather than assumed.
        note: Why the expectation is shaped as it is.
        extra: Remaining configured keys, for role-specific detail.
    """

    role: str
    names: Sequence[str] = field(default_factory=tuple)
    relative_paths: Sequence[str] = field(default_factory=tuple)
    relative_dirs: Sequence[str] = field(default_factory=tuple)
    search: Sequence[str] = field(default_factory=tuple)
    required: bool = True
    verified: bool = False
    note: str = ""
    extra: Mapping[str, Any] = field(default_factory=dict)

    @property
    def unmet_verdict(self) -> Verdict:
        """The verdict to report when this expectation is not met.

        Returns:
            ``FAILED`` when the expectation is verified and required -- a name we
            have confirmed, now absent, is a real defect. ``INCONCLUSIVE`` when the
            name is unverified, because we cannot distinguish "absent" from
            "looked in the wrong place".
        """
        if not self.required:
            return Verdict.HEALTHY
        return Verdict.FAILED if self.verified else Verdict.INCONCLUSIVE

    @property
    def display_names(self) -> str:
        """Candidate names rendered for a message."""
        return " or ".join(self.names) if self.names else self.role

    @classmethod
    def from_config(cls, entry: Mapping[str, Any], *, default_role: str = "") -> "Expectation":
        """Build an expectation from a configuration entry.

        Args:
            entry: The configured mapping.
            default_role: Role to use when the entry does not name one.

        Returns:
            The expectation.
        """
        names: list[str] = []
        if entry.get("name"):
            names.append(str(entry["name"]))
        names.extend(str(item) for item in entry.get("any_of", ()) or ())
        names.extend(str(item) for item in entry.get("candidates", ()) or ())
        consumed = {
            "role", "name", "any_of", "candidates", "relative_paths", "relative_dirs",
            "search", "required", "verified", "note",
        }
        return cls(
            role=str(entry.get("role") or default_role),
            names=tuple(names),
            relative_paths=tuple(str(item) for item in entry.get("relative_paths", ()) or ()),
            relative_dirs=tuple(str(item) for item in entry.get("relative_dirs", ()) or ()),
            search=tuple(str(item) for item in entry.get("search", ()) or ()),
            required=bool(entry.get("required", True)),
            verified=bool(entry.get("verified", False)),
            note=str(entry.get("note", "")),
            extra={key: value for key, value in entry.items() if key not in consumed},
        )


class ProductProfile:
    """Reader over the configured product profile.

    Args:
        section: The ``empmonitor`` configuration section.
    """

    __slots__ = ("_section",)

    def __init__(self, section: Mapping[str, Any] | None) -> None:
        """Initialise the profile.

        Args:
            section: The configuration section, or ``None`` when absent.
        """
        self._section: Mapping[str, Any] = dict(section or {})

    @property
    def raw(self) -> Mapping[str, Any]:
        """The underlying configuration section.

        Exposed so a collector can read a role-specific sub-block (for example
        ``synchronization``) without this class needing a typed accessor for every
        future block. Read-only by contract: callers must not mutate it.
        """
        return self._section

    @property
    def is_configured(self) -> bool:
        """Whether a usable profile is present.

        A profile with no install roots cannot locate anything, so validation
        cannot proceed -- that is a ``BLOCKED`` precondition, not a product defect.
        """
        return bool(self._section.get("install_roots"))

    @staticmethod
    def _expand(value: str) -> Path:
        """Expand environment variables and user references in a path.

        Args:
            value: Raw configured path, which may contain ``%VAR%`` or ``~``.

        Returns:
            The expanded path.
        """
        return Path(os.path.expandvars(os.path.expanduser(value)))

    def install_roots(self) -> tuple[Path, ...]:
        """Return the configured installation roots, expanded."""
        return tuple(
            self._expand(str(item)) for item in self._section.get("install_roots", ()) or ()
        )

    def data_roots(self) -> tuple[Path, ...]:
        """Return the configured data roots, expanded."""
        return tuple(
            self._expand(str(item)) for item in self._section.get("data_roots", ()) or ()
        )

    def existing_install_root(self) -> Path | None:
        """Return the first configured install root that exists.

        Returns:
            The located root, or ``None`` if none exist.
        """
        return next((root for root in self.install_roots() if root.is_dir()), None)

    def existing_data_root(self) -> Path | None:
        """Return the first configured data root that exists.

        Returns:
            The located root, or ``None`` if none exist.
        """
        return next((root for root in self.data_roots() if root.is_dir()), None)

    @property
    def install_roots_verified(self) -> bool:
        """Whether the install-root locations were directly observed."""
        return bool(self._section.get("install_roots_verified", False))

    @property
    def data_roots_verified(self) -> bool:
        """Whether the data-root locations were directly observed."""
        return bool(self._section.get("data_roots_verified", False))

    def executables(self) -> tuple[Expectation, ...]:
        """Return the expected executables."""
        return self._expectations("executables")

    def services(self) -> tuple[Expectation, ...]:
        """Return the expected Windows services."""
        return self._expectations("services")

    def processes(self) -> tuple[Expectation, ...]:
        """Return the expected processes."""
        return self._expectations("processes")

    def configuration_files(self) -> tuple[Expectation, ...]:
        """Return the expected configuration files."""
        return self._expectations("configuration_files")

    def storage_folders(self) -> tuple[Expectation, ...]:
        """Return the expected storage folders."""
        storage = self._section.get("storage", {})
        entries = storage.get("folders", ()) if isinstance(storage, Mapping) else ()
        return tuple(Expectation.from_config(entry) for entry in entries or ())

    def database(self) -> Expectation | None:
        """Return the expected database, if one is configured.

        Returns:
            The expectation, or ``None`` when no database is configured.
        """
        storage = self._section.get("storage", {})
        entry = storage.get("database") if isinstance(storage, Mapping) else None
        if not isinstance(entry, Mapping):
            return None
        merged = dict(entry)
        merged.setdefault("role", "database")
        merged["candidates"] = list(entry.get("patterns", ()) or ())
        return Expectation.from_config(merged, default_role="database")

    def registry_keys(self) -> tuple[Mapping[str, Any], ...]:
        """Return the configured registry expectations.

        Returns:
            The entries, empty when none are configured. Empty is the honest
            default: no registry key is documented for EmpMonitor, so the
            framework checks none rather than inventing one.
        """
        return tuple(
            entry
            for entry in self._section.get("registry_keys", ()) or ()
            if isinstance(entry, Mapping)
        )

    def _expectations(self, key: str) -> tuple[Expectation, ...]:
        """Build expectations from a named list in the profile.

        Args:
            key: Section key holding a list of entries.

        Returns:
            The expectations.
        """
        entries = self._section.get(key, ()) or ()
        return tuple(
            Expectation.from_config(entry)
            for entry in entries
            if isinstance(entry, Mapping)
        )

    def threshold(self, name: str, default: Any = None) -> Any:
        """Return a configured threshold.

        Args:
            name: Threshold key.
            default: Value to use when unset.

        Returns:
            The threshold value.
        """
        thresholds = self._section.get("thresholds", {})
        if not isinstance(thresholds, Mapping):
            return default
        value = thresholds.get(name, default)
        return default if value is None else value

    def network_setting(self, name: str, default: Any = None) -> Any:
        """Return a configured network setting.

        Args:
            name: Setting key.
            default: Value to use when unset.

        Returns:
            The setting value.
        """
        network = self._section.get("network", {})
        return network.get(name, default) if isinstance(network, Mapping) else default

    def collection_setting(self, name: str, default: Any = None) -> Any:
        """Return a configured collection setting.

        Args:
            name: Setting key.
            default: Value to use when unset.

        Returns:
            The setting value.
        """
        collection = self._section.get("collection", {})
        return collection.get(name, default) if isinstance(collection, Mapping) else default

    def resolve_search_roots(self, expectation: Expectation) -> tuple[Path, ...]:
        """Resolve an expectation's search roots to concrete directories.

        Supports glob segments so a tenant-specific directory can be discovered
        rather than hardcoded -- for example ``data_root/*/empm``.

        Args:
            expectation: The expectation whose roots are resolved.

        Returns:
            Existing directories to search, in configured order.
        """
        resolved: list[Path] = []
        for token in expectation.search or ("install_root",):
            base_name, _, pattern = token.partition("/")
            bases = (
                self.install_roots()
                if base_name == "install_root"
                else self.data_roots()
                if base_name == "data_root"
                else (self._expand(token),)
            )
            for base in bases:
                if not pattern:
                    if base.is_dir():
                        resolved.append(base)
                    continue
                try:
                    resolved.extend(
                        match for match in sorted(base.glob(pattern)) if match.is_dir()
                    )
                except OSError:  # pragma: no cover -- unreadable directory
                    _LOGGER.debug("Search root not traversable: %s/%s", base, pattern)
        # Preserve order while removing duplicates so a root searched twice is
        # only reported once.
        seen: set[Path] = set()
        unique: list[Path] = []
        for path in resolved:
            if path not in seen:
                seen.add(path)
                unique.append(path)
        return tuple(unique)

    def locate(self, expectation: Expectation) -> tuple[Path | None, tuple[Path, ...]]:
        """Locate the first path satisfying an expectation.

        Args:
            expectation: What to look for.

        Returns:
            The located path (or ``None``) and every location that was searched.
            The searched list is returned so a negative finding can state *where*
            the framework looked -- "not found" is only meaningful with that.
        """
        searched: list[Path] = []
        roots = self.resolve_search_roots(expectation)

        for root in roots:
            for relative in expectation.relative_paths:
                candidate = root / relative
                searched.append(candidate)
                if candidate.exists():
                    return candidate, tuple(searched)

        directories = [root / item for root in roots for item in expectation.relative_dirs]
        for directory in directories or roots:
            for name in expectation.names:
                candidate = directory / name
                searched.append(candidate)
                if candidate.exists():
                    return candidate, tuple(searched)
                if any(char in name for char in "*?["):
                    try:
                        matches = sorted(directory.glob(name))
                    except OSError:  # pragma: no cover -- unreadable directory
                        matches = []
                    if matches:
                        return matches[0], tuple(searched)
        return None, tuple(searched)
