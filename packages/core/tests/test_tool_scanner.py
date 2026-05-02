from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from packages.core.tests.discovery_fixtures import write_tool_yaml


def _scan_tools(base_dir: Path):
    from runsight_core.yaml.discovery import ToolScanner

    return ToolScanner(base_dir).scan().ids()


def test_tool_scanner_and_reserved_builtin_ids_are_publicly_importable() -> None:
    from runsight_core.yaml.discovery import RESERVED_BUILTIN_TOOL_IDS, ToolMeta, ToolScanner

    tool_module = importlib.import_module("runsight_core.yaml.discovery._tool")

    assert ToolScanner is not None
    assert ToolMeta is not None
    assert RESERVED_BUILTIN_TOOL_IDS == frozenset({"http", "file_io", "delegate"})
    assert ToolScanner.__module__ == tool_module.ToolScanner.__module__
    assert ToolMeta.__module__ == tool_module.ToolMeta.__module__
    assert RESERVED_BUILTIN_TOOL_IDS is tool_module.RESERVED_BUILTIN_TOOL_IDS


def test_legacy_discover_custom_tools_helper_is_removed_from_public_module() -> None:
    import runsight_core.yaml.discovery as discovery_module

    assert not hasattr(
        discovery_module,
        "discover_custom_tools",
    ), "Legacy discover_custom_tools helper should be removed from runsight_core.yaml.discovery"


@pytest.mark.parametrize(
    "legacy_helper_name",
    [
        "_validate_tool_main_contract",
        "_fail_tool_file",
        "_require_string",
        "_require_mapping",
        "_read_tool_code_file",
        "_normalize_request_config",
    ],
)
def test_legacy_tool_helpers_are_removed_from_public_module(
    legacy_helper_name: str,
) -> None:
    import runsight_core.yaml.discovery as discovery_module

    assert not hasattr(
        discovery_module,
        legacy_helper_name,
    ), f"Legacy helper {legacy_helper_name} should move out of runsight_core.yaml.discovery"


def test_missing_custom_tools_directory_returns_empty_dict(tmp_path) -> None:
    assert _scan_tools(tmp_path) == {}


def test_discovers_python_and_request_executor_tool_files_by_embedded_id(tmp_path) -> None:
    from runsight_core.yaml.discovery import ToolMeta

    base_dir = tmp_path
    write_tool_yaml(
        base_dir,
        "python_helper_embedded.yaml",
        tool_id="python_helper_embedded",
        executor="python",
        name="Python Helper",
        description="Echo values back to the caller.",
        parameters=[
            "type: object",
            "properties:",
            "  value:",
            "    type: string",
            "required:",
            "  - value",
        ],
        code="def main(args):\n    return args",
    )
    write_tool_yaml(
        base_dir,
        "request_lookup_embedded.yaml",
        tool_id="request_lookup_embedded",
        executor="request",
        name="Request Lookup",
        description="Fetch data from a remote service.",
        parameters=[
            "type: object",
            "properties:",
            "  user_id:",
            "    type: integer",
            "required:",
            "  - user_id",
        ],
        request=[
            "method: GET",
            "url: https://fixture.test/users/{{ user_id }}",
            "headers:",
            "  X-Test: runsight",
            "response_path: data.id",
        ],
        extra_lines=["timeout_seconds: 12"],
    )

    discovered = _scan_tools(base_dir)

    assert set(discovered.keys()) == {
        "python_helper_embedded",
        "request_lookup_embedded",
    }
    assert isinstance(discovered["python_helper_embedded"], ToolMeta)
    assert isinstance(discovered["request_lookup_embedded"], ToolMeta)
    assert discovered["python_helper_embedded"].tool_id == "python_helper_embedded"
    assert discovered["python_helper_embedded"].type == "custom"
    assert discovered["python_helper_embedded"].executor == "python"
    assert discovered["python_helper_embedded"].name == "Python Helper"
    assert discovered["request_lookup_embedded"].tool_id == "request_lookup_embedded"
    assert discovered["request_lookup_embedded"].type == "custom"
    assert discovered["request_lookup_embedded"].executor == "request"
    assert (
        discovered["request_lookup_embedded"].request["url"]
        == "https://fixture.test/users/{{ user_id }}"
    )


def test_legacy_type_http_is_rejected_with_file_specific_error(tmp_path) -> None:
    write_tool_yaml(tmp_path, "legacy_http.yaml", tool_id="legacy_http", type_="http")

    with pytest.raises(ValueError, match=r"legacy_http\.yaml.*type.*custom|legacy_http"):
        _scan_tools(tmp_path)


def test_malformed_yaml_raises_file_specific_error(tmp_path) -> None:
    write_tool_yaml(
        tmp_path,
        "broken.yaml",
        raw_content='version: "1.0"\ntype: custom\nexecutor: python\ncode: [not: valid',
    )

    with pytest.raises(Exception, match="broken.yaml"):
        _scan_tools(tmp_path)


def test_invalid_metadata_raises_file_specific_error(tmp_path) -> None:
    write_tool_yaml(
        tmp_path,
        "missing_executor.yaml",
        tool_id="missing_executor",
        name="Missing Executor",
        description="Broken metadata.",
        parameters=["type: object"],
        code="def main(args):\n    return args",
    )

    with pytest.raises(ValueError, match="missing_executor.yaml"):
        _scan_tools(tmp_path)


def test_custom_tool_rejects_both_code_and_code_file(tmp_path) -> None:
    write_tool_yaml(
        tmp_path,
        "double_code.yaml",
        tool_id="double_code",
        executor="python",
        name="Double Code",
        description="Declares both code and code_file.",
        parameters=["type: object"],
        code="def main(args):\n    return args",
        code_file="helper.py",
    )

    with pytest.raises(ValueError, match="double_code.yaml"):
        _scan_tools(tmp_path)


