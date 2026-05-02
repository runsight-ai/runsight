from __future__ import annotations

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
