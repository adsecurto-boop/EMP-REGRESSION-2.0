"""Golden dataset loading helper for Codegen tests.
"""

import json
from pathlib import Path
from typing import Any, Dict


def load_golden_dataset(path: str = "config/golden_dataset.json") -> Dict[str, Any]:
    """Load the golden dataset JSON configuration."""
    golden_path = Path(path)
    if not golden_path.exists():
        return {}
    with open(golden_path, "r", encoding="utf-8") as f:
        return json.load(f)
