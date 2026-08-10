"""Date and time helpers.

All framework timestamps are timezone-aware UTC. Naive datetimes are rejected
rather than coerced: a run may span hosts and timezones, and evidence
correlation depends on unambiguous ordering, so silently assuming local time
would corrupt exactly the comparisons validation relies on.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from framework.shared.exceptions import FrameworkError

__all__ = [
    "utc_now",
    "to_utc",
    "parse_iso8601",
    "format_iso8601",
    "format_timestamp_for_filename",
    "humanize_duration",
    "is_within_tolerance",
    "age",
]


def utc_now() -> datetime:
    """Return the current timezone-aware UTC time."""
    return datetime.now(timezone.utc)


def to_utc(value: datetime) -> datetime:
    """Convert an aware datetime to UTC.

    Args:
        value: A timezone-aware datetime.

    Returns:
        The equivalent time in UTC.

    Raises:
        FrameworkError: If ``value`` is naive. The caller must state the
            timezone rather than have one guessed.
    """
    if value.tzinfo is None:
        raise FrameworkError(
            "Naive datetime rejected; supply a timezone-aware value",
            {"value": value.isoformat()},
        )
    return value.astimezone(timezone.utc)


def parse_iso8601(text: str) -> datetime:
    """Parse an ISO 8601 timestamp into an aware UTC datetime.

    Accepts a trailing ``Z``, which :meth:`datetime.fromisoformat` does not
    handle before Python 3.11 conventions across all inputs.

    Args:
        text: Timestamp text.

    Returns:
        The parsed time in UTC. A value without an offset is assumed UTC, since
        the framework's own outputs are always UTC.

    Raises:
        FrameworkError: If the text is not a valid ISO 8601 timestamp.
    """
    candidate = text.strip()
    if candidate.endswith(("Z", "z")):
        candidate = f"{candidate[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise FrameworkError(
            "Value is not a valid ISO 8601 timestamp", {"value": text}
        ) from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def format_iso8601(value: datetime) -> str:
    """Format an aware datetime as an ISO 8601 UTC string.

    Args:
        value: Timezone-aware datetime.

    Returns:
        The formatted timestamp.

    Raises:
        FrameworkError: If ``value`` is naive.
    """
    return to_utc(value).isoformat()


def format_timestamp_for_filename(value: datetime | None = None) -> str:
    """Format a timestamp for use inside a filename.

    Produces a lexically sortable, filesystem-safe form so generated report
    directories sort chronologically by name.

    Args:
        value: Time to format; defaults to now.

    Returns:
        A string such as ``20260730T184500Z``.
    """
    moment = to_utc(value) if value is not None else utc_now()
    return moment.strftime("%Y%m%dT%H%M%SZ")


def humanize_duration(seconds: float) -> str:
    """Render a duration in compact human-readable form.

    Args:
        seconds: Duration in seconds.

    Returns:
        A string such as ``"1h 02m 03s"``, ``"45.2s"``, or ``"820ms"``.
    """
    if seconds < 0:
        return "0ms"
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    return f"{minutes}m {secs:02d}s"


def is_within_tolerance(
    left: datetime, right: datetime, tolerance: timedelta
) -> bool:
    """Whether two timestamps are within a tolerance of each other.

    Timestamp comparison across layers (for example, a locally recorded capture
    time versus a dashboard-displayed time) needs a tolerance because clocks and
    rendering lag differ; exact equality would produce false failures.

    Args:
        left: First timestamp.
        right: Second timestamp.
        tolerance: Maximum permitted difference.

    Returns:
        ``True`` if the absolute difference is within ``tolerance``.

    Raises:
        FrameworkError: If either value is naive.
    """
    return abs(to_utc(left) - to_utc(right)) <= tolerance


def age(value: datetime, *, now: datetime | None = None) -> timedelta:
    """Return how long ago a timestamp occurred.

    Args:
        value: Timestamp to measure.
        now: Reference time; defaults to the current time.

    Returns:
        The elapsed interval. Negative if ``value`` is in the future.

    Raises:
        FrameworkError: If either value is naive.
    """
    reference = to_utc(now) if now is not None else utc_now()
    return reference - to_utc(value)
