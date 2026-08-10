"""The Synchronization Monitor -- Layer 3 evidence collection (EV-007, EV-017).

Implements ``docs/design/Synchronization_Monitor.md``. Its §6 observation-strategy
spike is resolved: the three **passive** strategies are composed, and proxy
interception is rejected as both non-conformant and unnecessary.

Three collectors, one per artifact, so that evidence from any two of them is
genuinely independent and may corroborate under
``docs/ADS/validation_standard.md`` §4.1:

* :class:`SyncLogCollector` -- owns the agent's log files. The **primary** strategy:
  the agent logs request URLs, API names, HTTP reply codes, and per-item upload
  outcomes, which is higher fidelity than the original design estimated.
* :class:`SyncQueueCollector` -- owns queue-table state in the local database.
* :class:`AgentNetworkCollector` -- owns the host's connection table.

**Nothing is hardcoded.** Log patterns, table-name prefixes, endpoint discovery, and
thresholds all come from configuration; the collectors carry no URL, table name, or
log message of their own. A configured pattern that no longer matches yields *no*
evidence for that fact, which downstream becomes ``INCONCLUSIVE`` -- never a false
negative, because a product that changed its log format has not thereby broken.

**Passive throughout.** Nothing here issues a request, opens a socket to the
product's server, or writes to any product artifact. Logs and the database are
opened read-only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from framework.shared.interfaces import Collector
from framework.shared.logger import get_logger
from framework.shared.models import (
    Evidence,
    EvidenceLayer,
    SourceReliability,
    ValidationContext,
)
from framework.shared.profile import Expectation, ProductProfile
from framework.shared.utils import filesystem, sqlite_utils, windows

__all__ = [
    "EV_SYNC",
    "EV_NETWORK_STATE",
    "LogEvent",
    "SyncLogCollector",
    "SyncQueueCollector",
    "AgentNetworkCollector",
]

_LOGGER = get_logger(__name__)

EV_SYNC = "EV-007"
EV_NETWORK_STATE = "EV-017"

#: Substrings that mark a log field as carrying captured or credential content.
#: Matching fields are dropped before evidence is built. The agent's log contains
#: monitored activity (mail subjects, clipboard text), which is none of the
#: framework's business and must never enter a report.
_SENSITIVE_FIELD_HINTS = ("subj", "body", "mail", "clip", "text", "password", "token", "email")


def _sync_section(profile: ProductProfile) -> Mapping[str, Any]:
    """Return the ``synchronization`` block of the product profile.

    Args:
        profile: The product profile.

    Returns:
        The synchronization configuration, empty when unconfigured.
    """
    section = profile.raw.get("synchronization") if hasattr(profile, "raw") else None
    return section if isinstance(section, Mapping) else {}


@dataclass(frozen=True, slots=True)
class LogEvent:
    """One recognised line from an agent log.

    Args:
        pattern: Name of the configured pattern that matched.
        timestamp: Line timestamp, when parseable.
        level: Log level reported on the line.
        fields: Named capture groups, with sensitive fields removed.
        source_file: File the line came from.
        means: The configured plain-language meaning of the pattern.
    """

    pattern: str
    timestamp: datetime | None
    level: str
    fields: Mapping[str, str] = field(default_factory=dict)
    source_file: str = ""
    means: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-native representation.

        Returns:
            A serialisable mapping.
        """
        return {
            "pattern": self.pattern,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "level": self.level,
            "fields": dict(self.fields),
            "source_file": self.source_file,
            "means": self.means,
        }


