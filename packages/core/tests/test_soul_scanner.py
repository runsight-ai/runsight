from __future__ import annotations

from textwrap import dedent

import pytest
from runsight_core.primitives import Soul
from runsight_core.yaml.discovery import SoulScanner

from packages.core.tests.discovery_fixtures import write_soul_yaml


def test_discover_souls_empty_directory(tmp_path) -> None:
    base_dir = tmp_path
    souls_dir = base_dir / "custom" / "souls"
    souls_dir.mkdir(parents=True)

    souls = SoulScanner(base_dir).scan().ids()

    assert souls == {}


def test_discover_souls_nonexistent_directory(tmp_path) -> None:
    base_dir = tmp_path

    souls = SoulScanner(base_dir).scan().ids()

    assert souls == {}


def test_discover_single_soul(tmp_path) -> None:
    base_dir = tmp_path
    write_soul_yaml(
        base_dir,
        "researcher_soul.yaml",
        soul_id="researcher_soul",
        name="Custom Researcher",
        role="Custom Researcher",
        system_prompt="You are a custom researcher",
    )

    souls = SoulScanner(base_dir).scan().ids()

    assert "researcher_soul" in souls
    assert isinstance(souls["researcher_soul"], Soul)
    assert souls["researcher_soul"].id == "researcher_soul"
    assert souls["researcher_soul"].kind == "soul"
    assert souls["researcher_soul"].name == "Custom Researcher"
    assert souls["researcher_soul"].role == "Custom Researcher"


def test_discover_multiple_souls(tmp_path) -> None:
    base_dir = tmp_path
    write_soul_yaml(
        base_dir,
        "researcher_soul.yaml",
        soul_id="researcher_soul",
        name="Researcher",
        role="Researcher",
        system_prompt="Research the topic.",
    )
    write_soul_yaml(
        base_dir,
        "writer_soul.yaml",
        soul_id="writer_soul",
        name="Writer",
        role="Writer",
        system_prompt="Write the summary.",
    )

    souls = SoulScanner(base_dir).scan().ids()

    assert len(souls) == 2
    assert "researcher_soul" in souls
    assert "writer_soul" in souls


def test_discover_soul_with_tools(tmp_path) -> None:
    base_dir = tmp_path
    write_soul_yaml(
        base_dir,
        "tool_enabled_researcher.yaml",
        soul_id="tool_enabled_researcher",
        name="Tool User",
        role="Tool User",
        system_prompt="You have tools",
        tools=["summarize"],
    )

    souls = SoulScanner(base_dir).scan().ids()

    assert "tool_enabled_researcher" in souls
    assert souls["tool_enabled_researcher"].tools is not None
    assert len(souls["tool_enabled_researcher"].tools) == 1


def test_discover_soul_preserves_runtime_configuration_fields(tmp_path) -> None:
    souls_dir = tmp_path / "custom" / "souls"
    souls_dir.mkdir(parents=True)
    (souls_dir / "configured_soul.yaml").write_text(
        dedent(
            """\
            id: configured_soul
            kind: soul
            name: Configured Soul
            role: Configured Soul
            system_prompt: Preserve configured runtime fields.
            tools:
              - profile_lookup
            max_tool_iterations: 9
            model_name: local-analysis-model
            provider: local_provider
            temperature: 0.6
            max_tokens: 8192
            avatar_color: "#224466"
            """
        ),
        encoding="utf-8",
    )

    soul = SoulScanner(tmp_path).scan().ids()["configured_soul"]

    assert soul.tools == ["profile_lookup"]
    assert soul.max_tool_iterations == 9
    assert soul.model_name == "local-analysis-model"
    assert soul.provider == "local_provider"
    assert soul.temperature == 0.6
    assert soul.max_tokens == 8192
    assert soul.avatar_color == "#224466"


def test_discover_soul_uses_defaults_for_missing_optional_runtime_fields(tmp_path) -> None:
    write_soul_yaml(
        tmp_path,
        "minimal_soul.yaml",
        soul_id="minimal_soul",
        name="Minimal Soul",
        role="Minimal Soul",
        system_prompt="Keep defaults.",
    )

    soul = SoulScanner(tmp_path).scan().ids()["minimal_soul"]

    assert soul.max_tool_iterations == 5
    assert soul.model_name is None
    assert soul.provider is None
    assert soul.temperature is None
    assert soul.max_tokens is None
    assert soul.avatar_color is None


def test_discover_soul_missing_required_fields_reports_file_name(tmp_path) -> None:
    write_soul_yaml(
        tmp_path,
        "valid_soul.yaml",
        soul_id="valid_soul",
        name="Valid Soul",
        role="Valid Soul",
        system_prompt="Keep loading valid souls.",
    )
    souls_dir = tmp_path / "custom" / "souls"
    (souls_dir / "invalid_soul.yaml").write_text(
        dedent(
            """\
            id: invalid_soul
            kind: soul
            name: Invalid Soul
            system_prompt: Missing a role.
            """
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as exc_info:
        SoulScanner(tmp_path).scan()

    message = str(exc_info.value)
    assert "invalid_soul.yaml" in message
    assert "role" in message


def test_discover_empty_soul_yaml_is_skipped(tmp_path) -> None:
    souls_dir = tmp_path / "custom" / "souls"
    souls_dir.mkdir(parents=True)
    (souls_dir / "empty_soul.yaml").write_text("", encoding="utf-8")
    write_soul_yaml(
        tmp_path,
        "loaded_soul.yaml",
        soul_id="loaded_soul",
        name="Loaded Soul",
        role="Loaded Soul",
        system_prompt="Still loads.",
    )

    souls = SoulScanner(tmp_path).scan().ids()

    assert "empty_soul" not in souls
    assert "loaded_soul" in souls


def test_discover_soul_ignores_inline_override_keys(tmp_path) -> None:
    base_dir = tmp_path
    write_soul_yaml(
        base_dir,
        "overridden_soul.yaml",
        soul_id="overridden_soul",
        name="Overridden Soul",
        role="Overridden Soul",
        system_prompt="This should be ignored when overridden inline.",
    )
    write_soul_yaml(
        base_dir,
        "kept_soul.yaml",
        soul_id="kept_soul",
        name="Kept Soul",
        role="Kept Soul",
        system_prompt="This should remain visible.",
    )

    souls = SoulScanner(base_dir).scan(ignore_keys={"overridden_soul"}).ids()

    assert "overridden_soul" not in souls
    assert "kept_soul" in souls


def test_legacy_discover_souls_helper_is_removed_from_public_module() -> None:
    import runsight_core.yaml.discovery as discovery_module

    assert not hasattr(
        discovery_module,
        "_discover_souls",
    ), "Legacy _discover_souls helper should be removed from runsight_core.yaml.discovery"
