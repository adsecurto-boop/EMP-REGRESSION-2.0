"""Filesystem helpers.

Generic path and file operations only. No EmpMonitor paths appear here or
anywhere else in the framework: product locations are configuration, per
``docs/ADS/coding_standards.md`` (no hardcoded paths).
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Iterator

from framework.shared.exceptions import FrameworkError

__all__ = [
    "ensure_directory",
    "safe_filename",
    "iter_files",
    "file_size",
    "newest_file",
    "copy_into",
    "repository_root",
]

_UNSAFE_CHARACTERS = '<>:"/\\|?*'


def repository_root() -> Path:
    """Return the repository root directory.

    Derived from this module's location rather than the process working
    directory, so results do not depend on where the framework was launched.

    Returns:
        The repository root path.
    """
    return Path(__file__).resolve().parents[3]


def ensure_directory(path: Path | str) -> Path:
    """Create a directory (and parents) if it does not exist.

    Args:
        path: Directory to create.

    Returns:
        The directory path.

    Raises:
        FrameworkError: If the directory could not be created.
    """
    target = Path(path)
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise FrameworkError(
            "Directory could not be created", {"path": str(target)}
        ) from exc
    return target


def safe_filename(name: str, *, replacement: str = "_", max_length: int = 200) -> str:
    """Convert arbitrary text into a filename safe on Windows and POSIX.

    Args:
        name: Proposed name.
        replacement: Character substituted for unsafe characters.
        max_length: Maximum length of the result.

    Returns:
        A sanitised filename. Empty or all-unsafe input yields ``"unnamed"``, so
        callers never end up building a path from an empty string.
    """
    cleaned = "".join(
        replacement if char in _UNSAFE_CHARACTERS or ord(char) < 32 else char
        for char in name
    ).strip(" .")
    cleaned = cleaned[:max_length]
    return cleaned or "unnamed"


def iter_files(
    root: Path | str, *, pattern: str = "*", recursive: bool = True
) -> Iterator[Path]:
    """Yield files beneath a directory.

    Args:
        root: Directory to walk.
        pattern: Glob pattern to match.
        recursive: Whether to descend into subdirectories.

    Yields:
        Matching file paths. Yields nothing when ``root`` does not exist, so
        callers can treat a missing directory as "no files" rather than an error.
    """
    base = Path(root)
    if not base.is_dir():
        return
    globber = base.rglob if recursive else base.glob
    for candidate in globber(pattern):
        if candidate.is_file():
            yield candidate


def file_size(path: Path | str) -> int:
    """Return a file's size in bytes.

    Args:
        path: File to measure.

    Returns:
        Size in bytes, or ``-1`` if the file does not exist. A sentinel rather
        than an exception because "absent" is a normal observation.
    """
    target = Path(path)
    try:
        return target.stat().st_size
    except OSError:
        return -1


def newest_file(root: Path | str, *, pattern: str = "*") -> Path | None:
    """Return the most recently modified matching file.

    Args:
        root: Directory to search.
        pattern: Glob pattern.

    Returns:
        The newest matching file, or ``None`` if there are none.
    """
    candidates = list(iter_files(root, pattern=pattern))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.stat().st_mtime)


def copy_into(source: Path | str, destination_dir: Path | str) -> Path:
    """Copy a file into a directory, preserving its name and metadata.

    Args:
        source: File to copy.
        destination_dir: Target directory, created if absent.

    Returns:
        The path of the copied file.

    Raises:
        FrameworkError: If the copy fails.
    """
    src = Path(source)
    target_dir = ensure_directory(destination_dir)
    try:
        return Path(shutil.copy2(src, target_dir / src.name))
    except OSError as exc:
        raise FrameworkError(
            "File could not be copied",
            {"source": str(src), "destination": str(target_dir)},
        ) from exc


def is_within(path: Path | str, parent: Path | str) -> bool:
    """Whether ``path`` resolves to a location inside ``parent``.

    Useful for confirming an artifact path stays within the configured output
    root before writing to it.

    Args:
        path: Path to test.
        parent: Directory that should contain it.

    Returns:
        ``True`` if contained.
    """
    try:
        Path(path).resolve().relative_to(Path(parent).resolve())
    except (ValueError, OSError):
        return False
    return True


def free_space_bytes(path: Path | str) -> int:
    """Return free space on the filesystem holding ``path``.

    Args:
        path: Any existing path on the filesystem of interest.

    Returns:
        Free bytes, or ``-1`` if it could not be determined.
    """
    try:
        return shutil.disk_usage(os.fspath(path)).free
    except OSError:
        return -1