class SyncLogCollector(Collector):
    """Derives synchronization evidence from the agent's own logs.

    The primary Layer 3 strategy. It reads only lines matching configured patterns
    and records only their named capture groups, so unrecognised log content -- which
    is where captured monitoring data lives -- never enters evidence.
    """

    def __init__(self, profile: ProductProfile) -> None:
        """Initialise the collector.

        Args:
            profile: Product profile supplying log locations and patterns.
        """
        self._profile = profile
        self._config = _sync_section(profile)

    @property
    def name(self) -> str:
        """Component name."""
        return "sync.log.collector"

    @property
    def layer(self) -> EvidenceLayer:
        """The evidence layer this collector serves."""
        return EvidenceLayer.SYNCHRONIZATION

    @property
    def evidence_ids(self) -> Sequence[str]:
        """Evidence Catalog identifiers this collector produces."""
        return (EV_SYNC,)

    def collect(self, context: ValidationContext) -> Sequence[Evidence]:
        """Collect synchronization evidence from logs.

        Args:
            context: Run context.

        Returns:
            One evidence record per log source, plus a summary record describing the
            recognised event stream. When no pattern is configured the collector
            returns a single record saying so -- an unconfigured collector must not
            look like a clean result.
        """
        patterns = self._compiled_patterns()
        if not patterns:
            return (
                self._evidence(
                    "log patterns are not configured; no log-derived evidence collected",
                    {"state": "unconfigured", "pattern_count": 0},
                ),
            )

        line_re = self._line_pattern()
        collected: list[Evidence] = []
        events: list[LogEvent] = []
        for expectation, files in self._log_files():
            if not files:
                collected.append(
                    self._evidence(
                        f"no {expectation.role} file found to read",
                        {
                            "state": "absent",
                            "role": expectation.role,
                            "verified_name": expectation.verified,
                            "candidates": list(expectation.names),
                        },
                    )
                )
                continue
            for path in files:
                parsed, unmatched, last_ts = self._read(path, line_re, patterns)
                events.extend(parsed)
                collected.append(
                    self._evidence(
                        f"{len(parsed)} recognised sync event(s) in {path.name}",
                        {
                            "state": "read",
                            "role": expectation.role,
                            "path": str(path),
                            "size_bytes": filesystem.file_size(path),
                            "recognised_events": len(parsed),
                            "unrecognised_lines": unmatched,
                            "last_timestamp": last_ts.isoformat() if last_ts else None,
                            "age_seconds": (
                                (datetime.now(timezone.utc) - last_ts).total_seconds()
                                if last_ts
                                else None
                            ),
                        },
                    )
                )
        collected.append(self._summary_evidence(events))
        return tuple(collected)

    def _line_pattern(self) -> re.Pattern[str] | None:
        """Compile the configured log-line pattern.

        Returns:
            The compiled pattern, or ``None`` when unconfigured or invalid.
        """
        raw = self._config.get("log_line_pattern")
        if not raw:
            return None
        try:
            return re.compile(str(raw))
        except re.error as exc:
            _LOGGER.error("Configured log_line_pattern is not a valid regex: %s", exc)
            return None

    def _compiled_patterns(self) -> dict[str, tuple[re.Pattern[str], str, bool]]:
        """Compile the configured message patterns.

        Returns:
            A mapping of pattern name to its compiled regex, stated meaning, and
            verified flag. An invalid regex is logged and skipped rather than
            aborting collection.
        """
        raw = self._config.get("log_patterns")
        if not isinstance(raw, Mapping):
            return {}
        compiled: dict[str, tuple[re.Pattern[str], str, bool]] = {}
        for name, entry in raw.items():
            if not isinstance(entry, Mapping):
                continue
            expression = entry.get("regex")
            if not expression:
                continue
            try:
                compiled[str(name)] = (
                    re.compile(str(expression)),
                    str(entry.get("means", "")),
                    bool(entry.get("verified", False)),
                )
            except re.error as exc:
                _LOGGER.error("Log pattern %s is not a valid regex: %s", name, exc)
        return compiled

    def _log_files(self) -> list[tuple[Expectation, list[Path]]]:
        """Locate the configured log files.

        Returns:
            Each configured log source with the files found for it, newest first.
        """
        results: list[tuple[Expectation, list[Path]]] = []
        for entry in self._config.get("log_sources", ()) or ():
            if not isinstance(entry, Mapping):
                continue
            expectation = Expectation.from_config(entry)
            directory, _ = self._profile.locate(expectation)
            files: list[Path] = []
            if directory is not None and directory.is_dir():
                glob = str(entry.get("file_glob") or "*")
                try:
                    files = sorted(
                        (item for item in directory.glob(glob) if item.is_file()),
                        key=lambda item: item.stat().st_mtime,
                        reverse=True,
                    )[:3]
                except OSError as exc:  # pragma: no cover -- unreadable directory
                    _LOGGER.debug("Log directory not listable: %s (%s)", directory, exc)
            results.append((expectation, files))
        return results

    def _read(
        self,
        path: Path,
        line_re: re.Pattern[str] | None,
        patterns: Mapping[str, tuple[re.Pattern[str], str, bool]],
    ) -> tuple[list[LogEvent], int, datetime | None]:
        """Read one log file and extract recognised events.

        Args:
            path: Log file to read.
            line_re: Compiled line-structure pattern.
            patterns: Compiled message patterns.

        Returns:
            The recognised events, the count of unrecognised lines, and the latest
            timestamp seen.
        """
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            _LOGGER.error("Log file could not be read: %s (%s)", path, exc)
            return [], 0, None

        stamp_format = str(self._config.get("log_timestamp_format") or "")
        events: list[LogEvent] = []
        unmatched = 0
        latest: datetime | None = None

        for line in text.splitlines():
            if not line.strip():
                continue
            timestamp: datetime | None = None
            level = ""
            message = line
            if line_re is not None and (structure := line_re.match(line)):
                groups = structure.groupdict()
                message = groups.get("message") or line
                level = groups.get("level") or ""
                timestamp = self._parse_timestamp(groups.get("timestamp"), stamp_format)
                if timestamp is not None and (latest is None or timestamp > latest):
                    latest = timestamp

            recognised = False
            for name, (expression, means, _verified) in patterns.items():
                if match := expression.search(message):
                    events.append(
                        LogEvent(
                            pattern=name,
                            timestamp=timestamp,
                            level=level,
                            fields=self._safe_fields(match.groupdict()),
                            source_file=path.name,
                            means=means,
                        )
                    )
                    recognised = True
            if not recognised:
                unmatched += 1
        return events, unmatched, latest

    @staticmethod
    def _parse_timestamp(value: str | None, stamp_format: str) -> datetime | None:
        """Parse a log timestamp.

        Args:
            value: Raw timestamp text.
            stamp_format: Configured ``strptime`` format.

        Returns:
            An aware UTC datetime, or ``None`` when unparseable.
        """
        if not value:
            return None
        if stamp_format:
            try:
                return datetime.strptime(value, stamp_format).replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

    @staticmethod
    def _safe_fields(groups: Mapping[str, str | None]) -> dict[str, str]:
        """Drop capture groups that could carry captured or credential content.

        A pattern author could inadvertently capture a mail subject or a token. This
        filter is the backstop: any field whose *name* suggests content is discarded
        before the value reaches evidence.

        Args:
            groups: Named capture groups from a match.

        Returns:
            The retained fields, truncated.
        """
        safe: dict[str, str] = {}
        for key, value in groups.items():
            if value is None:
                continue
            if any(hint in key.lower() for hint in _SENSITIVE_FIELD_HINTS):
                safe[key] = "<elided: field name suggests captured content>"
                continue
            safe[key] = str(value)[:300]
        return safe

    def _summary_evidence(self, events: Sequence[LogEvent]) -> Evidence:
        """Summarise the recognised event stream, including observed cadence.

        Args:
            events: All recognised events.

        Returns:
            Evidence describing the synchronization event stream.
        """
        by_pattern: dict[str, int] = {}
        for event in events:
            by_pattern[event.pattern] = by_pattern.get(event.pattern, 0) + 1

        cycles = sorted(
            event.timestamp
            for event in events
            if event.pattern == "upload_cycle_trigger" and event.timestamp is not None
        )
        gaps = [
            (later - earlier).total_seconds()
            for earlier, later in zip(cycles, cycles[1:], strict=False)
        ]
        endpoints = sorted(
            {
                value
                for event in events
                for key, value in event.fields.items()
                if key == "url" and value.startswith(("http://", "https://", "ws://", "wss://"))
            }
        )
        api_calls = [
            {
                "api": event.fields.get("api") or event.fields.get("url", ""),
                "code": event.fields.get("code"),
                "at": event.timestamp.isoformat() if event.timestamp else None,
            }
            for event in events
            if event.pattern in ("api_reply", "api_url_reply")
        ]
        return self._evidence(
            f"{len(events)} recognised sync event(s); {len(cycles)} upload cycle(s) observed",
            {
                "state": "observed" if events else "no events",
                "event_count": len(events),
                "events_by_pattern": by_pattern,
                "cycle_timestamps": [item.isoformat() for item in cycles],
                "cycle_count": len(cycles),
                "observed_intervals_seconds": gaps,
                "observed_endpoints": endpoints,
                "api_calls": api_calls,
                "events": [event.to_dict() for event in events[-200:]],
            },
        )

    def _evidence(self, summary: str, data: Mapping[str, Any]) -> Evidence:
        """Build a log-derived evidence record.

        Args:
            summary: Human-readable statement.
            data: Structured detail.

        Returns:
            The evidence.
        """
        return Evidence(
            evidence_id=EV_SYNC,
            layer=EvidenceLayer.SYNCHRONIZATION,
            source="synchronization:log",
            summary=summary,
            collector=self.name,
            reliability=SourceReliability.MEDIUM,
            data=dict(data),
        )


