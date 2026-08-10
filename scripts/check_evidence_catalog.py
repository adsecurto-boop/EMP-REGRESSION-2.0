"""Evidence Catalog drift check.

The Evidence Catalog exists twice by design: ``docs/Evidence_Catalog.md`` is
authoritative for humans, and the ``evidence.sources`` block of
``config/framework.json`` is authoritative for the running framework. Nothing
mechanically kept them in step, and the risk was recorded as the highest-severity
long-term defect in the Phase 1 review (§9.1). It then happened: sources were added
to each side independently.

This check closes that gap. It compares the two and reports every divergence:

* a source registered in one and not the other;
* a layer or reliability that disagrees between them;
* a collector attribution that disagrees.

Run it as part of any change that touches either file::

    python scripts/check_evidence_catalog.py

Exit code 0 means the two agree; 1 means they have drifted and the output names
every difference.

Deliberately dependency-free and framework-free: it must be runnable in a bare
checkout, and a checker that imported the thing it checks could be broken by the
same change it is meant to catch.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = REPOSITORY_ROOT / "docs" / "Evidence_Catalog.md"
CONFIG_PATH = REPOSITORY_ROOT / "config" / "framework.json"

#: Matches a registry row: | **EV-001** | Name | ... | Collector | Confidence | L1 | ...
_ROW = re.compile(
    r"^\|\s*\*{0,2}(?P<id>EV-\d{3})\*{0,2}\s*\|"
    r"(?P<name>[^|]*)\|"
    r"(?P<description>[^|]*)\|"
    r"(?P<collector>[^|]*)\|"
    r"(?P<confidence>[^|]*)\|"
    r"\s*L(?P<layer>[1-4])\s*\|",
    re.MULTILINE,
)


def parse_catalog(path: Path) -> dict[str, dict[str, Any]]:
    """Parse the registry table from the catalog document.

    Args:
        path: Path to the catalog markdown.

    Returns:
        A mapping of evidence id to its documented fields.

    Raises:
        SystemExit: If the document cannot be read.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SystemExit(f"cannot read {path}: {exc}") from exc

    entries: dict[str, dict[str, Any]] = {}
    for match in _ROW.finditer(text):
        confidence = match.group("confidence").strip().strip("*")
        # Strip qualifiers such as "High *(target)*".
        confidence = re.sub(r"\*|\(.*?\)", "", confidence).strip()
        entries[match.group("id")] = {
            "name": match.group("name").strip().strip("`*"),
            "collector": match.group("collector").strip().strip("`*"),
            "reliability": confidence.lower(),
            "layer": int(match.group("layer")),
        }
    return entries


def parse_config(path: Path) -> dict[str, dict[str, Any]]:
    """Parse the evidence-source mirror from configuration.

    Args:
        path: Path to ``framework.json``.

    Returns:
        A mapping of evidence id to its configured fields.

    Raises:
        SystemExit: If the file cannot be read or parsed.
    """
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"cannot read {path}: {exc}") from exc

    sources = (payload.get("evidence") or {}).get("sources") or []
    return {
        str(entry.get("id")): {
            "name": str(entry.get("name", "")),
            "collector": str(entry.get("collector", "")),
            "reliability": str(entry.get("reliability", "")).lower(),
            "layer": int(entry.get("layer", 0)),
            "implemented": bool(entry.get("implemented", False)),
        }
        for entry in sources
        if entry.get("id")
    }


def compare(
    catalog: dict[str, dict[str, Any]], config: dict[str, dict[str, Any]]
) -> list[str]:
    """Compare the two registries.

    Layer and reliability must match exactly: they feed the confidence calculation,
    so a disagreement changes computed verdicts. Collector text is compared loosely,
    because the document may name a component while configuration names a file.

    Args:
        catalog: Parsed catalog entries.
        config: Parsed configuration entries.

    Returns:
        One message per divergence, empty when the two agree.
    """
    problems: list[str] = []

    for missing in sorted(set(config) - set(catalog)):
        problems.append(
            f"{missing}: in config/framework.json but NOT in docs/Evidence_Catalog.md "
            "-- the framework would admit evidence no document explains"
        )
    for missing in sorted(set(catalog) - set(config)):
        problems.append(
            f"{missing}: in docs/Evidence_Catalog.md but NOT in config/framework.json "
            "-- the framework would reject evidence the catalog says is valid"
        )

    for evidence_id in sorted(set(catalog) & set(config)):
        documented, configured = catalog[evidence_id], config[evidence_id]
        if documented["layer"] != configured["layer"]:
            problems.append(
                f"{evidence_id}: layer disagrees -- document says L{documented['layer']}, "
                f"config says L{configured['layer']} (this changes corroboration)"
            )
        if documented["reliability"] != configured["reliability"]:
            problems.append(
                f"{evidence_id}: reliability disagrees -- document says "
                f"{documented['reliability']!r}, config says {configured['reliability']!r} "
                "(this changes computed confidence)"
            )
        if not _collectors_agree(documented["collector"], configured["collector"]):
            problems.append(
                f"{evidence_id}: collector attribution disagrees -- document says "
                f"{documented['collector']!r}, config says {configured['collector']!r}"
            )
    return problems


def _collectors_agree(documented: str, configured: str) -> bool:
    """Whether two collector attributions plausibly describe the same component.

    Args:
        documented: Attribution from the catalog.
        configured: Attribution from configuration.

    Returns:
        ``True`` when they share a meaningful token. Prose such as "Synchronization
        Monitor (designed, not in scaffold)" should match
        ``framework/monitors/sync_monitor.py``, so an exact comparison would be
        useless noise rather than a useful signal.
    """
    # "monitor" and "collector" are excluded as well as the directory names: they
    # appear in almost every attribution, so leaving them in would make
    # runtime_monitor.py and executable_monitor.py compare as equal and mask exactly
    # the kind of mis-attribution this check exists to find.
    stopwords = {
        "framework", "monitors", "validators", "designed", "monitor",
        "collector", "scaffold", "implemented",
    }

    def tokens(value: str) -> set[str]:
        return {
            token
            for token in re.split(r"[^a-z0-9]+", value.lower())
            if len(token) > 3 and token not in stopwords
        }

    documented_tokens, configured_tokens = tokens(documented), tokens(configured)
    if not documented_tokens or not configured_tokens:
        return True
    return bool(documented_tokens & configured_tokens)


def main() -> int:
    """Run the check.

    Returns:
        ``0`` when the registries agree, ``1`` when they have drifted.
    """
    catalog = parse_catalog(CATALOG_PATH)
    config = parse_config(CONFIG_PATH)

    print(f"docs/Evidence_Catalog.md : {len(catalog)} source(s)")
    print(f"config/framework.json    : {len(config)} source(s)")

    problems = compare(catalog, config)
    if not problems:
        print(f"\nOK - the two registries agree on all {len(config)} source(s).")
        return 0

    print(f"\nDRIFT DETECTED - {len(problems)} divergence(s):\n")
    for problem in problems:
        print(f"  - {problem}")
    print(
        "\nThe document is authoritative for humans and the config for the running "
        "framework; both must be updated together."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
