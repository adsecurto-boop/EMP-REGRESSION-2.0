"""Version parsing and comparison.

Verified knowledge in the reverse-engineering knowledge base is recorded
"against version" (``knowledge_base/README.md`` §6.1), so comparing versions is
a first-class framework concern: it determines whether a previously verified
claim still applies to the build under observation.

Deliberately tolerant. Product version strings in the wild are not guaranteed
to be strict semantic versions, and refusing to parse an unexpected shape would
be worse than comparing it approximately -- so unparsable trailing text is
retained for equality but ignored for ordering.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import total_ordering
from typing import Any

from framework.shared.exceptions import FrameworkError

__all__ = [
    "Version",
    "parse_version",
    "compare_versions",
    "is_at_least",
    "satisfies",
    "parse_constraint",
]

_VERSION_RE = re.compile(
    r"^\s*v?(?P<numbers>\d+(?:\.\d+)*)(?:[-+.]?(?P<suffix>[A-Za-z0-9.\-+]*))?\s*$"
)


@total_ordering
@dataclass(frozen=True, slots=True)
class Version:
    """A parsed, comparable version.

    Ordering compares numeric components left to right, padding the shorter
    version with zeros so ``1.2`` and ``1.2.0`` compare equal. The suffix is
    excluded from ordering because there is no reliable universal precedence for
    arbitrary build suffixes.

    Args:
        numbers: Numeric components, most significant first.
        suffix: Trailing non-numeric text, if any.
        raw: The original string.
    """

    numbers: tuple[int, ...]
    suffix: str = ""
    raw: str = ""

    def __str__(self) -> str:
        return self.raw or ".".join(str(number) for number in self.numbers)

    @property
    def major(self) -> int:
        """The first numeric component, or ``0`` if there is none."""
        return self.numbers[0] if self.numbers else 0

    @property
    def minor(self) -> int:
        """The second numeric component, or ``0``."""
        return self.numbers[1] if len(self.numbers) > 1 else 0

    @property
    def patch(self) -> int:
        """The third numeric component, or ``0``."""
        return self.numbers[2] if len(self.numbers) > 2 else 0

    def _comparable(self, other: "Version") -> tuple[tuple[int, ...], tuple[int, ...]]:
        width = max(len(self.numbers), len(other.numbers))
        left = self.numbers + (0,) * (width - len(self.numbers))
        right = other.numbers + (0,) * (width - len(other.numbers))
        return left, right

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        left, right = self._comparable(other)
        return left == right and self.suffix == other.suffix

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        left, right = self._comparable(other)
        return left < right

    def __hash__(self) -> int:
        return hash((self.numbers, self.suffix))


def parse_version(text: str) -> Version:
    """Parse a version string.

    Args:
        text: Version text, optionally prefixed ``v`` and optionally carrying a
            trailing build/pre-release suffix.

    Returns:
        The parsed :class:`Version`.

    Raises:
        FrameworkError: If no leading numeric component can be found.
    """
    match = _VERSION_RE.match(text or "")
    if not match:
        raise FrameworkError("Value is not a recognisable version", {"value": text})
    numbers = tuple(int(part) for part in match.group("numbers").split("."))
    return Version(numbers=numbers, suffix=match.group("suffix") or "", raw=text.strip())


def compare_versions(left: str, right: str) -> int:
    """Compare two version strings.

    Args:
        left: First version.
        right: Second version.

    Returns:
        ``-1`` if ``left`` is lower, ``0`` if equivalent numerically, ``1`` if
        higher.

    Raises:
        FrameworkError: If either value cannot be parsed.
    """
    first, second = parse_version(left), parse_version(right)
    if first < second:
        return -1
    if second < first:
        return 1
    return 0


def is_at_least(candidate: str, minimum: str) -> bool:
    """Whether ``candidate`` is at least ``minimum``.

    Args:
        candidate: Version to test.
        minimum: Minimum acceptable version.

    Returns:
        ``True`` if ``candidate >= minimum`` numerically.

    Raises:
        FrameworkError: If either value cannot be parsed.
    """
    return compare_versions(candidate, minimum) >= 0


_CONSTRAINT_RE = re.compile(r"^\s*(?P<operator>>=|<=|==|!=|~=|>|<)?\s*(?P<version>.+?)\s*$")

_COMPARATORS: dict[str, Any] = {
    ">=": lambda left, right: left >= right,
    "<=": lambda left, right: left <= right,
    ">": lambda left, right: left > right,
    "<": lambda left, right: left < right,
    "==": lambda left, right: left == right,
    "!=": lambda left, right: left != right,
}


def parse_constraint(constraint: str) -> tuple[str, "Version"]:
    """Parse a single version constraint into an operator and version.

    Supported operators: ``>=``, ``<=``, ``>``, ``<``, ``==``, ``!=``, and ``~=``
    (compatible-release: same major, at least the given version). A bare version
    with no operator means ``==``.

    Args:
        constraint: Constraint text, e.g. ``">=1.2"``.

    Returns:
        The operator and the parsed version.

    Raises:
        FrameworkError: If the constraint cannot be parsed.
    """
    match = _CONSTRAINT_RE.match(constraint or "")
    if not match:
        raise FrameworkError("Unparsable version constraint", {"constraint": constraint})
    operator = match.group("operator") or "=="
    return operator, parse_version(match.group("version"))


def satisfies(candidate: str, constraint: str) -> bool:
    """Whether a version satisfies a constraint expression.

    Multiple constraints may be combined with commas, all of which must hold:
    ``">=1.2, <2.0"``.

    Numeric comparison only -- build suffixes are ignored for ordering, matching
    :class:`Version` semantics. Version strings for a product the framework only
    observes are not guaranteed to follow strict semantic versioning, so pretending
    to order arbitrary suffixes would invent precision the data does not have.

    Args:
        candidate: Version to test.
        constraint: One or more comma-separated constraints.

    Returns:
        ``True`` if every constraint holds.

    Raises:
        FrameworkError: If the candidate or any constraint cannot be parsed.
    """
    subject = parse_version(candidate)
    for part in (piece for piece in constraint.split(",") if piece.strip()):
        operator, target = parse_constraint(part)
        if operator == "~=":
            # Compatible release: same major component, and at least the target.
            if subject.major != target.major or subject < target:
                return False
            continue
        comparator = _COMPARATORS.get(operator)
        if comparator is None:  # pragma: no cover -- regex restricts the operator set
            raise FrameworkError(
                "Unsupported constraint operator", {"operator": operator}
            )
        if operator in ("==", "!="):
            # Equality ignores suffixes so that "1.2" matches "1.2.0".
            equal = compare_versions(candidate, str(target)) == 0
            if (operator == "==") is not equal:
                return False
            continue
        if not comparator(subject, target):
            return False
    return True