class SyncQueueCollector(Collector):
    """Observes upload-queue state in the local database.

    Table **names are discovered** from the database at runtime; only the prefix
    convention is configured, so a renamed or added queue table is picked up without
    a code or configuration change.

    This collector reads the same database file as
    :class:`framework.monitors.sqlite_monitor.SqliteCollector`. That is recorded in
    the evidence as ``shares_artifact_with``, because two readings of one artifact do
    not independently corroborate each other (§4.1) and a validator must be able to
    see that.
    """

    def __init__(self, profile: ProductProfile) -> None:
        """Initialise the collector.

        Args:
            profile: Product profile describing the database and queue conventions.
        """
        self._profile = profile
        self._config = _sync_section(profile)

    @property
    def name(self) -> str:
        """Component name."""
        return "sync.queue.collector"

    @property
    def layer(self) -> EvidenceLayer:
        """The evidence layer this collector serves."""
        return EvidenceLayer.SYNCHRONIZATION

    @property
    def evidence_ids(self) -> Sequence[str]:
        """Evidence Catalog identifiers this collector produces."""
        return (EV_SYNC,)

    def collect(self, context: ValidationContext) -> Sequence[Evidence]:
        """Collect queue-state evidence.

        Args:
            context: Run context.

        Returns:
            Evidence describing queue depth per discovered queue table.
        """
        expectation = self._profile.database()
        if expectation is None:
            return ()
        located, searched = self._profile.locate(expectation)
        if located is None:
            return (
                self._evidence(
                    "queue state unavailable: local database not found",
                    {"state": "absent", "searched": [str(item) for item in searched]},
                ),
            )

        queue_config = self._config.get("queue", {})
        pending_prefixes = tuple(
            str(item)
            for item in (queue_config.get("pending_table_prefixes", ()) if isinstance(queue_config, Mapping) else ())
            or ()
        )
        sent_prefixes = tuple(
            str(item)
            for item in (queue_config.get("sent_table_prefixes", ()) if isinstance(queue_config, Mapping) else ())
            or ()
        )
        if not pending_prefixes:
            return (
                self._evidence(
                    "queue table prefixes are not configured; queue depth not observed",
                    {"state": "unconfigured", "path": str(located)},
                ),
            )

        try:
            with sqlite_utils.open_readonly(located) as connection:
                tables = sqlite_utils.list_tables(connection)
                pending = {
                    name: self._safe_count(connection, name)
                    for name in tables
                    if name.startswith(pending_prefixes)
                }
                sent = {
                    name: self._safe_count(connection, name)
                    for name in tables
                    if sent_prefixes and name.startswith(sent_prefixes)
                }
        except Exception as exc:  # noqa: BLE001 -- normalised into an observation
            return (
                self._evidence(
                    "queue state could not be read from the local database",
                    {"state": "unreadable", "path": str(located), "error": str(exc)},
                ),
            )

        depth = sum(value for value in pending.values() if value is not None)
        non_empty = {name: value for name, value in pending.items() if (value or 0) > 0}
        return (
            self._evidence(
                f"queue depth {depth} across {len(pending)} discovered queue table(s)",
                {
                    "state": "observed",
                    "path": str(located),
                    "shares_artifact_with": "EV-003",
                    "discovered_pending_tables": sorted(pending),
                    "pending_depths": pending,
                    "discovered_sent_tables": sorted(sent),
                    "sent_depths": sent,
                    "total_queue_depth": depth,
                    "non_empty_queues": non_empty,
                    "prefixes_used": list(pending_prefixes),
                },
            ),
        )

    @staticmethod
    def _safe_count(connection: Any, table: str) -> int | None:
        """Count rows in a table, tolerating one bad table.

        Args:
            connection: Open read-only connection.
            table: Table name.

        Returns:
            The row count, or ``None`` when it could not be read.
        """
        try:
            return sqlite_utils.row_count(connection, table)
        except Exception:  # noqa: BLE001 -- one unreadable table must not stop the rest
            return None

    def _evidence(self, summary: str, data: Mapping[str, Any]) -> Evidence:
        """Build a queue evidence record.

        Args:
            summary: Human-readable statement.
            data: Structured detail.

        Returns:
            The evidence.
        """
        return Evidence(
            evidence_id=EV_SYNC,
            layer=EvidenceLayer.SYNCHRONIZATION,
            source="synchronization:queue",
            summary=summary,
            collector=self.name,
            reliability=SourceReliability.HIGH,
            data=dict(data),
        )


