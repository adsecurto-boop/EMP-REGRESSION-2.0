"""JSON report generator for test execution summary.
"""

import json
from pathlib import Path
from codegen.reporting.models import ExecutionSummary


class JSONReportGenerator:
    """Generates test_results.json report."""

    @staticmethod
    def generate(summary: ExecutionSummary, output_path: Path) -> Path:
        """Write execution summary to test_results.json."""
        data = summary.to_dict()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return output_path
