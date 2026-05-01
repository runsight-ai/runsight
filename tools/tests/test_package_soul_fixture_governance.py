"""Governance tests for package-owned soul fixture schema conformance.

Owner: repo tooling governance.
Boundary: package-owned soul YAML fixtures under packages/core/tests/fixtures
must stay valid against SoulDef and must not reintroduce retired soul-level
assertion fields. Repo-root custom/ is runtime/user state and is intentionally
not scanned here.
Exit criteria: replace this suite only after package fixture schema validation
moves into a documented repo tooling command with equivalent SoulDef coverage.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from runsight_core.yaml.schema import SoulDef

ROOT = Path(__file__).resolve().parents[2]
PACKAGE_SOUL_FIXTURE_ROOT = ROOT / "packages" / "core" / "tests" / "fixtures" / "custom" / "souls"

pytestmark = pytest.mark.governance


def _iter_yaml_files(base_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in base_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in {".yaml", ".yml"}
    )


def _load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"{path.relative_to(ROOT)} must parse to a mapping"
    return data


def test_package_soul_fixture_yaml_parses_through_souldef() -> None:
    failures: list[str] = []

    for path in _iter_yaml_files(PACKAGE_SOUL_FIXTURE_ROOT):
        try:
            SoulDef.model_validate(_load_yaml(path))
        except Exception as exc:
            failures.append(f"{path.relative_to(ROOT)}: {exc}")

    assert not failures, "Package soul fixture YAML failed SoulDef validation:\n" + "\n".join(
        f"  - {failure}" for failure in failures
    )


def test_package_soul_fixture_yaml_does_not_embed_retired_assertions_field() -> None:
    violations = [
        path.relative_to(ROOT)
        for path in _iter_yaml_files(PACKAGE_SOUL_FIXTURE_ROOT)
        if "assertions" in _load_yaml(path)
    ]

    assert violations == []
