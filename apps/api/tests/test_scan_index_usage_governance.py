"""API ScanIndex legacy usage governance.

Owner: apps/api runtime integration owners.
Boundary: API production source must not call the retired ScanIndex filename
stem helper API after discovery identity moved to entity ids.
Exit criteria: delete this suite once API integration tests cover discovery
lookups through entity ids and the legacy helpers stay removed for one release.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.governance

REPO_ROOT = Path(__file__).resolve().parents[3]
API_SOURCE_ROOTS = (REPO_ROOT / "apps" / "api" / "src",)
LEGACY_SCAN_METHODS = (".stems(", ".without_stems(")


def _find_legacy_scan_calls() -> list[str]:
    hits: list[str] = []
    for source_root in API_SOURCE_ROOTS:
        for path in sorted(source_root.rglob("*.py")):
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if any(marker in line for marker in LEGACY_SCAN_METHODS):
                    hits.append(f"{path.relative_to(REPO_ROOT)}:{lineno}: {line.strip()}")
    return hits


def test_api_production_source_no_longer_calls_legacy_scan_index_helpers() -> None:
    hits = _find_legacy_scan_calls()

    assert hits == [], (
        "legacy ScanIndex stem helpers remain in API production source:\n" + "\n".join(hits)
    )
