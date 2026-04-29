from __future__ import annotations

from pathlib import Path

from runsight_core.yaml.discovery._base import ScanIndex

ROOT = Path(__file__).resolve().parents[3]

LEGACY_SCAN_METHODS = (".stems(", ".without_stems(")
LEGACY_SOURCE_ROOTS = (ROOT / "packages" / "core" / "src", ROOT / "apps" / "api" / "src")


def _find_legacy_scan_calls() -> list[str]:
    hits: list[str] = []
    for source_root in LEGACY_SOURCE_ROOTS:
        for path in sorted(source_root.rglob("*.py")):
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if any(marker in line for marker in LEGACY_SCAN_METHODS):
                    hits.append(f"{path.relative_to(ROOT)}:{lineno}: {line.strip()}")
    return hits


def test_scan_index_public_surface_no_longer_exposes_legacy_stems_methods() -> None:
    assert not hasattr(ScanIndex, "stems")
    assert not hasattr(ScanIndex, "without_stems")


def test_production_source_no_longer_calls_legacy_stems_helpers() -> None:
    hits = _find_legacy_scan_calls()

    assert hits == [], "legacy ScanIndex stem helpers remain in production source:\n" + "\n".join(
        hits
    )


def test_base_scanner_does_not_fallback_to_filename_stem_identity() -> None:
    source = (ROOT / "packages/core/src/runsight_core/yaml/discovery/_base.py").read_text(
        encoding="utf-8"
    )

    assert "entity_id = path.stem" not in source
    assert "aliases.add(result.stem)" not in source
