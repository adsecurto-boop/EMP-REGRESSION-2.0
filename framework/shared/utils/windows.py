"""Generic Windows and host OS inspection helpers.

Reads host state -- OS identity, services, processes, disk, DNS, file signatures,
registry -- using the standard library and the OS's own tools. It knows nothing
about EmpMonitor: no product paths, service names, or process names appear here.
Product facts reach collectors through configuration.

**Every function degrades rather than raises.** A value that could not be
determined is returned as ``None`` (or an empty result), never as a fabricated
number. A collector must be able to record "not measured" as an honest
observation, and absence of a measurement is not the same as a measurement of
absence.

**On shelling out.** Windows exposes service and process state through ``sc.exe``,
``tasklist``, and PowerShell rather than through the Python standard library. This
module wraps those tools; it does not implement product behaviour with them. All
invocations are argument-list based (never ``shell=True``), time-bounded, and
read-only.

Importable on any platform: Windows-only facilities are probed at call time and
report unavailability off Windows, so the framework still imports and tests still
run elsewhere.
"""

from __future__ import annotations

import csv
import io
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from framework.shared.logger import get_logger

__all__ = [
    "CommandResult",
    "ServiceInfo",
    "ProcessInfo",
    "is_windows",
    "run_command",
    "os_information",
    "boot_time",
    "uptime_seconds",
    "time_zone_name",
    "current_user",
    "query_service",
    "list_processes",
    "find_processes",
    "disk_free_bytes",
    "path_permissions",
    "resolve_host",
    "check_internet",
    "clock_drift_seconds",
    "file_signature",
    "file_version_info",
    "read_registry_value",
]

_LOGGER = get_logger(__name__)
_DEFAULT_TIMEOUT = 20.0


def is_windows() -> bool:
    """Whether the host is Windows."""
    return sys.platform == "win32"


@dataclass(frozen=True, slots=True)
class CommandResult:
    """The outcome of running an external command.

    Args:
        command: Argument list executed.
        returncode: Process exit code, or ``None`` if it never ran.
        stdout: Captured standard output.
        stderr: Captured standard error.
        error: Why the command could not be run, if it could not.
        elapsed_seconds: How long it took.
    """

    command: Sequence[str]
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""
    error: str | None = None
    elapsed_seconds: float = 0.0

    @property
    def ok(self) -> bool:
        """Whether the command ran and exited successfully."""
        return self.error is None and self.returncode == 0


def run_command(
    command: Sequence[str], *, timeout: float = _DEFAULT_TIMEOUT
) -> CommandResult:
    """Run a read-only external command and capture its output.

    Never uses a shell, so no argument can be reinterpreted as shell syntax. A
    missing executable, a timeout, or a non-zero exit is reported in the result
    rather than raised: for an observing framework, "the tool is not available" is
    an observation to record.

    Args:
        command: Argument list. The first element is the executable.
        timeout: Seconds to allow before abandoning the command.

    Returns:
        The command result.
    """
    started = time.perf_counter()
    executable = shutil.which(command[0]) if command else None
    if executable is None:
        return CommandResult(
            command=tuple(command),
            error=f"executable not found: {command[0] if command else '(empty)'}",
            elapsed_seconds=time.perf_counter() - started,
        )
    try:
        completed = subprocess.run(  # noqa: S603 -- argument list, no shell, read-only
            [executable, *command[1:]],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        return CommandResult(
            command=tuple(command),
            error=f"timed out after {timeout}s",
            elapsed_seconds=time.perf_counter() - started,
        )
    except OSError as exc:
        return CommandResult(
            command=tuple(command),
            error=f"could not run: {exc}",
            elapsed_seconds=time.perf_counter() - started,
        )
    return CommandResult(
        command=tuple(command),
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
        elapsed_seconds=time.perf_counter() - started,
    )


def _powershell(script: str, *, timeout: float = _DEFAULT_TIMEOUT) -> CommandResult:
    """Run a read-only PowerShell expression.

    Used only where Windows exposes state no standard-library call reaches (service
    recovery settings, Authenticode signatures). ``-NoProfile`` keeps host profile
    configuration from altering behaviour.

    Args:
        script: Expression to evaluate.
        timeout: Seconds to allow.

    Returns:
        The command result.
    """
    return run_command(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ],
        timeout=timeout,
    )


