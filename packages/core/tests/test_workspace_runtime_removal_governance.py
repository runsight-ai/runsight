"""Governance for removing the legacy public subprocess harness path.

Owner: packages/core owns the workspace runtime isolation contract boundary.
Boundary: this suite may inspect checked-in source, tests, and user-facing docs.
It must not inspect repo-root runtime state such as .runsight/, runsight.db,
custom/, secrets, or user configuration.
Exit criteria: delete this suite once architectural tooling enforces the
workspace runtime public surface and worker IPC env contract.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.governance

REPO_ROOT = Path(__file__).resolve().parents[3]
THIS_FILE = Path(__file__).resolve()

CORE_SOURCE_ROOT = REPO_ROOT / "packages" / "core" / "src"
API_SOURCE_ROOT = REPO_ROOT / "apps" / "api" / "src"
CORE_TEST_ROOT = REPO_ROOT / "packages" / "core" / "tests"

LEGACY_HARNESS_NAME = "SubprocessHarness"
LEGACY_WORKER_ENV_NAMES = frozenset({"RUNSIGHT_IPC_SOCKET", "RUNSIGHT_GRANT_TOKEN"})
CURRENT_WORKER_ENV_NAME = "RUNSIGHT_IPC_CONFIG_B64"

PRODUCTION_SOURCE_ROOTS = (CORE_SOURCE_ROOT, API_SOURCE_ROOT)
PARSER_WRAPPER_ASSERTION_RUNTIME_FILES = (
    CORE_SOURCE_ROOT / "runsight_core" / "yaml" / "parser.py",
    CORE_SOURCE_ROOT / "runsight_core" / "isolation" / "wrapper.py",
    CORE_SOURCE_ROOT / "runsight_core" / "assertions" / "registry.py",
)
WORKER_SOURCE_FILES = (CORE_SOURCE_ROOT / "runsight_core" / "isolation" / "worker.py",)
DOC_ROOTS = (
    REPO_ROOT,
    REPO_ROOT / "apps" / "site",
)
DOC_FILE_PATTERNS = ("README*", "*.md", "*.mdx")


def _relative(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def _python_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)


def _line_hits(path: Path, pattern: re.Pattern[str]) -> list[str]:
    hits: list[str] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if pattern.search(line):
            hits.append(f"{_relative(path)}:{line_number}: {line.strip()}")
    return hits


def _doc_files() -> list[Path]:
    files: set[Path] = set()
    for root in DOC_ROOTS:
        if not root.exists():
            continue
        for pattern in DOC_FILE_PATTERNS:
            if root == REPO_ROOT and pattern in {"*.md", "*.mdx"}:
                files.update(path for path in root.glob(pattern) if path.is_file())
            else:
                files.update(path for path in root.rglob(pattern) if path.is_file())
    return sorted(files)


def _is_migration_or_governance_test(path: Path) -> bool:
    name = path.name.lower()
    parts = {part.lower() for part in path.parts}
    return (
        path.resolve() == THIS_FILE
        or "governance" in name
        or "migration" in name
        or "migration" in parts
    )


def _is_legacy_env_rejection_test(path: Path) -> bool:
    """Allow only suites whose names clearly own legacy IPC rejection coverage."""

    if _is_migration_or_governance_test(path):
        return True
    name = path.name.lower()
    return "ipc_config" in name or "startup" in name and "worker" in name


class _LegacyEnvReadVisitor(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.offenders: list[str] = []

    def visit_Call(self, node: ast.Call) -> None:
        env_name = self._legacy_env_name_from_get_call(node)
        if env_name is not None:
            self.offenders.append(
                f"{_relative(self.path)}:{node.lineno}: direct read of {env_name}"
            )
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        env_name = self._legacy_env_name_from_subscript(node)
        if env_name is not None:
            self.offenders.append(
                f"{_relative(self.path)}:{node.lineno}: direct read of {env_name}"
            )
        self.generic_visit(node)

    @staticmethod
    def _constant_string(node: ast.AST) -> str | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        return None

    def _legacy_env_name_from_get_call(self, node: ast.Call) -> str | None:
        if not node.args:
            return None
        first_arg = self._constant_string(node.args[0])
        if first_arg not in LEGACY_WORKER_ENV_NAMES:
            return None
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "getenv"
            and isinstance(func.value, ast.Name)
            and func.value.id == "os"
        ):
            return first_arg
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "get"
            and isinstance(func.value, ast.Attribute)
            and func.value.attr == "environ"
            and isinstance(func.value.value, ast.Name)
            and func.value.value.id == "os"
        ):
            return first_arg
        return None

    def _legacy_env_name_from_subscript(self, node: ast.Subscript) -> str | None:
        if not (
            isinstance(node.value, ast.Attribute)
            and node.value.attr == "environ"
            and isinstance(node.value.value, ast.Name)
            and node.value.value.id == "os"
        ):
            return None
        env_name = self._constant_string(node.slice)
        if env_name in LEGACY_WORKER_ENV_NAMES:
            return env_name
        return None


def test_public_isolation_package_no_longer_exports_subprocess_harness() -> None:
    import runsight_core.isolation as isolation

    assert not hasattr(isolation, LEGACY_HARNESS_NAME)
    with pytest.raises(ImportError):
        exec(f"from runsight_core.isolation import {LEGACY_HARNESS_NAME}", {})


def test_production_source_has_no_public_subprocess_harness_runtime_path() -> None:
    legacy_reference = re.compile(rf"\b{LEGACY_HARNESS_NAME}\b")

    offenders: list[str] = []
    for root in PRODUCTION_SOURCE_ROOTS:
        for path in _python_files(root):
            offenders.extend(_line_hits(path, legacy_reference))

    assert offenders == []


def test_parser_wrapper_and_assertion_runtime_paths_do_not_construct_subprocess_harness() -> None:
    legacy_runtime_reference = re.compile(
        rf"\b(?:from\s+[\w.]+\s+import\s+.*{LEGACY_HARNESS_NAME}"
        rf"|import\s+[\w.]+{LEGACY_HARNESS_NAME}"
        rf"|{LEGACY_HARNESS_NAME}\s*\()"
    )

    offenders: list[str] = []
    for path in PARSER_WRAPPER_ASSERTION_RUNTIME_FILES:
        assert path.exists(), f"Missing runtime path expected by governance scan: {_relative(path)}"
        offenders.extend(_line_hits(path, legacy_runtime_reference))

    assert offenders == []


def test_worker_code_only_reads_encoded_ipc_config_env_contract() -> None:
    offenders: list[str] = []
    for path in WORKER_SOURCE_FILES:
        assert path.exists(), f"Missing worker path expected by governance scan: {_relative(path)}"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        visitor = _LegacyEnvReadVisitor(path)
        visitor.visit(tree)
        offenders.extend(visitor.offenders)

    assert offenders == []


def test_ordinary_core_tests_no_longer_import_patch_or_instantiate_subprocess_harness() -> None:
    legacy_reference = re.compile(rf"\b{LEGACY_HARNESS_NAME}\b")

    offenders: list[str] = []
    for path in _python_files(CORE_TEST_ROOT):
        if _is_migration_or_governance_test(path):
            continue
        offenders.extend(_line_hits(path, legacy_reference))

    assert offenders == []


def test_ordinary_tests_keep_legacy_worker_env_names_in_rejection_or_governance_suites_only() -> (
    None
):
    legacy_env_reference = re.compile(r"\b(?:RUNSIGHT_IPC_SOCKET|RUNSIGHT_GRANT_TOKEN)\b")

    offenders: list[str] = []
    for path in _python_files(CORE_TEST_ROOT):
        if _is_legacy_env_rejection_test(path):
            continue
        offenders.extend(_line_hits(path, legacy_env_reference))

    assert offenders == []


def test_user_facing_docs_do_not_describe_removed_subprocess_harness_or_legacy_worker_env() -> None:
    removed_public_terms = re.compile(
        rf"\b(?:{LEGACY_HARNESS_NAME}|RUNSIGHT_IPC_SOCKET|RUNSIGHT_GRANT_TOKEN)\b"
    )

    offenders: list[str] = []
    for path in _doc_files():
        offenders.extend(_line_hits(path, removed_public_terms))

    assert offenders == []


def test_parsed_llm_workflow_uses_unix_local_harness_without_legacy_alias() -> None:
    from unittest.mock import MagicMock

    from runsight_core.isolation import IsolatedBlockWrapper, UnixLocalHarness
    from runsight_core.yaml.parser import parse_workflow_yaml

    workflow = parse_workflow_yaml(
        """\
version: "1.0"
id: workspace_runtime_removal_governance
kind: workflow
souls:
  writer:
    id: writer
    kind: soul
    name: Writer
    role: Writer
    system_prompt: Write clearly.
    model_name: fixture-isolation-model
blocks:
  draft:
    type: linear
    soul_ref: writer
workflow:
  name: workspace_runtime_removal_governance
  entry: draft
  transitions:
    - from: draft
      to: null
""",
        runner=MagicMock(),
        api_keys={"openai": "dummy-openai-key"},
    )

    wrapper = workflow.blocks["draft"]

    assert isinstance(wrapper, IsolatedBlockWrapper)
    assert isinstance(wrapper.harness, UnixLocalHarness)
    assert wrapper.harness.__class__.__name__ == "UnixLocalHarness"
    assert LEGACY_HARNESS_NAME not in {wrapper.harness.__class__.__name__, *dir(wrapper.harness)}
    assert CURRENT_WORKER_ENV_NAME == "RUNSIGHT_IPC_CONFIG_B64"
