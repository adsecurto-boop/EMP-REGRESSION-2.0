"""Golden Dataset Inspection and Comparison Utilities.

Parses golden datasets, generates test fixtures, and compares runtime collector/validator
outputs against golden benchmarks without silently ignoring mismatches.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

@dataclass(frozen=True, slots=True)
class GoldenDiff:
    """Represents a difference between expected golden data and actual runtime data."""
    field: str
    diff_type: str  # missing, unexpected, changed, mismatched, type_mismatch, timestamp_mismatch
    expected: Any
    actual: Any
    description: str

class GoldenDataset:
    """Reader and comparator for golden benchmark datasets."""

    def __init__(self, data: Mapping[str, Any]) -> None:
        self._data = dict(data)

    @classmethod
    def load_from_file(cls, path: Path | str) -> GoldenDataset:
        target = Path(path)
        if not target.is_file():
            raise FileNotFoundError(f"Golden dataset file not found: {target}")
        payload = json.loads(target.read_text(encoding="utf-8"))
        return cls(payload)

    @property
    def raw(self) -> Mapping[str, Any]:
        return self._data

    def compare(self, actual_data: Mapping[str, Any]) -> tuple[GoldenDiff, ...]:
        """Compare actual runtime data against golden dataset."""
        diffs: list[GoldenDiff] = []
        self._compare_dicts("", self._data, actual_data, diffs)
        return tuple(diffs)

    def _compare_dicts(self, prefix: str, expected: Mapping[str, Any], actual: Mapping[str, Any], diffs: list[GoldenDiff]) -> None:
        for k, exp_val in expected.items():
            field_name = f"{prefix}.{k}" if prefix else k
            if k not in actual:
                diffs.append(
                    GoldenDiff(
                        field=field_name,
                        diff_type="missing",
                        expected=exp_val,
                        actual=None,
                        description=f"Field '{field_name}' expected in golden dataset but missing from actual output"
                    )
                )
                continue

            act_val = actual[k]
            if type(exp_val) != type(act_val) and exp_val is not None and act_val is not None:
                diffs.append(
                    GoldenDiff(
                        field=field_name,
                        diff_type="type_mismatch",
                        expected=str(type(exp_val).__name__),
                        actual=str(type(act_val).__name__),
                        description=f"Type mismatch for '{field_name}': expected {type(exp_val).__name__}, got {type(act_val).__name__}"
                    )
                )
            elif isinstance(exp_val, dict) and isinstance(act_val, dict):
                self._compare_dicts(field_name, exp_val, act_val, diffs)
            elif exp_val != act_val:
                diffs.append(
                    GoldenDiff(
                        field=field_name,
                        diff_type="mismatched",
                        expected=exp_val,
                        actual=act_val,
                        description=f"Value mismatch for '{field_name}': expected {exp_val!r}, got {act_val!r}"
                    )
                )

        for k, act_val in actual.items():
            field_name = f"{prefix}.{k}" if prefix else k
            if k not in expected:
                diffs.append(
                    GoldenDiff(
                        field=field_name,
                        diff_type="unexpected",
                        expected=None,
                        actual=act_val,
                        description=f"Field '{field_name}' present in actual output but absent from golden dataset"
                    )
                )
