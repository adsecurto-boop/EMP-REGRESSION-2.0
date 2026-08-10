"""Hashing helpers.

Hashes give evidence artifacts stable identities: two collected artifacts can be
compared, and a report can cite an artifact without embedding it. Baseline
comparison (``baselines/`` versus a fresh observation) is the primary use.

SHA-256 is the default. These helpers are for integrity and identity only, never
for password or credential handling -- the framework does not handle credentials
at all.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from framework.shared.exceptions import FrameworkError

__all__ = [
    "DEFAULT_ALGORITHM",
    "hash_bytes",
    "hash_text",
    "hash_file",
    "hash_mapping",
    "short_hash",
]

DEFAULT_ALGORITHM = "sha256"
_CHUNK_SIZE = 1024 * 1024


def _new_digest(algorithm: str) -> "hashlib._Hash":
    """Create a hash object.

    Args:
        algorithm: Algorithm name recognised by :mod:`hashlib`.

    Returns:
        A new hash object.

    Raises:
        FrameworkError: If the algorithm is unavailable.
    """
    try:
        return hashlib.new(algorithm)
    except ValueError as exc:
        raise FrameworkError(
            "Unsupported hash algorithm", {"algorithm": algorithm}
        ) from exc


def hash_bytes(data: bytes, *, algorithm: str = DEFAULT_ALGORITHM) -> str:
    """Hash a byte string.

    Args:
        data: Bytes to hash.
        algorithm: Hash algorithm.

    Returns:
        The hex digest.

    Raises:
        FrameworkError: If the algorithm is unavailable.
    """
    digest = _new_digest(algorithm)
    digest.update(data)
    return digest.hexdigest()


def hash_text(text: str, *, algorithm: str = DEFAULT_ALGORITHM) -> str:
    """Hash text as UTF-8.

    Args:
        text: Text to hash.
        algorithm: Hash algorithm.

    Returns:
        The hex digest.
    """
    return hash_bytes(text.encode("utf-8"), algorithm=algorithm)


def hash_file(path: Path | str, *, algorithm: str = DEFAULT_ALGORITHM) -> str:
    """Hash a file's contents, reading in chunks.

    Chunked so that large artifacts (screen recordings, database copies) do not
    have to be held in memory.

    Args:
        path: File to hash.
        algorithm: Hash algorithm.

    Returns:
        The hex digest.

    Raises:
        FrameworkError: If the file cannot be read or the algorithm is
            unavailable.
    """
    target = Path(path)
    digest = _new_digest(algorithm)
    try:
        with target.open("rb") as handle:
            while chunk := handle.read(_CHUNK_SIZE):
                digest.update(chunk)
    except OSError as exc:
        raise FrameworkError(
            "File could not be read for hashing", {"path": str(target)}
        ) from exc
    return digest.hexdigest()


def hash_mapping(
    mapping: Mapping[str, Any], *, algorithm: str = DEFAULT_ALGORITHM
) -> str:
    """Hash a mapping deterministically.

    Keys are sorted so that logically equal mappings hash equally regardless of
    insertion order -- without this, comparing two observations of the same
    structured state would produce spurious differences.

    Args:
        mapping: Mapping to hash.
        algorithm: Hash algorithm.

    Returns:
        The hex digest.
    """
    canonical = json.dumps(mapping, sort_keys=True, separators=(",", ":"), default=str)
    return hash_text(canonical, algorithm=algorithm)


def short_hash(value: str, *, length: int = 12) -> str:
    """Return a shortened hash of text, for identifiers and filenames.

    Args:
        value: Text to hash.
        length: Number of hex characters to keep.

    Returns:
        The truncated hex digest. Not collision-proof; use only where a
        collision is inconvenient rather than incorrect.
    """
    return hash_text(value)[:length]