def test_custom_tool_rejects_missing_code_file(tmp_path) -> None:
    write_tool_yaml(
        tmp_path,
        "missing_code_file.yaml",
        tool_id="missing_code_file",
        executor="python",
        name="Missing Code File",
        description="References a file that does not exist.",
        parameters=["type: object"],
        code_file="missing_impl.py",
    )

    with pytest.raises(ValueError, match="missing_code_file.yaml"):
        _scan_tools(tmp_path)


def test_custom_tool_rejects_unreadable_code_file(tmp_path) -> None:
    tools_dir = tmp_path / "custom" / "tools"
    tools_dir.mkdir(parents=True)
    (tools_dir / "impl_dir.py").mkdir()
    write_tool_yaml(
        tmp_path,
        "unreadable_code_file.yaml",
        tool_id="unreadable_code_file",
        executor="python",
        name="Unreadable Code File",
        description="Points at an unreadable code file.",
        parameters=["type: object"],
        code_file="impl_dir.py",
    )

    with pytest.raises(ValueError, match=r"unreadable_code_file\.yaml"):
        _scan_tools(tmp_path)


def test_custom_tool_rejects_invalid_main_signature(tmp_path) -> None:
    write_tool_yaml(
        tmp_path,
        "bad_signature.yaml",
        tool_id="bad_signature",
        executor="python",
        name="Bad Signature",
        description="Uses the wrong main() signature.",
        parameters=["type: object"],
        code="def main():\n    return {}",
    )

    with pytest.raises(ValueError, match="bad_signature.yaml"):
        _scan_tools(tmp_path)


def test_request_executor_requires_request_url(tmp_path) -> None:
    write_tool_yaml(
        tmp_path,
        "missing_request_url.yaml",
        tool_id="missing_request_url",
        executor="request",
        name="Missing Request URL",
        description="Missing nested request.url.",
        parameters=["type: object"],
        request=["method: GET"],
    )

    with pytest.raises(ValueError, match=r"missing_request_url\.yaml"):
        _scan_tools(tmp_path)


def test_request_executor_rejects_python_fields(tmp_path) -> None:
    write_tool_yaml(
        tmp_path,
        "request_with_code.yaml",
        tool_id="request_with_code",
        executor="request",
        name="Request With Code",
        description="Request tools must not declare Python fields.",
        parameters=["type: object"],
        code="def main(args):\n    return args",
        request=["method: GET", "url: https://fixture.test/users/{{ user_id }}"],
    )

    with pytest.raises(ValueError, match=r"request_with_code\.yaml"):
        _scan_tools(tmp_path)


def test_python_executor_rejects_request_fields(tmp_path) -> None:
    write_tool_yaml(
        tmp_path,
        "python_with_request.yaml",
        tool_id="python_with_request",
        executor="python",
        name="Python With Request",
        description="Python tools must not declare request metadata.",
        parameters=["type: object"],
        code="def main(args):\n    return args",
        request=["method: GET", "url: https://fixture.test/users/{{ user_id }}"],
    )

    with pytest.raises(ValueError, match=r"python_with_request\.yaml"):
        _scan_tools(tmp_path)


def test_unknown_executor_raises_file_specific_error(tmp_path) -> None:
    write_tool_yaml(
        tmp_path,
        "unknown_executor.yaml",
        tool_id="unknown_executor",
        executor="shell",
        name="Unknown Executor",
        description="Unsupported executor.",
        parameters=["type: object"],
    )

    with pytest.raises(ValueError, match=r"unknown_executor\.yaml"):
        _scan_tools(tmp_path)


def test_duplicate_embedded_tool_id_raises_explicit_error(monkeypatch, tmp_path) -> None:
    tools_dir = tmp_path / "custom" / "tools"

    primary_file = write_tool_yaml(
        tmp_path,
        "duplicate_primary.yaml",
        tool_id="duplicate_tool_id",
        executor="python",
        name="Duplicate Tool",
        description="Detect duplicate file-backed tool ids.",
        parameters=["type: object"],
        code="def main(args):\n    return args",
    )
    shadow_file = write_tool_yaml(
        tmp_path,
        "shadow/duplicate_shadow.yaml",
        tool_id="duplicate_tool_id",
        executor="python",
        name="Duplicate Tool",
        description="Detect duplicate file-backed tool ids.",
        parameters=["type: object"],
        code="def main(args):\n    return args",
    )

    original_glob = Path.glob

    def _fake_glob(self: Path, pattern: str):
        if self == tools_dir and pattern == "*.yaml":
            return [primary_file, shadow_file]
        return original_glob(self, pattern)

    monkeypatch.setattr(Path, "glob", _fake_glob)

    with pytest.raises(ValueError, match=r"duplicate_tool_id.*duplicate|collision"):
        _scan_tools(tmp_path)


@pytest.mark.parametrize("reserved_tool_id", ["http", "file_io", "delegate"])
def test_reserved_builtin_tool_ids_are_rejected_during_discovery(
    reserved_tool_id: str,
    tmp_path,
) -> None:
    write_tool_yaml(
        tmp_path,
        f"shadow_{reserved_tool_id}.yaml",
        tool_id=reserved_tool_id,
        executor="python",
        name=f"Shadow {reserved_tool_id}",
        description="Attempts to shadow the reserved builtin tool id.",
        parameters=["type: object"],
        code="def main(args):\n    return args",
    )

    with pytest.raises(
        ValueError,
        match=rf"reserved builtin tool:{reserved_tool_id}|collision.*{reserved_tool_id}",
    ):
        _scan_tools(tmp_path)