class AgentNetworkCollector(Collector):
    """Observes the connection table for the agent's processes.

    Passive: it reads the host's connection list and attributes entries to agent
    process ids. It opens nothing and sends nothing.

    Payload is not observable -- the product's server traffic is TLS -- so this
    collector deliberately records **connection state only**. Remote addresses are
    recorded as endpoint identities, never resolved to owners or geolocated.
    """

    def __init__(self, profile: ProductProfile) -> None:
        """Initialise the collector.

        Args:
            profile: Product profile naming the agent's processes.
        """
        self._profile = profile
        self._config = _sync_section(profile)

    @property
    def name(self) -> str:
        """Component name."""
        return "sync.network.collector"

    @property
    def layer(self) -> EvidenceLayer:
        """The evidence layer this collector serves."""
        return EvidenceLayer.SYNCHRONIZATION

    @property
    def evidence_ids(self) -> Sequence[str]:
        """Evidence Catalog identifiers this collector produces."""
        return (EV_NETWORK_STATE,)

    def collect(self, context: ValidationContext) -> Sequence[Evidence]:
        """Collect agent connection-state evidence.

        Args:
            context: Run context.

        Returns:
            Evidence describing the agent's connections, or a record explaining why
            none could be observed.
        """
        network_config = self._config.get("network", {})
        if isinstance(network_config, Mapping) and not network_config.get(
            "observe_agent_connections", True
        ):
            return ()

        expected = {
            name.lower()
            for expectation in self._profile.processes()
            for name in expectation.names
        }
        if not expected:
            return ()

        processes = windows.list_processes()
        pids = {item.pid: item.name for item in processes if item.name.lower() in expected}
        if not pids:
            return (
                self._evidence(
                    "no agent process is running, so no agent connections exist to observe",
                    {"state": "no processes", "expected_processes": sorted(expected)},
                ),
            )

        result = windows.run_command(["netstat.exe", "-ano"])
        if not result.ok:
            return (
                self._evidence(
                    "agent connection state could not be read",
                    {
                        "state": "unmeasured",
                        "error": (result.error or result.stderr or "netstat failed")[:300],
                    },
                ),
            )

        server_ports = {
            int(port)
            for port in (
                network_config.get("server_ports", (443,))
                if isinstance(network_config, Mapping)
                else (443,)
            )
            or ()
        }
        connections = self._parse(result.stdout, pids)
        remote = [item for item in connections if not self._is_loopback(item["remote_address"])]
        loopback = [item for item in connections if self._is_loopback(item["remote_address"])]
        server = [
            item
            for item in remote
            if item["remote_port"] in server_ports and item["state"] == "ESTABLISHED"
        ]
        listening = [item for item in connections if item["state"] == "LISTENING"]

        return (
            self._evidence(
                f"{len(server)} established server connection(s) across "
                f"{len({item['process'] for item in server})} agent process(es)",
                {
                    "state": "observed" if connections else "no connections",
                    "agent_pids": {str(pid): name for pid, name in sorted(pids.items())},
                    "connection_count": len(connections),
                    "established_server_connections": server,
                    "loopback_connections": loopback,
                    "listening_endpoints": listening,
                    "server_ports_watched": sorted(server_ports),
                    "processes_with_server_connection": sorted(
                        {item["process"] for item in server}
                    ),
                    "payload_observable": False,
                    "payload_note": (
                        "Server traffic is TLS; connection state is observable but request "
                        "and response bodies are not. Interception was rejected by the "
                        "Synchronization Monitor design spike."
                    ),
                },
            ),
        )

    @staticmethod
    def _is_loopback(address: str) -> bool:
        """Whether an address is loopback or unspecified.

        Args:
            address: Address text.

        Returns:
            ``True`` for loopback, unspecified, or empty addresses.
        """
        return address.startswith(("127.", "::1", "0.0.0.0", "[::]", "*"))

    def _parse(
        self, output: str, pids: Mapping[int, str]
    ) -> list[dict[str, Any]]:
        """Parse ``netstat -ano`` output for the agent's processes.

        Args:
            output: Raw command output.
            pids: Agent process ids mapped to image names.

        Returns:
            One record per matching connection.
        """
        records: list[dict[str, Any]] = []
        for line in output.splitlines():
            parts = line.split()
            if len(parts) < 4 or parts[0] not in ("TCP", "UDP"):
                continue
            try:
                pid = int(parts[-1])
            except ValueError:
                continue
            if pid not in pids:
                continue
            local, remote = parts[1], parts[2]
            state = parts[3] if parts[0] == "TCP" and len(parts) >= 5 else "-"
            records.append(
                {
                    "protocol": parts[0],
                    "process": pids[pid],
                    "pid": pid,
                    "local_address": self._host(local),
                    "local_port": self._port(local),
                    "remote_address": self._host(remote),
                    "remote_port": self._port(remote),
                    "state": state,
                }
            )
        return records

    @staticmethod
    def _host(endpoint: str) -> str:
        """Extract the host part of an ``address:port`` string.

        Args:
            endpoint: Endpoint text, possibly bracketed IPv6.

        Returns:
            The host portion.
        """
        if endpoint.startswith("["):
            return endpoint.split("]", 1)[0] + "]"
        return endpoint.rsplit(":", 1)[0] if ":" in endpoint else endpoint

    @staticmethod
    def _port(endpoint: str) -> int | None:
        """Extract the port part of an ``address:port`` string.

        Args:
            endpoint: Endpoint text.

        Returns:
            The port, or ``None`` when absent or unparseable.
        """
        tail = endpoint.rsplit(":", 1)
        if len(tail) != 2:
            return None
        try:
            return int(tail[1])
        except ValueError:
            return None

    def _evidence(self, summary: str, data: Mapping[str, Any]) -> Evidence:
        """Build a network-state evidence record.

        Args:
            summary: Human-readable statement.
            data: Structured detail.

        Returns:
            The evidence.
        """
        return Evidence(
            evidence_id=EV_NETWORK_STATE,
            layer=EvidenceLayer.SYNCHRONIZATION,
            source="synchronization:network",
            summary=summary,
            collector=self.name,
            reliability=SourceReliability.MEDIUM,
            data=dict(data),
        )
