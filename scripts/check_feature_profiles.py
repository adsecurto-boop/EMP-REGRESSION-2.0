"""Feature profile integrity check.

Guards ``config/features.json`` against three classes of defect that are invisible on
inspection and silently disable validation:

1. **Control characters where a backslash belongs.** Real EmpMonitor configuration keys
   contain backslashes (``settings/data\\trackingMode``). Written in JSON with a single
   backslash, ``\\t`` is a **TAB** and the key can never match. This has happened once
   already: the tab form is a valid escape in most languages, so nothing warns. It is
   the reason this checker exists.
2. **Dangling references.** A profile citing an evidence source that is not in the
   Evidence Catalog, or a dashboard page that is not in the navigation model.
3. **Structural problems.** Duplicate feature ids, malformed ids, unknown verification
   statuses.

Run it after editing feature profiles::

    python scripts/check_feature_profiles.py

Exit 0 means the profiles are sound; 1 means the output names every problem.

Dependency-free and framework-free by design: it must run in a bare checkout, and a
checker that imported what it checks could be broken by the same edit it exists to catch.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PROFILES_PATH = REPOSITORY_ROOT / "config" / "features.json"
FRAMEWORK_CONFIG = REPOSITORY_ROOT / "config" / "framework.json"
NAVIGATION_PATH = REPOSITORY_ROOT / "docs" / "design" / "Dashboard_Navigation.md"

_FEATURE_ID = re.compile(r"^EM\d{3}_[A-Za-z0-9]+$")
_VALID_STATUS = {"Verified", "Partially Verified", "Hypothesis", "Deprecated"}
_PAGE_IDENTIFIER = re.compile(r"^\|\s*\d+\s*\|\s*`(?P<page>[a-z_]+)`")


def _read_json(path: Path) -> dict:
    """Read a JSON file.

    Args:
        path: File to read.

    Returns:
        The parsed document.

    Raises:
        SystemExit: If it cannot be read or parsed.
    """
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"cannot read {path}: {exc}") from exc


def known_pages() -> set[str]:
    """Extract page identifiers from the navigation specification.

    Returns:
        The page identifiers, or an empty set when the document is unreadable -- in
        which case page checks are skipped rather than reported as failures.
    """
    try:
        text = NAVIGATION_PATH.read_text(encoding="utf-8")
    except OSError:
        return set()
    return {
        match.group("page")
        for line in text.splitlines()
        if (match := _PAGE_IDENTIFIER.match(line))
    }


def _describe_control_characters(value: str) -> str | None:
    """Describe any control character in a string.

    Args:
        value: String to inspect.

    Returns:
        A human-readable description, or ``None`` when the string is clean.
    """
    # Control characters have no Unicode name, so unicodedata would report "UNNAMED" --
    # useless to whoever has to fix it. Name the ones a mis-escaped key actually
    # produces, and say which escape caused each.
    names = {
        "\t": "TAB (you wrote \\t where you meant \\\\t)",
        "\n": "NEWLINE (you wrote \\n where you meant \\\\n)",
        "\r": "CARRIAGE RETURN (you wrote \\r where you meant \\\\r)",
        "\b": "BACKSPACE (you wrote \\b where you meant \\\\b)",
        "\f": "FORM FEED (you wrote \\f where you meant \\\\f)",
        "\v": "VERTICAL TAB (you wrote \\v where you meant \\\\v)",
        "\a": "BELL (you wrote \\a where you meant \\\\a)",
    }
    found = [
        f"{names.get(char, unicodedata.name(char, 'control character'))} "
        f"(U+{ord(char):04X}) at position {index}"
        for index, char in enumerate(value)
        if ord(char) < 32
    ]
    return "; ".join(found) if found else None


def check() -> list[str]:
    """Check the feature profiles.

    Returns:
        One message per problem, empty when the profiles are sound.
    """
    profiles_document = _read_json(PROFILES_PATH)
    profiles = profiles_document.get("profiles")
    if not isinstance(profiles, list):
        return ["config/features.json has no 'profiles' list"]

    catalog_ids = {
        str(entry.get("id"))
        for entry in (_read_json(FRAMEWORK_CONFIG).get("evidence") or {}).get("sources", [])
        if entry.get("id")
    }
    pages = known_pages()
    problems: list[str] = []
    seen: set[str] = set()

    for profile in profiles:
        feature_id = str(profile.get("feature_id") or "<missing>")

        if not _FEATURE_ID.match(feature_id):
            problems.append(f"{feature_id}: id is not of the form EM<NNN>_<Name>")
        if feature_id in seen:
            problems.append(f"{feature_id}: duplicate feature id")
        seen.add(feature_id)

        status = str(profile.get("verification_status") or "")
        if status not in _VALID_STATUS:
            problems.append(
                f"{feature_id}: unknown verification_status {status!r} "
                f"(expected one of {sorted(_VALID_STATUS)})"
            )

        # The defect this checker exists for.
        key_fields = list(profile.get("required_configuration") or [])
        if interval := profile.get("expected_upload_interval_key"):
            key_fields.append(interval)
        for key in key_fields:
            if (description := _describe_control_characters(str(key))) is not None:
                problems.append(
                    f"{feature_id}: configuration key contains a control character -- "
                    f"{description}. A backslash in JSON must be written '\\\\\\\\'; a "
                    f"single '\\\\t' is a TAB and the key can never match. Key: {key!r}"
                )

        for evidence_id in profile.get("expected_evidence") or []:
            if catalog_ids and str(evidence_id) not in catalog_ids:
                problems.append(
                    f"{feature_id}: cites {evidence_id}, which is not registered in the "
                    "Evidence Catalog config mirror"
                )

        for page in profile.get("expected_dashboard_pages") or []:
            if pages and str(page) not in pages:
                problems.append(
                    f"{feature_id}: references dashboard page {page!r}, which is not in "
                    "docs/design/Dashboard_Navigation.md"
                )
    return problems


def main() -> int:
    """Run the check.

    Returns:
        ``0`` when sound, ``1`` when problems were found.
    """
    profiles = _read_json(PROFILES_PATH).get("profiles") or []
    pages = known_pages()
    print(f"config/features.json          : {len(profiles)} profile(s)")
    print(f"Dashboard_Navigation.md       : {len(pages)} page(s)")

    problems = check()
    if not problems:
        print(f"\nOK - all {len(profiles)} profile(s) are sound.")
        return 0

    print(f"\nPROBLEMS - {len(problems)} found:\n")
    for problem in problems:
        print(f"  - {problem}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
