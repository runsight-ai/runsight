"""Shared custom tool contract constants and function validation."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


def test_tool_contract_exports_canonical_function_signature() -> None:
    from runsight_core.tools.contract import TOOL_FUNCTION_NAME, TOOL_FUNCTION_PARAMS

    assert TOOL_FUNCTION_NAME == "main"
    assert TOOL_FUNCTION_PARAMS == ("args",)


def test_validate_tool_main_contract_accepts_canonical_signature() -> None:
    from runsight_core.yaml.discovery._tool import _validate_tool_main_contract

    _validate_tool_main_contract("def main(args):\n    return args\n")


@pytest.mark.parametrize(
    "bad_code", ["def run(args):\n    return args\n", "def main(context):\n    return context\n"]
)
def test_validate_tool_main_contract_reports_expected_signature(bad_code: str) -> None:
    from runsight_core.tools.contract import TOOL_FUNCTION_NAME, TOOL_FUNCTION_PARAMS
    from runsight_core.yaml.discovery._tool import _validate_tool_main_contract

    with pytest.raises(Exception) as exc_info:
        _validate_tool_main_contract(bad_code)

    message = str(exc_info.value)
    assert TOOL_FUNCTION_NAME in message or TOOL_FUNCTION_PARAMS[0] in message


def test_tool_scanner_imports_signature_constants_from_contract_module() -> None:
    import runsight_core.yaml.discovery._tool as tool_module

    source_file = tool_module.__file__
    assert source_file is not None
    tree = ast.parse(Path(source_file).read_text(encoding="utf-8"))

    assert any(
        isinstance(node, ast.ImportFrom)
        and "tools.contract" in (node.module or "")
        and "TOOL_FUNCTION_NAME" in [alias.name for alias in node.names]
        for node in ast.walk(tree)
    )