def os_information() -> dict[str, Any]:
    """Collect operating system identity.

    Returns:
        A mapping of OS facts. Windows-specific fields are ``None`` elsewhere.
    """
    info: dict[str, Any] = {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "architecture": platform.architecture()[0],
        "python_version": platform.python_version(),
        "node": platform.node(),
        "edition": None,
        "build": None,
        "is_64bit": sys.maxsize > 2**32,
    }
    if not is_windows():
        return info
    release = platform.win32_ver()
    info["build"] = release[1] if len(release) > 1 else None
    try:
        info["edition"] = platform.win32_edition()
    except (AttributeError, OSError):  # pragma: no cover -- older interpreters
        info["edition"] = None
    # ver reports the full build including revision, which win32_ver truncates.
    result = run_command(["cmd.exe", "/c", "ver"], timeout=5)
    if result.ok:
        info["version_string"] = result.stdout.strip()
    return info


def boot_time() -> datetime | None:
    """Return the host's boot time in UTC.

    Returns:
        Boot time, or ``None`` if it could not be determined.
    """
    if hasattr(time, "clock_gettime") and hasattr(time, "CLOCK_BOOTTIME"):
        try:  # pragma: no cover -- POSIX path
            uptime = time.clock_gettime(time.CLOCK_BOOTTIME)
            return datetime.now(timezone.utc).fromtimestamp(
                time.time() - uptime, tz=timezone.utc
            )
        except OSError:
            pass
    if not is_windows():
        return None
    result = _powershell(
        "(Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToUniversalTime()"
        ".ToString('o')",
        timeout=15,
    )
    if not result.ok or not result.stdout.strip():
        return None
    try:
        parsed = datetime.fromisoformat(result.stdout.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def uptime_seconds() -> float | None:
    """Return host uptime in seconds.

    Returns:
        Uptime, or ``None`` if it could not be determined.
    """
    booted = boot_time()
    if booted is None:
        return None
    return (datetime.now(timezone.utc) - booted).total_seconds()


def time_zone_name() -> str:
    """Return the host's local time zone name."""
    local = datetime.now().astimezone()
    return local.tzname() or time.tzname[0]


def current_user() -> str | None:
    """Return the account the process runs as.

    Returns:
        The username, or ``None`` if it could not be determined.
    """
    for variable in ("USERNAME", "USER", "LOGNAME"):
        value = os.environ.get(variable)
        if value:
            return value
    try:
        import getpass  # noqa: PLC0415 -- fallback only

        return getpass.getuser()
    except Exception:  # noqa: BLE001 -- depends on host account setup
        return None


@dataclass(frozen=True, slots=True)
class ServiceInfo:
    """Observed state of a Windows service.

    Args:
        name: Service short name.
        display_name: Display name.
        found: Whether the service exists.
        state: Reported state, e.g. ``"RUNNING"``.
        start_type: Startup type, e.g. ``"AUTO_START"``.
        binary_path: Service executable path.
        process_id: Owning process id, when running.
        recovery: Recovery/failure-action settings, when readable.
        raw: Raw tool output, retained as evidence of what was actually read.
    """

    name: str
    display_name: str | None = None
    found: bool = False
    state: str | None = None
    start_type: str | None = None
    binary_path: str | None = None
    process_id: int | None = None
    recovery: Mapping[str, Any] = field(default_factory=dict)
    raw: str = ""

    @property
    def is_running(self) -> bool:
        """Whether the service reports a running state."""
        return (self.state or "").upper().startswith("RUNNING")


def _parse_sc_output(text: str) -> dict[str, str]:
    """Parse ``sc.exe`` key/value output.

    Args:
        text: Raw command output.

    Returns:
        A mapping of normalised key to value.
    """
    parsed: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().upper().replace(" ", "_")
        if key:
            parsed[key] = value.strip()
    return parsed


def query_service(name: str, *, timeout: float = _DEFAULT_TIMEOUT) -> ServiceInfo:
    """Query a Windows service by short or display name.

    Args:
        name: Service short name, or display name as a fallback.
        timeout: Seconds to allow per command.

    Returns:
        The observed service state. ``found`` is ``False`` when the service does
        not exist or the host is not Windows.
    """
    if not is_windows():
        return ServiceInfo(name=name, raw="not a Windows host")

    query = run_command(["sc.exe", "queryex", name], timeout=timeout)
    if not query.ok:
        # Fall back to resolving a display name to its short name.
        lookup = _powershell(
            f"(Get-Service -DisplayName '{name}' -ErrorAction SilentlyContinue).Name",
            timeout=timeout,
        )
        resolved = lookup.stdout.strip() if lookup.ok else ""
        if not resolved:
            return ServiceInfo(
                name=name,
                found=False,
                raw=(query.stdout or query.stderr or query.error or "").strip(),
            )
        return query_service(resolved, timeout=timeout)

    fields = _parse_sc_output(query.stdout)
    config = run_command(["sc.exe", "qc", name], timeout=timeout)
    config_fields = _parse_sc_output(config.stdout) if config.ok else {}
    failure = run_command(["sc.exe", "qfailure", name], timeout=timeout)
    recovery = _parse_sc_output(failure.stdout) if failure.ok else {}

    pid_text = fields.get("PID", "")
    try:
        process_id = int(pid_text) or None
    except ValueError:
        process_id = None

    return ServiceInfo(
        name=name,
        display_name=config_fields.get("DISPLAY_NAME"),
        found=True,
        state=fields.get("STATE", "").split(maxsplit=1)[-1] or None
        if fields.get("STATE")
        else None,
        start_type=config_fields.get("START_TYPE"),
        binary_path=config_fields.get("BINARY_PATH_NAME"),
        process_id=process_id,
        recovery=recovery,
        raw=query.stdout.strip(),
    )


@dataclass(frozen=True, slots=True)
class ProcessInfo:
    """Observed state of a running process.

    Args:
        name: Image name.
        pid: Process id.
        memory_bytes: Working-set size, when readable.
        cpu_seconds: CPU time consumed, when readable.
        thread_count: Thread count, when readable.
        handle_count: Handle count, when readable.
        start_time: Process start time in UTC, when readable.
        parent_pid: Parent process id, when readable.
        executable_path: Image path, when readable.
    """

    name: str
    pid: int
    memory_bytes: int | None = None
    cpu_seconds: float | None = None
    thread_count: int | None = None
    handle_count: int | None = None
    start_time: datetime | None = None
    parent_pid: int | None = None
    executable_path: str | None = None


def _parse_tasklist_csv(text: str) -> list[dict[str, str]]:
    """Parse ``tasklist /fo csv`` output.

    Args:
        text: Raw CSV output.

    Returns:
        One mapping per row.
    """
    try:
        reader = csv.DictReader(io.StringIO(text))
        return [row for row in reader if row.get("Image Name")]
    except csv.Error:
        return []


def list_processes(*, timeout: float = _DEFAULT_TIMEOUT) -> tuple[ProcessInfo, ...]:
    """List running processes with as much detail as the host will report.

    Prefers PowerShell, which exposes threads, handles, parent, and start time in
    one pass; falls back to ``tasklist``, which reports only name, pid, and memory.
    Partial detail is recorded as partial detail -- unavailable fields stay ``None``.

    Args:
        timeout: Seconds to allow per command.

    Returns:
        The observed processes, empty when none could be read.
    """
    if not is_windows():
        return ()

    script = (
        "Get-CimInstance Win32_Process | "
        "Select-Object Name,ProcessId,ParentProcessId,WorkingSetSize,ThreadCount,"
        "HandleCount,CreationDate,ExecutablePath,UserModeTime,KernelModeTime | "
        "ConvertTo-Json -Compress -Depth 2"
    )
    result = _powershell(script, timeout=max(timeout, 30))
    if result.ok and result.stdout.strip():
        import json  # noqa: PLC0415 -- only needed on this path

        try:
            payload = json.loads(result.stdout)
        except (ValueError, TypeError):
            payload = None
        if payload is not None:
            rows = payload if isinstance(payload, list) else [payload]
            processes: list[ProcessInfo] = []
            for row in rows:
                if not isinstance(row, Mapping):
                    continue
                processes.append(
                    ProcessInfo(
                        name=str(row.get("Name") or ""),
                        pid=int(row.get("ProcessId") or 0),
                        memory_bytes=_as_int(row.get("WorkingSetSize")),
                        cpu_seconds=_cpu_seconds(
                            row.get("UserModeTime"), row.get("KernelModeTime")
                        ),
                        thread_count=_as_int(row.get("ThreadCount")),
                        handle_count=_as_int(row.get("HandleCount")),
                        start_time=_parse_cim_date(row.get("CreationDate")),
                        parent_pid=_as_int(row.get("ParentProcessId")),
                        executable_path=row.get("ExecutablePath") or None,
                    )
                )
            if processes:
                return tuple(processes)

    fallback = run_command(["tasklist.exe", "/fo", "csv"], timeout=timeout)
    if not fallback.ok:
        _LOGGER.debug("Process listing unavailable: %s", fallback.error or fallback.stderr)
        return ()
    processes = []
    for row in _parse_tasklist_csv(fallback.stdout):
        try:
            pid = int(row.get("PID", "0"))
        except ValueError:
            continue
        processes.append(
            ProcessInfo(
                name=row.get("Image Name", ""),
                pid=pid,
                memory_bytes=_parse_memory(row.get("Mem Usage")),
            )
        )
    return tuple(processes)


def _as_int(value: Any) -> int | None:
    """Coerce a value to ``int``, or ``None`` when it cannot be.

    Args:
        value: Value to coerce.

    Returns:
        The integer, or ``None``.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _cpu_seconds(user: Any, kernel: Any) -> float | None:
    """Convert Windows 100-nanosecond CPU ticks into seconds.

    Args:
        user: User-mode time in 100 ns units.
        kernel: Kernel-mode time in 100 ns units.

    Returns:
        Total CPU seconds, or ``None`` if neither was readable.
    """
    total = 0
    seen = False
    for value in (user, kernel):
        parsed = _as_int(value)
        if parsed is not None:
            total += parsed
            seen = True
    return total / 10_000_000 if seen else None


def _parse_cim_date(value: Any) -> datetime | None:
    """Parse a CIM/WMI date into an aware UTC datetime.

    Args:
        value: Date value, either ISO 8601 or WMI ``yyyymmddHHMMSS.ffffff+ooo``.

    Returns:
        The parsed time, or ``None``.
    """
    if not value:
        return None
    text = str(value)
    if "/Date(" in text:  # JSON serialisation of a .NET date
        digits = "".join(char for char in text if char.isdigit() or char == "-")
        millis = _as_int(digits)
        if millis is None:
            return None
        return datetime.fromtimestamp(millis / 1000, tz=timezone.utc)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        pass
    else:
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    if len(text) >= 14 and text[:14].isdigit():
        try:
            naive = datetime.strptime(text[:14], "%Y%m%d%H%M%S")
        except ValueError:
            return None
        return naive.replace(tzinfo=timezone.utc)
    return None


def _parse_memory(value: str | None) -> int | None:
    """Parse a ``tasklist`` memory figure such as ``"12,345 K"`` into bytes.

    Args:
        value: Raw text.

    Returns:
        Bytes, or ``None``.
    """
    if not value:
        return None
    digits = "".join(char for char in value if char.isdigit())
    parsed = _as_int(digits)
    return parsed * 1024 if parsed is not None else None


def find_processes(
    names: Sequence[str], *, processes: Sequence[ProcessInfo] | None = None
) -> dict[str, tuple[ProcessInfo, ...]]:
    """Group observed processes by the requested image names.

    Args:
        names: Image names to look for, matched case-insensitively.
        processes: Pre-collected process list, to avoid re-querying the host.

    Returns:
        A mapping of each requested name to the matching processes, present even
        when empty so a caller can distinguish "asked and found none" from
        "never asked".
    """
    observed = processes if processes is not None else list_processes()
    grouped: dict[str, tuple[ProcessInfo, ...]] = {}
    for name in names:
        wanted = name.lower()
        grouped[name] = tuple(
            item for item in observed if item.name.lower() == wanted
        )
    return grouped


def disk_free_bytes(path: Path | str) -> int | None:
    """Return free space on the filesystem holding a path.

    Args:
        path: Any existing path on the filesystem of interest.

    Returns:
        Free bytes, or ``None`` if it could not be determined.
    """
    try:
        return shutil.disk_usage(os.fspath(path)).free
    except OSError:
        return None


def path_permissions(path: Path | str) -> dict[str, Any]:
    """Report the process's effective access to a path.

    Reports what *this process* can do, which is what matters for validation --
    a full ACL listing would describe rights the framework may not hold.

    Args:
        path: Path to test.

    Returns:
        A mapping of access facts.
    """
    target = Path(path)
    exists = target.exists()
    return {
        "exists": exists,
        "readable": os.access(target, os.R_OK) if exists else False,
        "writable": os.access(target, os.W_OK) if exists else False,
        "executable": os.access(target, os.X_OK) if exists else False,
        "is_directory": target.is_dir() if exists else False,
    }


def resolve_host(hostname: str, *, timeout: float = 5.0) -> dict[str, Any]:
    """Attempt DNS resolution of a hostname.

    Args:
        hostname: Name to resolve.
        timeout: Socket timeout in seconds.

    Returns:
        A mapping describing the attempt, including addresses on success and the
        error on failure. Failure is data, not an exception.
    """
    previous = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)
    started = time.perf_counter()
    try:
        _, _, addresses = socket.gethostbyname_ex(hostname)
        return {
            "hostname": hostname,
            "resolved": True,
            "addresses": addresses,
            "elapsed_seconds": time.perf_counter() - started,
        }
    except (OSError, socket.gaierror) as exc:
        return {
            "hostname": hostname,
            "resolved": False,
            "addresses": [],
            "error": str(exc),
            "elapsed_seconds": time.perf_counter() - started,
        }
    finally:
        socket.setdefaulttimeout(previous)


def check_internet(
    hosts: Sequence[str] = ("www.microsoft.com",), *, port: int = 443, timeout: float = 5.0
) -> dict[str, Any]:
    """Test outbound connectivity by opening a TCP connection.

    Deliberately not an HTTP request: this establishes that the host has outbound
    network access, not that any particular service is reachable or healthy.

    Args:
        hosts: Hostnames to try, in order.
        port: TCP port to connect to.
        timeout: Per-host timeout in seconds.

    Returns:
        A mapping describing the attempts.
    """
    attempts: list[dict[str, Any]] = []
    for host in hosts:
        started = time.perf_counter()
        try:
            with socket.create_connection((host, port), timeout=timeout):
                attempts.append(
                    {
                        "host": host,
                        "port": port,
                        "connected": True,
                        "elapsed_seconds": time.perf_counter() - started,
                    }
                )
                return {"available": True, "attempts": attempts}
        except OSError as exc:
            attempts.append(
                {
                    "host": host,
                    "port": port,
                    "connected": False,
                    "error": str(exc),
                    "elapsed_seconds": time.perf_counter() - started,
                }
            )
    return {"available": False, "attempts": attempts}


def clock_drift_seconds(*, timeout: float = 8.0) -> dict[str, Any]:
    """Estimate local clock drift against the configured Windows time source.

    Uses ``w32tm /stripchart``, the OS's own comparison against its time source, so
    the framework does not have to become an NTP client. When the tool or the source
    is unavailable, drift is ``None`` -- unknown drift is reported as unknown.

    Args:
        timeout: Seconds to allow.

    Returns:
        A mapping with ``drift_seconds`` (possibly ``None``), the local time, and
        any error.
    """
    local = datetime.now(timezone.utc)
    outcome: dict[str, Any] = {
        "local_time_utc": local.isoformat(),
        "time_zone": time_zone_name(),
        "drift_seconds": None,
        "source": None,
    }
    if not is_windows():
        outcome["error"] = "not a Windows host"
        return outcome

    result = run_command(
        ["w32tm.exe", "/stripchart", "/computer:time.windows.com", "/samples:1", "/dataonly"],
        timeout=timeout,
    )
    if not result.ok:
        outcome["error"] = (result.error or result.stderr or "w32tm unavailable").strip()
        return outcome
    outcome["source"] = "time.windows.com"
    for line in result.stdout.splitlines():
        marker = line.strip()
        if "," not in marker:
            continue
        offset_text = marker.rsplit(",", 1)[-1].strip().rstrip("s")
        try:
            outcome["drift_seconds"] = float(offset_text.replace("+", ""))
        except ValueError:
            continue
        else:
            break
    if outcome["drift_seconds"] is None:
        outcome["error"] = "w32tm returned no comparable sample"
    return outcome


def file_signature(path: Path | str, *, timeout: float = _DEFAULT_TIMEOUT) -> dict[str, Any]:
    """Read a file's Authenticode signature status.

    Args:
        path: File to inspect.
        timeout: Seconds to allow.

    Returns:
        A mapping with ``status``, ``signer``, and ``available``. ``available`` is
        ``False`` when signature status could not be read at all, which is distinct
        from a file that is genuinely unsigned.
    """
    target = Path(path)
    if not is_windows() or not target.is_file():
        return {"available": False, "status": None, "signer": None}
    escaped = str(target).replace("'", "''")
    result = _powershell(
        f"$s = Get-AuthenticodeSignature -LiteralPath '{escaped}'; "
        "\"$($s.Status)|$($s.SignerCertificate.Subject)\"",
        timeout=timeout,
    )
    if not result.ok or "|" not in result.stdout:
        return {"available": False, "status": None, "signer": None}
    status, _, signer = result.stdout.strip().partition("|")
    return {
        "available": True,
        "status": status.strip() or None,
        "signer": signer.strip() or None,
    }


def file_version_info(path: Path | str, *, timeout: float = _DEFAULT_TIMEOUT) -> dict[str, Any]:
    """Read a file's version resource.

    Args:
        path: File to inspect.
        timeout: Seconds to allow.

    Returns:
        A mapping of version fields; values are ``None`` when unreadable.
    """
    target = Path(path)
    empty = {
        "file_version": None,
        "product_version": None,
        "product_name": None,
        "company": None,
        "file_build_part": None,
    }
    if not is_windows() or not target.is_file():
        return empty
    escaped = str(target).replace("'", "''")
    result = _powershell(
        f"$i = (Get-Item -LiteralPath '{escaped}').VersionInfo; "
        "\"$($i.FileVersion)|$($i.ProductVersion)|$($i.ProductName)|"
        "$($i.CompanyName)|$($i.FileBuildPart)\"",
        timeout=timeout,
    )
    if not result.ok or "|" not in result.stdout:
        return empty
    parts = [piece.strip() or None for piece in result.stdout.strip().split("|")]
    parts += [None] * (5 - len(parts))
    return {
        "file_version": parts[0],
        "product_version": parts[1],
        "product_name": parts[2],
        "company": parts[3],
        "file_build_part": parts[4],
    }


def read_registry_value(
    root: str, key_path: str, value_name: str | None = None
) -> dict[str, Any]:
    """Read a Windows registry value.

    Args:
        root: Hive name, e.g. ``"HKLM"``, ``"HKCU"``, ``"HKEY_LOCAL_MACHINE"``.
        key_path: Key path beneath the hive.
        value_name: Value to read; the key's default value when omitted.

    Returns:
        A mapping describing the read, including ``found`` and ``value``. A missing
        key is reported, never raised.
    """
    outcome: dict[str, Any] = {
        "root": root,
        "key": key_path,
        "value_name": value_name,
        "found": False,
        "value": None,
    }
    if not is_windows():
        outcome["error"] = "not a Windows host"
        return outcome
    try:
        import winreg  # noqa: PLC0415 -- Windows-only standard library
    except ImportError:  # pragma: no cover -- non-Windows
        outcome["error"] = "winreg unavailable"
        return outcome

    hives = {
        "HKLM": winreg.HKEY_LOCAL_MACHINE,
        "HKEY_LOCAL_MACHINE": winreg.HKEY_LOCAL_MACHINE,
        "HKCU": winreg.HKEY_CURRENT_USER,
        "HKEY_CURRENT_USER": winreg.HKEY_CURRENT_USER,
        "HKCR": winreg.HKEY_CLASSES_ROOT,
        "HKEY_CLASSES_ROOT": winreg.HKEY_CLASSES_ROOT,
    }
    hive = hives.get(root.upper())
    if hive is None:
        outcome["error"] = f"unknown registry root: {root}"
        return outcome
    try:
        with winreg.OpenKey(hive, key_path, 0, winreg.KEY_READ) as handle:
            value, kind = winreg.QueryValueEx(handle, value_name or "")
            outcome.update({"found": True, "value": value, "type": kind})
    except FileNotFoundError:
        outcome["error"] = "key or value not found"
    except OSError as exc:
        outcome["error"] = str(exc)
    return outcome
