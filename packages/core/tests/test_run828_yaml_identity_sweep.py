from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]

YAML_ROOTS = [
    (ROOT / "custom" / "souls", "soul", True),
    (ROOT / "custom" / "tools", "tool", False),
    (ROOT / "custom" / "workflows", "workflow", False),
    (ROOT / "packages" / "core" / "tests" / "fixtures" / "custom" / "souls", "soul", True),
    (ROOT / "packages" / "core" / "tests" / "fixtures" / "custom" / "tools", "tool", False),
    (ROOT / "packages" / "core" / "tests" / "fixtures" / "custom" / "workflows", "workflow", False),
]

STALE_SOUL_ID_PATTERN = re.compile(
    r"\b(researcher_1|reviewer_1|writer_1|soul_1|soul_main|soul_sim)\b"
)
DOC_ROOT = ROOT / "apps" / "site" / "src" / "content" / "docs"
INLINE_FIXTURE_FILES = [
    ROOT / "packages" / "core" / "tests" / "conftest.py",
    ROOT / "packages" / "core" / "tests" / "test_run569_project_root_resolution.py",
    ROOT / "packages" / "core" / "tests" / "test_run468_parser_soul_field_forwarding.py",
    ROOT / "packages" / "core" / "tests" / "test_parser_workflow_block.py",
    ROOT / "packages" / "core" / "tests" / "test_parser_inputs_outputs.py",
    ROOT / "packages" / "core" / "tests" / "test_yaml_parser.py",
    ROOT / "packages" / "core" / "tests" / "test_loop_block.py",
    ROOT / "packages" / "core" / "tests" / "test_loop_carry_context.py",
    ROOT / "packages" / "core" / "tests" / "test_loop_break_conditions.py",
    ROOT / "packages" / "core" / "tests" / "test_run570_kill_inline_souls.py",
    ROOT / "packages" / "core" / "tests" / "test_run685_eval_debt_integration.py",
    ROOT / "packages" / "core" / "tests" / "test_integration_workflow_block_parser.py",
    ROOT / "packages" / "core" / "tests" / "test_run222_migrate_blocks.py",
    ROOT / "packages" / "core" / "tests" / "unit" / "test_loop_exit_handle.py",
    ROOT / "apps" / "api" / "tests" / "logic" / "test_budget_run_status.py",
    ROOT / "apps" / "api" / "tests" / "logic" / "test_execution_service.py",
    ROOT / "apps" / "api" / "tests" / "logic" / "test_run141_execution_service_api_keys.py",
    ROOT
    / "apps"
    / "api"
    / "tests"
    / "unit"
    / "data"
    / "filesystem"
    / "test_run490_workflow_repo_tool_governance.py",
]

REQUIRED_INLINE_IDENTITY_FILES = [
    ROOT / "packages" / "core" / "tests" / "conftest.py",
    ROOT / "packages" / "core" / "tests" / "test_parser_inputs_outputs.py",
    ROOT / "packages" / "core" / "tests" / "test_loop_block.py",
    ROOT / "packages" / "core" / "tests" / "test_run570_kill_inline_souls.py",
    ROOT / "packages" / "core" / "tests" / "test_run685_eval_debt_integration.py",
    ROOT / "packages" / "core" / "tests" / "test_run571_wire_soul_ref_to_library.py",
    ROOT / "packages" / "core" / "tests" / "unit" / "test_loop_exit_handle.py",
    ROOT / "apps" / "api" / "tests" / "logic" / "test_budget_run_status.py",
    ROOT / "apps" / "api" / "tests" / "logic" / "test_execution_service.py",
    ROOT / "apps" / "api" / "tests" / "logic" / "test_run141_execution_service_api_keys.py",
]

# These files are intentional negative tests that validate missing identity fields at the
# schema/service boundary. The audit should not flag their omission-by-design fixtures.
INTENTIONAL_NEGATIVE_FILES = {
    ROOT / "packages" / "core" / "tests" / "test_run826_workflow_identity_schema.py",
    ROOT / "packages" / "core" / "tests" / "test_run827_core_soul_identity_schema.py",
    ROOT / "apps" / "api" / "tests" / "domain" / "test_run472_transport_soul_schema.py",
    ROOT / "apps" / "api" / "tests" / "logic" / "test_soul_service.py",
}


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


