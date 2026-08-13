"""Catalog parser for loading test metadata from CODEGEN_TEST_CATALOG.md.
"""

import re
from pathlib import Path
from typing import Dict, Optional
from codegen.reporting.models import TestCaseMetadata, mask_secrets


class CatalogLoader:
    """Parses CODEGEN_TEST_CATALOG.md into TestCaseMetadata objects."""

    def __init__(self, catalog_path: Optional[str] = None):
        if catalog_path is None:
            catalog_path = Path(__file__).parent.parent / "CODEGEN_TEST_CATALOG.md"
        self.catalog_path = Path(catalog_path)
        self.metadata_map: Dict[str, TestCaseMetadata] = {}
        self._load_catalog()

    def _clean_cell(self, text: str) -> str:
        """Strip markdown formatting, backticks, and whitespace."""
        clean = text.strip()
        clean = re.sub(r"^`|`$", "", clean)
        clean = clean.replace("`", "")
        return clean.strip()

    def _load_catalog(self) -> None:
        """Parse markdown table rows into metadata objects."""
        if not self.catalog_path.exists():
            return

        lines = self.catalog_path.read_text(encoding="utf-8").splitlines()
        for line in lines:
            if not line.startswith("|") or "---" in line or "Script" in line:
                continue

            parts = [p.strip() for p in line.split("|")[1:-1]]
            if len(parts) < 7:
                continue

            # Row format: TC ID | Script | Module | Functionality | Preconditions | Test Data | Assertions | Status
            tc_id = self._clean_cell(parts[0])
            script_path = self._clean_cell(parts[1])
            module = self._clean_cell(parts[2])
            functionality = self._clean_cell(parts[3])
            preconditions = self._clean_cell(parts[4])
            test_data_raw = self._clean_cell(parts[5])
            assertions = self._clean_cell(parts[6])

            meta = TestCaseMetadata(
                id=tc_id,
                module=module,
                title=functionality,
                description=functionality,
                test_data=mask_secrets(test_data_raw),
                preconditions=preconditions,
                expected=assertions
            )

            # Store by full relative path and basename
            norm_script = script_path.replace("\\", "/").strip()
            self.metadata_map[norm_script] = meta
            basename = Path(norm_script).name
            self.metadata_map[basename] = meta

    def get_metadata(self, script_key: str, default_title: str = "") -> TestCaseMetadata:
        """Retrieve metadata by script path or filename with fallback defaults."""
        norm_key = script_key.replace("\\", "/").strip()
        basename = Path(norm_key).name

        if norm_key in self.metadata_map:
            return self.metadata_map[norm_key]
        if basename in self.metadata_map:
            return self.metadata_map[basename]

        # Dynamic fallback if not found in catalog
        module_name = Path(norm_key).parent.name.capitalize() if "/" in norm_key else "General"
        tc_id = f"TC-{module_name[:3].upper()}-000"
        return TestCaseMetadata(
            id=tc_id,
            module=module_name,
            title=default_title or basename.replace(".py", "").replace("test_", "").replace("_", " ").title(),
            description=default_title,
            test_data={},
            preconditions="Authenticated Context",
            expected="Execution completes without assertion errors"
        )
