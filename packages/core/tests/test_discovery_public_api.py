from __future__ import annotations

import importlib

import pytest


def test_discovery_module_keeps_scanner_public_api() -> None:
    from runsight_core.yaml.discovery import (
        BaseScanner,
        ScanIndex,
        ScanResult,
        SoulScanner,
        ToolScanner,
        WorkflowScanner,
    )

    assert BaseScanner is not None
    assert ScanIndex is not None
    assert ScanResult is not None
    assert SoulScanner is not None
    assert ToolScanner is not None
    assert WorkflowScanner is not None


def test_discovery_surface_uses_real_package_layout() -> None:
    discovery_module = importlib.import_module("runsight_core.yaml.discovery")
    soul_module = importlib.import_module("runsight_core.yaml.discovery._soul")

    assert discovery_module.__file__ is not None
    assert discovery_module.__file__.endswith("yaml/discovery/__init__.py")
    assert soul_module.__file__ is not None
    assert soul_module.__file__.endswith("yaml/discovery/_soul.py")


@pytest.mark.parametrize(
    "legacy_helper_name",
    [
        "discover_custom_assets",
        "_to_snake_case",
        "_discover_blocks",
        "_discover_workflows",
    ],
)
def test_legacy_discovery_helpers_are_removed_from_public_module(
    legacy_helper_name: str,
) -> None:
    import runsight_core.yaml.discovery as discovery_module

    assert not hasattr(
        discovery_module,
        legacy_helper_name,
    ), f"Legacy helper {legacy_helper_name} should be removed from runsight_core.yaml.discovery"


def test_yaml_package_legacy_discover_custom_assets_export_is_retired() -> None:
    import runsight_core.yaml as yaml_module

    assert not hasattr(yaml_module, "discover_custom_assets")
