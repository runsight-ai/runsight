"""Governance tests for provider-service unit-test network isolation.

Owner: tools/tests owns temporary static checks for API test network-isolation
cleanup.
Boundary: apps/api/tests/logic/test_provider_service.py may mock provider
HTTP transport, but unit tests that exercise the default provider URL must also
mock provider-service SSRF validation so they cannot perform live DNS before
mocked HTTP is reached. This suite inspects repo-owned source only and does not
change or replace provider-service behavior coverage.
Exit criteria: delete this suite once provider-service unit tests own an
explicit no-live-network fixture or all default-provider connection cases mock
SSRF validation in the same test scope, with equivalent isolation covered by
normal API test fixtures.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PROVIDER_SERVICE_TEST = REPO_ROOT / "apps" / "api" / "tests" / "logic" / "test_provider_service.py"
PROVIDER_SERVICE_HTTPX = "runsight_api.logic.services.provider_service.httpx"
PROVIDER_SERVICE_VALIDATE_SSRF = "runsight_api.logic.services.provider_service.validate_ssrf"

pytestmark = pytest.mark.governance


@dataclass(frozen=True)
class UnisolatedProviderHttpxPatch:
    test_name: str
    line_number: int


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _source_tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=_relative(path))


def _literal_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        owner = _call_name(node.value)
        return f"{owner}.{node.attr}" if owner else node.attr
    return ""


def _is_patch_call(node: ast.AST, target: str) -> bool:
    if not isinstance(node, ast.Call):
        return False
    if _call_name(node.func) != "patch":
        return False
    if not node.args:
        return False
    return _literal_string(node.args[0]) == target


def _patches_target(test_function: ast.AsyncFunctionDef, target: str) -> bool:
    return any(_is_patch_call(node, target) for node in ast.walk(test_function))


def _provider_entity_uses_default_network_url(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    if _call_name(node.func) != "ProviderEntity":
        return False

    keywords = {keyword.arg: keyword.value for keyword in node.keywords if keyword.arg is not None}
    provider_type = _literal_string(keywords.get("type", ast.Constant(value=None)))
    has_base_url = "base_url" in keywords
    return provider_type == "openai" and not has_base_url


def _uses_default_provider_url(test_function: ast.AsyncFunctionDef) -> bool:
    return any(_provider_entity_uses_default_network_url(node) for node in ast.walk(test_function))


def _unisolated_provider_httpx_patches(path: Path) -> list[UnisolatedProviderHttpxPatch]:
    tree = _source_tree(path)
    violations: list[UnisolatedProviderHttpxPatch] = []

    for node in tree.body:
        if not isinstance(node, ast.AsyncFunctionDef):
            continue
        if not node.name.startswith("test_"):
            continue
        if not _uses_default_provider_url(node):
            continue
        if not _patches_target(node, PROVIDER_SERVICE_HTTPX):
            continue
        if _patches_target(node, PROVIDER_SERVICE_VALIDATE_SSRF):
            continue

        violations.append(
            UnisolatedProviderHttpxPatch(test_name=node.name, line_number=node.lineno)
        )

    return violations


def test_provider_service_default_url_httpx_mocks_also_mock_ssrf_validation() -> None:
    """Owner/boundary/exit: default provider URL tests must not perform live DNS."""
    violations = _unisolated_provider_httpx_patches(PROVIDER_SERVICE_TEST)

    assert violations == [], (
        f"{_relative(PROVIDER_SERVICE_TEST)} async tests that mock "
        f"{PROVIDER_SERVICE_HTTPX} while using an OpenAI provider fixture without "
        f"base_url must also mock {PROVIDER_SERVICE_VALIDATE_SSRF}. Otherwise "
        "ProviderService falls back to the third-party default URL and SSRF "
        "validation can perform live DNS before mocked HTTP is reached. Found:\n"
        + "\n".join(
            f"  - {violation.test_name} starts at line {violation.line_number}"
            for violation in violations
        )
    )