def _iter_inline_fixture_files() -> list[Path]:
    return sorted(path for path in INLINE_FIXTURE_FILES if path not in INTENTIONAL_NEGATIVE_FILES)


def test_yaml_identity_fields_match_filename_stem() -> None:
    mismatches: list[str] = []
    for root, expected_kind, requires_name in YAML_ROOTS:
        assert root.exists(), f"Expected YAML root to exist: {root.relative_to(ROOT)}"
        for path in _iter_yaml_files(root):
            data = _load_yaml(path)
            relative_path = path.relative_to(ROOT)

            if data.get("kind") != expected_kind:
                mismatches.append(f"{relative_path}: expected kind={expected_kind!r}")
            if data.get("id") != path.stem:
                mismatches.append(
                    f"{relative_path}: expected id={path.stem!r}, found {data.get('id')!r}"
                )
            if requires_name:
                if "name" not in data or not data["name"]:
                    mismatches.append(f"{relative_path}: missing required name field")

    assert not mismatches, "YAML identity mismatches remain:\n" + "\n".join(
        f"  - {mismatch}" for mismatch in mismatches
    )


def test_docs_do_not_reference_suffixed_soul_ids() -> None:
    assert DOC_ROOT.exists(), f"Expected docs root to exist: {DOC_ROOT.relative_to(ROOT)}"

    matches: list[str] = []
    for path in DOC_ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".md", ".mdx"}:
            continue
        content = path.read_text(encoding="utf-8")
        for match in STALE_SOUL_ID_PATTERN.finditer(content):
            matches.append(f"{path.relative_to(ROOT)}:{match.group(0)}")

    assert not matches, "Stale suffixed soul ids remain in docs:\n" + "\n".join(
        f"  - {match}" for match in matches
    )


def test_inline_yaml_and_dict_literals_use_embedded_identity_fields() -> None:
    stale_locations: list[str] = []

    for path in _iter_inline_fixture_files():
        text = path.read_text(encoding="utf-8")
        relative_path = path.relative_to(ROOT)
        for lineno, line in enumerate(text.splitlines(), start=1):
            if not STALE_SOUL_ID_PATTERN.search(line):
                continue
            stale_locations.append(f"{relative_path}:{lineno}:{line.strip()}")

    assert not stale_locations, "Inline YAML/dict identity drift remains:\n" + "\n".join(
        f"  - {location}" for location in stale_locations
    )


def test_inline_workflow_fixtures_include_top_level_identity_fields() -> None:
    missing_locations: list[str] = []

    for path in REQUIRED_INLINE_IDENTITY_FILES:
        lines = path.read_text(encoding="utf-8").splitlines()
        relative_path = path.relative_to(ROOT)
        for index, line in enumerate(lines):
            stripped = line.strip()
            if stripped == 'version: "1.0"':
                lookahead = [candidate.strip() for candidate in lines[index + 1 : index + 5]]
                if not any(candidate.startswith("id:") for candidate in lookahead):
                    missing_locations.append(f"{relative_path}:{index + 1}:missing top-level id")
                if not any(candidate == "kind: workflow" for candidate in lookahead):
                    missing_locations.append(f"{relative_path}:{index + 1}:missing top-level kind")
            if stripped == '"version": "1.0",':
                lookahead = [candidate.strip() for candidate in lines[index + 1 : index + 6]]
                if not any(candidate.startswith('"id":') for candidate in lookahead):
                    missing_locations.append(f"{relative_path}:{index + 1}:missing dict id")
                if not any(candidate == '"kind": "workflow",' for candidate in lookahead):
                    missing_locations.append(f"{relative_path}:{index + 1}:missing dict kind")

    assert not missing_locations, "Inline workflow identity fields missing:\n" + "\n".join(
        f"  - {location}" for location in missing_locations
    )
