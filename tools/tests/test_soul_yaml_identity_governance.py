"""Governance for package-owned soul fixtures and YAML identity.

Owner: tools/tests owns durable static governance for checked-in package YAML
identity. Boundary: package fixtures, docs, and selected checked-in test
fixtures only. Repo-root custom/ is runtime/user state and is intentionally not
scanned here.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
import yaml
from runsight_core.yaml.schema import SoulDef

ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.governance

PACKAGE_SOUL_FIXTURE_ROOT = ROOT / "packages" / "core" / "tests" / "fixtures" / "custom" / "souls"
YAML_ROOTS = (
    (PACKAGE_SOUL_FIXTURE_ROOT, "soul", True, True),
    (ROOT / "packages" / "core" / "tests" / "fixtures" / "custom" / "tools", "tool", False, True),
    (
        ROOT / "packages" / "core" / "tests" / "fixtures" / "custom" / "workflows",
        "workflow",
        False,
        True,
    ),
)

STALE_SOUL_ID_PATTERN = re.compile(
    r"\b(researcher_1|reviewer_1|writer_1|soul_1|soul_main|soul_sim)\b"
)
DOC_ROOT = ROOT / "apps" / "site" / "src" / "content" / "docs"
INLINE_FIXTURE_FILES = (
    ROOT / "packages" / "core" / "tests" / "conftest.py",
    ROOT / "packages" / "core" / "tests" / "test_project_root_resolution.py",
    ROOT / "packages" / "core" / "tests" / "test_parser_soul_field_forwarding.py",
    ROOT / "packages" / "core" / "tests" / "test_parser_workflow_block.py",
    ROOT / "packages" / "core" / "tests" / "test_parser_inputs_outputs.py",
    ROOT / "packages" / "core" / "tests" / "test_yaml_parser.py",
    ROOT / "packages" / "core" / "tests" / "test_loop_block.py",
    ROOT / "packages" / "core" / "tests" / "test_loop_carry_context.py",
    ROOT / "packages" / "core" / "tests" / "test_loop_break_conditions.py",
    ROOT / "packages" / "core" / "tests" / "test_kill_inline_souls.py",
    ROOT / "packages" / "core" / "tests" / "test_integration_workflow_block_parser.py",
    ROOT / "packages" / "core" / "tests" / "test_migrate_blocks.py",
    ROOT / "packages" / "core" / "tests" / "unit" / "test_loop_exit_handle.py",
    ROOT / "apps" / "api" / "tests" / "logic" / "test_budget_run_status.py",
    ROOT / "apps" / "api" / "tests" / "logic" / "test_execution_service.py",
    ROOT / "apps" / "api" / "tests" / "logic" / "test_execution_service_api_keys.py",
    ROOT
    / "apps"
    / "api"
    / "tests"
    / "unit"
    / "data"
    / "filesystem"
    / "test_workflow_repo_tool_governance.py",
)

REQUIRED_INLINE_IDENTITY_FILES = (
    ROOT / "packages" / "core" / "tests" / "conftest.py",
    ROOT / "packages" / "core" / "tests" / "test_parser_inputs_outputs.py",
    ROOT / "packages" / "core" / "tests" / "test_loop_block.py",
    ROOT / "packages" / "core" / "tests" / "test_kill_inline_souls.py",
    ROOT / "packages" / "core" / "tests" / "test_wire_soul_ref_to_library.py",
    ROOT / "packages" / "core" / "tests" / "unit" / "test_loop_exit_handle.py",
    ROOT / "apps" / "api" / "tests" / "logic" / "test_budget_run_status.py",
    ROOT / "apps" / "api" / "tests" / "logic" / "test_execution_service.py",
    ROOT / "apps" / "api" / "tests" / "logic" / "test_execution_service_api_keys.py",
)

INTENTIONAL_NEGATIVE_FILES = frozenset(
    {
        ROOT / "packages" / "core" / "tests" / "test_workflow_identity_schema.py",
        ROOT / "packages" / "core" / "tests" / "test_core_soul_identity_schema.py",
        ROOT / "apps" / "api" / "tests" / "domain" / "test_transport_soul_schema.py",
        ROOT / "apps" / "api" / "tests" / "logic" / "test_soul_service.py",
    }
)

PARSER_SOUL_FIELD_FORWARDING_TEST = (
    ROOT / "packages" / "core" / "tests" / "test_parser_soul_field_forwarding.py"
)
WIRE_ASSERTION_CONFIGS_TEST = (
    ROOT / "apps" / "api" / "tests" / "logic" / "test_wire_assertion_configs.py"
)


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _iter_yaml_files(base_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in base_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in {".yaml", ".yml"}
    )


def _load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"{_relative(path)} must parse to a mapping"
    return data


def _iter_inline_fixture_files() -> list[Path]:
    return sorted(
        path
        for path in INLINE_FIXTURE_FILES
        if path.exists() and path not in INTENTIONAL_NEGATIVE_FILES
    )


def _source_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _parse_ast(path: Path) -> ast.Module:
    return ast.parse(_source_text(path), filename=_relative(path))


def _extract_workflow_yaml_literals(path: Path) -> list[dict]:
    yaml_dicts: list[dict] = []
    for node in ast.walk(_parse_ast(path)):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        text = node.value
        if "kind: workflow" not in text and "version:" not in text:
            continue
        try:
            parsed = yaml.safe_load(text)
        except yaml.YAMLError:
            continue
        if isinstance(parsed, dict) and parsed.get("kind") == "workflow":
            yaml_dicts.append(parsed)
    return yaml_dicts


def _has_module_level_xfail(path: Path) -> bool:
    for node in ast.iter_child_nodes(_parse_ast(path)):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name) or target.id != "pytestmark":
                continue
            source_segment = ast.get_source_segment(_source_text(path), node)
            if source_segment and "xfail" in source_segment:
                return True
    return False


def _workflow_literals_with_inline_soul_defs(path: Path) -> list[dict]:
    offending: list[dict] = []
    for yaml_dict in _extract_workflow_yaml_literals(path):
        souls = yaml_dict.get("souls")
        if not isinstance(souls, dict):
            continue
        if any(isinstance(soul_value, dict) for soul_value in souls.values()):
            offending.append(yaml_dict)
    return offending


def _inline_soul_assertion_locations(path: Path) -> list[str]:
    locations: list[str] = []
    for yaml_dict in _extract_workflow_yaml_literals(path):
        souls = yaml_dict.get("souls")
        if not isinstance(souls, dict):
            continue
        for soul_key, soul_def in souls.items():
            if isinstance(soul_def, dict) and "assertions" in soul_def:
                locations.append(f"{_relative(path)}: soul {soul_key!r}")
    return locations


def test_package_fixture_yaml_identity_fields_match_filename_stem() -> None:
    mismatches: list[str] = []
    for root, expected_kind, requires_name, required in YAML_ROOTS:
        if not root.exists():
            assert not required, f"Expected YAML root to exist: {_relative(root)}"
            continue
        for path in _iter_yaml_files(root):
            data = _load_yaml(path)
            relative_path = _relative(path)

            if data.get("kind") != expected_kind:
                mismatches.append(f"{relative_path}: expected kind={expected_kind!r}")
            if data.get("id") != path.stem:
                mismatches.append(
                    f"{relative_path}: expected id={path.stem!r}, found {data.get('id')!r}"
                )
            if requires_name and ("name" not in data or not data["name"]):
                mismatches.append(f"{relative_path}: missing required name field")

    assert not mismatches, "YAML identity mismatches remain:\n" + "\n".join(
        f"  - {mismatch}" for mismatch in mismatches
    )


def test_package_soul_fixture_yaml_parses_through_souldef() -> None:
    failures: list[str] = []

    for path in _iter_yaml_files(PACKAGE_SOUL_FIXTURE_ROOT):
        try:
            SoulDef.model_validate(_load_yaml(path))
        except Exception as exc:
            failures.append(f"{_relative(path)}: {exc}")

    assert not failures, "Package soul fixture YAML failed SoulDef validation:\n" + "\n".join(
        f"  - {failure}" for failure in failures
    )


def test_package_soul_fixture_yaml_does_not_embed_retired_assertions_field() -> None:
    violations = [
        _relative(path)
        for path in _iter_yaml_files(PACKAGE_SOUL_FIXTURE_ROOT)
        if "assertions" in _load_yaml(path)
    ]

    assert violations == [], "Package soul fixtures still embed retired assertions:\n" + "\n".join(
        f"  - {violation}" for violation in violations
    )


def test_docs_do_not_reference_suffixed_soul_ids() -> None:
    assert DOC_ROOT.exists(), f"Expected docs root to exist: {_relative(DOC_ROOT)}"

    matches: list[str] = []
    for path in DOC_ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".md", ".mdx"}:
            continue
        content = path.read_text(encoding="utf-8")
        for match in STALE_SOUL_ID_PATTERN.finditer(content):
            matches.append(f"{_relative(path)}:{match.group(0)}")

    assert not matches, "Stale suffixed soul ids remain in docs:\n" + "\n".join(
        f"  - {match}" for match in matches
    )


def test_inline_fixtures_use_canonical_identity_fields() -> None:
    stale_locations: list[str] = []

    for path in _iter_inline_fixture_files():
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if not STALE_SOUL_ID_PATTERN.search(line):
                continue
            stale_locations.append(f"{_relative(path)}:{lineno}:{line.strip()}")

    assert not stale_locations, "Inline YAML/dict identity drift remains:\n" + "\n".join(
        f"  - {location}" for location in stale_locations
    )


def test_inline_workflow_fixtures_include_top_level_identity_fields() -> None:
    missing_locations: list[str] = []

    for path in REQUIRED_INLINE_IDENTITY_FILES:
        if not path.exists():
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            stripped = line.strip()
            if stripped == 'version: "1.0"':
                lookahead = [candidate.strip() for candidate in lines[index + 1 : index + 5]]
                if not any(candidate.startswith("id:") for candidate in lookahead):
                    missing_locations.append(f"{_relative(path)}:{index + 1}:missing top-level id")
                if not any(candidate == "kind: workflow" for candidate in lookahead):
                    missing_locations.append(
                        f"{_relative(path)}:{index + 1}:missing top-level kind"
                    )
            if stripped == '"version": "1.0",':
                lookahead = [candidate.strip() for candidate in lines[index + 1 : index + 6]]
                if not any(candidate.startswith('"id":') for candidate in lookahead):
                    missing_locations.append(f"{_relative(path)}:{index + 1}:missing dict id")
                if not any(candidate == '"kind": "workflow",' for candidate in lookahead):
                    missing_locations.append(f"{_relative(path)}:{index + 1}:missing dict kind")

    assert not missing_locations, "Inline workflow identity fields missing:\n" + "\n".join(
        f"  - {location}" for location in missing_locations
    )


def test_parser_soul_forwarding_suite_has_no_xfail_marker() -> None:
    assert not _has_module_level_xfail(PARSER_SOUL_FIELD_FORWARDING_TEST), (
        f"{_relative(PARSER_SOUL_FIELD_FORWARDING_TEST)} still has a module-level "
        "pytestmark xfail marker."
    )
    assert "xfail" not in _source_text(PARSER_SOUL_FIELD_FORWARDING_TEST), (
        f"{_relative(PARSER_SOUL_FIELD_FORWARDING_TEST)} still references xfail."
    )


@pytest.mark.parametrize(
    "path",
    (PARSER_SOUL_FIELD_FORWARDING_TEST, WIRE_ASSERTION_CONFIGS_TEST),
    ids=lambda path: _relative(path),
)
def test_checked_in_workflow_literals_use_library_soul_refs(path: Path) -> None:
    offending = _workflow_literals_with_inline_soul_defs(path)

    assert offending == [], (
        f"{_relative(path)} has workflow YAML literals with populated inline souls: "
        "definitions. Use package library soul refs instead."
    )


def test_checked_in_workflow_literals_do_not_embed_inline_soul_assertions() -> None:
    locations = _inline_soul_assertion_locations(WIRE_ASSERTION_CONFIGS_TEST)

    assert locations == [], (
        "Inline workflow literals must not embed retired soul-level assertions. Found:\n"
        + "\n".join(f"  - {location}" for location in locations)
    )
