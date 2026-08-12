"""Golden Dataset CLI Comparison & Inspector Tool.

Inspects golden datasets and compares actual collector/validator output against benchmarks.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from framework.shared.utils.golden import GoldenDataset

DEFAULT_GOLDEN_PATH = REPO_ROOT / "config" / "golden_dataset.json"

def ensure_sample_golden() -> Path:
    if not DEFAULT_GOLDEN_PATH.exists():
        DEFAULT_GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        sample = {
            "evidence_catalog": {
                "EV-001": {"layer": "CONFIGURATION", "source": "empm.ini"},
                "EV-005": {"layer": "RUNTIME", "source": "process"},
                "EV-007": {"layer": "DATABASE", "source": "local_db"},
            },
            "system_thresholds": {
                "min_windows_build": 10240,
                "max_clock_drift_seconds": 120
            }
        }
        DEFAULT_GOLDEN_PATH.write_text(json.dumps(sample, indent=2), encoding="utf-8")
    return DEFAULT_GOLDEN_PATH

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="EmpMonitor Golden Dataset Comparator")
    parser.add_argument("--golden", type=str, help="Path to golden dataset file")
    parser.add_argument("--actual", type=str, help="Path to actual output JSON file to compare")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    args = parser.parse_args(argv)

    golden_path = Path(args.golden) if args.golden else ensure_sample_golden()
    
    if not golden_path.is_file():
        print(f"Golden dataset not found at {golden_path}")
        return 1

    dataset = GoldenDataset.load_from_file(golden_path)

    if not args.actual:
        # Just inspect golden dataset
        out = {
            "status": "SUCCESS",
            "golden_file": str(golden_path),
            "keys": list(dataset.raw.keys()),
            "content": dataset.raw
        }
        if args.json:
            print(json.dumps(out, indent=2))
        else:
            print("=== GOLDEN DATASET INSPECTION ===")
            print(f"Golden File: {golden_path}")
            print("Contents:")
            print(json.dumps(dataset.raw, indent=2))
        return 0

    actual_path = Path(args.actual)
    if not actual_path.is_file():
        print(f"Actual data file not found at {actual_path}")
        return 1

    actual_data = json.loads(actual_path.read_text(encoding="utf-8"))
    diffs = dataset.compare(actual_data)

    diff_list = [
        {
            "field": d.field,
            "type": d.diff_type,
            "expected": d.expected,
            "actual": d.actual,
            "description": d.description
        }
        for d in diffs
    ]

    out = {
        "status": "PASSED" if not diffs else "MISMATCHED",
        "golden_file": str(golden_path),
        "actual_file": str(actual_path),
        "total_differences": len(diffs),
        "differences": diff_list,
    }

    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print("=== GOLDEN DATASET COMPARISON RESULT ===")
        print(f"Verdict:           {out['status']}")
        print(f"Total Differences: {len(diffs)}")
        for d in diff_list:
            print(f"  - [{d['type']}] {d['field']}: {d['description']}")
        print("\nJSON Output:")
        print(json.dumps(out, indent=2))

    return 0

if __name__ == "__main__":
    sys.exit(main())
